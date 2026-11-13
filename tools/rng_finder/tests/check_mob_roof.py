"""Roof/height/clearance/native-state checks and pinned game light/body/sampling methods."""
import math
import os
from pathlib import Path
import re
import subprocess
import struct
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend as gui
from combine import read_nbt
from combined_litematic import combined_litematic
from terrain_scan import _classpath

gui.scan_terrain=lambda *_:(True,'Roof geometry fixture; terrain not tested here')
for mob in ('witch','enderman','spider','creeper','zombie','skeleton'):
 raw,plan=gui.calculate(dict(seed='12345',mob=mob,x='0',z='0',radius='128',bound='16',view='10',players_min='1',players_max='1'))
 r=read_nbt(raw);w,h,d=[r[k][1] for k in ('Width','Height','Length')]
 origin=tuple(map(int,re.search(r'Combined schematic minimum corner: (-?\d+), (-?\d+), (-?\d+)',plan).groups()))
 def at(x,y,z):
  if not(origin[0]<=x<origin[0]+w and origin[1]<=y<origin[1]+h and origin[2]<=z<origin[2]+d):return 0,0
  i=((y-origin[1])*d+z-origin[2])*w+x-origin[0]
  return r['Blocks'][1][i],r['Data'][1][i]
 x0,y0,z0,x1,y1,z1=map(int,re.search(r'Mob roof bounds: (-?\d+), (\d+), (-?\d+) to (-?\d+), (\d+), (-?\d+)',plan).groups())
 initial=tuple(map(int,re.search(r'Initial random block: (-?\d+), (\d+), (-?\d+)',plan).groups()))
 bound=int(re.search(r'Assumed Y bound: (\d+)',plan).group(1))
 assert y0==y1==initial[1]+3 and y0<bound-2
 assert all(at(x,y0,z)==(44,0) for x in range(x0,x1+1) for z in range(z0,z1+1))
 attempts=[tuple(map(int,p[1:])) for p in re.findall(r'(\d+)\.\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)',re.search(r'Modeled spawn-attempt positions.*?:\n(.*?)\n\n',plan,re.S).group(1))]
 for x,y,z in attempts:
  assert min(x-x0,x1-x,z-z0,z1-z)>=15
  radius=1 if mob=='spider' else 0;height=3 if mob=='enderman' else 1 if mob=='spider' else 2
  assert all(at(x+dx,y+dy,z+dz)==(0,0) for dx in range(-radius,radius+1) for dz in range(-radius,radius+1) for dy in range(height))
 assert at(initial[0],bound-2,initial[2])==(1,0)
 assert at(initial[0],bound-1,initial[2])==(20,0)
 assert math.ceil(((bound-2)+2)/16)*16==bound
 if mob=='witch':
  native,native_origin,*_=combined_litematic(raw,plan,set())
  n=read_nbt(native,root_name=None)
  slabs=[s for _,region in n['Regions'][1].values() for s in region['BlockStatePalette'][1][1] if s.get('Name')==(8,'minecraft:stone_slab')]
  assert any(s['Properties'][1]['half']==(8,'bottom') for s in slabs)
  regions=[]
  for _,region in n['Regions'][1].values():
   size=[region['Size'][1][a][1] for a in ('x','y','z')]
   offset=[native_origin[i]+region['Position'][1][a][1] for i,a in enumerate(('x','y','z'))]
   palette=region['BlockStatePalette'][1][1];bits=max(2,(len(palette)-1).bit_length())
   regions.append((size,offset,palette,bits,[v[0] for v in struct.iter_unpack('>Q',region['BlockStates'][1])]))
  for x in range(x0,x1+1):
   for z in range(z0,z1+1):
    found=[]
    for (nw,nh,nd),(ox,oy,oz),palette,bits,words in regions:
     if not(ox<=x<ox+nw and oy<=y0<oy+nh and oz<=z<oz+nd):continue
     index=((y0-oy)*nd+z-oz)*nw+x-ox;word,shift=divmod(index*bits,64)
     state=words[word]>>shift
     if shift+bits>64:state|=words[word+1]<<(64-shift)
     found.append(palette[state&((1<<bits)-1)])
    assert len(found)==1 and found[0]['Name']==(8,'minecraft:stone_slab') and found[0]['Properties'][1]['half']==(8,'bottom')

  assert 'Rejected ' in plan, 'Known first candidate clashes with adapter; must be rejected/recalculated'
 print(mob,'roof/headroom/height and native palette verified',flush=True)
with tempfile.TemporaryDirectory() as tmp:
 cp=_classpath()
 subprocess.run(['javac','-proc:none','-cp',cp,'-d',tmp,str(Path(__file__).with_name('MobRoofProbe.java'))],check=True,capture_output=True)
 r=subprocess.run(['java','-cp',tmp+os.pathsep+cp,'MobRoofProbe'],check=True,capture_output=True,text=True,timeout=120)
 assert 'daytime sky/block light0' in r.stdout
 print(r.stdout.strip())
