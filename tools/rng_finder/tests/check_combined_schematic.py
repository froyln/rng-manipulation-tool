import re
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gui
from combine import read_nbt, placement, startup_marks, tile_startup_marks
from terrain_scan import _classpath
gui.scan_terrain = lambda *_: (True, 'Terrain scan stubbed for schematic-construction checks.')

values = dict(seed='12345', x='0', z='0', radius='128', view='10')
data, plan = gui.calculate_golem(values)
combined = read_nbt(data)
reference = read_nbt((Path(__file__).resolve().parents[1] / 'reference/xcom-chunk-loading-grid.schematic').read_bytes())
start = tuple(map(int, re.search(r'Combined schematic minimum corner: (-?\d+), (-?\d+), (-?\d+)', plan).groups()))
grid = placement(plan, 'Grid component within combined schematic:')
delta = tuple(grid[i] - start[i] for i in range(3))
w, h, d = (combined[k][1] for k in ('Width','Height','Length'))
rw, rh, rd = (reference[k][1] for k in ('Width','Height','Length'))
for y in range(rh):
    for z in range(rd):
        src = (y*rd+z)*rw
        dst = ((y+delta[1])*d+z+delta[2])*w+delta[0]
        for key in ('Blocks', 'Data'):
            assert combined[key][1][dst:dst+rw] == reference[key][1][src:src+rw], (key,y,z)
original = reference['TileEntities'][1][1]
merged = combined['TileEntities'][1][1]
assert len(original) == 1887 and len(merged) == 1888
for before, after in zip(original, merged[:len(original)]):
    expected = dict(before)
    for axis, shift in zip(('x','y','z'), delta):
        kind, value = expected[axis]
        expected[axis] = (kind, value + shift)
    assert after == expected
blocks = combined['Blocks'][1]
assert blocks.count(64) == 48  # 24 double-height doors
villagers = combined['Entities'][1][1]
assert len(villagers) == 300
center = tuple(map(int, re.search(r'Suggested village center: (-?\d+), (-?\d+), (-?\d+)', plan).groups()))
villager_positions = set()
for villager in villagers:
    assert villager['id'] == (8, 'minecraft:villager') and villager['Age'] == (3, 0)
    ex,ey,ez = (value + offset for value,offset in zip(villager['Pos'][1][1], start))
    assert abs(ex-center[0]) < 32 and abs(ez-center[2]) < 32 and abs(ey-center[1]) <= 3
    villager_positions.add((ex,ey,ez))
assert len(villager_positions) == 300
assert {pos[1] - center[1] for pos in villager_positions} == {-3,0,3}
assert plan.count('/summon minecraft:villager ') == 300
spawn = tuple(map(int, re.search(r'Modeled first golem spawn block: (-?\d+), (-?\d+), (-?\d+)', plan).groups()))
def block_at(x,y,z):
    return blocks[((y-start[1])*d+z-start[2])*w+x-start[0]]
assert block_at(*spawn) == 90
assert block_at(spawn[0], spawn[1]-1, spawn[2]) == 49
for dx in (-1,0):
    for dz in (-1,0):
        for dy in range(4):
            assert block_at(spawn[0]+dx, spawn[1]+dy, spawn[2]+dz) in (0,90)
with tempfile.TemporaryDirectory(prefix='combined-villagers-') as temp:
    schematic = Path(temp) / 'combined.schematic'
    schematic.write_bytes(data)
    classpath = _classpath()
    subprocess.run(['javac', '-proc:none', '-cp', classpath, '-d', temp, str(Path(__file__).with_name('VillagerEntityProbe.java'))], check=True, capture_output=True)
    check = subprocess.run(['java', '-cp', temp + os.pathsep + classpath, 'VillagerEntityProbe', str(schematic)], check=True, capture_output=True, text=True)
    assert 'Loaded 300 adult villagers with unique IDs' in check.stdout
player = re.search(r'Player position: (-?\d+\.5), (\d+), (-?\d+\.5)', plan)
x,y,z=(math.floor(float(value)) for value in player.groups())
index=((y-1-start[1])*d + z-start[2])*w + x-start[0]
assert (blocks[index],combined['Data'][1][index]) == (251,3)
for dx in range(-1,2):
    for dz in range(-1,2):
        i = index + dz*w + dx
        assert (blocks[i], combined['Data'][1][i]) == (251, 3 if dx == dz == 0 else 11)
