"""Place Command's sand detector at the north lazy edge and connect its 900-tick output."""
from pathlib import Path


# shortcut: gameplay is validated at view 10; test other distances before promising compatibility.
def detector_origin(player, view):
    x, y, z = player
    return x // 16 * 16, y - 3, (z // 16 - view + 1) * 16 - 6


def detector_component(player, view):
    # Import lazily: combine imports this module only after its NBT helpers exist.
    from combine import read_nbt
    source = Path(__file__).with_name('reference') / 'command-autosave-detector-1.12.schematic'
    return read_nbt(source.read_bytes()), detector_origin(player, view)


def detector_marks(player, grid, view, tile_tick=True):
    x, y, z = player
    dx, dy, dz = detector_origin(player, view)
    actual_grid = grid
    if not tile_tick:
        grid = (grid[0], y - 2, z - 8)
    marks = {}

    def put(px, py, pz, block, meta=0):
        position = px, py, pz
        value = block, meta
        if position in marks and marks[position] != value:
            raise ValueError(f'Detector routes overlap at {position}')
        marks[position] = value

    def wire(path):
        for index, (px, py, pz) in enumerate(path):
            put(px, py - 1, pz, 159, 11)
            if index and index % 14 == 0 and index + 1 < len(path):
                nx, _, nz = path[index + 1]
                facing = 1 if nx > px else 3 if nx < px else 0 if nz < pz else 2
                put(px, py, pz, 93, facing)
            else:
                put(px, py, pz, 55)

    # The edge detector releases the grid input even while the start lever stays on.
    put(x - 1, y, z - 2, 218, 3)
    wire([(x - 2, y, z), (x - 3, y + 1, z), (x - 4, y + 2, z)]
         + [(x - 4, y + 2, pz) for pz in range(z + 1, z + 4)]
         + [(px, y + 2, z + 3) for px in range(x - 3, x + 11)]
         + [(x + 10, y + 2, pz) for pz in range(z + 2, dz + 9, -1)]
         + [(px, y + 2, dz + 10) for px in range(x + 9, dx + 13, -1)]
         + [(dx + 13, y + 1, dz + 10)])
    # Refresh immediately before the detector's long ascending input line.
    marks[dx + 15, y + 2, dz + 10] = 93, 3
    if tile_tick:
        wire([(px, y, dz + 2) for px in range(dx + 2, dx - 5, -1)]
             + [(dx - 4, y, pz) for pz in range(dz + 3, grid[2])]
             + [(px, y, grid[2] - 1) for px in range(dx - 3, x - 1)])
    else:
        # Xcom's old detector drives this clock input; never feed recurring pulses to its startup piston.
        gx, gy, gz = actual_grid
        high = max(y + 12, gy + 18)
        path = [(px, y, dz + 2) for px in range(dx + 2, dx - 5, -1)]
        path += _rise((dx - 4, y, dz + 2), high, (0, 1))
        end_z = path[-1][2]
        path += [(px, high, end_z) for px in range(dx - 3, gx + 200)]
        path += [(gx + 199, high, pz) for pz in range(end_z + 1, gz + 8)]
        path += [(gx + 199, high - i, gz + 7 + i) for i in range(1, 7)]
        path += [(gx + 199 - i, high - 6, gz + 13) for i in range(1, 3)]
        # Descend away from the original grid, then return to its preserved output port.
        path += _rise((gx + 197, high - 6, gz + 13), gy + 3, (0, 1))
        end_z = path[-1][2]
        path += [(gx + 198, gy + 3, end_z)]
        path += [(gx + 198, gy + 3, pz) for pz in range(end_z - 1, gz + 11, -1)]
        path += [(gx + 199, gy + 3, gz + 12), (gx + 200, gy + 3, gz + 12)]
        _route(marks, path, preserve_support=(gx + 200, gy + 3, gz + 12))
    # Nonconducting crossings keep the held enable signal off the pulse lines.
    marks[x + 10, y + 1, grid[2] - 2] = 44, 8
    marks[x + 10, y + 1, grid[2] - 1] = 44, 8
    # Isolate the detector output and restore its attenuated dust signal.
    marks[dx + 2, y, dz + 2] = 93, 3
    extra_z = (z // 16 - view - 1) * 16 + 8
    wire([(px, y, grid[2] - 2) for px in range(x - 1, x + 13)]
         + [(x + 12, y, pz) for pz in range(grid[2] - 3, extra_z - 1, -1)]
         + [(px, y, extra_z) for px in range(x + 11, dx - 33, -1)])
    wire([(px, y, extra_z) for px in range(x + 13, dx + 48)])
    if not tile_tick:
        marks[x - 1, y, z - 7] = (93, 0)
        marks[x + 5, y, z - 10] = (93, 1)
        marks[x + 10, y, z - 10] = (93, 1)
        gx, gy, gz = actual_grid
        # The lever edge still performs Xcom's one-time slime-line calibration.
        start = (x + 12, y, z - 10)
        high = max(y + 5, gy + 10)
        path = _rise(start, high, (1, 0))
        # Stay north of Iron's door sky checks; very low mob players need the longer south ramp.
        if path[-1][0] <= gx + 220:
            end_z = z - 10
            path += [(px, high, end_z) for px in range(path[-1][0] + 1, gx + 221)]
        else:
            path = _rise(start, high, (0, 1))
            end_z = path[-1][2]
            path += [(px, high, end_z) for px in range(x + 13, gx + 221)]
        path += [(gx + 220, high, pz) for pz in range(end_z + 1, gz - 9)]
        path += [(px, high, gz - 10) for px in range(gx + 219, gx + 187, -1)]
        path += _rise((gx + 188, high, gz - 10), gy + 7, (0, 1))
        end_z = path[-1][2]
        path += [(gx + 188, gy + 7, pz) for pz in range(end_z + 1, gz - 1)]
        _route(marks, path)
        marks[gx + 188, gy + 7, gz - 2] = (93, 2)
        marks[gx + 188, gy + 6, gz - 1] = (159, 11)
        marks[gx + 188, gy + 7, gz - 1] = (33, 3)
    return [(*position, *value) for position, value in marks.items()]


def _rise(start, target_y, direction):
    x, y, z = start
    dx, dz = direction
    path = []
    while y != target_y:
        for _ in range(min(6, abs(target_y - y))):
            x += dx; z += dz; y += 1 if target_y > y else -1
            path.append((x, y, z))
        # Flat runs allow signal regeneration between slopes.
        for _ in range(3):
            x += dx; z += dz
            path.append((x, y, z))
    return path


def _route(marks, path, preserve_support=None):
    last = 0
    for i, (x, y, z) in enumerate(path):
        if i and (abs(x-path[i-1][0])+abs(z-path[i-1][2]) != 1 or abs(y-path[i-1][1]) > 1):
            raise ValueError('Generated component at detector route has a gap; this player height/view distance cannot fit the adapter')
        p = x, y, z
        if p != preserve_support:
            support = x, y - 1, z
            if support in marks and marks[support] != (159, 11):
                raise ValueError(f'Detector route support overlaps at {support}')
            marks[support] = (159, 11)
        straight = 0 < i < len(path) - 1 and path[i-1][1] == y == path[i+1][1] and (x-path[i-1][0], z-path[i-1][2]) == (path[i+1][0]-x, path[i+1][2]-z)
        if straight and i - last >= 7:
            nx, _, nz = path[i+1]
            value = (93, 1 if nx > x else 3 if nx < x else 0 if nz < z else 2)
            last = i
        else:
            if i - last > 14:
                raise ValueError('Detector route needs a repeater before its slope')
            value = (55, 0)
        if p in marks and marks[p] != value:
            raise ValueError(f'Detector routes overlap at {p}: {marks[p]} vs {value}')
        marks[p] = value
