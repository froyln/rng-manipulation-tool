"""Conservative collision scan using the local decompiled vanilla 1.12.2 generator."""
import os
import re
import struct
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from combine import read_nbt, write_nbt

TOOL_DIR = Path(__file__).resolve().parent
GRADLE_CACHE = Path(os.environ.get('GRADLE_USER_HOME', Path.home() / '.gradle')) / 'caches'
MCP = GRADLE_CACHE / 'minecraft/net/minecraft/minecraft/1.12.2/stable/39'
DEPS = GRADLE_CACHE / 'modules-2/files-2.1'
SCANNER = TOOL_DIR / 'TerrainScan.java'
CLASS_DIR = TOOL_DIR / 'target' / 'terrain-scan'


def _classpath():
    supplied = os.environ.get('RNG_MINECRAFT_CLASSPATH')
    if supplied:
        return supplied
    binary = MCP / 'minecraftBin-1.12.2.jar'
    if not binary.is_file() or not DEPS.is_dir():
        raise RuntimeError('Terrain scan needs the local MCP 1.12.2 source workspace; see the RNG finder README.')
    return str(binary) + os.pathsep + os.pathsep.join(str(p) for p in DEPS.rglob('*.jar'))


def scan(schematic, plan):
    root = read_nbt(schematic)
    corner = tuple(map(int, re.search(
        r'Combined schematic minimum corner: (-?\d+), (-?\d+), (-?\d+)', plan).groups()))
    width, height, length = (root[k][1] for k in ('Width', 'Height', 'Length'))
    blocks = root['Blocks'][1]
    point_set = set()
    required_air = set()
    occupied = bytes(blocks).translate(bytes([0] + [1] * 255))
    index = occupied.find(b'\x01')
    while index >= 0:
        y, rem = divmod(index, length * width)
        z, x = divmod(rem, width)
        point_set.add((corner[0] + x, corner[1] + y, corner[2] + z))
        index = occupied.find(b'\x01', index + 1)
    attempts = re.search(r'Modeled spawn-attempt positions.*?:\n(.*?)\n\n', plan, re.S)
    if attempts:
        mob = re.search(r'^Target: (\w+)', plan, re.M).group(1)
        headroom = 3 if mob == 'enderman' else 1 if mob == 'spider' else 2
        radius = 1 if mob == 'spider' else 0
        for _, x, y, z in re.findall(r'(\d+)\.\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)', attempts.group(1)):
            required_air.update((int(x)+dx, int(y)+dy, int(z)+dz) for dx in range(-radius,radius+1)
                                for dz in range(-radius,radius+1) for dy in range(headroom))
    roof = re.search(r'Mob roof bounds: (-?\d+), (\d+), (-?\d+) to (-?\d+), (\d+), (-?\d+)', plan)
    if roof and attempts:
        x0,ry,z0,x1,_,z1 = map(int,roof.groups())
        floors = {(int(x),int(y)-1,int(z)) for _,x,y,z in re.findall(r'(\d+)\.\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)',attempts.group(1))}
        required_air.update((x,y,z) for x in range(x0,x1+1) for z in range(z0,z1+1) for y in range(ry-4,ry) if (x,y,z) not in floors)
    golem = re.search(r'Modeled first golem spawn block:\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)', plan)
    portal_cells = set()
    if golem:
        gx, gy, gz = map(int, golem.groups())
        for dx in (-1, 0):
            for dy in range(4):
                for dz in (-1, 0):
                    point = (gx + dx, gy + dy, gz + dz)
                    local = (point[0] - corner[0], point[1] - corner[1], point[2] - corner[2])
                    in_schematic = 0 <= local[0] < width and 0 <= local[1] < height and 0 <= local[2] < length
                    index = ((local[1] * length + local[2]) * width + local[0]) if in_schematic else -1
                    if in_schematic and blocks[index] == 90:
                        portal_cells.add(point)
                    else:
                        required_air.add(point)
    point_set.update(required_air)
    point_set.difference_update(portal_cells)
    control = re.search(r'Height control block \(stone\): (-?\d+), (-?\d+), (-?\d+)', plan)
    if control:
        x, y, z = map(int, control.groups())
        point_set.update((x, yy, z) for yy in range(y + 1, 256))
    points = sorted(point_set)
    CLASS_DIR.mkdir(parents=True, exist_ok=True)
    cp = _classpath()
    compiled = CLASS_DIR / 'TerrainScan.class'
    if not compiled.is_file() or compiled.stat().st_mtime < SCANNER.stat().st_mtime:
        javac = subprocess.run(['javac', '-proc:none', '-cp', cp, '-d', str(CLASS_DIR), str(SCANNER)],
                               text=True, capture_output=True, timeout=120)
        if javac.returncode:
            raise RuntimeError('Could not compile the vanilla terrain scanner: ' + javac.stderr[-1800:])
    with tempfile.TemporaryDirectory(prefix='rng-terrain-') as temp:
        source, result = Path(temp) / 'points.bin', Path(temp) / 'result.bin'
        with source.open('wb') as f:
            for point in points:
                f.write(struct.pack('>iii', *point))
        seed = int(re.search(r'World seed: (-?\d+)', plan).group(1))
        java = subprocess.run(['java', '-cp', str(CLASS_DIR) + os.pathsep + cp, 'TerrainScan',
                               str(seed), str(source), str(result)], text=True, capture_output=True, timeout=180)
        if java.returncode:
            raise RuntimeError('Vanilla terrain scan failed: ' + java.stderr[-1800:])
        data = result.read_bytes()
    count = struct.unpack_from('>i', data)[0]
    if count == -1:
        hit_index, = struct.unpack_from('>i', data, 4)
        block = data[8]
        return False, (f'Seed terrain scan (vanilla 1.12.2 default terrain, structures enabled) rejected this candidate at the first non-structure obstruction: '
                       f'block ID {block} at {points[hit_index]}. Scan stopped early; no schematic from this candidate is offered.')
    if count != len(points):
        raise RuntimeError('Terrain scan returned an incomplete block list.')
    ids = data[4:4 + count]
    offset = 4 + count
    structure_count = struct.unpack_from('>i', data, offset)[0]
    offset += 4
    structures = []
    for _ in range(structure_count):
        size = struct.unpack_from('>H', data, offset)[0]
        offset += 2
        structures.append(data[offset:offset + size].decode('utf-8').split('\t'))
        offset += size
    if offset != len(data):
        raise RuntimeError('Terrain scan returned malformed structure data.')
    hits = [(point, value) for point, value in zip(points, ids) if value]
    volume = (corner[0], corner[1], corner[2], corner[0] + width - 1, corner[1] + height - 1, corner[2] + length - 1)
    touching = []
    nearby = []
    for structure in sorted(set(tuple(s) for s in structures)):
        name, *values = structure
        box = tuple(map(int, values))
        distance = sum(max(box[axis] - volume[axis + 3], volume[axis] - box[axis + 3], 0) ** 2 for axis in range(3))
        if distance <= 16 * 16:
            nearby.append((name, box, distance))
        if distance == 0:
            touching.append((name, box))
    structure_cells = defaultdict(list)
    for _, box in touching:
        for cx in range(box[0] // 16, box[3] // 16 + 1):
            for cy in range(box[1] // 16, box[4] // 16 + 1):
                for cz in range(box[2] // 16, box[5] // 16 + 1):
                    structure_cells[(cx, cy, cz)].append(box)
    terrain_hits = [(point, block) for point, block in hits if point not in portal_cells and
                    (point in required_air or (control and point[0] == x and point[2] == z and point[1] >= y)
                     or not any(box[0] <= point[0] <= box[3] and box[1] <= point[1] <= box[4] and box[2] <= point[2] <= box[5]
                                for box in structure_cells[(point[0] // 16, point[1] // 16, point[2] // 16)]))]
    summary = [f"Seed terrain scan (vanilla 1.12.2 default terrain, structures enabled): {len(points)} schematic blocks checked."]
    summary.append('Population decoration, scheduled fluid ticks, and prior chunk-generation history are not reproduced by this scan.')
    if terrain_hits:
        summary.append(f'{len(terrain_hits)} schematic blocks intersect generated terrain; this candidate is rejected.')
        summary.extend(f'  block ID {block} at {point}' for point, block in terrain_hits[:12])
    if touching:
        summary.append(f'{len(touching)} generated structure bounds intersect the schematic volume (including air); inspect these before placement:')
        summary.extend(f'  {name}: {box[0]}, {box[1]}, {box[2]} to {box[3]}, {box[4]}, {box[5]}' for name, box in touching)
    elif nearby:
        summary.append(f'{len(nearby)} generated structure bounds intersect or lie within 16 blocks of the schematic volume:')
        summary.extend(f'  {name}: {box[0]}, {box[1]}, {box[2]} to {box[3]}, {box[4]}, {box[5]}' for name, box, _ in nearby)
    if not terrain_hits and not touching:
        summary.append('No terrain or generated-structure-bounds collision found in the scanned model.')
    return not terrain_hits, '\n'.join(summary)


def mark_structures(schematic, report):
    root = read_nbt(schematic)
    structures = re.findall(r'^  ([^:]+): (-?\d+), (-?\d+), (-?\d+) to -?\d+, -?\d+, -?\d+$', report, re.M)
    if not structures:
        return schematic
    signs = root['TileEntities'][1][1]
    sign = next((tag for tag in signs if tag['id'][1] == 'minecraft:sign' and tag.get('Text1', (8,''))[1] == '{"text":"Player Spot"}'), None)
    if sign is None:
        return schematic
    for index, (name, *_coords) in enumerate(structures[:3], 2):
        label = {'Woodland Mansion':'Mansion', 'Ocean Monument':'Monument', 'Desert Pyramid':'Temple', 'Igloo':'Igloo', 'Jungle Temple':'Jungle', 'Swamp Hut':'Hut'}.get(name, name[:9])
        sign[f'Text{index}'] = (8, '{"text":"Near ' + label + '"}')
    if len(structures) > 3:
        sign['Text4'] = (8, '{"text":"See plan"}')
    return write_nbt(root)