sign = merged[-1]
assert sign['id'][1] == 'minecraft:sign' and sign['Text1'][1] == '{"text":"Player Spot"}'
assert (sign['x'][1], sign['y'][1], sign['z'][1]) == (x+1-start[0], y-start[1], z+1-start[2])
assert blocks[index + w*d + w + 1] == 63
marks = startup_marks((x,y,z), grid, 10)
for mx,my,mz,block,meta in marks:
    i=((my-start[1])*d + mz-start[2])*w + mx-start[0]
    assert (blocks[i],combined['Data'][1][i]) == (block,meta), (mx,my,mz,block,meta)
assert (grid[0] + 188, grid[1] + 6, grid[2] - 1, 159, 11) in marks
assert sum(block == 93 for _,_,_,block,_ in marks) >= 2
print('Combined grid blocks, all 1887 tile entities, villager cage doors, player platform and sign verified')

for calculate, settings in [
    (gui.calculate, dict(seed='12345', mob='witch', x='0', z='0', radius='25', bound='16', view='10', players_min='1', players_max='1')),
    (gui.calculate_fortune, dict(seed='12345', ore='diamond', level='3', target='4', x='0', z='0', radius='25', advances='0', view='10')),
    (gui.calculate_portal, dict(seed='12345', difficulty='3', x='0', z='0', radius='25', advances='0', view='10')),
]:
    schematic, text = calculate(settings)
    parsed = read_nbt(schematic)
    assert len(parsed['TileEntities'][1][1]) == (6 if calculate == gui.calculate_portal else 1888)
    assert parsed['TileEntities'][1][1][-1]['Text1'][1] == '{"text":"Player Spot"}'
    assert 'Combined schematic minimum corner:' in text
    player_match = re.search(r'(?:Suggested mining/player position|Suggested player position|Player position):\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)', text, re.I)
    gx = placement(text, 'Grid component within combined schematic:')
    player_xyz = tuple(math.floor(float(value)) for value in player_match.groups())
    bounds = tuple(map(int, re.search(r'Combined schematic minimum corner: (-?\d+), (-?\d+), (-?\d+)', text).groups()))
    width, height, depth = (parsed[k][1] for k in ('Width','Height','Length'))
    route = tile_startup_marks if calculate == gui.calculate_portal else startup_marks
    for mx,my,mz,block,meta in route(player_xyz, gx, 10):
        i=((my-bounds[1])*depth + mz-bounds[2])*width + mx-bounds[0]
        expected = (218,3) if calculate == gui.calculate_portal and (mx,my,mz) == (player_xyz[0]-1,player_xyz[1],player_xyz[2]-2) else (block,meta)
        assert (parsed['Blocks'][1][i],parsed['Data'][1][i]) == expected, (mx,my,mz)
    if calculate == gui.calculate:
        start = tuple(map(int, re.search(r'Combined schematic minimum corner: (-?\d+), (-?\d+), (-?\d+)', text).groups()))
        width, depth = parsed['Width'][1], parsed['Length'][1]
        cx, cy, cz = map(int, re.search(r'Height control block \(stone\): (-?\d+), (-?\d+), (-?\d+)', text).groups())
        ix, _, iz = map(int, re.search(r'Initial random block: (-?\d+), (-?\d+), (-?\d+)', text).groups())
        bound = int(re.search(r'Assumed Y bound: (\d+)', text).group(1))
        assert (cx, cy, cz) == (ix, bound - 2, iz)
        control_index = ((cy-start[1])*depth + cz-start[2])*width + cx-start[0]
        assert parsed['Blocks'][1][control_index] == 1
        assert parsed['Blocks'][1][control_index + width*depth] == 20
        assert all(parsed['Blocks'][1][control_index + i*width*depth] == 0 for i in range(2, height-(cy-start[1])))
        attempts = re.search(r'Modeled spawn-attempt positions.*?:\n(.*?)\n\n', text, re.S).group(1)
        for _, x, y, z in re.findall(r'(\d+)\.\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)', attempts):
            x, y, z = int(x), int(y), int(z)
            index = ((y-start[1])*depth + z-start[2])*width + x-start[0]
            assert parsed['Blocks'][1][index] == 20
            assert parsed['Blocks'][1][index-width*depth] == 251
            assert parsed['Data'][1][index-width*depth] == 5
    if calculate == gui.calculate_portal:
        assert parsed['Blocks'][1].count(90) == 4096
    print(calculate.__name__, 'combined output verified')
