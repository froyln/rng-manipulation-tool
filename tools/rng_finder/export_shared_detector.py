"""Finish Rust component exports using the same detector assembly as the desktop."""
from pathlib import Path
import re
import sys
from autosave import detector_origin
from combine import combine

def finish(directory):
    plan_path=directory/'rng-finder-plan.txt'
    plan=plan_path.read_text()
    player=re.search(r'(?:Suggested mining/player position|Suggested player position|Player position):\s*(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+)',plan)
    import math
    position=tuple(math.floor(float(v)) for v in player.groups())
    view=int(re.search(r'(?:Server )?view distance:\s*(\d+)',plan,re.I).group(1))
    origin=detector_origin(position,view)
    bounds=f'Autosave detector approximate bounds: {origin[0]}, {origin[1]}, {origin[2]} to {origin[0]+15}, {origin[1]+12}, {origin[2]+21}'
    plan=re.sub(r'^Autosave detector approximate bounds:.*$',bounds,plan,flags=re.M)
    if 'Autosave detector schematic:' not in plan:
        plan+=f'\nAutosave detector schematic: autosave-detector.schematic\nPlacement minimum corner (local 0,0,0): {origin[0]}, {origin[1]}, {origin[2]}\n'
    plan+='\nSHARED COMMAND SAND DETECTOR\nLeave the single AFK lever ON after starting. Existing conditional RNG call-count and reset-phase requirements still apply; detector pulses alone do not establish the predicted RNG outcome.\n'
    if 'Grid type: scheduled repeater' not in plan:
        plan+='The historical xcom-original-grid.schematic output name contains the derived grid with its obsolete detector removed; the source reference is preserved.\n'
    if 'Fortune-drop candidate' in plan:
        plan+='No automatic ore break or extra-advance mechanism is supplied; verify the harvest window separately.\n'
    if 'portal pigman RNG candidate' in plan and 'Grid type: scheduled repeater' not in plan:
        plan+='MANUAL/EXACT CALIBRATION: repeated detector outputs do not install the entered advance count. The selected conditional portal-roll alignment is not verified by these automatic-cycle trials.\n'
        plan=plan.replace('A prepared first lever window has been reproduced in a disposable vanilla server;', 'Historical prepared manual-window evidence does not validate the replacement detector’s selected advance count;')
    grid=directory/('tile-tick-grid.schematic' if 'Grid type: scheduled repeater' in plan else 'xcom-original-grid.schematic')
    extra_name='Village schematic:' if (directory/'golem-village.schematic').exists() else 'Portal-array schematic:' if (directory/'portal-platform.schematic').exists() else None
    extra=(directory/('golem-village.schematic' if extra_name=='Village schematic:' else 'portal-platform.schematic')).read_bytes() if extra_name else None
    data,text=combine(grid.read_bytes(),plan,extra,extra_name)
    outputs=[(directory/'rng-combined.schematic',data),(directory/'rng-combined-plan.txt',text.encode())]
    detector=directory/'autosave-detector.schematic'
    if not detector.exists():outputs.append((detector,Path(__file__).with_name('reference').joinpath('command-autosave-detector-1.12.schematic').read_bytes()))
    created=[]
    try:
        for path,raw in outputs:
            with path.open('xb') as f:
                created.append(path);f.write(raw)
    except OSError:
        for path in created:path.unlink()
        raise
    plan_path.write_text(plan+'\nConnected CLI output: rng-combined.schematic; place using rng-combined-plan.txt. Do not place separate component schematics over that connected file.\n')

if __name__=='__main__':
    try:
        finish(Path(sys.argv[1]))
    except (OSError,ValueError) as error:
        sys.exit(str(error))
