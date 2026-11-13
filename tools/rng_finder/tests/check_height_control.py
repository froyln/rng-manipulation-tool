import re
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend as gui
from combine import read_nbt
from terrain_scan import _classpath, CLASS_DIR

values = dict(seed='7480190280633614536', mob='witch', x='2560', z='1280',
              radius='0', bound='64', view='10', players_min='1', players_max='1')
data, plan = gui.calculate(values)
assert 'Mansion region: 2, 1' in plan
assert 'Assumed Y bound: 224' in plan
assert 'Initial random block: 2585, 174, 1100' in plan
assert 'Height control block (stone): 2585, 222, 1100' in plan
assert 'Seed terrain scan (vanilla 1.12.2 default terrain, structures enabled):' in plan
assert 'candidate is rejected' not in plan
root = read_nbt(data)
corner = tuple(map(int, re.search(r'Combined schematic minimum corner: (-?\d+), (-?\d+), (-?\d+)', plan).groups()))
w, d = root['Width'][1], root['Length'][1]
index = ((222-corner[1])*d + 1100-corner[2])*w + 2585-corner[0]
assert root['Blocks'][1][index] == 1
assert root['Blocks'][1][index + w*d] == 20
with tempfile.TemporaryDirectory(prefix='height-control-test-') as temp:
    classpath = str(CLASS_DIR) + os.pathsep + _classpath()
    source = Path(__file__).with_name('HeightControlProbe.java')
    subprocess.run(['javac', '-proc:none', '-cp', classpath, '-d', temp, str(source)], check=True)
    result = subprocess.run(['java', '-cp', temp + os.pathsep + classpath, 'HeightControlProbe'],
                            text=True, capture_output=True, check=True)
    assert 'Heightmap=223; random bound=224; glass opacity=0' in result.stdout
print('Screenshot region: recomputed Y=174, included height-control stone and passed base-terrain scan')
