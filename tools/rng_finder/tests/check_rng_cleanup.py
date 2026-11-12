"""Known NBT encoding, negative Anvil coordinates, exact scan scope and marker relocation."""
import gzip
from pathlib import Path
import struct
import sys
import tempfile
from unittest.mock import patch
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from combine import read_nbt,write_nbt
from rng_cleanup import SavedWorld,cleanup_positions,mark_cleanup,cleanup_litematic
import gui

# Java DataOutput.writeUTF vector: NUL + U+1F600 use modified UTF-8.
value={'Text':(8,'\0😀')}
encoded=write_nbt(value)
assert b'\xc0\x80\xed\xa0\xbd\xed\xb8\x80' in gzip.decompress(encoded)
assert read_nbt(encoded)==value
assert read_nbt(gzip.decompress(encoded),compressed=False)==value

with tempfile.TemporaryDirectory(prefix='rng-cleanup-test-') as d:
    world=Path(d)/'world';(world/'region').mkdir(parents=True)
    (world/'level.dat').write_bytes(write_nbt({'Data':(10,{'RandomSeed':(4,42),'Time':(4,123),'DataVersion':(3,1343)})}))
    chunks={}
    def put(cx,cz,x,y,z,block,meta=0):
        chunk=chunks.setdefault((cx,cz),{})
        b,m=chunk.setdefault(y//16,(bytearray(4096),bytearray(2048)))
        i=((y%16)*16+z)*16+x
        b[i]=block;m[i//2]|=meta<<(i%2*4)
    put(-2,-1,0,32,0,2)  # Earlier chunk: heights above target still matter.
    put(-2,-1,1,32,0,18,0)
    put(-2,-1,2,32,0,18,4)  # Persistent leaves must remain unmarked.
    put(-2,-1,4,32,0,35,14)  # Old flammable cleanup wool must become concrete.
    put(-2,-1,5,32,0,251,14)  # Inert red concrete needs no repeat cleanup.
    put(-2,-1,3,32,0,83)  # Supported reed ticks do not draw World.rand.
    put(-1,-1,0,1,0,11)
    put(-1,-1,1,16,0,2)  # Target section and higher must remain unmarked.
    chunks.setdefault((-1,-2),{})  # Saved air neighbor required by the lava-body boundary check.
    header=bytearray(8192);body=bytearray()
    for (cx,cz),sections in chunks.items():
        n={'Level':(10,{'xPos':(3,cx),'zPos':(3,cz),'Sections':(9,(10,[{'Y':(1,y),'Blocks':(7,b),'Data':(7,m)} for y,(b,m) in sections.items()])),'TileEntities':(9,(10,[{'Text':(8,'\0😀')}]))})}
        payload=zlib.compress(gzip.decompress(write_nbt(n)))
        data=struct.pack('>I',len(payload)+1)+b'\x02'+payload
        sectors=(len(data)+4095)//4096;i=(cx%32+cz%32*32)*4
        header[i:i+4]=((2+len(body)//4096)<<8|sectors).to_bytes(4,'big')
        body.extend(data+bytes(sectors*4096-len(data)))
    region=world/'region/r.-1.-1.mca';region.write_bytes(header+body)
    before=region.read_bytes()
    plan='''World seed: 42
Combined schematic minimum corner: -32, 64, -16
Combined dimensions: 2 x 2 x 2
Platform: y=0; portal blocks: y=16..31
Tick #1; list index 0; chunk (-2, -1)
Tick #2; list index 1; chunk (-1, -1) PORTAL
Tick #3; list index 2; chunk (0, -1)
'''
    root=dict(Width=(2,2),Height=(2,2),Length=(2,2),Materials=(8,'Alpha'),Blocks=(7,bytes([159]+[0]*6+[63])),Data=(7,bytes([11]+[0]*7)),Entities=(9,(10,[])),TileEntities=(9,(10,[{'id':(8,'minecraft:sign'),'x':(3,1),'y':(3,1),'z':(3,1),'Text1':(8,'😀')}])) )
    expected={(-32,32,-16),(-31,32,-16),(-28,32,-16),(-16,1,-16)}
    positions,rank=cleanup_positions(SavedWorld(world),plan)
    assert set(positions)==expected and rank==2
    original=write_nbt(root)
    data,text=mark_cleanup(original,plan,world)
    parsed=read_nbt(data,root_name=None)
    import re
    corner=tuple(map(int,re.search(r'Litematic placement origin: (-?\d+), (-?\d+), (-?\d+)',text).groups()))
    decoded=set()
    for _,(_,r) in parsed['Regions'][1].items():
        size=tuple(r['Size'][1][a][1] for a in ('x','y','z'))
        offset=tuple(r['Position'][1][a][1] for a in ('x','y','z'))
        w,h,l=size
        words=[v[0] for v in struct.iter_unpack('>Q',r['BlockStates'][1])]
        palette=r['BlockStatePalette'][1][1]
        for i in range(w*h*l):
            value=words[i//32] >> (i%32*2) & 3
            if value:
                yy,rem=divmod(i,w*l);zz,xx=divmod(rem,w)
                if palette[value]['Name']==(8,'minecraft:concrete'):
                    assert palette[value]['Properties'][1]['color']==(8,'red')
                    decoded.add(tuple(corner[a]+offset[a]+v for a,v in enumerate((xx,yy,zz))))
    assert decoded == expected
    assert len(parsed['Regions'][1])==2
    assert parsed['Metadata'][1]['TotalBlocks']==(4,6)
    assert region.read_bytes()==before
    try:cleanup_positions(SavedWorld(world),plan.replace('World seed: 42','World seed: 43'))
    except ValueError as e:assert 'different world seed' in str(e)
    else:raise AssertionError('Wrong save accepted')
    try:cleanup_positions(SavedWorld(world),plan.replace('chunk (-2, -1)','chunk (-3, -1)'))
    except ValueError as e:assert 'incomplete' in str(e)
    else:raise AssertionError('Missing chunks silently accepted')
    values=dict(world=str(world),seed='42')
    with patch.object(gui,'_search_with_terrain',return_value=(write_nbt(root),plan)):
        result=gui.calculate_portal(values)
    assert '4 blocks' in result[1] and 'Regions' in read_nbt(result[0],root_name=None) and len(result)==2
print('Java NBT encoding, saved-world scope/seed/coverage, red concrete, farm/sign coordinates and desktop wiring verified')

points={(-65,2,-65),(-64,3,-64),(64,90,64)}
raw,origin,count,volume,largest=cleanup_litematic(points)
assert count==3 and volume==3 and largest==1
assert read_nbt(raw,root_name=None)['Metadata'][1]['TotalVolume']==(4,3)
print('Separated cleanup zones retain only tiny regional bounds; farm bytes are unchanged')

try:cleanup_litematic({(i*64,0,0) for i in range(33)})
except ValueError as e:assert 'render budget' in str(e)
else:raise AssertionError('Client region limit was ignored')

# The desktop exporter saves exactly one native file, not farm + cleanup alternatives.
from types import SimpleNamespace
with tempfile.TemporaryDirectory(prefix='cleanup-export-') as directory:
    native=write_nbt({'Regions':(10,{})},root_name='')
    fake=SimpleNamespace(result=(native,'plan'),root=None,status=SimpleNamespace(set=lambda _:None))
    with patch.object(gui.filedialog,'askdirectory',return_value=directory), \
         patch.object(gui.messagebox,'showinfo'), patch.object(gui.messagebox,'showerror') as error:
        gui.FinderApp.export(fake)
        assert (Path(directory)/'rng-combined.litematic').read_bytes()==native
        assert len(list(Path(directory).glob('*.litematic')))==1
        gui.FinderApp.export(fake)
        assert error.called and (Path(directory)/'rng-combined.litematic').read_bytes()==native
print('Desktop saves exactly one native file and preserves existing exports')

# Lava sources beyond the modeled prefix must also be replaced to stop refilling.
import rng_cleanup
class FluidWorld:
    def block(self,x,y,z):
        return (11,0) if (x,y,z) in {(15,9,0),(16,9,0),(17,9,0)} else (0,0)
positions={(15,9,0):'lava'}
rng_cleanup.include_connected_lava(FluidWorld(),positions)
assert set(positions)=={(15,9,0),(16,9,0),(17,9,0)}
assert positions[17,9,0]=='connected lava supply outside the tick prefix'
with patch.object(rng_cleanup,'MAX_CONNECTED_LAVA',2):
    try:rng_cleanup.include_connected_lava(FluidWorld(),{(15,9,0):'lava'})
    except ValueError as e:assert 'cleanup limit' in str(e)
    else:raise AssertionError('Unbounded fluid scan accepted')
print('Cross-chunk lava supply and bounded flood-fill verified')
