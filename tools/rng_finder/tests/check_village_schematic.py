import os, re, subprocess, tempfile, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combine import read_nbt
from terrain_scan import _classpath

binary = Path(__file__).resolve().parents[1] / 'target/release/rng-finder'
with tempfile.TemporaryDirectory(prefix='village-test-') as temp:
    rng_probe = Path(__file__).with_name('IronRngReference.java')
    subprocess.run(['javac', '-d', temp, str(rng_probe)], check=True, capture_output=True)
    reference = subprocess.run(['java', '-cp', temp, 'IronRngReference'], check=True, capture_output=True, text=True)
    assert reference.stdout.splitlines() == ['0', '4,-1,3']
    output = Path(temp) / 'output'
    subprocess.run([str(binary), '--golem', '12345', '0', '0', '5', '10', str(output)], check=True, capture_output=True)
    plan = (output / 'rng-finder-plan.txt').read_text()
    assert 'Mansion region: 0, -5' in plan
    assert 'Modeled first spawn offset from village center: 4, -1, 3' in plan
    assert 'Suggested Nether portal search center: 11, -830' in plan
    root = read_nbt((output / 'golem-village.schematic').read_bytes())
    classpath = _classpath()
    probe = Path(__file__).with_name('VillagerEntityProbe.java')
    subprocess.run(['javac', '-proc:none', '-cp', classpath, '-d', temp, str(probe)], check=True, capture_output=True)
    check = subprocess.run(['java', '-cp', temp + os.pathsep + classpath, 'VillagerEntityProbe', str(output / 'golem-village.schematic')], check=True, capture_output=True, text=True)
    assert 'Loaded 300 adult villagers with unique IDs' in check.stdout
tags={name:value for name, (_,value) in root.items()}
entities = tags['Entities'][1]
assert len(entities) == 300
assert (tags['Width'],tags['Height'],tags['Length'],tags['Materials'])==(23,13,29,'Alpha')
W,D=23,29
at=lambda x,y,z: tags['Blocks'][((y+4)*D+(z+14))*W+(x+11)]
meta=lambda x,y,z: tags['Data'][((y+4)*D+(z+14))*W+(x+11)]
doors=[(x,z) for x in range(-10,11) for z in range(-9,10) if at(x,0,z)==64]
assert len(doors)==24 and sum(x for x,z in doors)==0 and sum(z for x,z in doors)==0
for x,z in doors:
 assert abs(x)==10 and at(x,-1,z)==1 and meta(x,0,z)==0 and at(x,1,z)==64 and meta(x,1,z)==8
 for step in range(1,6): assert at(x-(1 if x>0 else -1)*step,8,z)==1
assert tags['Blocks'].count(90) == 8 and tags['Blocks'].count(49) == 16
sx, sy, sz = map(int, re.search(r'Modeled first spawn offset from village center: (-?\d+), (-?\d+), (-?\d+)', plan).groups())
assert at(sx, sy, sz) == 90 and at(sx, sy-1, sz) == 49
for dx in (-1,0):
 for dz in (-1,0):
  for dy in range(4): assert at(sx+dx, sy+dy, sz+dz) in (0,90)
assert 'Required villager count: 300 counted villagers' in plan
assert '30 villagers allow 3, 300 allow 30' in plan
assert 'at least 21 valid registered wooden doors' in plan
assert 'doMobSpawning=false; randomTickSpeed=0' in plan
assert 'no other village records are present' in plan
assert 'stone=571, glass=2284, wooden door blocks=48 (24 doorways), obsidian=16, portal=8' in plan
layers = {-3: set(), 0: set(), 3: set()}
for entity in entities:
 assert entity['id'] == (8, 'minecraft:villager') and entity['Age'] == (3, 0)
 px, py, pz = entity['Pos'][1][1]
 assert px % 1 == pz % 1 == 0.5 and py in (1,4,7)
 x, y, z = int(px - 0.5) - 11, int(py) - 4, int(pz - 0.5) - 14
 assert abs(x) <= 9 and abs(z) <= 13 and abs(y) <= 3
 assert tags['Blocks'][((int(py)-1)*D + int(pz-0.5))*W + int(px-0.5)] == 1
 for dy in (0,1):
  for dx,dz in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
   assert at(x+dx,y+dy,z+dz) == 20
 layers[y].add((x,z))
assert all(len(cells)==100 for cells in layers.values())
assert len(set((x,y,z) for y,cells in layers.items() for x,z in cells)) == 300
print('MCP entity loading, independent Java RNG sequence, 300 separated adult cells, counts, 24 doors and portal clearance verified')
