"""Remove only Wout's embedded detector from a derived Xcom grid."""
from pathlib import Path
import gzip
import sys
TOOL=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TOOL))
from combine import read_nbt,write_nbt

def obsolete_detector(x,y,z):
    return (194<=x<=206 and 3<=y<=7 and 12<=z<=17 and (x,y,z)!=(200,3,12)) or (x==200 and y==5 and 7<=z<=11) or (y==6 and ((194<=x<=200 and z==4) or (x==200 and 5<=z<=11)))

if __name__=='__main__':
    root=read_nbt((TOOL/'reference/xcom-chunk-loading-grid.schematic').read_bytes())
    w,h,d=[root[k][1] for k in ('Width','Height','Length')]
    blocks,meta=bytearray(root['Blocks'][1]),bytearray(root['Data'][1])
    for i in range(len(blocks)):
        y,r=divmod(i,w*d);z,x=divmod(r,w)
        if obsolete_detector(x,y,z):blocks[i]=meta[i]=0
    root['Blocks'],root['Data']=(7,blocks),(7,meta)
    root['TileEntities']=(9,(10,[t for t in root['TileEntities'][1][1] if not obsolete_detector(*(t[a][1] for a in ('x','y','z')))]))
    (TOOL/'reference/xcom-shared-detector-grid.schematic').write_bytes(gzip.compress(gzip.decompress(write_nbt(root)),compresslevel=1,mtime=0))
