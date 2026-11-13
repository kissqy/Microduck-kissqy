import json
import io
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import threading
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import startup_diagnostic as diag
from service_control import ServiceController,ServiceTransport
from controls import ControlError
from console import handler_for

class DiagnosticTests(unittest.TestCase):
    def test_partial_command_errors_are_saved_and_next_sections_are_still_collected(self):
        def run(args,**kwargs):
            self.assertEqual(kwargs['timeout'],5)
            if args[:2]==['fuser','/dev/ttyS2']:raise subprocess.TimeoutExpired(args,5)
            return SimpleNamespace(returncode=1 if '-1' in args else 0,stdout='snapshot',stderr='')
        with patch.object(diag.subprocess,'run',side_effect=run) as commands,patch.object(Path,'read_text',return_value='read-only'):
            report=diag.collect()['diagnostic']
        self.assertEqual(len(report['sections']),len(diag.COMMANDS)+4)
        self.assertIn('error',report['sections'][1])
        self.assertEqual(report['sections'][8]['exit_code'],1)
        self.assertEqual(commands.call_count,len(diag.COMMANDS))
        for _,args in diag.COMMANDS:
            self.assertFalse(set(args)&{'start','stop','restart','enable','disable','power','scan','connect','pair'})

    def test_ssh_service_state_listeners_and_boot_log_are_collected_without_mutations(self):
        def run(args, **kwargs):
            self.assertEqual(kwargs['timeout'], 5)
            if args == ['ss', '-ltnp']:
                return SimpleNamespace(returncode=0, stdout='LISTEN 0 128 0.0.0.0:22 users:(("sshd",pid=777,fd=3))', stderr='')
            if args == diag.COMMANDS[10][1]:
                return SimpleNamespace(returncode=0, stdout='[12.123] sshd[777]: Server listening on 0.0.0.0 port 22.', stderr='')
            return SimpleNamespace(returncode=0, stdout='Id=ssh.service\nActiveState=active', stderr='')
        with patch.object(diag.subprocess, 'run', side_effect=run) as commands, patch.object(Path, 'read_text', return_value='read-only'):
            report = diag.collect()['diagnostic']
        services = diag.COMMANDS[0][1]
        self.assertIn('ssh.service', services)
        self.assertIn('sshd.service', services)
        self.assertEqual(diag.COMMANDS[8][0], 'previous_kernel_log')
        self.assertEqual(len(diag.COMMANDS), 11)
        sections = {section['name']: section for section in report['sections']}
        self.assertIn('ActiveState=active', sections['services']['text'])
        self.assertIn('0.0.0.0:22', sections['listening_sockets']['text'])
        self.assertIn('Server listening', sections['ssh_boot_log']['text'])
        self.assertEqual(commands.call_count, 11)
        self.assertEqual(diag.COMMANDS[10][1], ['journalctl', '-b', '-u', 'ssh.service', '-u', 'sshd.service', '-n', '80', '--no-pager', '-o', 'short-monotonic'])

    def test_export_does_not_create_motion_jobs_suspend_inputs_or_require_live_imu(self):
        store=SimpleNamespace(service_operation=False,connection_paused=threading.Event())
        transport=Mock();transport.diagnose_service.return_value={'diagnostic':{'schema':'test'}}
        controls=Mock();controller=ServiceController(store,transport=transport,controls=controls)
        self.assertIn('diagnostic',controller.diagnose({'sudo_password':'secret'}))
        self.assertFalse(controller.busy);self.assertFalse(store.service_operation)
        self.assertIsNone(controller.job);self.assertEqual(controls.mock_calls,[])
        transport.diagnose_service.assert_called_once_with(password='secret')
        with self.assertRaises(ControlError):controller.diagnose({'command':'reboot'})
        controller.busy=True
        with self.assertRaises(ControlError):controller.diagnose({})

    def test_transport_embeds_read_only_helper_and_keeps_password_out_of_command(self):
        transport=ServiceTransport('radxa@192.168.6.151','/run/robotd.sock')
        with patch.object(transport,'_manage',return_value={'diagnostic':{}}) as manage:
            transport.diagnose_service(password='secret')
        self.assertEqual(manage.call_args.args[0][:3],['python3','-u','-c'])
        self.assertNotIn('secret',repr(manage.call_args.args[0]))

    def test_http_export_requires_same_origin_token_and_active_ssh(self):
        service=Mock();service.diagnose.return_value={'diagnostic':{'schema':'test'}}
        connection=SimpleNamespace(active=False)
        Handler=handler_for(Mock(),{'bind':'127.0.0.1','control_token':'token','service_enabled':True},service_controller=service,connection=connection)
        def request(origin='http://127.0.0.1:8765',token='token'):
            handler=Handler.__new__(Handler);handler.path='/api/service/diagnostic'
            headers=Message()
            for key,value in {'Host':'127.0.0.1:8765','Origin':origin,'X-Control-Token':token,'Content-Type':'application/json','Content-Length':'2'}.items():headers[key]=value
            handler.headers=headers;handler.rfile=io.BytesIO(b'{}');handler.connection=Mock();handler.reply=Mock()
            handler.do_POST();return handler.reply.call_args
        self.assertEqual(request().args[1],503);service.diagnose.assert_not_called()
        connection.active=True
        self.assertEqual(request(origin='http://untrusted').args[1],403)
        self.assertEqual(request(token='wrong').args[1],403);service.diagnose.assert_not_called()
        self.assertIn('diagnostic',request().args[0]);service.diagnose.assert_called_once_with({})

if __name__=='__main__':unittest.main()
