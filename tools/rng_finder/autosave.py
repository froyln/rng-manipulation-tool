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


def detector_marks(player, grid, view):
    x, y, z = player
    dx, dy, dz = detector_origin(player, view)
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
    wire([(px, y, dz + 2) for px in range(dx + 2, dx - 5, -1)]
         + [(dx - 4, y, pz) for pz in range(dz + 3, grid[2])]
         + [(px, y, grid[2] - 1) for px in range(dx - 3, x - 1)])
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
    return [(*position, *value) for position, value in marks.items()]
