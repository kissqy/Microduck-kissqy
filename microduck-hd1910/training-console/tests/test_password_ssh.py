"""Credential privacy, persistence compatibility and host confirmation binding."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import training_console as c
from training.remote_ssh import RemoteTraining,validate_connection

class PasswordTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.manager=c.TrainingManager(directory=Path(self.temp.name))
        self.remote=RemoteTraining(self.manager.directory,c.ROOT,self.manager,c.save_json)
    def tearDown(self):
        self.remote.close();self.manager.close();self.temp.cleanup()
    def configure(self,**changes):
        self.remote.configure({'connection':{'host':'seoul.example.org','user':'ubuntu','auth':'password',**changes},'password':'fixture %& " spaces 中文'})
    def test_password_never_enters_saved_connection_or_state(self):
        self.configure()
        secret=self.remote.passwords[self.remote.password_id()]
        self.assertTrue(self.remote.snapshot()['password_available'])
        self.assertNotIn(secret,json.dumps(self.remote.snapshot()))
        self.assertNotIn(secret,(self.manager.directory/'remote_connection.json').read_text())
        restored=RemoteTraining(self.manager.directory,c.ROOT,self.manager,c.save_json)
        self.assertEqual(restored.connection['auth'],'password')
        self.assertFalse(restored.snapshot()['password_available'])
        with self.assertRaisesRegex(ValueError,'重新输入'):restored.start('connect')
    def test_blank_password_keeps_session_secret_but_another_endpoint_does_not_reuse_it(self):
        self.configure();first=self.remote.passwords[self.remote.password_id()]
        self.remote.configure({'connection':self.remote.connection,'password':''})
        self.assertEqual(self.remote.passwords[self.remote.password_id()],first)
        self.remote.configure({'connection':{**self.remote.connection,'port':2222},'password':''})
        self.assertFalse(self.remote.snapshot()['password_available'])
        with self.assertRaisesRegex(ValueError,'请输入SSH'):self.remote.start('connect')
    def test_unknown_host_confirmation_is_bound_to_exact_endpoint_and_fingerprint(self):
        self.configure()
        pending={'details':{'fingerprint':'SHA256:fixture','hostname':'seoul.example.org','key_type':'ssh-ed25519','key':'QUJD'},'connection':dict(self.remote.connection),'operation':'deploy'}
        self.remote.pending_host=pending
        with self.assertRaisesRegex(ValueError,'确认不一致'):self.remote.trust_pending_host({'fingerprint':'wrong'})
        with patch('training.password_ssh.trust_host') as trust,patch.object(self.remote,'start',return_value={'busy':True}) as start:
            self.remote.trust_pending_host({'fingerprint':'SHA256:fixture'})
            trust.assert_called_once();start.assert_called_once_with('deploy')
        self.assertIsNone(self.remote.pending_host)
        self.remote.pending_host=pending
        self.remote.configure({'connection':{**self.remote.connection,'host':'another.example.org'}})
        with self.assertRaises(ValueError):self.remote.trust_pending_host({'fingerprint':'SHA256:fixture'})
    def test_failure_secret_is_redacted_and_target_never_falls_back(self):
        self.configure();secret=self.remote.passwords[self.remote.password_id()]
        self.remote.target='ssh';self.remote.operation='connect'
        with patch('training.password_ssh.PasswordClient',side_effect=ValueError('connection '+secret)):
            self.remote._connect('connect')
        self.assertEqual(self.remote.status,'failed');self.assertEqual(self.remote.target,'ssh')
        self.assertNotIn(secret,self.remote.message);self.assertFalse(self.manager.jobs)
    def test_old_saved_connection_keeps_key_login(self):
        c.save_json(self.manager.directory/'remote_connection.json',{'target':'ssh','connection':{'host':'example.org','user':'ubuntu','port':22,'identity':'','workspace':'~/training'}})
        restored=RemoteTraining(self.manager.directory,c.ROOT,self.manager,c.save_json)
        self.assertEqual(restored.connection['auth'],'key')
        self.assertEqual(restored.target,'ssh')
    def test_close_forgets_password_and_does_not_touch_training_jobs(self):
        self.configure();self.remote.close()
        self.assertFalse(self.remote.passwords);self.assertFalse(self.manager.jobs)
    def test_bad_auth_and_invalid_password_rejected(self):
        with self.assertRaises(ValueError):validate_connection({'host':'example.org','auth':'other'})
        with self.assertRaises(ValueError):self.remote.configure({'connection':{'host':'example.org'},'password':'bad\x00value'})

if __name__=='__main__':unittest.main()
