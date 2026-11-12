"""Portable runtime discovery without redistributing Minecraft binaries."""
import os
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import terrain_scan

with patch.dict(os.environ,{'RNG_MINECRAFT_CLASSPATH':os.pathsep.join(['game.jar','dependency.jar'])}):
    assert terrain_scan._classpath()==os.pathsep.join(['game.jar','dependency.jar'])
with patch.dict(os.environ,{'RNG_MINECRAFT_CLASSPATH':''}), patch.object(terrain_scan,'MCP',Path('/nonexistent-rng-runtime')):
    try:
        terrain_scan._classpath()
    except RuntimeError as error:
        assert 'README' in str(error)
    else:
        raise AssertionError('Missing Minecraft runtime must fail explicitly')
print('Portable runtime override and missing-runtime error verified')
