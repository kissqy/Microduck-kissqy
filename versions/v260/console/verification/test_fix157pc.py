"""Regression checks for v157 PC connection handoff, removal and concise logs."""
import json
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from telemetry import Store
from raw_telemetry import Hub,raw_loop
from remote_input import Input,Robot,ActionRefused,AXES
from controls import Transport,ControlError
from service_control import ServiceController,validate
from system_log import SystemLog

class HandoffTests(unittest.TestCase):
    def test_endpoint_reset_clears_old_errors_and_samples_preserves_tof(self):
        store=Store('service')
        store.ingest({'channel':'tof','data':{'seq':1}})
        store.ingest({'channel':'startup','data':{'steps':{'4':{'status':'success'}}}})
        store.ingest({'channel':'bus','data':{'mode':'motion','cycle':100,'last_sample':{'cycle':100}}})
        store.ingest({'channel':'state','error':'old daemon EOF'})
        store.ingest({'channel':'robotd_stream','data':{'status':'waiting'}})
        self.assertEqual(store.data,{'tof':{'seq':1}})
        self.assertEqual(store.peek()['channels']['state']['status'],'waiting')
        self.assertFalse(store.peek()['service_sample_fresh'])
        report={'steps':{'2':{'status':'waiting','detail':'等待有效 IMU'}}}
        store.ingest({'channel':'startup','data':report})
        self.assertEqual(store.peek()['startup'],report)
        self.assertFalse(store.peek()['service_sample_fresh'])
    def test_hub_does_not_replay_old_robot_metadata_after_handoff(self):
        hub=Hub();gen=hub.generation
        hub.raw(b'xxxx\x01old',gen);hub.raw(b'xxxx\x03tof',gen,metadata=True)
        hub.event({'channel':'startup','data':{'steps':{}}},gen)
        hub.event({'channel':'robotd_stream','data':{'status':'waiting'}},gen)
        self.assertEqual(hub.generation,gen)
        q=hub.subscribe();messages=[]
        while not q.empty():messages.append(q.get())
        self.assertEqual([data for op,data in messages if op==2],[b'xxxx\x03tof'])
        hub.raw(b'xxxx\x01new',gen)
        self.assertEqual(q.get(),(2,b'xxxx\x01new'))
    def test_restart_keeps_healthy_input_channel_and_audio_read(self):
        t=Transport();channel=Mock(error='');channel.request.return_value={'accepted':True,'available':True}
        t.input_channel=channel;t.audio_requested=True
        with patch.object(t,'_load_audio_once') as audio:
            result=t.reconnect_after_service()
        self.assertTrue(result['available']);self.assertIs(t.input_channel,channel)
        channel.request.assert_called_once_with({'action':'reset'});channel.close.assert_not_called()
        self.assertTrue(t.audio_requested)
    def test_remote_reset_clears_input_and_old_ipc_without_action_edges(self):
        robot=Mock();control=Input(robot);control.owner='webpage-test';control.previous={'select'};control.select_at=0
        control.bindings={'rb':'old'}
        result=control.command({'action':'reset'})
        self.assertTrue(result['accepted']);self.assertIsNone(control.owner);self.assertIsNone(control.bindings)
        robot.close.assert_called_once();robot.request.assert_not_called()
        calls=robot.notify.call_args.args[0]
        self.assertFalse(any(method in {'robot.relax','robot.shutdown','robot.enable','robot.init'} for method,_ in calls))
    def test_legitimate_refusal_keeps_same_framed_connection_for_next_request(self):
        with tempfile.TemporaryDirectory() as directory:
            # This executor forbids AF_UNIX; substitute loopback TCP only at the
            # socket boundary, exercising the production request/framing methods.
            factory=socket.socket;server=factory(socket.AF_INET);server.bind(('127.0.0.1',0));server.listen();path=server.getsockname()
            substitute=lambda family=socket.AF_INET,*args,**kwargs:factory(socket.AF_INET if family==socket.AF_UNIX else family,*args,**kwargs)
            boundary=patch('remote_input.socket.socket',side_effect=substitute);boundary.start()
            received=[]
            def serve():
                peer,_=server.accept()
                with peer,peer.makefile('rb') as reader:
                    for index in range(2):
                        row=json.loads(reader.readline());received.append(row)
                        answer={'id':row['id'],'error':{'message':'the policy is not driving'}} if index==0 else {'id':row['id'],'result':{'accepted':True}}
                        peer.sendall((json.dumps(answer)+'\n').encode())
            thread=threading.Thread(target=serve);thread.start();robot=Robot(path)
            try:
                with self.assertRaisesRegex(ActionRefused,'not driving'):robot.request('robot.do',{'skill':'kick_right'})
                old=robot.peer
                self.assertTrue(robot.request('robot.sound',{'tag':'chirp'})['accepted'])
                self.assertIs(robot.peer,old)
            finally:robot.close();thread.join(2);server.close();boundary.stop()
            self.assertEqual(len(received),2)
    def test_production_raw_handoff_suppresses_expected_eof_but_preserves_real_failures(self):
        import raw_telemetry as raw
        from ssh_connect import SSHConnectError
        class Stop:
            ended=False
            def is_set(self):return self.ended
            def wait(self,_):self.ended=True;return True
        class Worker:
            def __init__(self,*args,**kwargs):pass
            def start(self):pass
            def join(self,**kwargs):pass
        class Stream:
            def __init__(self,tail=b''):
                self.data=bytearray(json.dumps({'id':1,'result':{'accepted':True,'schema':'r17.raw.v1','framing':'u32le'}}).encode()+b'\n'+tail)
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def settimeout(self,_):pass
            def sendall(self,_):pass
            def recv(self,size):result=bytes(self.data[:size]);del self.data[:size];return result
        for restart,error,tail in [(True,None,b''),(False,None,b''),(True,SSHConnectError('Permission denied'),b''),(True,None,struct.pack('<I',0))]:
            stop=Stop();hub=Hub();events=[];guard=threading.Event()
            if restart:guard.set()
            startup=Stream();startup.data=bytearray(json.dumps({'id':1,'result':{'steps':{str(n):{'status':'success','detail':'ready'} for n in range(1,5)}}}).encode()+b'\n')
            opener=Mock(side_effect=error) if error else Mock(side_effect=[startup,Stream(tail)])
            with patch('socket_transport.open_remote_socket',opener),patch.object(raw.threading,'Thread',Worker):
                raw_loop('duck',{'hub':hub,'robotd_socket':'robot','tofd_socket':'tof','robotd_restarting':guard},events.append,stop)
            errors=[e for e in events if 'error' in e]
            if restart and error is None and not tail:
                self.assertFalse(errors);self.assertTrue(any(e['channel']=='robotd_stream' for e in events))
            else:self.assertTrue(errors)

    def test_removed_shortcut_is_rejected_but_remote_rb_mapping_remains(self):
        with self.assertRaises(ControlError) as failure:validate({'action':'run-skill','name':'kick_right','supported':True})
        self.assertEqual(failure.exception.status,400)
        source=Path(__file__).resolve().parents[1]
        for name in ['service_control.py','service_rpc.py','static/service-management.js','static/service.js']:
            text=(source/name).read_text();self.assertNotIn('run-skill',text);self.assertNotIn('management-kick-right',text)
        self.assertIn("intent('robot.do', {'skill':skill})",(source/'remote_input.py').read_text())
    def test_failed_input_cleanup_does_not_gate_main_restart(self):
        store=Store('service');store.system_log=Mock();controls=Mock();controls.pause_input.side_effect=OSError('input unavailable')
        transport=Mock();transport.switch_mode.return_value={'accepted':True,'message':'motion'}
        service=ServiceController(store,transport=transport,controls=controls,warm=False)
        job={'status':'running','action':'switch-mode'}
        with patch.object(service,'_start_input_recovery') as recover:
            service._execute({'action':'switch-mode','target':'motion'},job,0)
        self.assertEqual(job['status'],'completed');transport.switch_mode.assert_called_once()
        self.assertFalse(store.robotd_restarting.is_set());recover.assert_called_once()
        store.system_log.add.assert_any_call('服务操作','服务模式切换：请求已完成；服务启动结果见 robotd 启动 1/4～4/4')

