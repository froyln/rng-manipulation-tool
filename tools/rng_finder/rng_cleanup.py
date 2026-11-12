"""Read a saved 1.12.2 Overworld and mark pre-portal RNG consumers; never write to it."""
import argparse
from collections import Counter, defaultdict, deque
import gzip
from pathlib import Path
import re
import struct
import zlib

from combine import read_nbt, write_nbt

# Inspected updateTick implementations; some consume World.rand conditionally.
CONSUMERS = {
    2: 'grass', 6: 'sapling', 10: 'flowing lava', 11: 'lava', 39: 'brown mushroom',
    40: 'red mushroom', 51: 'fire', 59: 'wheat', 104: 'pumpkin stem',
    105: 'melon stem', 106: 'vine', 110: 'mycelium', 115: 'nether wart',
    127: 'cocoa', 141: 'carrots', 142: 'potatoes', 200: 'chorus flower',
    207: 'beetroot', 212: 'frosted ice',
}


class SavedWorld:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        level = self.path / 'level.dat'
        if not level.is_file() or not (self.path / 'region').is_dir():
            raise ValueError('Select the Overworld save folder containing level.dat and region/.')
        if level.stat().st_size == 0:
            raise ValueError('level.dat is empty. Select a valid saved copy; this tool will not alter or restore your world.')
        root = read_nbt(level.read_bytes(), root_name=None)
        if root.get('Data', (0,))[0] != 10:
            raise ValueError('Invalid world level.dat: missing Data compound')
        data = root['Data'][1]
        if not all(key in data for key in ('RandomSeed', 'Time')):
            raise ValueError('Invalid world level.dat: missing seed or time')
        if data.get('DataVersion', data.get('Version', (10, {}))[1].get('Id', (3, -1)))[1] != 1343:
            raise ValueError('Cleanup markers require a Java 1.12.2 world save (DataVersion 1343).')
        self.seed = data['RandomSeed'][1]
        self.time = data['Time'][1]
        self.regions = {}
        self.chunks = {}

    def chunk(self, cx, cz):
        if (cx, cz) in self.chunks:
            return self.chunks[cx, cz]
        region = cx // 32, cz // 32
        if region not in self.regions:
            file = self.path / 'region' / f'r.{region[0]}.{region[1]}.mca'
            if not file.is_file():
                raise ValueError(f'Cleanup coverage is incomplete: chunk ({cx}, {cz}) has not been saved. Generate/save the required chunks first.')
            for _ in range(3):
                before = file.stat()
                raw = file.read_bytes()
                after = file.stat()
                if (before.st_mtime_ns, before.st_size) == (after.st_mtime_ns, after.st_size):
                    break
            else:
                raise ValueError('The world is changing during the scan. Use a stopped/saved copy and retry.')
            self.regions[region] = raw
        raw = self.regions[region]
        index = (cx % 32 + cz % 32 * 32) * 4
        if len(raw) < 8192:
            raise ValueError('Invalid Anvil region header')
        location = int.from_bytes(raw[index:index + 4], 'big')
        offset, sectors = (location >> 8) * 4096, location & 255
        if not offset or not sectors:
            raise ValueError(f'Cleanup coverage is incomplete: chunk ({cx}, {cz}) has not been saved. Generate/save the required chunks first.')
        if offset < 8192 or offset + sectors * 4096 > len(raw):
            raise ValueError('Invalid Anvil chunk location')
        size = int.from_bytes(raw[offset:offset + 4], 'big')
        if not 1 < size <= sectors * 4096 - 4:
            raise ValueError('Invalid Anvil chunk length')
        payload = raw[offset + 5:offset + 4 + size]
        compression = raw[offset + 4]
        try:
            if compression == 2:
                payload = zlib.decompress(payload)
            elif compression == 1:
                payload = gzip.decompress(payload)
            else:
                raise ValueError(f'Unsupported 1.12 Anvil compression {compression}')
        except (zlib.error, OSError) as error:
            raise ValueError(f'Cannot decompress saved chunk ({cx}, {cz}); use a saved/stopped copy.') from error
        root = read_nbt(payload, root_name=None, compressed=False)
        if root.get('Level', (0,))[0] != 10:
            raise ValueError('Invalid Anvil chunk: missing Level compound')
        level = root['Level'][1]
        if (level['xPos'][1], level['zPos'][1]) != (cx, cz):
            raise ValueError('Anvil chunk coordinates do not match its region slot')
        sections = {}
        for section in level['Sections'][1][1]:
            if len(section['Blocks'][1]) != 4096 or len(section['Data'][1]) != 2048:
                raise ValueError('Invalid 1.12 chunk section arrays')
            sy = section['Y'][1]
            if not 0 <= sy < 16 or sy in sections or ('Add' in section and len(section['Add'][1]) != 2048):
                raise ValueError('Invalid or duplicate 1.12 chunk section')
            sections[sy] = section
        self.chunks[cx, cz] = sections
        return sections

    def block(self, x, y, z):
        if not 0 <= y < 256:
            return 0, 0
        section = self.chunk(x // 16, z // 16).get(y // 16)
        if not section:
            return 0, 0
        index = ((y % 16) * 16 + z % 16) * 16 + x % 16
        shift = index % 2 * 4
        block = section['Blocks'][1][index]
        if 'Add' in section:
            block |= ((section['Add'][1][index // 2] >> shift) & 15) << 8
        return block, (section['Data'][1][index // 2] >> shift) & 15


MAX_CONNECTED_LAVA = 50_000


def include_connected_lava(world, positions):
    # A chunk boundary is not a fluid boundary: include the sources feeding it.
    pending = deque(p for p, reason in positions.items() if reason in ('lava', 'flowing lava'))
    seen, body = set(pending), set(pending)
    if len(body) > MAX_CONNECTED_LAVA:
        raise ValueError('Connected lava body exceeds the 50000-block cleanup limit; inspect it before exporting.')
    while pending:
        x, y, z = pending.popleft()
        for dx, dy, dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
            point = x+dx, y+dy, z+dz
            if point in seen or not 0 <= point[1] < 256:
                continue
            seen.add(point)
            if world.block(*point)[0] in (10,11):
                body.add(point)
                if len(body) > MAX_CONNECTED_LAVA:
                    raise ValueError('Connected lava body exceeds the 50000-block cleanup limit; inspect it before exporting.')
                positions.setdefault(point, 'connected lava supply outside the tick prefix')
                pending.append(point)


def cleanup_positions(world, plan):
    seed = int(re.search(r'World seed: (-?\d+)', plan)[1])
    if seed != world.seed:
        raise ValueError('The selected save has a different world seed from this plan.')
    order = [(int(rank), int(cx), int(cz), bool(target)) for rank, cx, cz, target in re.findall(
        r'^Tick #(\d+); list index \d+; chunk \((-?\d+), (-?\d+)\)( PORTAL)?$', plan, re.M)]
    targets = [row for row in order if row[3]]
    height = re.search(r'portal blocks: y=(\d+)\.\.(\d+)', plan)
    if len(targets) != 1 or not height:
        raise ValueError('Cleanup markers need the generated portal tick order and section height.')
    target_rank = targets[0][0]
    if [row[0] for row in order[:target_rank]] != list(range(1, target_rank + 1)):
        raise ValueError('Portal tick order is incomplete')
    section_bottom = int(height[1]) // 16 * 16
    positions = {}
    for rank, cx, cz, _ in order[:target_rank]:
        limit = section_bottom if rank == target_rank else 256
        for sy, section in world.chunk(cx, cz).items():
            if sy * 16 >= limit:
                continue
            for index, block in enumerate(section['Blocks'][1]):
                meta = section['Data'][1][index // 2] >> (index % 2 * 4) & 15
                if 'Add' in section:
                    block |= ((section['Add'][1][index // 2] >> (index % 2 * 4)) & 15) << 8
                reason = CONSUMERS.get(block)
                if block == 35 and meta == 14:
                    reason = 'flammable old red-wool replacement'
                if block in (18, 161) and not meta & 4:
                    reason = 'natural leaves (decay risk)'
                # Unsupported decorative plants can drop items during random ticks.
                if block in (31, 32, 37, 38, 175):
                    x, y, z = cx * 16 + index % 16, sy * 16 + index // 256, cz * 16 + index // 16 % 16
                    below, _ = world.block(x, y - 1, z)
                    if block == 32:
                        valid = below in (3, 12, 159, 172)
                    elif block == 175 and meta & 8:
                        valid = below == 175
                    else:
                        valid = below in (2, 3, 60)
                    if not valid:
                        reason = 'unsupported plant (drop risk)'
                if reason:
                    positions[cx * 16 + index % 16, sy * 16 + index // 256, cz * 16 + index // 16 % 16] = reason
    include_connected_lava(world, positions)
    return positions, target_rank


def cleanup_litematic(positions):
    """Clip each 64x64 block zone independently; reuse the cluster writer's 2-bit packing."""
    groups = defaultdict(list)
    for point in positions:
        groups[point[0] // 64, point[2] // 64].append(point)
    origin = tuple(min(p[a] for p in positions) for a in range(3))
    high = tuple(max(p[a] for p in positions) for a in range(3))
    xyz = lambda values: (10, {a: (3, v) for a, v in zip(('x', 'y', 'z'), values)})
    regions, total_volume, largest = {}, 0, 0
    for index, (_, points) in enumerate(sorted(groups.items())):
        low = tuple(min(p[a] for p in points) for a in range(3))
        size = tuple(max(p[a] for p in points) - low[a] + 1 for a in range(3))
        w, h, d = size
        volume = w * h * d
        total_volume += volume
        largest = max(largest, volume)
        words = [0] * ((volume * 2 + 63) // 64)
        for x, y, z in points:
            offset = (((y - low[1]) * d + z - low[2]) * w + x - low[0]) * 2
            words[offset // 64] |= 1 << (offset % 64)
        regions[f'Cleanup_{index + 1:02d}'] = (10, {
            'Position': xyz(tuple(low[a] - origin[a] for a in range(3))),
            'Size': xyz(size),
            'BlockStatePalette': (9, (10, [
                {'Name': (8, 'minecraft:air')},
                {'Name': (8, 'minecraft:wool'), 'Properties': (10, {'color': (8, 'red')})},
            ])),
            'BlockStates': (12, b''.join(struct.pack('>Q', word) for word in words)),
            'Entities': (9, (10, [])), 'TileEntities': (9, (10, [])),
            'PendingBlockTicks': (9, (10, [])),
        })
    # Match the original Kisde client limits rather than relying on raised limits.
    if len(regions) > 32 or total_volume > 16_777_216:
        raise ValueError('Cleanup regions exceed the client render budget; use a smaller validated cleanup area.')
    root = {
        'Version': (3, 4), 'MinecraftDataVersion': (3, 1343),
        'Metadata': (10, {'Name': (8, 'RNG cleanup markers'), 'Author': (8, 'Threadstone research'),
            'Description': (8, 'Red wool cleanup preview; farm is a separate schematic.'),
            'RegionCount': (3, len(regions)), 'TimeCreated': (4, 0), 'TimeModified': (4, 0),
            'TotalBlocks': (4, len(positions)), 'TotalVolume': (4, total_volume),
            'EnclosingSize': xyz(tuple(high[a] - origin[a] + 1 for a in range(3)))}),
        'Regions': (10, regions),
    }
    return write_nbt(root, root_name=''), origin, len(regions), total_volume, largest


def mark_cleanup(schematic, plan, world_path):
    from combined_litematic import combined_litematic
    world = SavedWorld(world_path)
    positions, rank = cleanup_positions(world, plan)
    data, origin, regions, volume = combined_litematic(schematic, plan, positions)
    plan = plan.replace('Combined schematic minimum corner:', 'Farm template minimum corner (reference only):').replace('Combined dimensions:', 'Farm template dimensions:')
    enclosing = read_nbt(data, root_name=None)['Metadata'][1]['EnclosingSize'][1]
    size = tuple(enclosing[a][1] for a in ('x','y','z'))
    summary = [f'RNG RED REPLACEMENTS: {len(positions)} blocks.',
        'ONE FILE: rng-combined.litematic contains the complete RNG build AND all red-concrete replacement blocks.',
        f'Litematic placement origin: {origin[0]}, {origin[1]}, {origin[2]} (fixed farm anchor; some subregion offsets are negative)',
        f'Combined dimensions: {size[0]} x {size[1]} x {size[2]} (enclosing size only; no dense air box)',
        f'Subregions: {regions}; total allocated region volume: {volume}.',
        f'Saved Overworld: {world.path}; saved world time: {world.time}; checked through portal rank: {rank}.',
        'Every red-concrete block occupies an actual block position to remove or safely replace. No outlines or borders are generated.',
        'RNG_Build subregions contain the farm. Cleanup subregions contain replacement zones. Replacements inside build bounds are included there to avoid overlapping air regions.',
        'Keep all relative subregion positions unchanged. Farm and AFK world coordinates are preserved.',
        'Replace grass/mycelium with coarse dirt, lava with inert solids, leaves with player-placed non-decaying leaves, and remove marked fire/growth/unsupported plants.',
        'Preview before editing. Paste with AIR IGNORED. Red concrete is nonflammable; it replaces the old cleanup wool too. Saved-block coverage does not verify later changes, scheduled updates or server mods.']
    summary.extend(f'  {name}: {count}' for name,count in sorted(Counter(positions.values()).items()))
    return data, '\n'.join(summary)+'\n\n'+plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('world', type=Path)
    parser.add_argument('schematic', type=Path)
    parser.add_argument('plan', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        result = mark_cleanup(args.schematic.read_bytes(), args.plan.read_text(), args.world)
        data, plan = result[:2]
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'rng-combined.litematic').write_bytes(data)
        (args.output / 'rng-finder-plan.txt').write_text(plan)
        print('\n'.join(plan.splitlines()[:3]))
    except (OSError, ValueError, zlib.error) as error:
        parser.exit(1, str(error) + '\n')
