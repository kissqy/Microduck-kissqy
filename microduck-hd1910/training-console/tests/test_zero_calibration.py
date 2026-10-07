"""ZERO import: real local SSH-process boundary, HTTP concurrency, persisted data."""
import copy
import json
import os
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import training_console as tc
from training import zero_calibration as zero


class ZeroCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.manager=tc.TrainingManager(self.root/'MicroduckTrainingStudio')
        self.addCleanup(self.manager.close)
        self.before=copy.deepcopy(self.manager.recipe)
        self.cal=copy.deepcopy(self.before['calibration']['data'])
        self.cal['joints'][0]['zero_raw']+=12
        self.cal['imu_mount_quat']=[1,0,0,0]
        # JSON is accepted in the test only through a TOML fixture generated here.
        self.text='imu_mount_verified = true\nimu_mount_quat = [1,0,0,0]\n'
        for joint in self.cal['joints']:
            self.text+='\n[[joints]]\n'+''.join(k+' = '+json.dumps(v)+'\n' for k,v in joint.items())

    def test_import_survives_restart_and_preserves_training_snapshot_and_environment(self):
        self.manager.environment={'ready':True,'status':'ready','tasks':['unchanged']}
        self.manager.jobs['running']={'id':'running','op':'train','status':'running',
                                      'request':{'studio_recipe':copy.deepcopy(self.before)}}
        with patch.object(zero,'read_calibration',return_value=self.text) as reader,patch.object(self.manager,'launch') as launch:
            result=self.manager.import_zero_calibration({'target':'192.168.6.151'})
        reader.assert_called_once_with('radxa@192.168.6.151');launch.assert_not_called()
        self.assertEqual(result['count'],15)
        self.assertEqual(len(result['changes']['joints']),1)
        self.assertTrue(result['changes']['imu_changed'])
        self.assertEqual(result['changes']['joints'][0]['fields']['zero_raw']['before'],2035)
        self.assertEqual(self.manager.recipe['calibration']['data']['joints'][0]['zero_raw'],2047)
        self.assertEqual(self.manager.jobs['running']['request']['studio_recipe'],self.before)
        self.assertEqual(self.manager.environment,{'ready':True,'status':'ready','tasks':['unchanged']})
        self.assertEqual(self.manager.recipe['robot'],self.before['robot'])
        restored=tc.TrainingManager(self.manager.directory)
        self.addCleanup(restored.close)
        self.assertEqual(restored.recipe['calibration'],result['calibration'])
        self.assertEqual(restored.zero_connection['target'],'radxa@192.168.6.151')
        # Delayed autosave from another page cannot undo new zeros.
        self.manager.save_recipe({'recipe':self.before})
        self.assertEqual(self.manager.recipe['calibration'],result['calibration'])

    def test_reuses_runtime_console_target_with_own_saved_target_taking_priority(self):
        console=self.root/'MicroduckConsole';console.mkdir()
        (console/'connection.json').write_text(json.dumps({'last_target':'radxa@192.168.6.151'}))
        self.assertEqual(zero.load_connection(self.manager.directory),{'target':'radxa@192.168.6.151','source':'运行中控'})
        (self.manager.directory/'zero_connection.json').write_text(json.dumps({'target':'10.0.0.2'}))
        self.assertEqual(zero.load_connection(self.manager.directory)['target'],'radxa@10.0.0.2')

    def test_invalid_or_failed_read_does_not_replace_calibration(self):
        for response in ('not toml', 'imu_mount_quat = [1,0,0,0]', self.text.replace('zero_raw = 2047','zero_raw = 9000')):
            with self.subTest(response=response[:35]),patch.object(zero,'read_calibration',return_value=response):
                with self.assertRaises(ValueError):self.manager.import_zero_calibration({'target':'duck-10e4'})
            self.assertEqual(self.manager.recipe,self.before)
        with patch.object(zero,'read_calibration',side_effect=ValueError('连接超时')):
            with self.assertRaisesRegex(ValueError,'超时'):self.manager.import_zero_calibration({'target':'duck-10e4'})
        self.assertEqual(self.manager.recipe,self.before)

    def test_slow_read_does_not_block_state_and_concurrent_import_is_not_overwritten(self):
        entered=threading.Event();release=threading.Event();failures=[]
        def read(_):
            entered.set();self.assertTrue(release.wait(3));return self.text
        def fetch():
            try:self.manager.import_zero_calibration({'target':'duck-10e4'})
            except ValueError as error:failures.append(str(error))
        with patch.object(zero,'read_calibration',side_effect=read):
            worker=threading.Thread(target=fetch);worker.start()
            try:
                self.assertTrue(entered.wait(1))
                self.assertTrue(self.manager.lock.acquire(timeout=.2));self.manager.lock.release()
                with self.assertRaisesRegex(ValueError,'正在'):self.manager.import_zero_calibration({'target':'duck-10e4'})
                alternate=copy.deepcopy(self.cal);alternate['joints'][0]['zero_raw']=2111
                self.manager.import_calibration({'name':'local.json','text':json.dumps(alternate)})
            finally:release.set();worker.join(2)
        self.assertTrue(any('其他操作' in error for error in failures))
        self.assertEqual(self.manager.recipe['calibration']['data']['joints'][0]['zero_raw'],2111)

    def test_connection_input_rejects_shell_and_option_injection(self):
        for target in ['--proxycommand=id','user@a;whoami','a\nwhoami','user@$(id)','a@b@c','999.0.0.1','',None]:
            with self.subTest(target=target),self.assertRaises(ValueError):zero.normalize_target(target)

    @unittest.skipIf(os.name=='nt','POSIX test executable')
    def test_real_subprocess_reads_only_fixed_file_and_has_no_interactive_prompt(self):
        binary=self.root/'ssh'
        binary.write_text('#!/usr/bin/env python3\nimport sys,json\n'
                          'assert sys.argv[-1]=='+repr('head -c '+str(zero.MAX_BYTES+1)+' -- '+zero.CALIBRATION_PATH)+'\n'
                          "assert 'StrictHostKeyChecking=yes' in sys.argv\n"
                          "assert 'BatchMode=yes' in sys.argv\n"
                          "assert sys.stdin.read()==''\n"
                          'sys.stdout.write('+repr(self.text)+')\n')
        binary.chmod(0o700)
        with patch.object(zero.shutil,'which',return_value=str(binary)):
            actual=zero.read_calibration('radxa@duck-10e4')
        self.assertEqual(actual,self.text)

    def test_timeout_auth_and_size_errors_are_bounded_and_readable(self):
        with patch.object(zero.shutil,'which',return_value='/usr/bin/ssh'):
            with patch.object(zero.subprocess,'run',side_effect=subprocess.TimeoutExpired('ssh',15)):
                with self.assertRaisesRegex(ValueError,'15秒'):zero.read_calibration('duck-10e4')
            for code,out,err,match in [(255,b'',b'Permission denied (publickey).','密钥'),
                                       (0,b'x'*(zero.MAX_BYTES+1),b'','256KB'),
                                       (0,b'\xff',b'','UTF-8'),(0,b'',b'','为空')]:
                with patch.object(zero.subprocess,'run',return_value=subprocess.CompletedProcess([],code,out,err)):
                    with self.assertRaisesRegex(ValueError,match):zero.read_calibration('duck-10e4')

    def test_http_import_uses_existing_token_and_does_not_need_environment_ready(self):
        server=tc.ThreadingHTTPServer(('127.0.0.1',0),tc.handler_for(self.manager,'test-token'))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        url='http://127.0.0.1:'+str(server.server_port)+'/api/calibration/zero'
        headers={'Content-Type':'application/json','X-Training-Token':'test-token'}
        request=urllib.request.Request(url,data=b'{"target":"duck-10e4"}',headers=headers)
        with patch.object(zero,'read_calibration',return_value=self.text):
            with urllib.request.urlopen(request,timeout=2) as reply:result=json.load(reply)
        self.assertTrue(result['okay']);self.assertEqual(result['count'],15)
        request=urllib.request.Request(url,data=b'{"target":"duck-10e4"}',headers={'Content-Type':'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request,timeout=2)
        self.assertEqual(error.exception.code,403)


if __name__=='__main__':unittest.main()
