"""Motion shutdown retains Select behavior after reading the actual mode."""
import json
from pathlib import Path
import socket
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import power_control
import service_rpc
from controls import ControlError
from service_control import ServiceController, ServiceTransport, validate
from telemetry import Store

NATIVE_REPLY = {'id': 1, 'result': {'accepted': True}}
RECEIPT = {'accepted': True, 'shutdown_requested': True,
           'shutdown_path': 'robot.shutdown',
           'message': '官方关机请求已接收；尚未确认已关机'}


class InlineThread:
    def __init__(self, target, args=(), **_): self.target, self.args = target, args
    def start(self): self.target(*self.args)


class PairSocket:
    def __init__(self, stream): self.stream = stream; self.path = None
    def __enter__(self): return self
    def __exit__(self, *_): self.stream.close()
    def connect(self, path): self.path = path
    def settimeout(self, value): self.stream.settimeout(value)
    def sendall(self, data): self.stream.sendall(data)
    def makefile(self, mode): return self.stream.makefile(mode)


class PairChannel:
    """Real AF_UNIX bytes; connect is replaced because socketpair is connected."""
    def __init__(self, reply=NATIVE_REPLY): self.reply=reply; self.requests=[]; self.wire=[]
    def request(self, request, **_):
        self.requests.append(request)
        client, server = socket.socketpair()
        connected = PairSocket(client)
        errors=[]
        def native():
            try:
                with server, server.makefile('rb') as reader:
                    self.wire.append(json.loads(reader.readline()))
                    server.sendall((json.dumps(self.reply)+'\n').encode())
            except Exception as error: errors.append(error)
        worker=threading.Thread(target=native);worker.start()
        try:
            with patch.object(service_rpc.socket,'socket',return_value=connected), \
                 patch.object(service_rpc.sys,'argv',['service_rpc.py','/fixture/robotd.sock']):
                result=service_rpc.execute(request)
        finally:
            client.close();worker.join(2)
        if worker.is_alive(): raise AssertionError('native fixture did not finish')
        if errors: raise errors[0]
        if connected.path!='/fixture/robotd.sock':raise AssertionError('wrong native socket')
        return result


