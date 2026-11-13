import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend as gui
gui.scan_terrain = lambda *_: (True, 'Terrain scan stubbed for next-match ordering checks.')

cases = [
    (gui.calculate, dict(seed='12345', mob='witch', x='0', z='0', radius='25', bound='16', view='10', players_min='1', players_max='1')),
    (gui.calculate_fortune, dict(seed='12345', ore='diamond', level='3', target='4', x='0', z='0', radius='25', advances='0', view='10')),
    (gui.calculate_golem, dict(seed='12345', x='0', z='0', radius='128', view='10')),
    (gui.calculate_portal, dict(seed='12345', difficulty='3', x='0', z='0', radius='25', advances='0', view='10')),
]
for calculate, values in cases:
    first = calculate(dict(values, skip=0))
    first_region = re.search(r'Mansion region: (-?\d+),\s*(-?\d+)', first[1]).groups()
    first_index = int(re.search(r'Terrain candidate index: (\d+)', first[1]).group(1))
    results = [first, calculate(dict(values, skip=first_index + 1, exclude_region=first_region))]
    regions = [re.search(r'Mansion region: (-?\d+),\s*(-?\d+)', result[1]).groups() for result in results]
    assert regions[0] != regions[1], (calculate.__name__, regions)
    assert all(result[0] and result[1] for result in results)
    assert all(len(result) == 2 for result in results)
    print(calculate.__name__, regions)
