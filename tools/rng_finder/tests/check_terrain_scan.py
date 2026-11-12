import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combine import write_nbt, read_nbt
from terrain_scan import scan, mark_structures

def schematic_at(y):
    blocks = bytearray(1)
    blocks[0] = 1
    return write_nbt({'Width':(2,1),'Height':(2,1),'Length':(2,1),'Materials':(8,'Alpha'),
                       'Blocks':(7,bytes(blocks)),'Data':(7,bytes(1)),
                       'Entities':(9,(10,[])), 'TileEntities':(9,(10,[
                           {'id':(8,'minecraft:sign'),'x':(3,0),'y':(3,0),'z':(3,0),
                            'Text1':(8,'{"text":"Player Spot"}'),'Text2':(8,'{"text":""}'),
                            'Text3':(8,'{"text":""}'),'Text4':(8,'{"text":""}')}
                       ]))})
plan = 'Combined schematic minimum corner: 2582, {y}, 1100\nWorld seed: 7480190280633614536\n'
clear, report = scan(schematic_at(33), plan.format(y=33))
assert not clear
assert 'block ID 1 at (2582, 33, 1100)' in report
clear, report = scan(schematic_at(62), plan.format(y=62))
assert not clear
assert 'block ID 9 at (2582, 62, 1100)' in report
clear, report = scan(schematic_at(100), plan.format(y=100) + 'Height control block (stone): 2582, 60, 1100\n')
assert not clear and 'at (2582,' in report
clear, report = scan(schematic_at(100), plan.format(y=100) + 'Modeled first golem spawn block: 2582, 33, 1100\n')
assert not clear and 'block ID 1 at' in report
portal_volume = write_nbt({'Width':(2,2),'Height':(2,4),'Length':(2,2),'Materials':(8,'Alpha'),
                           'Blocks':(7,bytes([90]*16)),'Data':(7,bytes(16)),
                           'Entities':(9,(10,[])), 'TileEntities':(9,(10,[]))})
clear, report = scan(portal_volume,
                     'Combined schematic minimum corner: 2581, 33, 1099\nWorld seed: 7480190280633614536\n'
                     'Modeled first golem spawn block: 2582, 33, 1100\n')
assert clear, report
tagged = read_nbt(mark_structures(schematic_at(33), 'Nearby structures:\n  Woodland Mansion: 2600, 30, 1090 to 2610, 70, 1110'))
assert tagged['TileEntities'][1][1][0]['Text2'][1] == '{"text":"Near Mansion"}'
print('Vanilla 1.12.2 terrain scanner rejects the screenshot’s stone and water blocks; nearby structure sign annotation verified')
