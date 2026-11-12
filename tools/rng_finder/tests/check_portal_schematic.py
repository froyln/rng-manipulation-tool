import gzip
import re
import struct
import subprocess
import tempfile
from pathlib import Path

binary = Path(__file__).resolve().parents[1] / 'target/release/rng-finder'
with tempfile.TemporaryDirectory(prefix='portal-test-') as temp:
    probe = Path(__file__).with_name('PortalRandomProbe.java')
    subprocess.run(['javac', '-d', temp, str(probe)], check=True, capture_output=True)
    reference = subprocess.run(['java', '-cp', temp, 'PortalRandomProbe'], check=True, capture_output=True, text=True)
    assert reference.stdout.splitlines() == ['2,1501,446', '634,1908,518', '451,1759,2', '0,1611,1986']
    output = Path(temp) / 'output'
    command = [str(binary), '--portal', '12345', '3', '0', '0', '25', '0', '10', str(output)]
    subprocess.run(command, check=True, capture_output=True)
    b = gzip.decompress((output / 'portal-platform.schematic').read_bytes())
    plan = (output / 'rng-finder-plan.txt').read_text()
    assert 'Placement minimum corner (local 0,0,0): 47, 64, 6143' in plan
    assert 'attempt 3 of 3, World.rand.nextInt(2000) = 2 < difficulty 3' in plan
    assert 'four bounded RNG draws' in plan
    assert 'ignite each slice separately' in plan
    assert 'not on the lower stone platform' in plan
    assert 'updateLCG is not predicted by this tool' in plan
    assert 'CONDITIONAL 1.12.2 CHUNK TICK ORDER' in plan
    assert 'Tick #82; list index 199; chunk (3, 384) PORTAL' in plan
    assert 'Tick rank is not an RNG advance count' in plan
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert gzip.decompress((output / 'portal-platform.schematic').read_bytes()) == b
    exact = Path(temp) / 'exact'
    subprocess.run([str(binary), '--portal', '553', '3', '2560', '2560', '0', '29', '3', str(exact), '--exact-advances'], check=True, capture_output=True)
    exact_plan = (exact / 'rng-finder-plan.txt').read_text()
    assert 'Mansion region: 2, 2' in exact_plan
    assert 'Modeled advances: 29 unbounded' in exact_plan
    assert 'attempt 1 of 3, World.rand.nextInt(2000) = 0 < difficulty 3' in exact_plan

i = 0
def take(n):
    global i
    result = b[i:i+n]
    i += n
    return result

def name():
    return take(struct.unpack('>H', take(2))[0]).decode()

assert take(1) == b'\x0a' and name() == 'Schematic'
tags = {}
while True:
    t = take(1)[0]
    if not t:
        break
    n = name()
    if t == 2:
        tags[n] = struct.unpack('>h', take(2))[0]
    elif t == 8:
        tags[n] = name()
    elif t == 7:
        tags[n] = take(struct.unpack('>i', take(4))[0])
    elif t == 9:
        assert take(1) == b'\x0a' and struct.unpack('>i', take(4))[0] == 0
    else:
        raise AssertionError((n, t))
assert i == len(b)
assert (tags['Width'], tags['Height'], tags['Length'], tags['Materials']) == (18, 33, 18, 'Alpha')
blocks, data = tags['Blocks'], tags['Data']
assert len(blocks) == len(data) == 18 * 33 * 18
for y in range(33):
    for z in range(18):
        for x in range(18):
            index = (y * 18 + z) * 18 + x
            expected = 0
            if y == 0 and 1 <= x <= 16 and 1 <= z <= 16:
                expected = 1
            elif 1 <= z <= 16 and (y in (15, 32) and 0 <= x <= 17 or 16 <= y <= 31 and x in (0, 17)):
                expected = 49
            elif 16 <= y <= 31 and 1 <= x <= 16 and 1 <= z <= 16:
                expected = 90
            assert blocks[index] == expected, (x, y, z, blocks[index], expected)
            assert data[index] == (1 if expected == 90 else 0)
assert blocks.count(90) == 16 ** 3
assert blocks.count(49) == 1088
print('Portal array frames, 16 adjacent apertures, floor, placement and no-overwrite behavior verified')
