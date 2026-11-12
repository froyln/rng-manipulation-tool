"""Combine the legacy 1.12 schematics without dropping the grid's tile entities."""
import gzip
import math
import re
import struct


def read_nbt(data, *, root_name='Schematic', compressed=True):
    data = gzip.decompress(data) if compressed else data
    offset = 0
    def take(n):
        nonlocal offset
        if n < 0 or offset + n > len(data):
            raise ValueError('Invalid schematic NBT length')
        value = data[offset:offset+n]
        offset += n
        return value
    def unpack(fmt):
        return struct.unpack('>' + fmt, take(struct.calcsize(fmt)))[0]
    def name():
        value = take(unpack('H')).replace(b'\xc0\x80', b'\0').decode('utf-8', 'surrogatepass')
        return value.encode('utf-16-be', 'surrogatepass').decode('utf-16-be', 'surrogatepass')
    def payload(kind):
        if kind in (1, 2, 3, 4, 5, 6):
            return unpack({1:'b', 2:'h', 3:'i', 4:'q', 5:'f', 6:'d'}[kind])
        if kind == 7:
            return take(unpack('i'))
        if kind == 8:
            return name()
        if kind == 9:
            child = unpack('B')
            return (child, [payload(child) for _ in range(unpack('i'))])
        if kind == 10:
            result = {}
            while True:
                child = unpack('B')
                if child == 0:
                    return result
                key = name()
                result[key] = (child, payload(child))
        if kind in (11, 12):
            count = unpack('i')
            return take(count * (4 if kind == 11 else 8))
        raise ValueError(f'Unsupported NBT tag {kind}')
    if unpack('B') != 10:
        raise ValueError('Expected a legacy schematic')
    actual_name = name()
    if root_name is not None and actual_name != root_name:
        raise ValueError('Expected a legacy schematic')
    result = payload(10)
    if offset != len(data):
        raise ValueError('Trailing NBT data')
    return result