class NativeShutdownTests(unittest.TestCase):
    def transport(self, reply=NATIVE_REPLY):
        transport=ServiceTransport.__new__(ServiceTransport)
        transport.log=None;transport.path='/fixture/robotd.sock'
        class MotionChannel(PairChannel):
            def request(self, request, **kwargs):
                original = self.reply
                if request.get('method') == 'robot.busStatus':
                    self.reply = {'id':1, 'result':{'mode':'motion'}}
                try:return super().request(request, **kwargs)
                finally:self.reply = original
        transport.channel=MotionChannel(reply)
        transport._manage=Mock(side_effect=AssertionError('shutdown must not execute an OS or sound command'))
        transport.credential=Mock()
        return transport

    def test_shutdown_crosses_the_real_relay_with_physical_select_method(self):
        transport=self.transport()
        receipt=transport.power('shutdown',password='must-not-be-sent')
        self.assertIs(receipt['accepted'],True)
        self.assertIs(receipt['shutdown_requested'],True)
        self.assertEqual(receipt['shutdown_path'],'robot.shutdown')
        self.assertNotIn('scheduled',receipt)
        self.assertIn('尚未确认',receipt['message'])
        self.assertEqual(transport.channel.wire,[{'jsonrpc':'2.0','id':1,
                                                 'method':'robot.busStatus','params':{}},
                                                {'jsonrpc':'2.0','id':1,
                                                 'method':'robot.shutdown','params':{}}])
        self.assertEqual(len(transport.channel.requests),2)
        self.assertNotIn('must-not-be-sent',repr(transport.channel.requests))
        transport._manage.assert_not_called()
        transport.credential.get.assert_not_called()

    def test_rejected_malformed_and_disconnected_ipc_never_use_os_fallback(self):
        replies=[{'id':1,'result':{'accepted':False,'reason':'native shutdown refused'}},
                 {'id':1,'result':{}},{'id':1,'result':{'accepted':1}},
                 {'id':1,'result':True},{'id':1,'result':None},
                 {'id':1,'error':{'message':'native RPC error'}}]
        for reply in replies:
            with self.subTest(reply=reply):
                transport=self.transport(reply)
                with self.assertRaises(ControlError):transport.power('shutdown')
                self.assertEqual(len(transport.channel.requests),2)
                transport._manage.assert_not_called()
        transport=self.transport();transport.channel=Mock()
        transport.channel.request.side_effect=OSError('native socket unavailable')
        with self.assertRaisesRegex(OSError,'unavailable'):transport.power('shutdown')
        transport.channel.request.assert_called_once()
        transport._manage.assert_not_called()

    def test_shutdown_does_not_grant_the_ai_lease_permission_to_power_off(self):
        with patch.object(service_rpc,'validate_ai_input_token') as validate_token, \
             patch.object(service_rpc.socket,'socket') as open_socket:
            with self.assertRaisesRegex(ValueError,'不能上力'):
                service_rpc.execute({'method':'robot.shutdown','params':{},
                                     'ai_input_token':'a'*32})
            validate_token.assert_not_called();open_socket.assert_not_called()

    def test_reboot_remains_one_privileged_os_command_and_shutdown_helper_is_closed(self):
        transport=self.transport();transport._manage=Mock(return_value={'message':''})
        result=transport.power('reboot',password='reboot-password')
        self.assertIs(result['scheduled'],True)
        transport._manage.assert_called_once_with(['/usr/bin/systemctl','--no-block','reboot'],
                                                 password='reboot-password')
        self.assertEqual(transport.channel.requests,[])
        runner=Mock()
        with self.assertRaises(ValueError):power_control.power('shutdown',runner=runner)
        runner.assert_not_called()

    def controller(self, receipt=RECEIPT, error=None):
        store=Store();store.system_log=Mock()
        transport=SimpleNamespace(power=Mock(return_value=receipt,side_effect=error),
                                  channel=SimpleNamespace(disconnect=Mock()),
                                  call=Mock(side_effect=AssertionError('no extra robot requests')))
        controls=SimpleNamespace(suspend_connections=Mock(),resume_connections=Mock(),pause_input=Mock())
        return ServiceController(store,transport=transport,controls=controls),transport,controls

    def submit(self,controller,seq=1):
        with patch('service_control.threading.Thread',InlineThread):
            return controller.handle({'client':'shutdown-ui45','seq':seq,'command':{'action':'shutdown'}})

    def test_api_shutdown_needs_no_sudo_or_imu_and_success_only_confirms_request(self):
        self.assertEqual(validate({'action':'shutdown'}),{'action':'shutdown'})
        self.assertEqual(validate({'action':'shutdown','sudo_password':'secret'})['action'],'shutdown')
        self.assertEqual(validate({'action':'reboot','sudo_password':'secret'})['action'],'reboot')
        controller,transport,controls=self.controller()
        self.assertFalse(controller.store.snapshot().get('service_sample_fresh'))
        answer=self.submit(controller)
        self.assertTrue(answer['accepted'])
        transport.power.assert_called_once_with('shutdown', password=None)
        self.assertEqual(controller.job['status'],'completed')
        self.assertEqual(controller.job['result'],RECEIPT)
        self.assertTrue(controller.store.connection_paused.is_set())
        self.assertTrue(controller.stopping)
        controls.suspend_connections.assert_called_once();controls.resume_connections.assert_not_called()
        controls.pause_input.assert_not_called();transport.call.assert_not_called()
        transport.channel.disconnect.assert_called_once()
        with self.assertRaises(ControlError):self.submit(controller,seq=2)
        transport.power.assert_called_once()

    def test_native_failure_or_ambiguous_receipt_does_not_pause_or_retry(self):
        cases=[(None,ControlError('native rejected',409)),
               (None,OSError('native disconnected')),
               ({},None),({'scheduled':True},None),
               ({'accepted':True,'shutdown_requested':1,'shutdown_path':'robot.shutdown'},None),
               ({'accepted':True,'shutdown_requested':True,'shutdown_path':'systemctl'},None)]
        for receipt,error in cases:
            with self.subTest(receipt=receipt,error=error):
                controller,transport,controls=self.controller(receipt,error)
                self.submit(controller)
                self.assertEqual(controller.job['status'],'error')
                self.assertFalse(controller.store.connection_paused.is_set())
                self.assertFalse(controller.stopping)
                controls.suspend_connections.assert_not_called()
                controls.resume_connections.assert_not_called()
                transport.channel.disconnect.assert_not_called()
                transport.power.assert_called_once_with('shutdown', password=None)
                transport.call.assert_not_called()


if __name__=='__main__':unittest.main()
