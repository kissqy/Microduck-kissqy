import io
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from training import event_protocol as protocol, runtime_adapter, live_view, worker


class EventProtocolTests(unittest.TestCase):
    def frame(self,kind='training_view_state',**data):
        return protocol.PREFIX+json.dumps({'kind':kind,**data},ensure_ascii=False)

    def test_joined_json_and_plain_logs_are_recovered_in_order(self):
        a=self.frame(data={'step':700})
        b=self.frame('training_curriculum_state',data={'standing_prob':.3})
        parts=list(protocol.split_output('progress 50% '+a+b+' Mean reward: 61.0'))
        self.assertEqual([p[0] for p in parts],['log','event','event','log'])
        self.assertEqual(parts[1][1]['data']['step'],700)
        self.assertEqual(parts[-1][1],'Mean reward: 61.0')
        parts=list(protocol.split_output(a+json.dumps({'kind':'log','line':'still training'})))
        self.assertEqual(parts[-1][1]['line'],'still training')

    def test_prefix_and_braces_inside_json_strings_are_not_split(self):
        value='中文 } '+protocol.PREFIX+'{"kind":"log"} \\n'
        parts=list(protocol.split_output(self.frame('log',line=value)))
        self.assertEqual(parts,[('event',{'kind':'log','line':value})])

    def test_malformed_message_does_not_hide_following_good_event(self):
        for broken in ('{"kind":', '{"kind":[]}', '{"kind":"sim_state","value":NaN}', 'null'):
            with self.subTest(broken=broken):
                parts=list(protocol.split_output(protocol.PREFIX+broken+self.frame(data={'step':800})))
                self.assertTrue(any(kind=='log' and '中控消息异常' in value for kind,value in parts))
                self.assertEqual(parts[-1][1]['data']['step'],800)

    def test_emit_uses_one_shared_writer_and_one_write_per_frame(self):
        self.assertIs(runtime_adapter.emit,protocol.emit)
        self.assertIs(live_view.emit,protocol.emit)
        class Sink:
            def __init__(self):self.writes=[]
            def write(self,text):self.writes.append(text);time.sleep(.0001)
            def flush(self):pass
        sink=Sink()
        def send(index):
            for i in range(20):protocol.emit('training_view_state',data={'thread':index,'step':i})
        with patch.object(protocol.sys,'stdout',sink):
            threads=[threading.Thread(target=send,args=(i,)) for i in range(4)]
            for thread in threads:thread.start()
            for thread in threads:thread.join()
        self.assertEqual(len(sink.writes),80)
        for frame in sink.writes:
            self.assertTrue(frame.endswith('\n'))
            self.assertEqual(len(list(protocol.split_output(frame))),1)

    def test_renderer_pipe_is_relayed_through_parent_reporter(self):
        records=[]
        view=live_view.TrainingLiveView.__new__(live_view.TrainingLiveView)
        view.stop=threading.Event();view.failed=False
        view.report=lambda kind,**data:records.append((kind,data))
        view.proc=SimpleNamespace(stdout=io.BytesIO(('renderer ready '+self.frame(url='http://127.0.0.1:8093')+'\n').encode()))
        view._relay_output()
        self.assertEqual([r[0] for r in records],['log','training_view_state'])
        self.assertTrue(view.proc.stdout.closed)

    def test_real_child_continues_after_extra_data_but_actual_exit_failure_surfaces(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);fixture=root/'fake_trainer.py'
            # This exact shape raised JSONDecodeError in the old adapter_event.
            line=self.frame(data={'step':700})+self.frame('training_curriculum_state',data={'step':700})+' Mean reward: 61.0'
            fixture.write_text('import sys\nprint("Learning iteration 700/1000",flush=True)\nprint('+repr(line)+',flush=True)\nprint('+repr(protocol.PREFIX+'{"kind":broken')+',flush=True)\nprint("TRAINER_STILL_RUNNING",flush=True)\n')
            req={'op':'train','task':'Mjlab-Test','run_name':'fixture','num_envs':1,'iterations':1000}
            records=[]
            worker.STOP.clear()
            with patch.object(worker,'prepare',return_value=(root,[sys.executable,'-u',str(fixture)],'a'*40)),patch.object(worker,'monitor_gpu'),patch.object(worker,'checkpoints',return_value=[]),patch.object(worker,'emit',side_effect=lambda kind,**data:records.append((kind,data))):
                worker.run_prepared(req,root)
                self.assertIn(('log',{'line':'TRAINER_STILL_RUNNING'}),records)
                self.assertTrue(any(k=='metric' and v['data'].get('reward')==61 for k,v in records))
                self.assertEqual(records[-1][0],'complete')
                fixture.write_text(fixture.read_text()+'sys.exit(7)\n')
                records.clear()
                with self.assertRaisesRegex(RuntimeError,'退出码 7'):worker.run_prepared(req,root)
                self.assertFalse(any(k=='complete' for k,v in records))

    def test_private_worker_bundle_imports_new_module_without_installed_training_package(self):
        # Same stdlib-only bundle copied to WSL by the console.
        source=Path(worker.__file__).read_text()
        self.assertIn("'event_protocol.py'",source)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('event_protocol.py','sample_alignment.py','live_view.py','runtime_adapter.py','sim_protocol.py','recipe.py','official_spec.py','action_filter.py'):
                (root/name).write_bytes(Path(worker.__file__).with_name(name).read_bytes())
            result=subprocess.run([sys.executable,'-c','import live_view,runtime_adapter,event_protocol; assert live_view.emit is runtime_adapter.emit is event_protocol.emit'],cwd=root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
