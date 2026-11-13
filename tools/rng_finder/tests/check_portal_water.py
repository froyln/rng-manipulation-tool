"""Stepped packed-ice/water transport, unchanged portal geometry and native states."""
import sys,subprocess,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from combine import read_nbt,placement,combine
from combined_litematic import combined_litematic
import backend as gui
with tempfile.TemporaryDirectory(prefix='portal-water-') as d:
 out=Path(d)/'export'
 subprocess.run([str(gui.BINARY),'--portal','84785424703645','3','0','0','0','0','10',str(out),'--portal-tick-model','--portal-successes','3'],check=True,capture_output=True)
 root=read_nbt((out/gui.PORTAL_NAME).read_bytes());plan=(out/gui.PLAN_NAME).read_text()
 assert (root['Width'][1],root['Height'][1],root['Length'][1])==(18,37,20)
 def state(x,y,z):
  i=(y*20+z)*18+x
  return root['Blocks'][1][i],root['Data'][1][i]
 assert placement(plan,'Portal-array schematic:')[1]==60
 for z in range(1,19):
  floor=4 if z<=7 else 3 if z<=14 else 2 if z<=16 else 0
  level=0 if z==1 else 8 if z in (8,15) else z-1 if z<=7 else z-8 if z<=14 else z-15
  for x in range(1,17):
   assert state(x,floor,z)==(174,0)
   if z<=16:assert state(x,floor+1,z)==(8,level)
   else:assert state(x,1,z)==(0,0)
   if z==17:assert state(x,3,z)==(107,4)
   if z in (8,15):assert state(x,floor+2,z)==(8,7)
   else:assert state(x,floor+2,z)==(0,0)
   for y in range(max(floor+3,4),20):assert state(x,y,z)==(0,0)
 for z in range(1,17):
  for y in range(20,36):
   for x in range(1,17):assert state(x,y,z)==(90,1)
 for z in range(20):
  for y in range(1,6 if z==0 else 7):
   assert state(0,y,z)==state(17,y,z)==(159,11)
 assert sum(b==8 and m==0 for b,m in zip(root['Blocks'][1],root['Data'][1]))==16
 assert not any(b in root['Blocks'][1] for b in (1,79,212)), 'No stone, melting ice or frosted ice'
 raw,combined=combine((out/gui.PORTAL_GRID_NAME).read_bytes(),plan,(out/gui.PORTAL_NAME).read_bytes(),'Portal-array schematic:')
 native,*_=combined_litematic(raw,combined,{})
 n=read_nbt(native,root_name=None)
 palettes=[s for _,r in n['Regions'][1].values() for s in r['BlockStatePalette'][1][1]]
 assert any(s['Name']==(8,'minecraft:packed_ice') for s in palettes)
 assert any(s['Name']==(8,'minecraft:flowing_water') for s in palettes)
 assert 'receiving rows z=16..17, outside the portal chunk' in combined
print('Ice grades, source/flow/fall states, containment, headroom, fixed portals, route compatibility and native palette verified')
