"""Multi-success search, desktop flag plumbing and pinned real-spawn methods."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend as gui
from terrain_scan import _classpath
with tempfile.TemporaryDirectory(prefix='portal-successes-') as tmp:
    def command(seed,required,output):
        return [str(gui.BINARY),'--portal',str(seed),'3','0','0','0','0','10',str(output),'--portal-tick-model','--portal-successes',str(required)]
    for required,seed,attempt,roll in [(1,171656809007210,1,1),(2,171656809007210,2,2),(3,84785424703645,3,1)]:
        out=Path(tmp)/str(required)
        subprocess.run(command(seed,required,out),check=True,capture_output=True)
        plan=(out/gui.PLAN_NAME).read_text()
        assert f'Requested manipulation: at least {required}/3' in plan
        assert f'attempt {attempt} of 3, World.rand.nextInt(2000) = {roll}' in plan
        assert 'Mansion region: 0, 0' in plan
        if required>1:assert 'only reports the first success' not in plan
        values=dict(seed=str(seed),difficulty='3',x='0',z='0',radius='0',advances='0',view='10',successes=f'{required}/3')
        def capture(values,build,*rest):
            flags=build(str(out),0)
            assert flags[flags.index('--portal-successes')+1]==str(required)
            return b'unchanged',plan
        with patch.object(gui,'_search_with_terrain',side_effect=capture):gui.calculate_portal(values)
    failed=Path(tmp)/'no-three'
    result=subprocess.run(command(171656809007210,3,failed),capture_output=True,text=True)
    assert result.returncode and 'requested successful random ticks' in result.stderr and not failed.exists()
    for invalid in ('0','4','-1','three'):
        assert subprocess.run(command(1,invalid,Path(tmp)/'invalid'),capture_output=True).returncode
    assert subprocess.run([str(gui.BINARY),'--portal-successes','2'],capture_output=True).returncode
    cp=_classpath()
    subprocess.run(['javac','-proc:none','-cp',cp,'-d',tmp,str(Path(__file__).with_name('PortalSpawnSequenceProbe.java'))],check=True,capture_output=True)
    result=subprocess.run(['java','-cp',tmp+os.pathsep+cp,'PortalSpawnSequenceProbe'],check=True,capture_output=True,text=True,timeout=90)
    assert 'actual pigmen=2' in result.stdout and 'actual pigmen=3' in result.stdout and '513 initializations' in result.stdout
    print(result.stdout.strip())
print('1/3 default path, 2/3 and 3/3 search/desktop flags, no fallback and invalid-input guards verified')
