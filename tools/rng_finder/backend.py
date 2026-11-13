"""Headless calculation and assembly shared by both desktop frontends."""
import os
import re
import subprocess
import tempfile
from pathlib import Path
from combine import combine, read_nbt
from terrain_scan import mark_structures, scan as scan_terrain

TOOL_DIR = Path(__file__).resolve().parent
BINARY = TOOL_DIR / 'target' / 'release' / ('rng-finder.exe' if os.name == 'nt' else 'rng-finder')
GRID_NAME = 'xcom-original-grid.schematic'
PORTAL_GRID_NAME = 'tile-tick-grid.schematic'
PLAN_NAME = 'rng-finder-plan.txt'
COMBINED_NAME = 'rng-combined.schematic'
VILLAGE_NAME = 'golem-village.schematic'
PORTAL_NAME = 'portal-platform.schematic'


def _shift_plan_y(plan, shift):
    if not shift:
        return plan
    prefixes = ('Suggested mining/player position:', 'Suggested player position:',
                'Player position:', 'Suggested village center:', 'Modeled first golem spawn block:',
                'Placement minimum corner', 'Village schematic minimum corner:',
                'Tile-grid input block:', 'Tile-grid input repeater:',
                'Autosave detector approximate bounds:')
    coords = re.compile(r'(-?\d+(?:\.5)?),\s*(-?\d+),\s*(-?\d+(?:\.5)?)')
    lines = []
    for line in plan.splitlines(keepends=True):
        if line.startswith(prefixes):
            label, separator, value = line.partition(':')
            line = label + separator + coords.sub(lambda m: f'{m[1]}, {int(m[2]) + shift}, {m[3]}', value)
        elif line.startswith('Platform: y=64; portal blocks: y=80..95'):
            line = line.replace('obsidian top frame y=96;', f'obsidian top frame y={96 + shift};')
            line = line.replace('Platform: y=64; portal blocks: y=80..95; obsidian frame y=79,96',
                                f'Platform: y={64 + shift}; portal blocks: y={80 + shift}..{95 + shift}; obsidian frame y={79 + shift},{96 + shift}')
            line = line.replace('Platform: y=64; portal blocks: y=80..95;', f'Platform: y={64 + shift}; portal blocks: y={80 + shift}..{95 + shift};')
        elif line.startswith('Water transport:'):
            line = re.sub(r'y=(\d+)', lambda m: f'y={int(m[1]) + shift}', line)
        elif line.startswith('Portal array:'):
            line = re.sub(r'y=(\d+)\.\.(\d+)', lambda m: f'y={int(m[1]) + shift}..{int(m[2]) + shift}', line)
        lines.append(line)
    return f'Vertical placement shift: +{shift} blocks from the modeled baseline.\n\n' + ''.join(lines)


def _search_with_terrain(values, command, interactive_input, assemble, shifts=(0,)):
    progress = values.get("_progress", lambda _: None)
    if not BINARY.is_file():
        raise RuntimeError('Build the Rust finder first; see the README for the build command.')
    if any((TOOL_DIR / name).stat().st_mtime > BINARY.stat().st_mtime for name in ('src/main.rs', 'Cargo.toml', 'reference/xcom-shared-detector-grid.schematic', 'reference/command-autosave-detector-1.12.schematic')):
        raise RuntimeError('The Rust finder is out of date. Rebuild it using the command in the README.')
    first = int(values.get('skip', 0))
    rejected = []
    with tempfile.TemporaryDirectory(prefix='rng-finder-') as temp:
        for candidate_index in range(first, first + 64):
            output = Path(temp) / f'output-{candidate_index}'
            args = command(str(output), candidate_index)
            progress(f"Calculating candidate {candidate_index + 1}…")
            result = subprocess.run(args, input=interactive_input(str(output)), text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=120)
            if result.returncode:
                reason = result.stderr.strip() or result.stdout.strip() or 'Search failed.'
                if '--auto-height' in args and 'Shared detector export failed:' in reason and any(message in reason for message in ('Generated component at', 'Schematic components overlap', 'Height control:', 'Combined schematic exceeds')):
                    rejected.append(f'Candidate {candidate_index+1}: {reason}')
                    continue
                if rejected:
                    reason = 'No usable RNG match remains in the selected search radius.\n' + f'{len(rejected)} earlier placement(s) were rejected; latest checks:\n' + '\n'.join(rejected[-3:])
                raise RuntimeError(reason)
            if values.get('exclude_region'):
                raw_plan = (output / PLAN_NAME).read_text(encoding='utf-8')
                region = re.search(r'Mansion region:\s*(-?\d+),\s*(-?\d+)', raw_plan)
                if region and values['exclude_region'] == region.groups():
                    continue
            for shift in shifts:
                try:
                    data, plan = assemble(output, shift)
                except ValueError as error:
                    if str(error).startswith(('Player is above the startup piston', 'Player height leaves too little room', 'Height control', 'Generated component at', 'Schematic components overlap', 'Combined schematic exceeds')):
                        rejected.append(f'Candidate {candidate_index + 1}, Y shift {shift}: {error}')
                        continue
                    raise
                progress(f"Checking terrain for candidate {candidate_index + 1}…")
                clear, report = scan_terrain(data, plan)
                if clear:
                    data = mark_structures(data, report)
                    if rejected:
                        report += f'\nRejected {len(rejected)} earlier geometry/terrain placements; retained candidate {candidate_index+1} without changing its RNG bound.'
                    plan = f'{report}\nTerrain candidate index: {candidate_index}\n\n' + plan
                    return data, plan
                rejected.append(f'Candidate {candidate_index + 1}, Y shift {shift}: {report}')
    heights = f' Tried grid base heights {64 + shifts[0]} through {64 + shifts[-1]}.' if len(shifts) > 1 else ''
    raise RuntimeError(f'No collision-free candidate found among 64 modeled locations.{heights} Latest checks:\n' + '\n'.join(rejected[-3:]))


