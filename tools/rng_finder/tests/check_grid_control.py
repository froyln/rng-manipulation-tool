import collections
import gzip
import struct
from pathlib import Path

raw = gzip.decompress((Path(__file__).resolve().parents[1] / 'reference/xcom-chunk-loading-grid.schematic').read_bytes())
pos = 0

def take(n):
    global pos
    result = raw[pos:pos+n]
    pos += n
    return result

def number(fmt):
    return struct.unpack('>' + fmt, take(struct.calcsize(fmt)))[0]

def name():
    return take(number('H')).decode('utf-8')

def payload(kind):
    if kind in (1, 2, 3, 4, 5, 6):
        return number({1:'b', 2:'h', 3:'i', 4:'q', 5:'f', 6:'d'}[kind])
    if kind == 7:
        return take(number('i'))
    if kind == 8:
        return name()
    if kind == 9:
        child = number('B')
        return [payload(child) for _ in range(number('i'))]
    if kind == 10:
        result = {}
        while True:
            child = number('B')
            if not child:
                return result
            key = name()
            result[key] = payload(child)
    if kind in (11, 12):
        return [number('i' if kind == 11 else 'q') for _ in range(number('i'))]
    raise ValueError(kind)

assert number('B') == 10 and name() == 'Schematic'
root = payload(10)
w, d = root['Width'], root['Length']
colors = collections.defaultdict(list)
for i, (block, meta) in enumerate(zip(root['Blocks'], root['Data'])):
    if block == 251 and meta in (11, 4, 3):
        colors[meta].append((i % w, (i // w) % d, i // (w * d)))
assert len(colors[11]) == 1514
assert (min(x for x, z, y in colors[11]), max(x for x, z, y in colors[11])) == (128, 223)
assert (min(z for x, z, y in colors[11]), max(z for x, z, y in colors[11])) == (0, 15)
assert any(16 <= z <= 31 for x, z, y in colors[3])
assert any(16 <= z <= 31 for x, z, y in colors[4])
print('Blue platform and neighboring colored line chunks identified in reference schematic')
