"""Headless protocol, parity and data-loss checks; no display or terrain required."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend
from combine import write_nbt
import desktop_worker as worker


class DesktopWorkerTests(unittest.TestCase):
    def test_validation(self):
        values = dict(seed='hello', x='0', z='0', radius='25', view='10', difficulty='3',
                      successes='3/3', advances='999', exact=False, exclude_region=['-1', '2'])
        checked = worker.validate('Gold', values)
        self.assertEqual(checked['advances'], '0')
        self.assertEqual(checked['exclude_region'], ('-1', '2'))
        self.assertEqual(values['advances'], '999')
        for key, value in [('view','2'), ('seed','a\nb'), ('successes','4/3'), ('exact','false')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                worker.validate('Gold', dict(values, **{key:value}))

    def test_all_modes_reuse_exact_bytes(self):
        common=dict(seed='12345',x='0',z='0',radius='25',view='10',mob='witch',bound='64',
                    players_min='1',players_max='1',ore='diamond',level='3',target='4',
                    difficulty='3',advances='0',successes='1/3')
        plan='Combined schematic minimum corner: -10, 20, 30\nPlayer position: -1.5, 70, 2.5\nMansion region: -1, 2\nTerrain candidate index: 7\n'
        for mode, name in [('Mob','calculate'),('Fortune','calculate_fortune'),('Iron','calculate_golem'),('Gold','calculate_portal')]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                data=write_nbt({'Regions':(10,{})},root_name='')
                source=Path(temp)/'source';destination=Path(temp)/'dest';destination.mkdir()
                with patch.object(backend,name,return_value=(data,plan)) as calculate, patch.object(worker,'emit'):
                    result=worker.run(dict(action='search',mode=mode,values=common,output=str(source)))
                self.assertTrue(calculate.called)
                self.assertEqual(result['index'],7)
                self.assertEqual(result['coordinates'][1]['xyz'],['-1.5','70','2.5'])
                self.assertEqual(result['region'],['-1','2'])
                worker.export_files(source,destination)
                self.assertEqual((destination/'rng-combined.litematic').read_bytes(),data)
                self.assertEqual((destination/backend.PLAN_NAME).read_text(),plan)
                with self.assertRaises(FileExistsError):worker.export_files(source,destination)
                self.assertEqual((destination/'rng-combined.litematic').read_bytes(),data)

    def test_partial_export_rolls_back_only_new_files(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source';source.mkdir();destination=Path(temp)/'dest';destination.mkdir()
            (source/'rng-combined.schematic').write_bytes(b'candidate')
            (source/backend.PLAN_NAME).write_text('plan')
            (destination/backend.PLAN_NAME).write_text('existing user plan')
            with self.assertRaises(FileExistsError):worker.export_files(source,destination)
            self.assertFalse((destination/'rng-combined.schematic').exists())
            self.assertEqual((destination/backend.PLAN_NAME).read_text(),'existing user plan')

    def test_saved_world_selection_reads_seed_without_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            world=Path(temp); (world/'region').mkdir()
            raw=write_nbt({'Data':(10,{'DataVersion':(3,1343),'RandomSeed':(4,12345),'Time':(4,0)})},root_name='')
            (world/'level.dat').write_bytes(raw)
            result=worker.run(dict(action='world',path=temp))
            self.assertEqual(result['seed'],'12345')
            self.assertEqual((world/'level.dat').read_bytes(),raw)
            self.assertEqual(list((world/'region').iterdir()),[])

    def test_protocol_errors_are_structured(self):
        process=subprocess.run([sys.executable,str(Path(worker.__file__))],input=json.dumps({'action':'invalid'}),text=True,capture_output=True)
        self.assertEqual(process.returncode,1)
        self.assertEqual(json.loads(process.stdout)['kind'],'error')

    def test_headless_import(self):
        subprocess.run([sys.executable,'-c',"import desktop_worker,sys; assert 'tkinter' not in sys.modules"],cwd=Path(worker.__file__).parent,check=True)


if __name__=='__main__':unittest.main()
