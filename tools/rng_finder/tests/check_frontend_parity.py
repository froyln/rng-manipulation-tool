"""Compare actual calculated artifacts at the Tk/JSON boundary, without terrain.

Terrain is stubbed here for deterministic, bounded ordering. This is neither a
desktop interaction test nor evidence of gameplay. Native palette/cleanup
decoding has separate independent fixtures in check_combined_litematic.py and
check_rng_cleanup.py.
"""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend
import desktop_worker as worker
import gui

common = dict(seed='12345', x='0', z='0', radius='25', view='10',
              mob='witch', bound='64', players_min='1', players_max='1',
              ore='diamond', level='3', target='4', advances='0',
              difficulty='3', successes='1/3', exact=False)
cases = [('Mob', 'calculate', {}),
         ('Fortune', 'calculate_fortune', {}),
         ('Iron', 'calculate_golem', {'radius': '128'}),
         ('Gold', 'calculate_portal', {}),
         ('Gold', 'calculate_portal', {'exact': True})]

with tempfile.TemporaryDirectory(prefix='rng-frontend-parity-') as temp, \
     patch.object(backend, 'scan_terrain', return_value=(True, 'Parity fixture: terrain omitted.')):
    for case, (mode, name, overrides) in enumerate(cases):
        values = dict(common, **overrides)
        assert getattr(gui, name) is getattr(backend, name)
        with contextlib.redirect_stdout(io.StringIO()):
            expected, plan = getattr(gui, name)(values)
            output = Path(temp) / str(case)
            with patch.object(worker, 'emit'):
                result = worker.run(dict(action='search', mode=mode, values=values, output=str(output)))
        artifacts = list(output.glob('*.litematic')) + list(output.glob('*.schematic'))
        assert len(artifacts) == 1
        # Compare every decoded NBT tag: palette/block-state words, entities,
        # tile entities, region positions/dimensions and origins, not file size.
        assert backend.read_nbt(artifacts[0].read_bytes(), root_name=None) == backend.read_nbt(expected, root_name=None)
        assert (output / backend.PLAN_NAME).read_text() == plan == result['plan']
        assert result['region'] and result['coordinates']
        print(mode, 'exact' if values['exact'] else 'default', 'complete decoded NBT and plan equal')
