"""Check lazy-edge alignment, rearming coverage and pulse isolation independently of spawn counts."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autosave import detector_component, detector_marks, detector_origin
from combine import tile_startup_marks

for region in [(2,2),(-7,-5)]:
    for view in (3,10,32):
        player = (region[0]*1280-view*16-8, 130, region[1]*1280+8)
        grid = (region[0]*1280-208, 128, region[1]*1280)
        source, origin = detector_component(player,view)
        dx,dy,dz = origin
        w,h,d = [source[k][1] for k in ('Width','Height','Length')]
        assert (w,h,d) == (16,13,22)
        sand=[]
        for i,block in enumerate(source['Blocks'][1]):
            if block==12:
                yy,r=divmod(i,w*d);zz,xx=divmod(r,w)
                sand.append(((dx+xx)//16,(dz+zz)//16))
        pcx,pcz=player[0]//16,player[2]//16
        assert len(sand)==8 and set(sand)=={(pcx,pcz-view+1)}
        for tile in source['TileEntities'][1][1]:
            assert tile['id'][1] in ('minecraft:sign','minecraft:comparator')
            if tile['id'][1]=='minecraft:sign':
                for line in range(1,5):json.loads(tile[f'Text{line}'][1])
        marks={tuple(m[:3]):tuple(m[3:]) for m in detector_marks(player,grid,view)}
        extra_z=(pcz-view-1)*16+8
        reached={px//16 for px,py,pz in marks if pz==extra_z and marks[px,py,pz][0] in (55,93)}
        assert reached==set(range(pcx-2,pcx+3))
        assert marks[player[0]-1,player[1],player[2]-2]==(218,3)
        assert marks[dx+2,player[1],dz+2]==(93,3)
        for pz in (grid[2]-2,grid[2]-1):
            assert marks[player[0]+10,player[1]+1,pz]==(44,8)
        startup=tile_startup_marks(player,grid,view)
        assert startup[-1] == (grid[0]+202,grid[1]+1,grid[2]+20,93,2)
        assert sum(m[3]==69 for m in startup)==1
        assert not any(m[3] in (1,77,143) for m in startup)
print('Detector lazy alignment, eight sand blocks, five-chunk priming, diode/slab isolation and shared two-line input verified')

# Original scenery/button delay is entirely west of the shared input; retain all live control/lattice cells.
from combine import read_nbt
root = Path(__file__).resolve().parents[3]
original = read_nbt((root/'sources/GridTileTick.schematic').read_bytes())
clean = read_nbt((root/'tools/rng_finder/reference/command-tile-tick-grid-1.12.schematic').read_bytes())
removed = 0
for i, (block, meta) in enumerate(zip(original['Blocks'][1],original['Data'][1])):
    if i % 720 < 202 or block in (137,77):
        expected = (0,0)
        removed += block != 0
    else:
        expected = (159,11) if block in (57,1) else (block,meta)
    assert (clean['Blocks'][1][i],clean['Data'][1][i]) == expected, i
assert removed == 2126, removed
assert clean['Blocks'][1][(1*512+21)*720+202] == 55
print('Trees/plants and obsolete button delay removed; all shared control and lattice cells retained')
