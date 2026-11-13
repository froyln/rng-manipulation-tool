import re
from collections import Counter
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend as gui
from combine import placement, read_nbt

cases = [
    (gui.calculate_fortune, dict(seed='12345', ore='diamond', level='3', target='4', x='0', z='0', radius='25', advances='0', view='10')),
    (gui.calculate_golem, dict(seed='12345', x='0', z='0', radius='5', view='10')),
    (gui.calculate_portal, dict(seed='12345', difficulty='3', x='0', z='0', radius='25', advances='0', view='10')),
]

for calculate, values in cases:
    tried = []
    def scan(_data, plan):
        y = placement(plan, 'Grid component within combined schematic:')[1]
        tried.append(y)
        return y >= 96, 'Terrain scan stub: lower placement blocked.' if y < 96 else 'Terrain scan stub: clear.'
    gui.scan_terrain = scan
    data, plan = calculate(values)
    assert tried == [64, 96], (calculate.__name__, tried)
    assert 'Terrain candidate index: 0' in plan
    assert 'Vertical placement shift: +32' in plan
    assert re.search(r'(?:Suggested mining/player position|Suggested player position|Player position): [^\n]*, 98,', plan)
    root = read_nbt(data)
    if calculate == gui.calculate_golem:
        center = tuple(map(int, re.search(r'Suggested village center: (-?\d+), (-?\d+), (-?\d+)', plan).groups()))
        spawn = tuple(map(int, re.search(r'Modeled first golem spawn block: (-?\d+), (-?\d+), (-?\d+)', plan).groups()))
        offset = tuple(map(int, re.search(r'Modeled first spawn offset from village center: (-?\d+), (-?\d+), (-?\d+)', plan).groups()))
        assert center[1] == 96 and tuple(spawn[i] - center[i] for i in range(3)) == offset
        assert placement(plan, 'Village component within combined schematic:')[1] == 92
        assert root['Blocks'][1].count(64) == 48
        assert len(root['Entities'][1][1]) == 300
        corner = tuple(map(int, re.search(r'Combined schematic minimum corner: (-?\d+), (-?\d+), (-?\d+)', plan).groups()))
        entity_levels = [round(entity['Pos'][1][1][1] + corner[1] - center[1]) for entity in root['Entities'][1][1]]
        assert Counter(entity_levels) == {-3: 100, 0: 100, 3: 100}
        commands = re.findall(r'/summon minecraft:villager (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)', plan)
        assert len(commands) == 300 and Counter(round(float(command[1]) - center[1]) for command in commands) == {-3: 100, 0: 100, 3: 100}
    if calculate == gui.calculate_portal:
        assert placement(plan, 'Portal component within combined schematic:')[1] == 92
        assert 'Platform: y=96; portal blocks: y=112..127; obsidian top frame y=128; bottom frame removed (sliced)\n' in plan
        assert root['Blocks'][1].count(90) == 4096
    print(calculate.__name__, 'retries same region at Y=96 and keeps coordinates consistent')
