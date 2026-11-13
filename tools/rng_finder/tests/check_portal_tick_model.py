"""Check derived portal search, desktop wiring/export, and pinned Minecraft methods."""
import os
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL))
import backend as gui
from terrain_scan import _classpath
from combine import combine, read_nbt

with tempfile.TemporaryDirectory(prefix='portal-tick-test-') as directory:
    output = Path(directory) / 'output'
    args = [str(gui.BINARY), '--portal', '12345', '3', '0', '0', '25', '0', '10', str(output), '--portal-tick-model']
    subprocess.run(args, check=True, capture_output=True)
    plan = (output / gui.PLAN_NAME).read_text()
    assert 'Mansion region: 6, 7' in plan
    assert 'Suggested player position: 7512.5, 66, 8968.5' in plan
    assert 'then 82 nextInt(16) calls' in plan
    assert 'attempt 3 of 3, World.rand.nextInt(2000) = 1 < difficulty 3' in plan
    assert 'Tick #82; list index 199; chunk (468, 560) PORTAL' in plan
    assert 'Grid type: scheduled repeater' in plan
    assert 'complete route' in plan
    assert (output / 'autosave-detector.schematic').is_file()
    tile_grid = read_nbt((output / gui.PORTAL_GRID_NAME).read_bytes())
    grid_blocks = tile_grid['Blocks'][1]
    assert (tile_grid['Width'][1], tile_grid['Height'][1], tile_grid['Length'][1]) == (720, 7, 512)
    assert grid_blocks.count(93) + grid_blocks.count(94) == 1027
    assert not any(block in grid_blocks for block in (1, 17, 18, 31, 37, 57, 77, 137, 154, 158, 161, 162, 175))
    assert all(block == 0 for i, block in enumerate(grid_blocks) if i % 720 < 202)
    assert all(meta == 11 for block, meta in zip(grid_blocks, tile_grid['Data'][1]) if block == 159)
    portal = read_nbt((output / gui.PORTAL_NAME).read_bytes())
    blocks = portal['Blocks'][1]
    assert blocks.count(90) == 4096 and blocks.count(1) == 0
    assert blocks.count(174) == 288 and blocks.count(8) == 288
    assert (portal['Width'][1], portal['Height'][1], portal['Length'][1]) == (18,37,20)
    assert all(blocks[(19 * 20 + z) * 18 + x] == 0 for z in range(18) for x in range(18))
    assert 'sliced final-state blueprint' in plan
    assert 'platform Y + 1.1' in plan
    assert 'receiving floor y=60' in plan
    shifted = gui._shift_plan_y(plan,32)
    assert 'north packed-ice floor y=96; middle packed-ice floor y=95; south packed-ice floor y=94; dry receiving floor y=92' in shifted
    assert tile_grid['TileEntities'][1][1][0]['id'] == (8, 'minecraft:comparator')
    assert 'Modeled advances:' not in plan
    assert 'TICK MODEL BUILD CONDITIONS' in plan
    assert subprocess.run(args + ['--exact-advances'], capture_output=True).returncode != 0

    values = dict(seed='12345', difficulty='3', x='0', z='0', radius='25', advances='0', view='10')
    def check_desktop(values, command, interactive_input, assemble, shifts):
        assert max(shifts) + 96 < 256, 'Portal top frame must remain inside the 1.12 build height'
        flags = command(str(output), 0)
        assert '--portal-tick-model' in flags and '--exact-advances' not in flags
        data, combined = assemble(output, 32)
        assert data
        assert 'Autosave detector component within combined schematic: included in combined schematic' in combined
        assert 'Suggested player position: 7512.5, 98, 8968.5' in combined
        assert 'Tile-grid input repeater: 7674, 97, 8980' in combined
        assert 'Tick #82; list index 199; chunk (468, 560) PORTAL' in combined
        return data, combined
    with patch.object(gui, '_search_with_terrain', side_effect=check_desktop):
        gui.calculate_portal(values)

    negative = Path(directory) / 'negative'
    negative_args = args.copy()
    negative_args[4:6] = ['-10000', '-10000']
    negative_args[9] = str(negative)
    subprocess.run(negative_args, check=True, capture_output=True)
    negative_plan = (negative / gui.PLAN_NAME).read_text()
    data, combined = combine((negative / gui.PORTAL_GRID_NAME).read_bytes(), negative_plan,
                             (negative / gui.PORTAL_NAME).read_bytes(), 'Portal-array schematic:')
    root = read_nbt(data)
    player = tuple(math.floor(float(v)) for v in re.search(
        r'Suggested player position: ([\d.-]+), ([\d.-]+), ([\d.-]+)', combined).groups())
    corner = tuple(map(int, re.search(r'Combined schematic minimum corner: (-?\d+), (-?\d+), (-?\d+)', combined).groups()))
    x, y, z = (player[i] - corner[i] for i in range(3))
    width, depth = root['Width'][1], root['Length'][1]
    assert player[0] < 0 and player[2] < 0
    assert root['Blocks'][1][((y - 1) * depth + z) * width + x] == 251
    assert root['Data'][1][((y - 1) * depth + z) * width + x] == 3

    cp = _classpath()
    subprocess.run(['javac', '-proc:none', '-cp', cp, '-d', directory,
                    str(Path(__file__).with_name('PortalTickProbe.java'))], check=True, capture_output=True)
    result = subprocess.run(['java', '-cp', directory + os.pathsep + cp, 'PortalTickProbe'],
                            check=True, capture_output=True, text=True, timeout=60)
    assert 'Pinned Minecraft tick pipeline: [1723, 1572, 1]' in result.stdout

print('Derived portal sequence, desktop export and pinned Minecraft tick methods verified')
