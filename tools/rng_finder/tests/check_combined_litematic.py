"""Independently decode full native build + exact replacement voxels, including cross-word states."""
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from combine import read_nbt,write_nbt
from combined_litematic import combined_litematic,legacy_palette,REPLACEMENT_STATE

# Six native states force 3-bit indices across a 64-bit word boundary.
blocks=bytes([i%5+1 for i in range(31)]+[63])
root=dict(Width=(2,32),Height=(2,1),Length=(2,1),Materials=(8,'Alpha'),
    Blocks=(7,blocks),Data=(7,bytes(32)),Entities=(9,(10,[])),
    TileEntities=(9,(10,[{'id':(8,'minecraft:sign'),'x':(3,31),'y':(3,0),'z':(3,0),'Text1':(8,'{"text":"Test"}')}])))
plan='Combined schematic minimum corner: -32, 64, -16\n'
replacements={(-65,2,-65),(-64,3,-64),(64,90,64)}
raw,origin,count,volume=combined_litematic(write_nbt(root),plan,replacements)
n=read_nbt(raw,root_name=None)
decoded={};tile_positions=[]
for name,(_,r) in n['Regions'][1].items():
    size=[r['Size'][1][a][1] for a in ('x','y','z')]
    offset=[r['Position'][1][a][1] for a in ('x','y','z')]
    palette=r['BlockStatePalette'][1][1];bits=max(2,(len(palette)-1).bit_length())
    words=[v[0] for v in struct.iter_unpack('>Q',r['BlockStates'][1])]
    w,h,d=size
    for index in range(w*h*d):
        bit=index*bits;word,shift=divmod(bit,64)
        value=words[word]>>shift
        if shift+bits>64:value|=words[word+1]<<(64-shift)
        value&=(1<<bits)-1
        if value:
            y,rem=divmod(index,w*d);z,x=divmod(rem,w)
            point=tuple(origin[a]+offset[a]+v for a,v in enumerate((x,y,z)))
            assert point not in decoded,'Overlapping non-air subregions'
            decoded[point]=palette[value]
    for tile in r['TileEntities'][1][1]:
        tile_positions.append(tuple(origin[a]+offset[a]+tile[key][1] for a,key in enumerate(('x','y','z'))))
states=legacy_palette({0,REPLACEMENT_STATE}|{b*16 for b in blocks})
assert set(decoded)==replacements|{(-32+x,64,-16) for x in range(32)}
assert all(decoded[p]==states[REPLACEMENT_STATE] for p in replacements)
assert all(decoded[-32+x,64,-16]==states[b*16] for x,b in enumerate(blocks))
assert tile_positions==[(-1,64,-16)]
assert count==4 and volume==35
assert n['Metadata'][1]['TotalBlocks']==(4,35)
print('One-file build, exact red-concrete voxels, native block states, cross-word palette and sign coordinates verified')

assert origin==(-32,64,-16), 'Placement must stay at the farm anchor across cleanup rescans'
