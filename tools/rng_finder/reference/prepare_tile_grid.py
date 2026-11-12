"""Derive a 1.12 research copy; preserve Command's downloaded schematic unchanged."""
from pathlib import Path
import json
import sys

TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL))
from combine import read_nbt, write_nbt

source = read_nbt((TOOL.parents[1] / 'sources/GridTileTick.schematic').read_bytes())
blocks, metadata = bytearray(source['Blocks'][1]), bytearray(source['Data'][1])
debug = sum(block == 137 for block in blocks)
assert debug == 3
assert blocks.count(77) == 1
width = source['Width'][1]
for i, block in enumerate(blocks):
    # The shared lever/detector input joins at x=202; everything west is old button delay or scenery.
    if i % width < 202 or block in (137, 77):
        blocks[i], metadata[i] = 0, 0
    elif block in (57, 1):
        blocks[i], metadata[i] = 159, 11
    elif block in (18, 161):
        metadata[i] = (metadata[i] & 3) | 4  # Normal non-decaying player-placed leaves.
source['Blocks'], source['Data'] = (7, blocks), (7, metadata)
tiles = []
for tile in source['TileEntities'][1][1]:
    if tile['id'][1] == 'Control':
        continue
    assert tile['id'][1] == 'Comparator'
    tiles.append(dict(tile, id=(8, 'minecraft:comparator')))
source['TileEntities'] = (9, (10, tiles))
assert len(tiles) == 1 and 154 not in blocks and 158 not in blocks
destination = Path(__file__).with_name('command-tile-tick-grid-1.12.schematic')
destination.write_bytes(write_nbt(source))
print(destination)

detector = read_nbt((TOOL.parents[1] / 'sources/AutoSaveDetector.schematic').read_bytes())
metadata = bytearray(detector['Data'][1])
for i, block in enumerate(detector['Blocks'][1]):
    if block == 159:
        metadata[i] = 11
detector['Data'] = (7, metadata)
for tile in detector['TileEntities'][1][1]:
    tile['id'] = (8, {'Sign': 'minecraft:sign', 'Comparator': 'minecraft:comparator'}[tile['id'][1]])
    if tile['id'][1] == 'minecraft:sign':
        for i in range(1, 5):
            key = f'Text{i}'
            tile[key] = (8, json.dumps({'text': tile[key][1]}))
destination = Path(__file__).with_name('command-autosave-detector-1.12.schematic')
destination.write_bytes(write_nbt(detector))
print(destination)
