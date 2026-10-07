import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from io import BytesIO
from system_log import SystemLog
from service_control import ServiceTransport
from service_rpc import execute
import controls
from controls import Transport,ControlError

class SystemLogTests(unittest.TestCase):
    def test_complete_install_output_persists_beyond_old_page_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            log=SystemLog(directory)
            try:
                for n in range(720): log.add('安装',f'stage {n}: '+('x'*1024))
                log.add('安装','END-INSTALL-VERIFIED')
                log.flush()
                data=log.path.read_text()
                self.assertGreater(len(data),512*1024)
                self.assertIn('stage 0:',data);self.assertIn('END-INSTALL-VERIFIED',data)
                after=0;count=0
                while True:
                    result=log.tail(after,100);after=result['cursor'];count+=len(result['entries'])
                    if not result['has_more']:break
                self.assertEqual(count,721)
            finally:log.close()

    def test_password_redaction_covers_stream_and_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            log=SystemLog(directory);log.hide('secret123')
            try:
                log.add('SSH','\x1b[31msudo secret123 rejected\x1b[0m');log.flush()
                self.assertNotIn('secret123',log.path.read_text())
                self.assertNotIn('secret123',json.dumps(log.tail()))
                self.assertIn('[已隐藏]',log.path.read_text())
            finally:log.close()

    def test_actual_warm_relay_streams_the_full_install_to_log(self):
        with tempfile.TemporaryDirectory() as directory:
            log=SystemLog(directory);transport=ServiceTransport('', '/unused',log)
            try:
                transport._manage([sys.executable,'-u','-c',"[print('x'*8193) for _ in range(70)];print('INSTALL-END-MARKER')"],privileged=False)
                log.flush();data=log.path.read_text()
                self.assertGreater(len(data),512*1024)
                self.assertIn('INSTALL-END-MARKER',data)
                self.assertIn('退出码 0',data)
            finally:transport.channel.close();log.close()

    def test_log_api_and_full_download_use_same_session_file(self):
        from http.server import ThreadingHTTPServer
        from urllib.request import urlopen
        from console import handler_for
        from telemetry import Store
        with tempfile.TemporaryDirectory() as directory:
            store=Store();store.system_log=SystemLog(directory)
            server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(store,{'bind':'127.0.0.1'}))
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            try:
                store.system_log.add('SSH','FIRST-STAGE');store.system_log.add('SSH','LAST-STAGE')
                base=f'http://127.0.0.1:{server.server_port}'
                with urlopen(base+'/api/system-log?after=0&limit=1') as response:page=json.load(response)
                self.assertTrue(page['has_more']);self.assertEqual(page['entries'][0]['text'],'FIRST-STAGE')
                with urlopen(base+'/api/system-log?after=1') as response:page=json.load(response)
                self.assertEqual(page['entries'][0]['text'],'LAST-STAGE')
                with urlopen(base+'/api/system-log/download') as response:
                    text=response.read().decode();self.assertIn('attachment',response.headers['Content-Disposition'])
                self.assertIn('FIRST-STAGE',text);self.assertIn('LAST-STAGE',text)
            finally:server.shutdown();server.server_close();worker.join();store.system_log.close()

    def test_audio_timeout_remains_a_failure_and_preserves_last_confirmed_value(self):
        from remote_audio import NativeAudio
        with tempfile.TemporaryDirectory() as directory:
            setup=Path(directory)/'voice.json';setup.write_text('{"card":"VOICE"}')
            events=[]
            def runner(command,**options):
                self.assertEqual(options['timeout'],4)
                if 'cset' in command:raise subprocess.TimeoutExpired(command,4)
                return SimpleNamespace(returncode=0,stdout=': values=900',stderr='')
            audio=NativeAudio(None,events.append,config=Path(directory)/'missing.toml',setup=setup,runner=runner)
            before=audio.volume
            with self.assertRaisesRegex(RuntimeError,'回读超时'):audio.set_volume(65)
            self.assertEqual(audio.volume,before)
            self.assertTrue(any(x.get('source')=='音量错误' for x in events))

    def test_management_streams_to_system_log_without_explicit_install_callback(self):
        with tempfile.TemporaryDirectory() as directory:
            log=SystemLog(directory)
            class Channel:
                def request(self,request,timeout,progress=None):
                    self.stream=request['progress'];self.input=request['input']
                    progress('actual secret123 stdout\n');return {'returncode':0,'stdout':'{}','stderr':''}
            transport=ServiceTransport('', '/unused',log);channel=transport.channel=Channel()
            try:
                transport._manage(['true'],password='secret123')
                log.flush();data=log.path.read_text()
                self.assertTrue(channel.stream);self.assertIn('actual [已隐藏] stdout',data)
                self.assertNotIn('secret123',data)
            finally:log.close()

    def test_relay_keeps_every_install_line_in_progress_even_when_summary_is_bounded(self):
        lines=[]
        script="import sys;[print('x'*8193) for _ in range(70)];print('END-MARKER')"
        result=execute({'kind':'manage','argv':[sys.executable,'-c',script],'input':'','timeout':8},lines.append)
        self.assertEqual(result['returncode'],0)
        self.assertGreater(len(''.join(lines)),512*1024)
        self.assertTrue(''.join(lines).endswith('END-MARKER\n'))
        self.assertEqual(len(lines[0]),8194)

    def test_closed_idle_peer_is_replaced_before_press_is_sent(self):
        devices=[]
        class Socket:
            def __init__(self):self.sent=[];self.closed=False;devices.append(self)
            def settimeout(self,_):pass
            def makefile(self,_):return BytesIO(b'{"accepted":true,"owner":"test-page"}\n'*2)
            def sendall(self,data):self.sent.append(json.loads(data))
            def close(self):self.closed=True
        transport=Transport();old=Socket();transport.peer=old;transport.reader=old.makefile('rb')
        try:
            with patch.object(controls,'open_remote_socket',side_effect=lambda *_a,**_kw:Socket()),patch.object(controls.select,'select',side_effect=lambda items,*_: (items,[],[])):
                transport.call({'action':'webpad_state','owner':'test-page','frame':{'buttons':['start']}})
            self.assertEqual(len(devices),2);self.assertTrue(old.closed)
            self.assertEqual(old.sent,[])
            self.assertEqual(devices[1].sent,[{'action':'state','owner':'test-page','frame':{'buttons':['start']}}])
        finally:transport.close()

    def test_write_failure_never_resends_uncertain_action(self):
        sent=[]
        class Socket:
            def settimeout(self,_):pass
            def makefile(self,_):return BytesIO()
            def sendall(self,data):sent.append(data);raise BrokenPipeError('closed')
            def close(self):pass
        transport=Transport()
        with patch.object(controls,'open_remote_socket',side_effect=lambda *_a,**_kw:Socket()):
            with self.assertRaisesRegex(ControlError,'本次输入未重发'):transport.call({'action':'webpad_state','owner':'test-page','frame':{'buttons':['start']}})
        self.assertEqual(len(sent),1);self.assertIsNone(transport.peer)

if __name__=='__main__':unittest.main()
