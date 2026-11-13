"""Real local process/relay tests, with fake ALSA and fake cloud; no hardware."""
import base64
import io
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile
import hashlib

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_hat_audio import NativeMicrophone,NativeSpeaker,AudioError,hat_device
from ai_doubao import DoubaoNative
from ai_remote import RemoteAI,worker_bundle
from ai_zero import GateRelay,ZeroHub
from service_channel import ServiceChannel
from verification.test_ai_v200 import FakeRobot
import service_rpc


class Hub:
    def __init__(self):
        self.events=[];self.error='';self.api_key='fixture-secret-1234'
        self.voice_id='test_voice';self.provider_ready=False
        self.stop=threading.Event()
        self.robot=FakeRobot();self.gate=self.robot.gate
        self.gate.set_skills(self.robot.skills);self.gate.log=self.log
    def log(self,kind,**fields):self.events.append({'kind':kind,**fields})


class ALSATests(unittest.TestCase):
    def test_card_uses_existing_hat_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'card.json';p.write_text('{"card":"aic3104"}')
            self.assertEqual(hat_device(p),'plughw:aic3104')
            p.write_text('{"card":"oops; rm"}')
            with self.assertRaises(AudioError):hat_device(p)

    def executable(self,directory,name,source):
        path=Path(directory)/name
        path.write_text('#!'+sys.executable+'\n'+source)
        path.chmod(0o700);return str(path)

    def test_capture_is_640_byte_pcm_and_owned_process_is_released(self):
        with tempfile.TemporaryDirectory() as directory:
            exe=self.executable(directory,'arecord','import os,time\nwhile True:\n os.write(1,b"\\x01\\x02"*320)\n time.sleep(.02)\n')
            with patch('ai_hat_audio.shutil.which',return_value=exe):
                with NativeMicrophone('plughw:aic3104') as mic:
                    proc=mic.proc
                    self.assertEqual(mic.read(),b'\x01\x02'*320)
                    self.assertEqual(mic.read(),b'\x01\x02'*320)
                    self.assertIn('16000',proc.args)
                    self.assertNotIn('48000',proc.args)
                self.assertIsNotNone(proc.poll())

    def test_speaker_is_lazy_and_finishes_raw_pcm_at_24k(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'pcm.bin'
            source='import sys\nfrom pathlib import Path\nPath('+repr(str(output))+').write_bytes(sys.stdin.buffer.read())\n'
            exe=self.executable(directory,'aplay',source)
            with patch('ai_hat_audio.shutil.which',return_value=exe) as which:
                with NativeSpeaker('plughw:aic3104') as speaker:
                    self.assertIsNone(speaker.proc);which.assert_not_called()
                    pcm=struct.pack('<h',321)*4000;speaker.write(pcm)
                    proc=speaker.proc;self.assertIn('24000',proc.args)
                    speaker.finish();self.assertIsNone(speaker.proc)
                self.assertEqual(output.read_bytes(),pcm)

    def test_stop_or_locked_state_cannot_start_playback(self):
        stop=threading.Event();stop.set()
        with patch('ai_hat_audio.subprocess.Popen') as popen:
            with NativeSpeaker('plughw:aic3104',stop) as speaker:speaker.write(b'\0'*640)
        popen.assert_not_called()
        hub=Hub();provider=DoubaoNative(hub,hub.api_key,hub.voice_id,None,None,threading.Event())
        provider._handle({'type':'response.output_audio.delta','audio':base64.b64encode(b'\0'*640).decode()})
        self.assertFalse(provider.stop_event.is_set());self.assertTrue(provider.audio_queue.empty())

    def test_capture_failure_reports_hat_device_error(self):
        with tempfile.TemporaryDirectory() as directory:
            exe=self.executable(directory,'arecord','import sys\nsys.stderr.write("Device or resource busy\\n");sys.exit(1)\n')
            with patch('ai_hat_audio.shutil.which',return_value=exe):
                with NativeMicrophone('plughw:aic3104') as mic:
                    with self.assertRaisesRegex(AudioError,'HAT 麦克风'):mic.read()


FAKE_PROVIDER='''import time,os
class DoubaoNative:
 def __init__(self,hub,key,voice,input_device,output_device,stop):
  self.hub,self.stop=hub,stop
 def run(self):
  self.hub.log('provider_session',event='session.created')
  self.hub.log('fixture_persona',persona=self.hub.persona)
  self.hub.log('fixture_vision_settings',model=self.hub.vision_settings['model'],enabled=self.hub.vision_settings['enabled'],credential_present=bool(self.hub.vision_settings['api_key']))
  self.hub.log('fixture_pid',pid=os.getpid())
  self.hub.gate.transcript('你好小鸭',final=True)
  self.hub.log('fixture_speech_initial',enabled=self.hub.gate.speaking_enabled)
  self.hub.gate.execute('perform_skill',{'skill':'play_dead'})
  self.hub.log('fixture_action_finished')
  self.hub.log('secret_probe',message=self.hub.api_key)
  while not self.stop.wait(.05):pass
 def set_speech(self,enabled,request_id):
  self.hub.gate.speaking_enabled=enabled
  self.hub.log('voice_state',source='speech_control',control_request_id=request_id,
               speech_session=self.hub.speech_session,speech_revision=1,
               unlocked=self.hub.gate.speaking_enabled,message='fixture manual speech ACK')
 def update_tools(self):self._send(self._session('update'))
 def _session(self,mode):return {'type':'session.'+mode,'session':{'tools':self.hub.gate.tool_definitions()}}
 def _send(self,payload):self.hub.log('fixture_session_update',payload=payload)
 def inspect_scene(self,question):
  self.hub.log('fixture_vision_button',question=question,message=self.hub.vision_settings['api_key'])
 def close(self):self.stop.set()
'''


class RelayTests(unittest.TestCase):
    def fake_bundle(self):
        encoded,_=worker_bundle()
        original=zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded)))
        out=io.BytesIO()
        with original,zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
            for info in original.infolist():
                archive.writestr(info.filename,FAKE_PROVIDER.encode() if info.filename=='ai_doubao.py' else original.read(info))
        data=out.getvalue();return base64.b64encode(data).decode(),hashlib.sha256(data).hexdigest()

    def wait_for(self,predicate,timeout=4):
        deadline=time.monotonic()+timeout
        while not predicate() and time.monotonic()<deadline:threading.Event().wait(.01)
        self.assertTrue(predicate())

    def test_real_service_channel_starts_zero_tools_logs_stops_and_restarts(self):
        channel=ServiceChannel(None,'/tmp/fixture-unused.sock')
        bundle=self.fake_bundle()
        try:
            original_process=None
            for _ in range(2):
                hub=Hub();hub.persona='你是机灵的小鸭。';stop=threading.Event();remote=RemoteAI(hub,channel,stop)
                with patch('ai_remote.worker_bundle',return_value=bundle):
                    thread=threading.Thread(target=remote.run);thread.start()
                    try:
                        self.wait_for(lambda:any(e['kind']=='secret_probe' for e in hub.events))
                        self.assertTrue(hub.provider_ready)
                        self.assertEqual(next(e['persona'] for e in hub.events if e['kind']=='fixture_persona'),hub.persona)
                        self.assertFalse(next(e['enabled'] for e in hub.events if e['kind']=='fixture_speech_initial'))
                        self.assertFalse(hub.gate.speaking_enabled)
                        self.assertIn(('robot.do',{'skill':'play_dead'}),hub.robot.calls)
                        secret=next(e for e in hub.events if e['kind']=='secret_probe')
                        self.assertEqual(secret['message'],'[REDACTED]')
                        remote.update_tools([{'type':'function','name':'stay_silent','parameters':{'type':'object','properties':{}}}])
                        self.wait_for(lambda:any(e['kind']=='fixture_session_update' for e in hub.events))
                        update=next(e['payload'] for e in hub.events if e['kind']=='fixture_session_update')
                        self.assertEqual(update['type'],'session.update')
                        self.assertEqual(update['session']['tools'][0]['name'],'stay_silent')
                        remote.set_speech(True,'e'*32)
                        self.wait_for(lambda:any(e.get('control_request_id')=='e'*32 for e in hub.events))
                        ack=next(e for e in hub.events if e.get('control_request_id')=='e'*32)
                        self.assertTrue(ack['unlocked'])
                        self.assertEqual(ack['source'],'speech_control')
                        if original_process:self.assertIs(channel.proc,original_process)
                        original_process=channel.proc
                        remote.close();thread.join(3);self.assertFalse(thread.is_alive())
                        pid=next(e['pid'] for e in hub.events if e['kind']=='fixture_pid')
                        with self.assertRaises(ProcessLookupError):os.kill(pid,0)
                        self.assertTrue(all('audio' not in e or e['kind']=='speaker_ready' for e in hub.events))
                    finally:
                        remote.close();thread.join(3)
        finally:channel.close()

    def test_ssh_disconnect_reaps_only_the_voice_worker(self):
        channel=ServiceChannel(None,'/tmp/fixture-unused.sock');hub=Hub()
        remote=RemoteAI(hub,channel,threading.Event());failures=[]
        def run():
            try:remote.run()
            except Exception as exc:failures.append(str(exc))
        with patch('ai_remote.worker_bundle',return_value=self.fake_bundle()):
            thread=threading.Thread(target=run);thread.start()
            try:
                self.wait_for(lambda:any(e['kind']=='fixture_action_finished' for e in hub.events))
                pid=next(e['pid'] for e in hub.events if e['kind']=='fixture_pid')
                channel.close();thread.join(3)
                self.assertFalse(thread.is_alive())
                with self.assertRaises(ProcessLookupError):os.kill(pid,0)
                # EOF can now shut the worker down cleanly before the channel
                # closes. Either route must stop AI and leave no live child.
                self.assertTrue(remote.stop_event.is_set())
            finally:remote.stop_event.set();channel.close();thread.join(3)

    def test_bundle_rejects_traversal_and_checksums(self):
        encoded,checksum=self.fake_bundle()
        request={'session_id':'a'*32,'bundle':encoded,'bundle_sha256':'wrong','config':{}}
        with self.assertRaisesRegex(ValueError,'checksum'):service_rpc.ai_session(request,lambda e:None)
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:
            for name in ('ai_zero.py','ai_doubao.py','ai_hat_audio.py','_ai_vendor/__init__.py','../escape.py'):
                archive.writestr(name,'')
        data=stream.getvalue()
        request.update(bundle=base64.b64encode(data).decode(),bundle_sha256=hashlib.sha256(data).hexdigest())
        with self.assertRaisesRegex(ValueError,'path'):service_rpc.ai_session(request,lambda e:None)
        self.assertIsNone(service_rpc._ai_session)

    def test_current_sources_import_without_audio_or_pip_on_pc(self):
        result=subprocess.run([sys.executable,'-S','-c',
            'import ai_runtime,ai_remote; import sys; '
            'assert "ai_hat_audio" not in sys.modules; '
            'assert "sounddevice" not in sys.modules; print("PC control only")'],
            cwd=ROOT,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        html=(ROOT/'static/index.html').read_text();js=(ROOT/'static/ai-panel.js').read_text()
        for term in ('ai-devices','ai-input-device','ai-output-device','getUserMedia','AudioContext'):
            self.assertNotIn(term,html+js)

    def test_real_zero_bundle_imports_offline_and_contains_only_code(self):
        encoded,_=worker_bundle()
        with tempfile.TemporaryDirectory() as directory:
            with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as archive:
                self.assertNotIn('ai_audio.py',archive.namelist())
                self.assertNotIn('ai_runtime.py',archive.namelist())
                for name in archive.namelist():
                    self.assertNotIn(b'fixture-secret-1234',archive.read(name))
                archive.extractall(directory)
            result=subprocess.run([sys.executable,'-S','-c',
                'import ai_zero,ai_doubao,ai_hat_audio; from _ai_vendor import websocket; '
                'assert websocket.__version__ == "1.9.0"'],
                cwd=directory,capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_old_pc_device_settings_are_rejected(self):
        from ai_runtime import AIHub
        from telemetry import Store
        hub=AIHub(Store('service'))
        try:
            with self.assertRaises(ValueError):hub.configure({'input_device':0})
            self.assertEqual(hub.status()['execution_host'],'Zero')
        finally:hub.close()


if __name__=='__main__':unittest.main()
