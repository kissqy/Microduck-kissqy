"""Local WSL SSH test isolation, trusted keys and server settings recovery."""
import base64
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import training_console as console
from training.remote_ssh import RemoteTraining, validate_connection, ssh_argv
from training import wsl_ssh_test as wsl

ROOT=Path(console.__file__).parent

class WslSSHTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.manager=console.TrainingManager(directory=Path(self.temp.name))
        self.remote=RemoteTraining(self.manager.directory,ROOT,self.manager,console.save_json)
    def tearDown(self):
        self.remote.close();self.manager.close();self.temp.cleanup()
    def connection(self):
        return dict(host='127.0.0.1',user='tester',port=22122,identity='/test key',known_hosts='/trusted host',workspace='~/microduck-training-ssh-wsl-test',wsl_distro='Ubuntu')
    def test_same_deployment_path_preserves_existing_server_and_local_jobs(self):
        self.remote.connection=validate_connection(dict(host='seoul.example.org',port=2222))
        self.remote._connect=Mock(side_effect=lambda operation:setattr(self.remote,'operation',None))
        with patch('training.remote_ssh.sys.platform','win32'),patch('training.remote_ssh.threading.Thread'):
            state=self.remote.start_wsl_test({'distro':'Ubuntu'})
        self.assertEqual(state['target'],'ssh');self.assertTrue(state['busy']);self.assertTrue(state['has_server_backup'])
        with patch('training.wsl_ssh_test.prepare',return_value=self.connection()) as prepare:
            self.remote._wsl_test('Ubuntu')
        prepare.assert_called_once();self.remote._connect.assert_called_once_with('deploy')
        self.assertEqual(self.remote.connection['wsl_distro'],'Ubuntu');self.assertFalse(self.manager.jobs)
        state=self.remote.restore_server()
        self.assertEqual(state['connection']['host'],'seoul.example.org');self.assertEqual(state['connection']['port'],2222)
        self.assertEqual(state['target'],'ssh');self.assertEqual(state['status'],'disconnected')
    def test_setup_failure_never_launches_or_falls_back(self):
        self.remote.target='ssh';self.remote.operation='wsl_test'
        with patch('training.wsl_ssh_test.prepare',side_effect=ValueError('WSL unavailable')):
            self.remote._wsl_test('Ubuntu')
        self.assertEqual(self.remote.status,'failed');self.assertEqual(self.remote.target,'ssh')
        self.assertIsNone(self.remote.operation);self.assertFalse(self.manager.jobs)
    def test_save_preserves_private_keys_and_manual_host_change_clears_test_metadata(self):
        self.remote.connection=validate_connection(self.connection())
        same={k:v for k,v in self.connection().items() if k not in ('known_hosts','wsl_distro')}
        self.remote.configure({'connection':same})
        self.assertEqual(self.remote.connection['known_hosts'],'/trusted host')
        self.remote.configure({'connection':{**same,'host':'seoul.example.org'}})
        self.assertEqual(self.remote.connection['known_hosts'],'');self.assertEqual(self.remote.connection['wsl_distro'],'')
    def test_trusted_host_file_with_spaces_is_passed_as_one_quoted_option(self):
        known=Path(self.temp.name)/'host keys';known.write_text('trusted key')
        connection=validate_connection(dict(host='127.0.0.1',known_hosts=str(known)))
        with patch('training.remote_ssh.shutil.which',return_value='ssh'):
            argv=ssh_argv(connection)
        self.assertIn('UserKnownHostsFile="'+str(known)+'"',argv)
        self.assertIn('StrictHostKeyChecking=yes',argv)
    def test_windows_preparation_uses_selected_distro_and_gets_host_key_through_wsl(self):
        argv=[]
        def run(command,timeout=30):
            argv.append(command)
            if command[-2:]==['id','-un']:return b'tester\n'
            if command[0].endswith('ssh-keygen'):
                identity=Path(command[command.index('-f')+1]);identity.write_text('fixture key');Path(str(identity)+'.pub').write_text('ssh-ed25519 QUJD fixture')
                return b''
            payload=json.loads(base64.b64decode(command[-1]))
            self.assertEqual(payload['user'],'tester');self.assertEqual(payload['public_key'],'ssh-ed25519 QUJD fixture')
            return b'MICRODUCK_WSL_SSH {"port":22122,"user":"tester","host_key":"ssh-ed25519 QUJD","workspace":"~/microduck-training-ssh-wsl-test"}\n'
        sock=Mock();sock.__enter__=Mock(return_value=sock);sock.__exit__=Mock();sock.recv.return_value=b'SSH-2.0-test\r\n'
        with patch('training.wsl_ssh_test.sys.platform','win32'),patch('training.wsl_ssh_test.shutil.which',side_effect=lambda name:name),patch('training.wsl_ssh_test.run',side_effect=run),patch('training.wsl_ssh_test.socket.create_connection',return_value=sock):
            result=wsl.prepare(self.manager.directory,ROOT,'Ubuntu-24.04',Mock())
        self.assertEqual(result['wsl_distro'],'Ubuntu-24.04');self.assertEqual(result['host'],'127.0.0.1')
        self.assertEqual(Path(result['known_hosts']).read_text(),'[127.0.0.1]:22122 ssh-ed25519 QUJD\n')
        self.assertIn('--user',argv[-1]);self.assertIn('root',argv[-1]);self.assertIn('Ubuntu-24.04',argv[-1])
    def test_wrong_host_key_is_rejected_before_connecting(self):
        # A shell name or untrusted key cannot enter the SSH connection settings.
        for name in ['-x','Ubuntu;id','Ubuntu\n']:
            with self.assertRaises(ValueError):wsl.validate_distro(name)
        bad=self.connection();bad['host']='seoul.example.org'
        with self.assertRaises(ValueError):validate_connection(bad)
        with self.assertRaises(ValueError):self.remote.start_wsl_test({'distro':'Ubuntu'})
        self.assertEqual(wsl.text_output('Ubuntu'.encode('utf-16')),'Ubuntu')

if __name__=='__main__':unittest.main()
