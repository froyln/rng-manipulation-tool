#!/usr/bin/env python3
"""Desktop interface for the experimental Rust world-RNG finder."""
import os
import queue
import re
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
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
    if not BINARY.is_file():
        raise RuntimeError('Build the Rust finder first; see the README for the build command.')
    if any((TOOL_DIR / name).stat().st_mtime > BINARY.stat().st_mtime for name in ('src/main.rs', 'Cargo.toml')):
        raise RuntimeError('The Rust finder is out of date. Rebuild it using the command in the README.')
    first = int(values.get('skip', 0))
    rejected = []
    with tempfile.TemporaryDirectory(prefix='rng-finder-') as temp:
        for candidate_index in range(first, first + 64):
            output = Path(temp) / f'output-{candidate_index}'
            args = command(str(output), candidate_index)
            result = subprocess.run(args, input=interactive_input(str(output)), text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=120)
            if result.returncode:
                reason = result.stderr.strip() or result.stdout.strip() or 'Search failed.'
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
                clear, report = scan_terrain(data, plan)
                if clear:
                    data = mark_structures(data, report)
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


class FinderApp:
    def __init__(self, root):
        self.root = root
        root.title('Minecraft 1.12.2 World RNG Finder — single combined Litematic')
        root.geometry('920x800')
        root.minsize(640, 560)
        self.values = {}
        self.input_widgets = {}
        self.result = None
        self.messages = queue.Queue()
        tabs = ttk.Notebook(root)
        self.tabs = tabs
        tabs.pack(fill='both', expand=True)
        frame = ttk.Frame(tabs, padding=18)
        tabs.add(frame, text='Mob RNG')
        ttk.Label(frame, text='World RNG Finder', font=('TkDefaultFont', 18, 'bold')).grid(row=0, column=0, columnspan=4, sticky='w')
        ttk.Label(frame, text='Minecraft Java 1.12.2 · Experimental spawn and loading-grid planner').grid(row=1, column=0, columnspan=4, sticky='w', pady=(0, 12))
        fields = [
            ('World creation seed', 'seed', '', 2, 0),
            ('Mob', 'mob', 'witch', 2, 2),
            ('Search near block X', 'x', '0', 3, 0),
            ('Search near block Z', 'z', '0', 3, 2),
            ('Search radius (80-chunk regions)', 'radius', '25', 4, 0),
            ('Minimum random Y bound', 'bound', '64', 4, 2),
            ('Server view distance (chunks)', 'view', '10', 5, 0),
            ('Minimum players (stacked)', 'players_min', '1', 5, 2),
            ('Maximum players (stacked)', 'players_max', '1', 6, 0),
        ]
        for label, key, default, row, col in fields:
            ttk.Label(frame, text=label).grid(row=row * 2, column=col, sticky='w', pady=(8, 2))
            var = tk.StringVar(value=default)
            self.values[key] = var
            if key == 'mob':
                widget = ttk.Combobox(frame, textvariable=var, state='readonly', values=('witch', 'creeper', 'skeleton', 'zombie', 'spider', 'enderman'))
            else:
                widget = ttk.Entry(frame, textvariable=var)
            self.input_widgets[key] = widget
            widget.grid(row=row * 2 + 1, column=col, columnspan=2, sticky='ew', padx=(0, 16))
        ttk.Label(frame, text='Searches height bounds from this minimum to 256. The schematic includes a control block above the initial random column; verify the heightmap in game.', wraplength=800).grid(row=14, column=0, columnspan=4, sticky='w', pady=(12, 4))
        ttk.Label(frame, text='Base terrain blocks and structure bounds are scanned. Population features and chunk history are not. The schematic includes an unverified startup line; the grid cycle is unverified.', foreground='#8b3e00', wraplength=800).grid(row=15, column=0, columnspan=4, sticky='w', pady=(0, 10))
        buttons = ttk.Frame(frame)
        buttons.grid(row=16, column=0, columnspan=4, sticky='ew')
        self.search_button = ttk.Button(buttons, text='Find candidate', command=self.search)
        self.search_button.pack(side='left')
        self.current_index = -1
        self.next_button = ttk.Button(buttons, text='Next location', command=lambda: self.search(True), state='disabled')
        self.next_button.pack(side='left', padx=4)
        self.export_button = ttk.Button(buttons, text='Save schematic and plan…', command=self.export, state='disabled')
        self.export_button.pack(side='left', padx=8)
        self.status = tk.StringVar(value='Enter a world seed to begin.')
        ttk.Label(buttons, textvariable=self.status).pack(side='left', padx=8)
        ttk.Label(frame, text='Result', font=('TkDefaultFont', 11, 'bold')).grid(row=17, column=0, columnspan=4, sticky='w', pady=(14, 4))
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=18, column=0, columnspan=4, sticky='nsew')
        self.output = tk.Text(output_frame, wrap='word', height=12, state='disabled', font=('TkFixedFont', 10))
        scroll = ttk.Scrollbar(output_frame, command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.output.pack(side='left', fill='both', expand=True)
        for col in (0, 1, 2, 3):
            frame.columnconfigure(col, weight=1)
        frame.rowconfigure(18, weight=1)
        for var in self.values.values():
            var.trace_add('write', self.invalidate)
        root.after(100, self.poll)
        self.fortune_tab = FortuneTab(tabs)
        self.golem_tab = GolemTab(tabs)
        self.portal_tab = PortalTab(tabs)

    def invalidate(self, *_):
        if self.result is not None:
            self.result = None
            self.export_button.config(state='disabled')
            self.next_button.config(state='disabled')
            self.current_index = -1
            self.output.config(state='normal')
            self.output.delete('1.0', 'end')
            self.output.config(state='disabled')
            self.status.set('Settings changed; search again.')

    def search(self, next_candidate=False):
        values = {key: var.get().strip() for key, var in self.values.items()}
        try:
            if not values['seed']:
                raise ValueError('Enter a world creation seed.')
            if '\n' in values['seed'] or '\r' in values['seed']:
                raise ValueError('The seed must fit on one line.')
            x, z, radius, bound, view, players_min, players_max = (int(values[key]) for key in ('x', 'z', 'radius', 'bound', 'view', 'players_min', 'players_max'))
            if abs(x) > 29_000_000 or abs(z) > 29_000_000:
                raise ValueError('The search center is too close to the world border.')
            if not 0 <= radius <= 128:
                raise ValueError('The search radius must be between 0 and 128 regions.')
            if not 16 <= bound <= 256 or bound % 16:
                raise ValueError('The Y bound must be a multiple of 16 between 16 and 256.')
            if not 3 <= view <= 32:
                raise ValueError('The server view distance must be between 3 and 32 chunks.')
            if not 1 <= players_min <= players_max <= 100:
                raise ValueError('The player range must be within 1 to 100, with minimum no greater than maximum.')
            for key, number in zip(('x', 'z', 'radius', 'bound', 'view', 'players_min', 'players_max'), (x, z, radius, bound, view, players_min, players_max)):
                values[key] = str(number)
        except ValueError as error:
            messagebox.showerror('Invalid input', str(error), parent=self.root)
            return
        self.pending_index = self.current_index + 1 if next_candidate else 0
        values['skip'] = self.pending_index
        if next_candidate and self.result:
            region = re.search(r'Mansion region:\s*(-?\d+),\s*(-?\d+)', self.result[1])
            if region:
                values['exclude_region'] = region.groups()
        self.search_button.config(state='disabled')
        self.next_button.config(state='disabled')
        self.export_button.config(state='disabled')
        for widget in self.input_widgets.values():
            widget.config(state='disabled')
        self.output.config(state='normal')
        self.output.delete('1.0', 'end')
        self.output.config(state='disabled')
        self.status.set('Searching and scanning seed terrain…')
        def work():
            try:
                self.messages.put(('ok', calculate(values)))
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                self.messages.put(('error', str(error)))
            except RuntimeError as error:
                self.messages.put(('error', str(error)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            kind, data = self.messages.get_nowait()
            self.search_button.config(state='normal')
            for key, widget in self.input_widgets.items():
                widget.config(state='readonly' if key in ('mob', 'ore', 'successes') else 'normal')
            if kind == 'ok':
                self.result = data
                terrain_index = re.search(r'Terrain candidate index: (\d+)', data[1])
                self.current_index = int(terrain_index.group(1)) if terrain_index else self.pending_index
                self.next_button.config(state='normal')
                self.output.config(state='normal')
                self.output.delete('1.0', 'end')
                self.output.insert('1.0', data[1])
                self.output.config(state='disabled')
                self.export_button.config(state='normal')
                cleanup = re.search(r'RNG RED REPLACEMENTS: (\d+)', data[1])
                self.status.set(f'Candidate {self.current_index + 1}: {cleanup[1]} red-concrete replacement blocks.' if cleanup else f'Candidate {self.current_index + 1}: experimental control boundary.')
            else:
                self.status.set('No further candidate found.' if self.result else 'Search failed.')
                if self.result is not None:
                    self.export_button.config(state='normal')
                    self.next_button.config(state='normal')
                    self.output.config(state='normal')
                    self.output.delete('1.0', 'end')
                    self.output.insert('1.0', self.result[1])
                    self.output.config(state='disabled')
                messagebox.showerror('Search failed', data, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def export(self):
        if self.result is None:
            return
        directory = filedialog.askdirectory(title='Save schematic and plan in a directory', parent=self.root)
        if not directory:
            return
        created = []
        try:
            native = 'Regions' in read_nbt(self.result[0], root_name=None)
            name = 'rng-combined.litematic' if native else COMBINED_NAME
            files = [(name, self.result[0]), (PLAN_NAME, self.result[1].encode('utf-8'))]
            for name, data in files:
                path = Path(directory) / name
                with path.open('xb') as file:
                    created.append(path)
                    file.write(data)
        except OSError as error:
            for path in created:
                try:
                    path.unlink()
                except OSError:
                    pass
            messagebox.showerror('Could not save', f'{error}\nChoose a directory without existing output files.', parent=self.root)
            return
        self.status.set('Schematics and plan saved.')
        messagebox.showinfo('Saved', f'Saved {", ".join(name for name, _ in files)} in:\n{directory}', parent=self.root)


class GolemTab(FinderApp):
    def __init__(self, tabs):
        self.root = tabs.winfo_toplevel()
        self.values, self.input_widgets, self.result = {}, {}, None
        self.messages = queue.Queue()
        frame = ttk.Frame(tabs, padding=18)
        tabs.add(frame, text='Iron golems')
        ttk.Label(frame, text='Iron golem finder', font=('TkDefaultFont', 18, 'bold')).grid(row=0, column=0, columnspan=4, sticky='w')
        ttk.Label(frame, text='Minecraft Java 1.12.2 · Experimental single-player village RNG model').grid(row=1, column=0, columnspan=4, sticky='w', pady=(0, 12))
        fields = [
            ('World creation seed', 'seed', ''), ('Server view distance (chunks)', 'view', '10'),
            ('Search near block X', 'x', '0'), ('Search near block Z', 'z', '0'),
            ('Search radius (80-chunk regions)', 'radius', '128'),
        ]
        for index, (label, key, default) in enumerate(fields):
            row, col = 2 + (index // 2) * 2, (index % 2) * 2
            ttk.Label(frame, text=label).grid(row=row, column=col, sticky='w', pady=(7, 2))
            var = tk.StringVar(value=default)
            self.values[key] = var
            widget = ttk.Entry(frame, textvariable=var)
            self.input_widgets[key] = widget
            widget.grid(row=row + 1, column=col, columnspan=2, sticky='ew', padx=(0, 16))
        ttk.Label(frame, text='300 counted villagers support a 30-golem cache threshold; the plan includes 300 adults in separate cells. Keep one village, 21+ valid doors, and villagers inside its count bounds. Use doMobSpawning=false, randomTickSpeed=0, and clear weather. RNG timing and portal transfer remain unverified.', foreground='#8b3e00', wraplength=800).grid(row=8, column=0, columnspan=4, sticky='w', pady=(12, 8))
        buttons = ttk.Frame(frame)
        buttons.grid(row=9, column=0, columnspan=4, sticky='ew')
        self.search_button = ttk.Button(buttons, text='Find golem candidate', command=self.search)
        self.search_button.pack(side='left')
        self.current_index = -1
        self.next_button = ttk.Button(buttons, text='Next location', command=lambda: self.search(True), state='disabled')
        self.next_button.pack(side='left', padx=4)
        self.export_button = ttk.Button(buttons, text='Save schematic and plan…', command=self.export, state='disabled')
        self.export_button.pack(side='left', padx=8)
        self.status = tk.StringVar(value='Enter a world seed to begin.')
        ttk.Label(buttons, textvariable=self.status).pack(side='left', padx=8)
        ttk.Label(frame, text='Result', font=('TkDefaultFont', 11, 'bold')).grid(row=10, column=0, columnspan=4, sticky='w', pady=(14, 4))
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=11, column=0, columnspan=4, sticky='nsew')
        self.output = tk.Text(output_frame, wrap='word', height=10, state='disabled', font=('TkFixedFont', 10))
        scroll = ttk.Scrollbar(output_frame, command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.output.pack(side='left', fill='both', expand=True)
        for col in range(4):
            frame.columnconfigure(col, weight=1)
        frame.rowconfigure(11, weight=1)
        for var in self.values.values():
            var.trace_add('write', self.invalidate)
        self.root.after(100, self.poll)

    def search(self, next_candidate=False):
        values = {key: var.get().strip() for key, var in self.values.items()}
        try:
            if not values['seed'] or '\n' in values['seed'] or '\r' in values['seed']:
                raise ValueError('Enter a world creation seed on one line.')
            keys = ('x', 'z', 'radius', 'view')
            x, z, radius, view = (int(values[key]) for key in keys)
            if abs(x) > 29_000_000 or abs(z) > 29_000_000 or not 0 <= radius <= 128:
                raise ValueError('Search coordinates or radius are outside the supported range.')
            if not 3 <= view <= 32:
                raise ValueError('Server view distance must be 3–32.')
            for key, number in zip(keys, (x, z, radius, view)):
                values[key] = str(number)
        except ValueError as error:
            messagebox.showerror('Invalid input', str(error), parent=self.root)
            return
        self.pending_index = self.current_index + 1 if next_candidate else 0
        values['skip'] = self.pending_index
        self.search_button.config(state='disabled')
        self.next_button.config(state='disabled')
        self.export_button.config(state='disabled')
        for widget in self.input_widgets.values():
            widget.config(state='disabled')
        self.output.config(state='normal')
        self.output.delete('1.0', 'end')
        self.output.config(state='disabled')
        self.status.set('Searching and scanning seed terrain…')
        def work():
            try:
                self.messages.put(('ok', calculate_golem(values)))
            except (OSError, ValueError, subprocess.TimeoutExpired, RuntimeError) as error:
                self.messages.put(('error', str(error)))
        threading.Thread(target=work, daemon=True).start()


class FortuneTab(FinderApp):
    def __init__(self, tabs):
        self.root = tabs.winfo_toplevel()
        self.values, self.input_widgets, self.result = {}, {}, None
        self.messages = queue.Queue()
        frame = ttk.Frame(tabs, padding=18)
        tabs.add(frame, text='Fortune drops')
        ttk.Label(frame, text='Fortune drop finder', font=('TkDefaultFont', 18, 'bold')).grid(row=0, column=0, columnspan=4, sticky='w')
        ttk.Label(frame, text='Minecraft Java 1.12.2 · Experimental Overworld RNG model').grid(row=1, column=0, columnspan=4, sticky='w', pady=(0, 12))
        fields = [
            ('World creation seed', 'seed', ''), ('Ore', 'ore', 'diamond'),
            ('Fortune level (0–3)', 'level', '3'), ('Minimum items per ore', 'target', '4'),
            ('Search near block X', 'x', '0'), ('Search near block Z', 'z', '0'),
            ('Maximum RNG advances', 'advances', '0'),
            ('Server view distance (chunks)', 'view', '10'),
        ]
        for index, (label, key, default) in enumerate(fields):
            row, col = 2 + (index // 2) * 2, (index % 2) * 2
            ttk.Label(frame, text=label).grid(row=row, column=col, sticky='w', pady=(7, 2))
            var = tk.StringVar(value=default)
            self.values[key] = var
            widget = (ttk.Combobox(frame, textvariable=var, state='readonly', values=('diamond', 'coal', 'emerald', 'quartz', 'lapis', 'redstone')) if key == 'ore' else ttk.Entry(frame, textvariable=var))
            self.input_widgets[key] = widget
            widget.grid(row=row + 1, column=col, columnspan=2, sticky='ew', padx=(0, 16))
        ttk.Label(frame, text='One ore per reset. The grid, advances, and exact mining timing need in-game validation. Redstone activation consumes RNG; quartz must be mined in the Overworld.', foreground='#8b3e00', wraplength=800).grid(row=12, column=0, columnspan=4, sticky='w', pady=(12, 8))
        buttons = ttk.Frame(frame)
        buttons.grid(row=13, column=0, columnspan=4, sticky='ew')
        self.search_button = ttk.Button(buttons, text='Find Fortune candidate', command=self.search)
        self.search_button.pack(side='left')
        self.current_index = -1
        self.next_button = ttk.Button(buttons, text='Next location', command=lambda: self.search(True), state='disabled')
        self.next_button.pack(side='left', padx=4)
        self.export_button = ttk.Button(buttons, text='Save schematic and plan…', command=self.export, state='disabled')
        self.export_button.pack(side='left', padx=8)
        self.status = tk.StringVar(value='Enter a world seed to begin.')
        ttk.Label(buttons, textvariable=self.status).pack(side='left', padx=8)
        ttk.Label(frame, text='Result', font=('TkDefaultFont', 11, 'bold')).grid(row=14, column=0, columnspan=4, sticky='w', pady=(14, 4))
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=15, column=0, columnspan=4, sticky='nsew')
        self.output = tk.Text(output_frame, wrap='word', height=10, state='disabled', font=('TkFixedFont', 10))
        scroll = ttk.Scrollbar(output_frame, command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.output.pack(side='left', fill='both', expand=True)
        for col in range(4):
            frame.columnconfigure(col, weight=1)
        frame.rowconfigure(15, weight=1)
        for var in self.values.values():
            var.trace_add('write', self.invalidate)
        self.root.after(100, self.poll)

    def search(self, next_candidate=False):
        values = {key: var.get().strip() for key, var in self.values.items()}
        try:
            if not values['seed'] or '\n' in values['seed'] or '\r' in values['seed']:
                raise ValueError('Enter a world creation seed on one line.')
            keys = ('level', 'target', 'x', 'z', 'radius', 'advances', 'view')
            level, target, x, z, radius, advances, view = (int(values[key]) for key in keys)
            if not 0 <= level <= 3 or not 1 <= target <= 32:
                raise ValueError('Fortune level must be 0–3 and minimum items 1–32.')
            if abs(x) > 29_000_000 or abs(z) > 29_000_000 or not 0 <= radius <= 128:
                raise ValueError('Search coordinates or radius are outside the supported range.')
            if not 0 <= advances <= 1000 or not 3 <= view <= 32:
                raise ValueError('Advances must be 0–1000 and server view distance 3–32.')
            for key, number in zip(keys, (level, target, x, z, radius, advances, view)):
                values[key] = str(number)
        except ValueError as error:
            messagebox.showerror('Invalid input', str(error), parent=self.root)
            return
        self.pending_index = self.current_index + 1 if next_candidate else 0
        values['skip'] = self.pending_index
        self.search_button.config(state='disabled')
        self.next_button.config(state='disabled')
        self.export_button.config(state='disabled')
        for widget in self.input_widgets.values():
            widget.config(state='disabled')
        self.output.config(state='normal')
        self.output.delete('1.0', 'end')
        self.output.config(state='disabled')
        self.status.set('Searching and scanning seed terrain…')
        def work():
            try:
                self.messages.put(('ok', calculate_fortune(values)))
            except (OSError, ValueError, subprocess.TimeoutExpired, RuntimeError) as error:
                self.messages.put(('error', str(error)))
        threading.Thread(target=work, daemon=True).start()


class PortalTab(FinderApp):
    def __init__(self, tabs):
        self.root = tabs.winfo_toplevel()
        self.values, self.input_widgets, self.result = {}, {}, None
        self.exact = tk.BooleanVar(value=False)
        self.messages = queue.Queue()
        frame = ttk.Frame(tabs, padding=18)
        tabs.add(frame, text='Gold / portal pigmen')
        ttk.Label(frame, text='Portal pigman RNG finder', font=('TkDefaultFont', 18, 'bold')).grid(row=0, column=0, columnspan=4, sticky='w')
        ttk.Label(frame, text='Minecraft Java 1.12.2 · Experimental Overworld RNG model').grid(row=1, column=0, columnspan=4, sticky='w', pady=(0, 12))
        ttk.Button(frame, text='Open existing Pigman RNG finder…', command=self.open_pigman_finder).grid(row=0, column=2, columnspan=2, sticky='e')
        fields = [
            ('World creation seed', 'seed', ''), ('Difficulty (1 easy, 2 normal, 3 hard)', 'difficulty', '3'),
            ('Search near block X', 'x', '0'), ('Search near block Z', 'z', '0'),
            ('Search radius (80-chunk regions)', 'radius', '25'),
            ('Measured extra RNG calls (trace mode only)', 'advances', '0'),
            ('Server view distance (chunks)', 'view', '10'),
            ('Saved Overworld for red-concrete replacements (optional)', 'world', ''),
            ('Target successful random ticks', 'successes', '1/3'),
        ]
        for index, (label, key, default) in enumerate(fields):
            row, col = 2 + (index // 2) * 2, (index % 2) * 2
            ttk.Label(frame, text=label).grid(row=row, column=col, sticky='w', pady=(7, 2))
            var = tk.StringVar(value=default)
            self.values[key] = var
            holder = ttk.Frame(frame)
            holder.grid(row=row + 1, column=col, columnspan=2, sticky='ew', padx=(0, 16))
            widget = (ttk.Combobox(holder, textvariable=var, state='readonly', values=('1/3', '2/3', '3/3')) if key == 'successes' else ttk.Entry(holder, textvariable=var))
            widget.pack(side='left', fill='x', expand=True)
            self.input_widgets[key] = widget
            if key == 'world':
                browse = ttk.Button(holder, text='Browse…', command=self.choose_world)
                browse.pack(side='left', padx=(4, 0))
                self.input_widgets['world_browse'] = browse
        exact_box = ttk.Checkbutton(frame, text='Trace mode: use measured advances instead of deriving the tick sequence', variable=self.exact)
        exact_box.grid(row=12, column=0, columnspan=4, sticky='w', pady=(8, 0))
        self.input_widgets['exact'] = exact_box
        ttk.Label(frame, text='Select a saved Overworld to export ONE .litematic containing the RNG build and small red-concrete replacement subregions. Each red block is an actual replacement position, not an outline. No world is edited. 2/3 and 3/3 matches are rarer and may need a wider search. Follow the placement origin in the plan.', foreground='#8b3e00', wraplength=800).grid(row=13, column=0, columnspan=4, sticky='w', pady=(12, 8))
        buttons = ttk.Frame(frame)
        buttons.grid(row=14, column=0, columnspan=4, sticky='ew')
        self.search_button = ttk.Button(buttons, text='Find portal candidate', command=self.search)
        self.search_button.pack(side='left')
        self.current_index = -1
        self.next_button = ttk.Button(buttons, text='Next location', command=lambda: self.search(True), state='disabled')
        self.next_button.pack(side='left', padx=4)
        self.export_button = ttk.Button(buttons, text='Save schematic and plan…', command=self.export, state='disabled')
        self.export_button.pack(side='left', padx=8)
        self.status = tk.StringVar(value='Enter a world seed to begin.')
        ttk.Label(buttons, textvariable=self.status).pack(side='left', padx=8)
        ttk.Label(frame, text='Result', font=('TkDefaultFont', 11, 'bold')).grid(row=15, column=0, columnspan=4, sticky='w', pady=(14, 4))
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=16, column=0, columnspan=4, sticky='nsew')
        self.output = tk.Text(output_frame, wrap='word', height=10, state='disabled', font=('TkFixedFont', 10))
        scroll = ttk.Scrollbar(output_frame, command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.output.pack(side='left', fill='both', expand=True)
        for col in range(4):
            frame.columnconfigure(col, weight=1)
        frame.rowconfigure(16, weight=1)
        for var in self.values.values():
            var.trace_add('write', self.invalidate)
        self.exact.trace_add('write', self.invalidate)
        self.root.after(100, self.poll)

    def choose_world(self):
        directory = filedialog.askdirectory(title='Select Overworld save (level.dat and region)', parent=self.root)
        if directory:
            try:
                from rng_cleanup import SavedWorld
                world = SavedWorld(directory)
                self.values['world'].set(str(world.path))
                self.values['seed'].set(str(world.seed))
            except (OSError, ValueError) as error:
                messagebox.showerror('Could not read world', str(error), parent=self.root)

    def open_pigman_finder(self):
        messagebox.showwarning('Old finder ordering limitation', 'RandomFT corrected this on November 9, 2026: the old Chunk Hash Order is for 1.8. Use our generated plan for the conditional fresh-player 1.12.2 tick order. Movement and chunk-list history still need verification.', parent=self.root)
        jar = TOOL_DIR.parent.parent / 'sources' / 'PigmanRNG_1_12' / 'PigmanRNG_1_12.jar'
        try:
            if not jar.is_file():
                raise FileNotFoundError(f'Finder not found: {jar}')
            subprocess.Popen(['java', '-jar', str(jar)], cwd=str(TOOL_DIR))
        except OSError as error:
            messagebox.showerror('Could not open Pigman RNG finder', f'{error}\nInstall Java and check that it is on your PATH.', parent=self.root)

    def search(self, next_candidate=False):
        values = {key: var.get().strip() for key, var in self.values.items()}
        values['exact'] = self.exact.get()
        if not values['exact']:
            values['advances'] = '0'
        try:
            if not values['seed'] or '\n' in values['seed'] or '\r' in values['seed']:
                raise ValueError('Enter a world creation seed on one line.')
            if values['successes'] not in ('1/3', '2/3', '3/3'):
                raise ValueError('Choose 1/3, 2/3 or 3/3 successful random ticks.')
            keys = ('difficulty', 'x', 'z', 'radius', 'advances', 'view')
            difficulty, x, z, radius, advances, view = (int(values[key]) for key in keys)
            if not 1 <= difficulty <= 3:
                raise ValueError('Difficulty must be 1, 2, or 3.')
            if abs(x) > 29_000_000 or abs(z) > 29_000_000 or not 0 <= radius <= 128:
                raise ValueError('Search coordinates or radius are outside the supported range.')
            if not 0 <= advances <= 1000 or not 3 <= view <= 32:
                raise ValueError('Advances must be 0–1000 and server view distance 3–32.')
            for key, number in zip(keys, (difficulty, x, z, radius, advances, view)):
                values[key] = str(number)
        except ValueError as error:
            messagebox.showerror('Invalid input', str(error), parent=self.root)
            return
        self.pending_index = self.current_index + 1 if next_candidate else 0
        values['skip'] = self.pending_index
        self.search_button.config(state='disabled')
        self.next_button.config(state='disabled')
        self.export_button.config(state='disabled')
        for widget in self.input_widgets.values():
            widget.config(state='disabled')
        self.output.config(state='normal')
        self.output.delete('1.0', 'end')
        self.output.config(state='disabled')
        self.status.set('Searching and scanning seed terrain…')
        def work():
            try:
                self.messages.put(('ok', calculate_portal(values)))
            except (OSError, ValueError, subprocess.TimeoutExpired, RuntimeError) as error:
                self.messages.put(('error', str(error)))
        threading.Thread(target=work, daemon=True).start()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', help='Preselect a saved Overworld for gold cleanup markers')
    args = parser.parse_args()
    window = tk.Tk()
    app = FinderApp(window)
    if args.world:
        from rng_cleanup import SavedWorld
        world = SavedWorld(args.world)
        app.portal_tab.values['world'].set(str(world.path))
        app.portal_tab.values['seed'].set(str(world.seed))
        app.tabs.select(app.tabs.tabs()[-1])
    window.mainloop()
