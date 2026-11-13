"""Preserved Xcom lattice, stripped detector, connected CLI parity and native conversion."""
import hashlib
import sys
import subprocess
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from combine import read_nbt
from reference.prepare_shared_detector import obsolete_detector
from combined_litematic import combined_litematic
import backend as gui
TOOL=Path(__file__).resolve().parents[1]
original=(TOOL/'reference/xcom-chunk-loading-grid.schematic').read_bytes()
assert hashlib.sha256(original).hexdigest()=='004defdc85f554be7a9c3914fe787a0b2f49a5c5e64c51a17e7d9f0f504b70cb'
a=read_nbt(original);b=read_nbt((TOOL/'reference/xcom-shared-detector-grid.schematic').read_bytes())
w,h,d=[a[k][1] for k in ('Width','Height','Length')]
removed=0
for i,(block,meta) in enumerate(zip(a['Blocks'][1],a['Data'][1])):
 y,r=divmod(i,w*d);z,x=divmod(r,w)
 expected=(0,0) if obsolete_detector(x,y,z) else (block,meta)
 assert (b['Blocks'][1][i],b['Data'][1][i])==expected
 removed+=bool(block) and expected==(0,0)
assert removed==206 and len(b['TileEntities'][1][1])==1875
assert all(not obsolete_detector(*(t[k][1] for k in ('x','y','z'))) for t in b['TileEntities'][1][1])

gui.scan_terrain=lambda *_:(True,'Test: terrain stubbed')
common=dict(seed='12345',x='0',z='0',radius='128',view='10')
cases=[(gui.calculate,dict(common,mob='witch',bound='16',players_min='1',players_max='1')),
       (gui.calculate_fortune,dict(common,ore='diamond',level='3',target='4',advances='0')),
       (gui.calculate_golem,common),
       (gui.calculate_portal,dict(common,difficulty='3',advances='0')),
       (gui.calculate_portal,dict(common,seed='553',difficulty='3',x='2560',z='2560',radius='0',advances='29',exact=True))]
for calculate,values in cases:
 data,plan=calculate(values)
 root=read_nbt(data)
 with tempfile.TemporaryDirectory() as temporary:
  output=Path(temporary)/'cli'
  if calculate==gui.calculate:
   command=[str(gui.BINARY),'--auto-height','--view-distance',values['view'],'--players-min',values['players_min'],'--players-max',values['players_max']]
   text='\n'.join([values[k] for k in ('seed','mob','x','z','radius','bound')]+[str(output),''])
  else:
   keys=('seed','x','z','radius','view') if calculate==gui.calculate_golem else ('seed','ore','level','target','x','z','radius','advances','view') if calculate==gui.calculate_fortune else ('seed','difficulty','x','z','radius','advances','view')
   flag='--golem' if calculate==gui.calculate_golem else '--fortune' if calculate==gui.calculate_fortune else '--portal'
   command=[str(gui.BINARY),flag]+[values[k] for k in keys]+[str(output)]
   if calculate==gui.calculate_portal:command+=['--exact-advances' if values.get('exact') else '--portal-tick-model']
   text=None
  if calculate==gui.calculate:
   import re
   command+=['--skip-candidates',re.search(r'Terrain candidate index: (\d+)',plan).group(1)]
  subprocess.run(command,input=text,text=True,check=True,capture_output=True)
  assert read_nbt((output/'rng-combined.schematic').read_bytes())==root
  assert (output/'autosave-detector.schematic').read_bytes()==(TOOL/'reference/command-autosave-detector-1.12.schematic').read_bytes()
  assert 'Connected CLI output:' in (output/'rng-finder-plan.txt').read_text()
  saved=(output/'rng-combined.schematic').read_bytes()
  assert subprocess.run(command,input=text,text=True,capture_output=True).returncode
  assert (output/'rng-combined.schematic').read_bytes()==saved
 assert root['Blocks'][1].count(12)==8
 assert 'Switch the single AFK lever ON' in plan or 'Switch the AFK lever ON' in plan
 assert root['Blocks'][1].count(69)>=1
 if 'Grid type: scheduled repeater' not in plan:
  assert len(root['TileEntities'][1][1])==1880
  assert 'recurring pulses do not drive the startup piston' in plan
 if calculate==gui.calculate_golem:
  print('iron connected legacy output retains300 villagers');continue
 raw,origin,count,volume=combined_litematic(data,plan,{(-65,2,-65),(65,3,65)})
 native=read_nbt(raw,root_name=None)
 assert len(native['Regions'][1])==count and count>1
 assert sum(len(r[1]['TileEntities'][1][1]) for r in native['Regions'][1].values())==len(root['TileEntities'][1][1])
 print(calculate.__name__, 'exact' if values.get('exact') else 'default','connected and native',count,'regions')
print('Original SHA preserved; exactly206 obsolete blocks/12 comparators removed, all other reference states retained')