class LogTests(unittest.TestCase):
    def test_all_sources_and_repeated_stages_remain_visible_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            log=SystemLog(directory);log.hide('secret-test')
            try:
                rows=[('SSH 输出','huge model JSON secret-test'),('SSH 命令结束','退出码 0'),
                      ('robotd 启动 2/4','等待 · 等待 IMU'),('robotd 启动 2/4','成功 · 首次有效反馈'),
                      ('robotd 启动 2/4','成功 · 硬件就绪'),('服务操作错误','启动失败：原始原因 secret-test'),
                      ('robotd 本次开机日志','ordinary startup journal'),('手柄长连接','连接已开启')]
                for source,text in rows:log.add(source,text)
                log.flush();output=log.path.read_text();page=log.tail()
                self.assertEqual(len(page['entries']),len(rows));self.assertEqual(page['cursor'],len(rows))
                self.assertFalse(page['has_more']);self.assertEqual(output.count('[robotd 启动 2/4]'),3)
                for source,text in rows:self.assertIn(text.replace('secret-test','[已隐藏]'),output)
                self.assertNotIn('secret-test',output+json.dumps(page));self.assertEqual(len(list(Path(directory).glob('*.log'))),1)
            finally:log.close()
            self.assertTrue(log.stream.closed);self.assertFalse(log.worker.is_alive())

    def test_real_management_relay_retains_full_output_in_shared_log(self):
        from service_control import ServiceTransport
        with tempfile.TemporaryDirectory() as directory:
            log=SystemLog(directory);transport=ServiceTransport('', '/unused',log)
            try:
                transport._manage([sys.executable,'-u','-c',"[print('x'*8193) for _ in range(70)];print('INSTALL-END-MARKER')"],privileged=False)
                log.flush();output=log.path.read_text()
                self.assertGreater(len(output),512*1024);self.assertIn('INSTALL-END-MARKER',output);self.assertIn('退出码 0',output)
                page=log.tail(limit=400)
                self.assertTrue(any('INSTALL-END-MARKER' in row['text'] for row in page['entries']))
            finally:transport.channel.close();log.close()

    def test_complete_download_with_old_detail_query_compatibility(self):
        from http.server import ThreadingHTTPServer
        from urllib.request import urlopen
        from console import handler_for
        with tempfile.TemporaryDirectory() as directory:
            store=Store('service');log=store.system_log=SystemLog(directory)
            log.add('SSH 输出','FULL-OUTPUT');log.add('服务操作','FLOW')
            server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(store,{'bind':'127.0.0.1'},None,None))
            server.daemon_threads=True;thread=threading.Thread(target=server.serve_forever);thread.start()
            try:
                base='http://127.0.0.1:'+str(server.server_port)+'/api/system-log/download'
                output=urlopen(base).read();old_link=urlopen(base+'?detail=1').read()
                self.assertIn(b'FLOW',output);self.assertIn(b'FULL-OUTPUT',output);self.assertEqual(output,old_link)
            finally:server.shutdown();server.server_close();thread.join();log.close()

if __name__=='__main__':unittest.main()