def calculate(values):
    def command(output, skip):
        return [str(BINARY), '--auto-height', '--view-distance', values['view'], '--players-min', values['players_min'], '--players-max', values['players_max'], '--skip-candidates', str(skip)]
    def interactive_input(output):
        return '\n'.join([values['seed'], values['mob'], values['x'], values['z'], values['radius'], values['bound'], output, ''])
    def assemble(output, shift):
        grid = (output / GRID_NAME).read_bytes()
        plan = (output / PLAN_NAME).read_text(encoding='utf-8').replace(f'Grid schematic: {output / GRID_NAME}', f'Grid schematic: {GRID_NAME}')
        return combine(grid, plan)
    return _search_with_terrain(values, command, interactive_input, assemble)


def calculate_fortune(values):
    def command(output, skip):
        return [str(BINARY), '--fortune'] + [values[key] for key in ('seed', 'ore', 'level', 'target', 'x', 'z', 'radius', 'advances', 'view')] + [output, '--skip-candidates', str(skip)]
    def assemble(output, shift):
        grid = (output / GRID_NAME).read_bytes()
        plan = (output / PLAN_NAME).read_text(encoding='utf-8').replace(f'Grid schematic: {output / GRID_NAME}', f'Grid schematic: {GRID_NAME}')
        return combine(grid, _shift_plan_y(plan, shift))
    return _search_with_terrain(values, command, lambda _: '', assemble, range(0, 161, 32))


def calculate_portal(values):
    if values.get('world'):
        from rng_cleanup import SavedWorld
        SavedWorld(values['world'])
    def command(output, skip):
        exact = ['--exact-advances'] if values.get('exact', False) else ['--portal-tick-model']
        return [str(BINARY), '--portal'] + [values[key] for key in ('seed', 'difficulty', 'x', 'z', 'radius', 'advances', 'view')] + [output, '--skip-candidates', str(skip)] + exact + ['--portal-successes', values.get('successes', '1/3').split('/')[0]]
    def assemble(output, shift):
        grid_name = GRID_NAME if values.get('exact', False) else PORTAL_GRID_NAME
        grid = (output / grid_name).read_bytes()
        portal = (output / PORTAL_NAME).read_bytes()
        plan = (output / PLAN_NAME).read_text(encoding='utf-8').replace(f'Grid schematic: {output / grid_name}', f'Grid schematic: {grid_name}').replace(f'Portal-array schematic: {output / PORTAL_NAME}', f'Portal-array schematic: {PORTAL_NAME}').replace(f'Autosave detector schematic: {output / "autosave-detector.schematic"}', 'Autosave detector schematic: autosave-detector.schematic')
        return combine(grid, _shift_plan_y(plan, shift), portal, 'Portal-array schematic:')
    result = _search_with_terrain(values, command, lambda _: '', assemble, range(0, 129, 32))
    if values.get('world'):
        from rng_cleanup import mark_cleanup
        values.get("_progress", lambda _: None)("Scanning saved-world cleanup replacements…")
        return mark_cleanup(*result, values['world'])
    return result[0], 'RNG cleanup markers were not generated. Select a saved Overworld in the gold tab to include red-concrete replacement blocks.\n\n' + result[1]


def calculate_golem(values):
    def command(output, skip):
        return [str(BINARY), '--golem'] + [values[key] for key in ('seed', 'x', 'z', 'radius', 'view')] + [output, '--skip-candidates', str(skip)]
    def assemble(output, shift):
        grid = (output / GRID_NAME).read_bytes()
        village = (output / VILLAGE_NAME).read_bytes()
        plan = (output / PLAN_NAME).read_text(encoding='utf-8').replace(f'Grid schematic: {output / GRID_NAME}', f'Grid schematic: {GRID_NAME}').replace(f'Village schematic: {output / VILLAGE_NAME}', f'Village schematic: {VILLAGE_NAME}')
        return combine(grid, _shift_plan_y(plan, shift), village, 'Village schematic:')
    return _search_with_terrain(values, command, lambda _: '', assemble, range(0, 161, 32))
