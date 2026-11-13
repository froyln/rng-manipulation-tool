#!/usr/bin/env python3
"""One JSON request on stdin; JSON-line progress/result events on stdout.

Local trusted desktop protocol. Calculations remain in backend.py; no Tk imports.
"""
import contextlib
import json
import re
import signal
import sys
from pathlib import Path

import backend


PROTOCOL = sys.stdout


class InputError(ValueError):
    def __init__(self, field, message):
        super().__init__(message)
        self.field = field


class Cancelled(BaseException):
    pass


def emit(kind, **fields):
    print(json.dumps(dict(kind=kind, **fields)), file=PROTOCOL, flush=True)


def validate(mode, values):
    if mode not in ('Mob', 'Fortune', 'Iron', 'Gold'):
        raise ValueError('Choose Mob, Fortune, Iron or Gold.')
    values = dict(values)
    seed = values.get('seed', '').strip()
    if not seed or '\n' in seed or '\r' in seed:
        raise InputError('seed', 'Enter a world creation seed on one line.')
    values['seed'] = seed
    limits = {'x': (-29_000_000, 29_000_000), 'z': (-29_000_000, 29_000_000),
              'radius': (0, 128), 'view': (3, 32), 'skip': (0, 1_000_000)}
    if mode == 'Mob':
        limits.update(bound=(16, 256), players_min=(1, 100), players_max=(1, 100))
        if values.get('mob') not in ('witch', 'creeper', 'skeleton', 'zombie', 'spider', 'enderman'):
            raise InputError('mob', 'Choose a supported mob.')
    if mode == 'Fortune':
        limits.update(level=(0, 3), target=(1, 32), advances=(0, 1000))
        if values.get('ore') not in ('diamond', 'coal', 'emerald', 'quartz', 'lapis', 'redstone'):
            raise InputError('ore', 'Choose a supported ore.')
    if mode == 'Gold':
        limits.update(difficulty=(1, 3), advances=(0, 1000))
        if values.get('successes') not in ('1/3', '2/3', '3/3'):
            raise InputError('successes', 'Choose 1/3, 2/3 or 3/3 passing checks.')
        if not isinstance(values.get('exact', False), bool):
            raise ValueError('Trace mode must be true or false.')
        if not values.get('exact', False):
            values['advances'] = '0'
    for key, (low, high) in limits.items():
        try:
            number = int(values.get(key, '0' if key == 'skip' else ''))
        except (ValueError, TypeError):
            raise InputError(key, f'{key}: enter a whole number.') from None
        if not low <= number <= high:
            raise InputError(key, f'{key} must be {low}–{high}.')
        values[key] = str(number)
    if mode == 'Mob' and (int(values['bound']) % 16 or int(values['players_min']) > int(values['players_max'])):
        raise InputError('bound' if int(values['bound']) % 16 else 'players_min', 'Y bound must be a multiple of 16; minimum players must not exceed maximum.')
    if values.get("exclude_region"):
        values["exclude_region"] = tuple(values["exclude_region"])
    return values


def summary(plan):
    """Adapt the existing machine-generated plan at the legacy backend boundary.

    UI receives named coordinate fields, never parses displayed labels itself.
    Raw plan remains authoritative; omit unrecognized fields instead of guessing.
    """
    coordinates = []
    patterns = [
        ('Placement minimum', r'^Combined schematic minimum corner:\s*([^\n]+)'),
        ('Player / AFK', r'^(?:Suggested mining/player position|Suggested player position|Player position):\s*([^\n]+)'),
        ('Village center', r'^Suggested village center:\s*([^\n]+)'),
        ('First golem spawn', r'^Modeled first golem spawn block:\s*([^\n]+)'),
    ]
    for label, pattern in patterns:
        match = re.search(pattern, plan, re.M)
        if match:
            xyz = re.match(r'(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)', match[1])
            if xyz:
                coordinates.append(dict(label=label, xyz=list(xyz.groups())))
    region = re.search(r'^Mansion region:\s*(-?\d+),\s*(-?\d+)', plan, re.M)
    index = re.search(r'^Terrain candidate index: (\d+)', plan, re.M)
    requirements = [line for line in plan.splitlines() if line.startswith((
        'Mob roof', 'Roof ', 'Villager design:', 'Water transport:', 'RNG RED REPLACEMENTS:',
        'RNG cleanup markers were not', 'Startup:', 'Start interaction:', 'Nether portal',
        'Required ', 'Clear ', 'Height control', 'Placement:', 'Leave the single AFK lever',
        'Suggested Nether portal search center:'))]
    return dict(coordinates=coordinates, region=list(region.groups()) if region else [],
                index=int(index[1]) if index else 0, requirements=requirements)


def export_files(source, destination):
    source, destination = Path(source), Path(destination)
    # Exactly the artifact pair from a completed search, with exclusive creation.
    names = [name for name in ('rng-combined.litematic', 'rng-combined.schematic') if (source / name).is_file()]
    if len(names) != 1 or not (source / backend.PLAN_NAME).is_file():
        raise ValueError('Completed candidate files are missing. Find the candidate again.')
    created = []
    try:
        for name in names + [backend.PLAN_NAME]:
            path = destination / name
            with path.open('xb') as output:
                created.append(path)
                output.write((source / name).read_bytes())
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return [str(destination / name) for name in names + [backend.PLAN_NAME]]


def run(request):
    action = request['action']
    if action == 'world':
        from rng_cleanup import SavedWorld
        world = SavedWorld(request['path'])
        return dict(kind='world', path=str(world.path), seed=str(world.seed))
    if action == 'export':
        return dict(kind='exported', paths=export_files(request['source'], request['destination']))
    if action != 'search':
        raise ValueError('Unknown desktop action.')
    mode = request['mode']
    values = validate(mode, request['values'])
    values['_progress'] = lambda stage: emit('progress', stage=stage)
    functions = dict(Mob=backend.calculate, Fortune=backend.calculate_fortune,
                     Iron=backend.calculate_golem, Gold=backend.calculate_portal)
    emit('progress', stage='Calculating candidate…')
    with contextlib.redirect_stdout(sys.stderr):
        data, plan = functions[mode](values)
    emit('progress', stage='Preparing schematic and plan…')
    directory = Path(request['output'])
    directory.mkdir(parents=True, exist_ok=False)
    native = 'Regions' in backend.read_nbt(data, root_name=None)
    name = 'rng-combined.litematic' if native else backend.COMBINED_NAME
    (directory / name).write_bytes(data)
    (directory / backend.PLAN_NAME).write_text(plan, encoding='utf-8')
    return dict(kind='result', plan=plan, **summary(plan))


def main():
    def cancel(*_):
        raise Cancelled()
    signal.signal(signal.SIGTERM, cancel)
    try:
        emit_result = run(json.load(sys.stdin))
        print(json.dumps(emit_result), flush=True)
    except Cancelled:
        emit('cancelled')
    except Exception as error:
        emit('error', message=str(error), field=getattr(error, 'field', None))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