def write_nbt(root, *, root_name='Schematic'):
    def name(value):
        # Java NBT uses modified UTF-8 (UTF-16 surrogate pairs and a two-byte NUL).
        units = value.encode('utf-16-be', 'surrogatepass')
        value = b''.join(chr(unit).encode('utf-8', 'surrogatepass') for (unit,) in struct.iter_unpack('>H', units)).replace(b'\0', b'\xc0\x80')
        if len(value) > 65535:
            raise ValueError('NBT string exceeds the Java UTF length limit')
        return struct.pack('>H', len(value)) + value
    def payload(kind, value):
        if kind in (1, 2, 3, 4, 5, 6):
            return struct.pack('>' + {1:'b', 2:'h', 3:'i', 4:'q', 5:'f', 6:'d'}[kind], value)
        if kind == 7:
            return struct.pack('>i', len(value)) + value
        if kind == 8:
            return name(value)
        if kind == 9:
            child, values = value
            return bytes([child]) + struct.pack('>i', len(values)) + b''.join(payload(child, v) for v in values)
        if kind == 10:
            return b''.join(bytes([k]) + name(n) + payload(k, v) for n, (k, v) in value.items()) + b'\0'
        if kind in (11, 12):
            return struct.pack('>i', len(value) // (4 if kind == 11 else 8)) + value
        raise ValueError(f'Unsupported NBT tag {kind}')
    return gzip.compress(b'\x0a' + name(root_name) + payload(10, root), compresslevel=1)


def placement(plan, section):
    match = re.search(re.escape(section) + r'.*?minimum corner(?: \(local 0,0,0\))?:\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)', plan, re.I | re.S)
    if not match:
        raise ValueError(f'Missing {section} placement in plan')
    return tuple(map(int, match.groups()))


def startup_marks(player, grid, view):
    x, y, z = player
    gx, gy, gz = grid
    wire_y, sx, sz = gy + 7, x - 1, z
    tx, tz = gx + 188, gz - 2
    if y > wire_y:
        raise ValueError('Player is above the startup piston; lower the assumed Y bound before exporting.')
    ramp = wire_y - y
    z_ramp = min(ramp, tz - 1 - sz)
    x_ramp = ramp - z_ramp
    if x_ramp > tx - sx:
        raise ValueError('Player height leaves too little room for the startup line inside the view square; lower the Y bound or increase view distance.')

    path = [(sx, y, sz)]
    for step in range(1, z_ramp + 1):
        path.append((sx, y + step, sz + step))
    turn_z = sz + z_ramp
    for step in range(1, x_ramp + 1):
        path.append((sx + step, y + z_ramp + step, turn_z))
    for px in range(sx + x_ramp + 1, tx + 1):
        path.append((px, wire_y, turn_z))
    for pz in range(turn_z + 1, tz + 1):
        path.append((tx, wire_y, pz))

    # Lever meta 5 is floor-mounted on the AFK platform; the piston needs a base.
    marks = [(sx, y, z - 1, 69, 5), (gx + 188, gy + 6, gz - 1, 159, 11),
             (gx + 188, gy + 7, gz - 1, 33, 3)]
    for i, (px, py, pz) in enumerate(path):
        if i and not (py == y and abs(px - x) <= 1 and abs(pz - z) <= 1):
            marks.append((px, py - 1, pz, 159, 11))
        if i == len(path) - 1:
            marks.append((px, py, pz, 93, 2))
        elif i and i % 14 == 0:
            nx, _, nz = path[i + 1]
            # 1.12 repeater metadata points toward its input, opposite its output.
            facing = 2 if nz > pz else 0 if nz < pz else 1 if nx > px else 3
            marks.append((px, py, pz, 93, facing))
        else:
            marks.append((px, py, pz, 55, 0))
    pcx, pcz = x // 16, z // 16
    if any(abs(px // 16 - pcx) > view or abs(pz // 16 - pcz) > view for px, _, pz, _, _ in marks):
        raise ValueError('Startup line leaves the player view square; increase view distance before exporting.')
    return marks


def tile_startup_marks(player, grid, view):
    x, y, z = player
    gx, gy, gz = grid
    tx = gx + 202
    if y != gy + 2 or tx < x:
        raise ValueError('Tile-grid player and input heights/positions do not match')
    # Pulse the shared control line; the former completion-line input only starts one wave.
    path = ([(x - 1, y, pz) for pz in range(z, gz - 2, -1)]
            + [(x - 1 + step, y + step, gz - 1) for step in range(1, 6)]
            + [(px, y + 5, gz - 1) for px in range(x + 5, tx + 1)]
            + [(tx, y + 5, pz) for pz in range(gz, gz + 14)]
            + [(tx, y + 5 - step, gz + 13 + step) for step in range(1, 7)]
            + [(tx, y - 1, gz + 20)])
    marks = [(x - 1, y, z + 1, 69, 5)]
    last_repeater = 0
    for index, (px, py, pz) in enumerate(path):
        if not (abs(px - x) <= 1 and abs(pz - z) <= 1):
            marks.append((px, py - 1, pz, 159, 11))
        straight = False
        if 0 < index < len(path) - 1:
            before, after = path[index - 1], path[index + 1]
            straight = before[1] == py == after[1] and (px - before[0], pz - before[2]) == (after[0] - px, after[2] - pz)
        if index == len(path) - 1:
            marks.append((px, py, pz, 93, 2))
        elif straight and index - last_repeater >= 7:
            nx, _, nz = path[index + 1]
            facing = 1 if nx > px else 3 if nx < px else 0 if nz < pz else 2
            marks.append((px, py, pz, 93, facing))
            last_repeater = index
        else:
            if index - last_repeater > 13:
                raise ValueError('Tile-grid input route needs a signal refresh before its next slope')
            marks.append((px, py, pz, 55, 0))
    pcx, pcz = x // 16, z // 16
    if any(abs(px // 16 - pcx) > view or abs(pz // 16 - pcz) > view for px, _, pz, _, _ in marks):
        raise ValueError('Tile-grid input route leaves the player view square')
    return marks


def combine(grid_bytes, plan, extra=None, extra_name=None):
    parts = [(read_nbt(grid_bytes), placement(plan, 'Grid schematic:'))]
    if extra is not None:
        parts.append((read_nbt(extra), placement(plan, extra_name)))
    marks = []
    player = re.search(r'(?:Suggested mining/player position|Suggested player position|Player position):\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)', plan, re.I)
    if not player:
        raise ValueError('Player position missing from plan')
    x, y, z = (math.floor(float(value)) for value in player.groups())
    player_pos = (x, y, z)
    view = int(re.search(r'(?:Server )?view distance:\s*(\d+)', plan, re.I).group(1))
    tile_tick = 'Grid type: scheduled repeater' in plan
    marks.extend((tile_startup_marks if tile_tick else startup_marks)(player_pos, parts[0][1], view))
    if tile_tick:
        from autosave import detector_component, detector_marks
        parts.append(detector_component(player_pos, view))
        merged = {tuple(mark[:3]): tuple(mark[3:]) for mark in marks}
        for px, py, pz, block, meta in detector_marks(player_pos, parts[0][1], view):
            if (px, py, pz) in merged and merged[px, py, pz] != (block, meta) and block != 218:
                raise ValueError(f'Detector startup conflicts at {px}, {py}, {pz}')
            merged[px, py, pz] = block, meta
        marks = [(*position, *value) for position, value in merged.items()]
    for dx in range(-1, 2):
        for dz in range(-1, 2):
            marks.append((x + dx, y-1, z + dz, 251, 3 if dx == 0 and dz == 0 else 11))
    marks.append((x + 1, y, z + 1, 63, 0))
    mob_attempts = re.search(r'Modeled spawn-attempt positions.*?:\n(.*?)\n\n', plan, re.S)
    control = None
    if mob_attempts:
        initial = re.search(r'Initial random block:\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)', plan)
        bound = re.search(r'Assumed Y bound:\s*(\d+)', plan)
        if not initial or not bound:
            raise ValueError('Missing mob height-control information')
        ix, _, iz = map(int, initial.groups())
        control = (ix, int(bound.group(1)) - 2, iz)
        marks.append((*control, 1, 0))
        marks.append((ix, control[1] + 1, iz, 20, 0))
        for _, x, y, z in re.findall(r'(\d+)\.\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)', mob_attempts.group(1)):
            x, y, z = int(x), int(y), int(z)
            if (x, z) == (ix, iz) and y <= control[1] <= y + 2:
                raise ValueError('Height control block obstructs a modeled mob spawn')
            marks.append((x, y-1, z, 251, 5))
            marks.append((x, y, z, 20, 0))
    low = [min([p[i] for _, p in parts] + [m[i] for m in marks]) for i in range(3)]
    high = [max([p[i] + root[('Width','Height','Length')[i]][1] - 1 for root, p in parts] + [m[i] for m in marks]) for i in range(3)]
    w, h, d = [high[i] - low[i] + 1 for i in range(3)]
    volume = w*h*d
    if max(w,h,d) > 32767 or volume > 150_000_000:
        raise ValueError('Combined schematic exceeds supported dimensions; reduce the Y bound or view distance.')
    blocks, metadata = bytearray(volume), bytearray(volume)
    tiles, entities = [], []
    for root, origin in parts:
        if root.get('AddBlocks'):
            raise ValueError('High block IDs are not supported in the combined schematic')
        pw, ph, pd = (root[n][1] for n in ('Width','Height','Length'))
        source, source_data = root['Blocks'][1], root['Data'][1]
        if len(source) != pw*ph*pd or len(source_data) != len(source):
            raise ValueError('Incorrect schematic array length')
        ox, oy, oz = (origin[i] - low[i] for i in range(3))
        for sy in range(ph):
            for sz in range(pd):
                src = (sy*pd+sz)*pw
                dst = ((sy+oy)*d+sz+oz)*w+ox
                for sx, block in enumerate(source[src:src+pw]):
                    if block:
                        if blocks[dst+sx] and (blocks[dst+sx], metadata[dst+sx]) != (block, source_data[src+sx]):
                            raise ValueError('Schematic components overlap with conflicting blocks')
                        blocks[dst+sx] = block
                        metadata[dst+sx] = source_data[src+sx]
        for entity in root['TileEntities'][1][1]:
            entity = dict(entity)
            for axis, delta in zip(('x','y','z'), (ox,oy,oz)):
                kind, value = entity[axis]
                entity[axis] = (kind, value + delta)
            tiles.append(entity)
        for entity in root['Entities'][1][1]:
            entity = dict(entity)
            pos = entity.get('Pos')
            if entity.get('id') != (8, 'minecraft:villager') or not pos or pos[0] != 9 or pos[1][0] != 6 or len(pos[1][1]) != 3 or any(k in entity for k in ('Passengers', 'Leash', 'UUID', 'UUIDMost', 'UUIDLeast')):
                raise ValueError('Unsupported schematic entity; cannot safely relocate it')
            entity['Pos'] = (9, (6, [value + delta for value, delta in zip(pos[1][1], (ox, oy, oz))]))
            entities.append(entity)
        if root.get('TileTicks', (9,(0,[])))[1][1]:
            raise ValueError('Scheduled ticks are not supported by combined export')
    for x,y,z,block,meta in marks:
        index = ((y-low[1])*d + z-low[2])*w + x-low[0]
        if blocks[index] and (blocks[index], metadata[index]) != (block,meta):
            raise ValueError(f'Generated component at {x}, {y}, {z} conflicts with another schematic block')
        blocks[index], metadata[index] = block, meta
    if control:
        cx, cy, cz = control
        for yy in range(cy + 1, high[1] + 1):
            block = blocks[((yy-low[1])*d + cz-low[2])*w + cx-low[0]]
            if block and not (yy == cy + 1 and block == 20):
                raise ValueError('Height control column has a schematic block above the control block')
    sx, sy, sz = player_pos[0] + 1 - low[0], player_pos[1] - low[1], player_pos[2] + 1 - low[2]
    tiles.append({'id': (8, 'minecraft:sign'), 'x': (3, sx), 'y': (3, sy), 'z': (3, sz),
                  'Text1': (8, '{"text":"Player Spot"}'), 'Text2': (8, '{"text":""}'),
                  'Text3': (8, '{"text":""}'), 'Text4': (8, '{"text":""}')})
    root = {'Width':(2,w),'Height':(2,h),'Length':(2,d),'Materials':(8,'Alpha'),
            'Blocks':(7,bytes(blocks)), 'Data':(7,bytes(metadata)),
            'Entities':(9,(10,entities)), 'TileEntities':(9,(10,tiles))}
    label = f'Combined schematic minimum corner: {low[0]}, {low[1]}, {low[2]}\nCombined dimensions: {w} x {h} x {d}\nThe blue 3x3 platform and Player Spot sign mark where to stand. Use its lever: switch it on, then off to extend and retract the normal piston; it shifts the slime and redstone-block line one block toward +Z. Blue terracotta supports the startup line between the player and detector. Repeaters connect the lever to the piston. Green concrete marks modeled mob spawn floors. Glass occupies each modeled spawn block; remove it to permit spawning and clear the headroom.\nThe elevated startup route and complete grid cycle remain unverified in Minecraft. The desktop finder scans generated terrain blocks and structure bounds; population decoration and generation history remain unresolved. The schematic contains a large air volume: placing air can erase existing builds. Kill and collection mechanisms are not supplied. The portal array uses valid 16x16 apertures in each Z slice; see its plan instructions for lighting sequence and conditional RNG assumptions.\n\n'
    if tile_tick:
        label = label.replace('Use its lever: switch it on, then off to extend and retract the normal piston; it shifts the slime and redstone-block line one block toward +Z. Blue terracotta supports the startup line between the player and detector. Repeaters connect the lever to the piston.',
                              'Switch the AFK lever ON and leave it on. Its edge pulse starts the grid, its separate enable line runs the autosave detector, and the detector repeats the shared two-line input automatically. Allow the first natural autosave to synchronize. No separate button is needed.')
        label = label.replace('The elevated startup route and complete grid cycle remain unverified in Minecraft.',
                              'Detector-driven repeated cycles passed two prepared vanilla 1.12.2 Survival-mode trials at server view distance 10; see research/experiments/pigman-afk-export/README.md. Entirely survival-built construction and modded-server compatibility remain unverified.')
    if tile_tick:
        label = label.replace('Green concrete marks modeled mob spawn floors. Glass occupies each modeled spawn block; remove it to permit spawning and clear the headroom. ', '')
        label = label.replace('The portal array uses valid 16x16 apertures in each Z slice; see its plan instructions for lighting sequence and conditional RNG assumptions.', 'The portal array is sliced: bottom obsidian is absent and the lower stone platform remains. Import all portal blocks without neighbor updates; normal lighting requires a temporary complete frame and update-suppressed slicing. Pigmen spawn above the lower platform. The export does not supply an update suppressor.')
    if extra_name == 'Village schematic:':
        label += 'The Iron component includes 300 adults in separate cells and 24 wooden doors; see the plan for the count threshold and village conditions.\n\n'
    if entities:
        label += ('The schematic contains 300 adult villagers in separate glass cells. Some importers discard entities; WorldEdit 6.1 cannot load them from legacy schematics. '
                  'If they are missing, use these commands once each or bring villagers manually:\n')
        for entity in entities:
            ex, ey, ez = (value + delta for value, delta in zip(entity['Pos'][1][1], low))
            label += f'/summon minecraft:villager {ex:g} {ey:g} {ez:g} {{Age:0}}\n'
        label += '\n'
    if control:
        label += f'Height control block (stone): {control[0]}, {control[1]}, {control[2]}. Glass above it prevents spawning without changing the heightmap; keep the rest of the column clear and verify the heightmap after construction.\n\n'
    plan = plan.replace('xcom-original-grid.schematic', 'included in combined schematic')
    plan = plan.replace('tile-tick-grid.schematic', 'included in combined schematic')
    plan = plan.replace('autosave-detector.schematic', 'included in combined schematic')
    plan = plan.replace('golem-village.schematic', 'included in combined schematic')
    plan = plan.replace('portal-platform.schematic', 'included in combined schematic')
    plan = plan.replace('Grid schematic:', 'Grid component within combined schematic:')
    plan = plan.replace('Village schematic:', 'Village component within combined schematic:')
    plan = plan.replace('Portal-platform schematic:', 'Portal component within combined schematic:')
    plan = plan.replace('Portal-array schematic:', 'Portal component within combined schematic:')
    plan = plan.replace('Autosave detector schematic:', 'Autosave detector component within combined schematic:')
    return write_nbt(root), label + plan
