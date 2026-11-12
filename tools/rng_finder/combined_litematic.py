"""One compact native file: RNG build plus voxel-exact red-concrete replacement zones."""
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
from collections import defaultdict

from combine import read_nbt, write_nbt
from terrain_scan import _classpath

REPLACEMENT_STATE = 251 * 16 + 14  # Nonflammable red concrete; wool can burn and reopen lava paths.


def legacy_palette(states):
    tool = Path(__file__).resolve().parent
    source = tool / 'LegacyPalette.java'
    classes = tool / 'target' / 'terrain-scan'
    classes.mkdir(parents=True, exist_ok=True)
    compiled = classes / 'LegacyPalette.class'
    cp = _classpath()
    if not compiled.exists() or compiled.stat().st_mtime < source.stat().st_mtime:
        result = subprocess.run(['javac', '-proc:none', '-cp', cp, '-d', str(classes), str(source)], capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError('Could not compile native block palette converter: ' + result.stderr[-1800:])
    with tempfile.TemporaryDirectory(prefix='rng-palette-') as d:
        input_file, output_file = Path(d)/'states.bin', Path(d)/'palette.nbt'
        input_file.write_bytes(b''.join(struct.pack('>H', state) for state in sorted(states)))
        result = subprocess.run(['java', '-cp', str(classes)+os.pathsep+cp, 'LegacyPalette', str(input_file), str(output_file)], capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError('Native block conversion failed: ' + result.stderr[-1800:])
        root = read_nbt(output_file.read_bytes(), root_name=None)
    return {entry['Legacy'][1]: entry['State'][1] for entry in root['States'][1][1]}


def combined_litematic(schematic, plan, replacements):
    root = read_nbt(schematic)
    if root['Entities'][1][1]:
        raise ValueError('Native gold export does not support schematic entities')
    corner = tuple(map(int, re.search(r'Combined schematic minimum corner: (-?\d+), (-?\d+), (-?\d+)', plan).groups()))
    w,h,d = [root[k][1] for k in ('Width','Height','Length')]
    farm = defaultdict(dict)
    mask = root['Blocks'][1].translate(bytes([0]+[1]*255))
    index = mask.find(b'\x01')
    while index >= 0:
        y,rem = divmod(index,w*d);z,x = divmod(rem,w)
        point = corner[0]+x,corner[1]+y,corner[2]+z
        farm[point[1]//16][point] = root['Blocks'][1][index]*16+root['Data'][1][index]
        index = mask.find(b'\x01',index+1)
    bounds = {sy: (tuple(min(p[a] for p in cells) for a in range(3)), tuple(max(p[a] for p in cells) for a in range(3))) for sy,cells in farm.items()}
    cleanup = defaultdict(dict)
    for p in replacements:
        box = bounds.get(p[1]//16)
        if box and all(box[0][a] <= p[a] <= box[1][a] for a in range(3)):
            old = farm[p[1]//16].get(p,0)
            if old and old//16 not in (2,6,10,11,18,31,32,37,38,39,40,51,59,104,105,106,110,115,127,141,142,161,175,200,207,212):
                raise ValueError(f'Red-concrete replacement conflicts with a functional build block at {p}')
            farm[p[1]//16][p] = REPLACEMENT_STATE
        else:
            cleanup[p[0]//64,p[2]//64][p] = REPLACEMENT_STATE
    groups = [(f'RNG_Build_Y{sy*16}',cells) for sy,cells in sorted(farm.items())]
    groups += [(f'Cleanup_{i+1:02d}',cells) for i,(_,cells) in enumerate(sorted(cleanup.items()))]
    if not groups:
        raise ValueError('No build or replacement blocks to export')
    all_points = [p for _,cells in groups for p in cells]
    low_all = tuple(min(p[a] for p in all_points) for a in range(3))
    origin = corner  # Keep placement fixed across rescans; cleanup regions may have negative offsets.
    high = tuple(max(p[a] for p in all_points) for a in range(3))
    states = legacy_palette({0}|{v for _,cells in groups for v in cells.values()})
    xyz = lambda values: (10,{a:(3,v) for a,v in zip(('x','y','z'),values)})
    regions,boxes = {},[]
    total_volume,total_blocks = 0,0
    for name,cells in groups:
        low = tuple(min(p[a] for p in cells) for a in range(3))
        size = tuple(max(p[a] for p in cells)-low[a]+1 for a in range(3))
        top = tuple(low[a]+size[a]-1 for a in range(3))
        # Overlapping air regions can erase each other's blocks when placed.
        if any(all(low[a]<=b[1][a] and top[a]>=b[0][a] for a in range(3)) for b in boxes):
            raise ValueError('Cleanup zones overlap a build subregion; inspect this placement')
        boxes.append((low,top))
        rw,rh,rd = size;volume=rw*rh*rd
        total_volume+=volume;total_blocks+=len(cells)
        if len(groups)>32 or total_volume>16_777_216:
            raise ValueError('Combined subregions exceed the original client render budget')
        ids=[0]+sorted(set(cells.values())-{0});lookup={v:i for i,v in enumerate(ids)}
        bits=max(2,(len(ids)-1).bit_length());words=[0]*((volume*bits+63)//64)
        for (x,y,z),value in cells.items():
            offset=(((y-low[1])*rd+z-low[2])*rw+x-low[0])*bits
            word,shift=divmod(offset,64);v=lookup[value]
            words[word]|=(v<<shift)&((1<<64)-1)
            if shift+bits>64:words[word+1]|=v>>(64-shift)
        tiles=[]
        if name.startswith('RNG_Build_'):
            for tile in root['TileEntities'][1][1]:
                absolute=tuple(tile[a][1]+corner[i] for i,a in enumerate(('x','y','z')))
                if all(low[i]<=absolute[i]<=top[i] for i in range(3)):
                    tiles.append(dict(tile,**{a:(3,absolute[i]-low[i]) for i,a in enumerate(('x','y','z'))}))
        regions[name]=(10,{'Position':xyz(tuple(low[a]-origin[a] for a in range(3))), 'Size':xyz(size),
            'BlockStatePalette':(9,(10,[states[v] for v in ids])),
            'BlockStates':(12,b''.join(struct.pack('>Q',v) for v in words)),
            'TileEntities':(9,(10,tiles)), 'Entities':(9,(10,[])), 'PendingBlockTicks':(9,(10,[]))})
    result={'Version':(3,4),'MinecraftDataVersion':(3,1343),'Regions':(10,regions),
        'Metadata':(10,{'Name':(8,'Pigman RNG build and replacements'),'Author':(8,'Threadstone research'),
            'Description':(8,'Complete RNG build and voxel-exact red-concrete replacements in one file.'),
            'RegionCount':(3,len(regions)),'TotalBlocks':(4,total_blocks),'TotalVolume':(4,total_volume),
            'TimeCreated':(4,0),'TimeModified':(4,0),'EnclosingSize':xyz(tuple(high[a]-low_all[a]+1 for a in range(3)))})}
    return write_nbt(result,root_name=''),origin,len(regions),total_volume
