"""Real separate RPC processes and injected AI failures; no robot/cloud access."""
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from ai_channel import AIChannel
from ai_doubao import DoubaoNative
from ai_preferences import AIPreferences
from ai_remote import worker_bundle
from ai_runtime import AIHub
from process_lifecycle import spawn_process
from service_channel import ServiceChannel
from telemetry import Store


FAULT_CLOUD='''from _ai_vendor.websocket._fault_fixture import DoubaoNative as Real
import _ai_vendor.websocket._fault_fixture as native
class Mic:
 def __init__(self,*args):pass
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self):return bytes(640)
class DoubaoNative(Real):
 def _send(self,event):
  if event.get('type')=='input_audio_buffer.append':raise TimeoutError('The write operation timed out')
  return True
 def run(self):
  self._handle({'type':'session.created'})
  if self.voice_id=='fixture-wait':self.stop_event.wait(20);return
  native.NativeMicrophone=Mic
  self._microphone()
'''


FAKE_IPC = r'''class FixtureIPC:
 def __init__(self,*args,**kwargs):self.request={}
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def settimeout(self,value):pass
 def connect(self,path):pass
 def sendall(self,data):self.request=json.loads(data)
 def makefile(self,*args):
  r=self.request
  result={'skills':[{'name':'roulade'}],'built_in':[]} if r['method']=='robot.skills' else {'accepted':True}
  return io.BytesIO((json.dumps({'jsonrpc':'2.0','id':r['id'],'result':result})+'\n').encode())
socket.socket=FixtureIPC
'''


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.socket_path=str(Path(self.temp.name)/'robot.sock')
        # Real separate service_rpc processes, with robotd IPC stubbed in each
        # child. The robotd stub needs neither hardware nor a local network listener.
        def relay_process(argv,*args,**kwargs):
            argv=list(argv)
            if '-c' in argv and '--stream' in argv:
                index=argv.index('-c')+1
                argv[index]=argv[index].replace("if __name__ == '__main__':",FAKE_IPC+"\nif __name__ == '__main__':")
            return spawn_process(argv,*args,**kwargs)
        self.spawn_patch=patch('service_channel.spawn_process',side_effect=relay_process)
        self.spawn_patch.start();self.addCleanup(self.spawn_patch.stop)
        self.primary=ServiceChannel(None,self.socket_path);self.addCleanup(self.primary.close)
        self.skills(self.primary);self.primary_pid=self.primary.proc.pid
        self.hub=AIHub(Store('service'),service_controller=SimpleNamespace(
            transport=SimpleNamespace(channel=self.primary,log=None)),
            connection=SimpleNamespace(active=True),preferences=AIPreferences(Path(self.temp.name)/'prefs.json'))
        self.addCleanup(self.hub.close)

    def skills(self,channel):
        result=channel.request({'method':'robot.skills','params':{}},timeout=3)
        self.assertEqual(result['result']['skills'],[{'name':'roulade'}])
        return result

    def main_still_works(self):
        self.assertIsNone(self.primary.proc.poll());self.assertEqual(self.primary.proc.pid,self.primary_pid)
        self.skills(self.primary)
        result=self.primary.request({'method':'robot.move','params':{'vx':0,'vy':0,'vyaw':0}},timeout=2)
        self.assertTrue(result['result']['accepted'])

    def test_ai_queries_and_stop_own_a_different_process_and_retry_state(self):
        self.hub.load_skills();private=self.hub.ai_channel
        self.assertIsNot(private,self.primary)
        self.assertIsNot(private.lock,self.primary.lock);self.assertIsNot(private.retry,self.primary.retry)
        self.assertNotEqual(private.proc.pid,self.primary_pid)
        ai_proc=private.proc
        self.hub.stop()
        self.assertIsNone(self.hub.ai_channel);self.assertTrue(private.closed)
        self.assertIsNotNone(ai_proc.poll());self.main_still_works()

    def test_ai_pipe_backpressure_times_out_without_touching_primary(self):
        private=AIChannel(None,self.socket_path,write_timeout=1);self.addCleanup(private.close)
        def stalled_peer(*args,**kwargs):
            return spawn_process([sys.executable,'-u','-c','import time;time.sleep(30)'],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        before=time.monotonic();errors=[]
        def request():
            try:private.request({'kind':'probe','data':'x'*500000},timeout=2)
            except Exception as exc:errors.append(exc)
        worker=threading.Thread(target=request)
        with patch('service_channel.spawn_process',side_effect=stalled_peer):
            worker.start();deadline=time.monotonic()+.5
            while not private.writes.unfinished_tasks and time.monotonic()<deadline:threading.Event().wait(.005)
            self.assertTrue(private.writes.unfinished_tasks)
            self.main_still_works()
            self.assertTrue(worker.is_alive(),'primary requests finish while AI is still stalled')
            worker.join(3)
        self.assertFalse(worker.is_alive());self.assertEqual(len(errors),1)
        self.assertIsInstance(errors[0],TimeoutError);self.assertIn('写入超时',str(errors[0]))
        self.assertLess(time.monotonic()-before,3)
        self.assertFalse(private.pending)
        self.assertEqual(self.primary.retry.failures,0)
        self.main_still_works()

    def test_broken_ai_ssh_process_does_not_disconnect_primary(self):
        self.hub.load_skills();private=self.hub.ai_channel
        private.proc.terminate();private.proc.wait(1)
        deadline=time.monotonic()+1
        while private.proc is not None and time.monotonic()<deadline:threading.Event().wait(.01)
        self.hub.stop();self.main_still_works()

    def test_connection_target_change_stops_ai_without_retargeting_old_requests(self):
        self.hub.load_skills();old=self.hub.ai_channel
        self.primary.target='radxa@192.0.2.1'
        self.assertFalse(self.hub.ai_connection_current(old))
        self.primary.target=None
        self.hub.stop();self.main_still_works()

    def fault_bundle(self):
        encoded,_=worker_bundle();out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as source,zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as result:
            for name in source.namelist():result.writestr(name,FAULT_CLOUD if name=='ai_doubao.py' else source.read(name))
            result.writestr('_ai_vendor/websocket/_fault_fixture.py',source.read('ai_doubao.py'))
        data=out.getvalue();return base64.b64encode(data).decode(),hashlib.sha256(data).hexdigest()

    def test_real_ai_worker_upload_timeout_exits_only_ai_and_keeps_main_ipc_alive(self):
        self.hub.api_key='fixture-native-key'
        with patch('ai_remote.worker_bundle',return_value=self.fault_bundle()):
            self.hub.start();self.hub.worker.join(5)
        self.assertFalse(self.hub.worker.is_alive())
        self.assertIsNone(self.hub.ai_channel)
        failure=next(e for e in self.hub.events if e['kind']=='provider_error')
        self.assertEqual(failure['stage'],'audio_upload')
        self.assertIn('write operation timed out',failure['reason'])
        self.assertFalse(any(e['kind']=='mic_error' for e in self.hub.events))
        self.assertTrue(self.hub.connection.active);self.main_still_works()

    def test_stopping_a_live_ai_worker_keeps_primary_process_and_control_requests_alive(self):
        self.hub.api_key='fixture-native-key';self.hub.voice_id='fixture-wait'
        with patch('ai_remote.worker_bundle',return_value=self.fault_bundle()):
            self.hub.start()
            deadline=time.monotonic()+3
            while not self.hub.provider_ready and time.monotonic()<deadline:threading.Event().wait(.01)
            self.assertTrue(self.hub.provider_ready)
            before=time.monotonic();self.hub.stop();self.hub.worker.join(3)
        self.assertFalse(self.hub.worker.is_alive());self.assertLess(time.monotonic()-before,3)
        self.main_still_works()


if __name__=='__main__':unittest.main()
