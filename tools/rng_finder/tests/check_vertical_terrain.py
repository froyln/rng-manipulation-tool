import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend as gui

cases = [
    (gui.calculate_fortune, dict(seed='12345', ore='diamond', level='3', target='4', x='0', z='0', radius='25', advances='0', view='10'), 'Mansion region: 0, -1', '+64'),
    (gui.calculate_golem, dict(seed='12345', x='0', z='0', radius='128', view='10'), 'Mansion region: 0, -5', '+64'),
    (gui.calculate_portal, dict(seed='12345', difficulty='3', x='0', z='0', radius='25', advances='0', view='10'), 'Mansion region: 6, 7', '+32'),
    (gui.calculate_golem, dict(seed='7480190280633614536', x='0', z='0', radius='128', view='10'), 'Mansion region: -66, -25', '+64'),
]

for calculate, values, region, shift in cases:
    schematic, plan = calculate(values)
    assert schematic and region in plan
    assert 'Terrain candidate index: 0' in plan
    assert f'Vertical placement shift: {shift} blocks' in plan
    assert 'Seed terrain scan (vanilla 1.12.2 default terrain, structures enabled):' in plan
    print(calculate.__name__, 'found a base-terrain-clear elevated placement in the first region')
