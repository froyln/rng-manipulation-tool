import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combine import startup_marks

for view in range(3, 33):
    grid = (0, 64, 0)
    for player_y in (34, 66):
        player = (168, player_y, (1 - view) * 16 + 8)
        marks = startup_marks(player, grid, view)
        assert (167, player_y, player[2] - 1, 69, 5) in marks
        assert (188, 71, -1, 33, 3) in marks
        assert (188, 70, -1, 159, 11) in marks
        assert all((block, meta) == (159, 11) for _, _, _, block, meta in marks if block in (1, 159))
        assert (188, 71, -2, 93, 2) in marks
        assert sum(block == 93 for _,_,_,block,_ in marks) >= 2
assert (167, 48, -122, 93, 2) in startup_marks((168, 34, -136), (0, 64, 0), 10)
try:
    startup_marks((168, 7, -24), (0, 64, 0), 3)
except ValueError as error:
    assert 'too little room' in str(error)
else:
    raise AssertionError('A startup ramp that cannot fit inside view distance 3 was accepted')
print('Startup lever, supported repeater path and piston endpoint fit view distances 3–32 when height allows')
