import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
import training_console as tc

class RollerHttpBounds(unittest.TestCase):
    def test_only_roller_accepts_push_06_and_maintains_zero_sideways(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = tc.BaseTrainingManager(Path(temporary))
            jid='r'*16
            stream=io.BytesIO()
            manager.jobs[jid]={'id':jid,'op':'play','status':'running','resolved_task':'Mjlab-Velocity-Flat-MicroDuck-Rollers','request':{'task':'Mjlab-Velocity-Flat-MicroDuck-Rollers'},'sim_controls':{'movement':True}}
            manager.processes[jid]=SimpleNamespace(stdin=stream,poll=lambda:None)
            try:
                req={'job_id':jid,'action':'move','velocity':[.6,0,0],'client':'r1524test','sequence':1}
                self.assertTrue(manager.control(req)['queued'])
                end=time.monotonic()+1
                while not stream.getvalue() and time.monotonic()<end:time.sleep(.01)
                packets=[json.loads(x) for x in stream.getvalue().splitlines()]
                self.assertEqual(packets[0]['velocity'],[.6,0,0])
                for v in ([.61,0,0],[0,.01,0],[0,0,.01],[-.51,0,0]):
                    with self.subTest(v=v),self.assertRaisesRegex(ValueError,'轮滑推进/制动'):
                        manager.control({**req,'velocity':v,'sequence':len(manager.control_sequences)+3})
                manager.jobs[jid]['resolved_task']='Mjlab-Velocity-Flat-MicroDuck'
                with self.assertRaisesRegex(ValueError,'仿真速度'):
                    manager.control({**req,'sequence':90})
            finally:
                for ch in manager.control_channels.values():ch.close()

if __name__=='__main__':unittest.main()
