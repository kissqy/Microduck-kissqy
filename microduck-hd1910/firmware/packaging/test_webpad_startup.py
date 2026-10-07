"""A started systemd unit is insufficient: require a usable input socket."""
import importlib.util
import json
from pathlib import Path
import socket
import socketserver
import shlex
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('webpad_install_verified',Path(__file__).with_name('gamepad.py'))
gamepad=importlib.util.module_from_spec(spec);spec.loader.exec_module(gamepad)


class StartupTests(unittest.TestCase):
    def test_install_migrates_to_socket_activation_without_status_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);base=root/'bundle';base.mkdir()
            for name in ('microduck-webpad.service','microduck-webpad.socket'):
                (base/name).write_bytes(Path(__file__).with_name(name).read_bytes())
            calls=[]
            with patch.object(gamepad,'ROOT',root),patch.object(gamepad,'BASE',base),patch.object(gamepad,'run',lambda *argv,**_:calls.append(argv) or SimpleNamespace(returncode=0)),patch.object(gamepad,'webpad_socket_ready',return_value=True):
                gamepad.install_webpad();gamepad.ensure_webpad()
            self.assertIn(('systemctl','--no-reload','disable','microduck-webpad.service'),calls)
            self.assertIn(('systemctl','--no-reload','enable','microduck-webpad.socket'),calls)
            self.assertEqual(calls.count(('systemctl','restart','microduck-webpad.socket')),1)
            self.assertFalse(any(c[1] in ('start','restart') and 'microduck-webpad.service' in c for c in calls))
            self.assertTrue((root/'etc/systemd/system/microduck-webpad.socket').is_file())

    def test_socket_readiness_rejects_a_stale_regular_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'run/microduck-webpad/input.sock';path.parent.mkdir(parents=True);path.touch()
            with patch.object(gamepad,'ROOT',root),patch.object(gamepad,'run',return_value=SimpleNamespace(returncode=0)):
                self.assertFalse(gamepad.webpad_socket_ready())

    def test_missing_socket_after_start_reports_unit_and_journal_instead_of_success(self):
        with tempfile.TemporaryDirectory() as directory:
            calls=[]
            def run(*argv,**_):calls.append(argv);return SimpleNamespace(stdout='unit startup failed',stderr='')
            with patch.object(gamepad,'ROOT',Path(directory)),patch.object(gamepad,'run',run),patch.object(gamepad.time,'monotonic',side_effect=[0,5]):
                with self.assertRaisesRegex(ValueError,'网页手柄接口未启动'):gamepad.verify_webpad()
            self.assertTrue(any('status' in argv for argv in calls))
            self.assertTrue(any(argv[0]=='journalctl' for argv in calls))
    def test_restart_failure_includes_service_journal(self):
        calls=[]
        def run(*argv,**_):
            calls.append(argv)
            if 'restart' in argv:raise gamepad.subprocess.CalledProcessError(1,argv,stderr='startup failed')
            return SimpleNamespace(stdout='actual unit failure',stderr='')
        with patch.object(gamepad,'run',run):
            with self.assertRaisesRegex(ValueError,'网页手柄监听重启失败'):gamepad.restart_webpad()
        self.assertTrue(any(argv[0]=='journalctl' for argv in calls))
    def test_partial_install_failure_preserves_running_input_and_reports_stage(self):
        # Execute the real install error trap with a fake systemctl. A later
        # check can fail after padd was restarted; the pause must be restored.
        prefix=Path(__file__).with_name('service.sh').read_text().split('if [[ ${1:-} == models',1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);script=root/'service-prefix.sh';script.write_text(prefix)
            output=root/'calls'
            command='source '+shlex.quote(str(script))+'\nsystemctl() { printf "%s\\n" "$@" >> '+shlex.quote(str(output))+'; }\ninput_paused=1\nfalse\n'
            result=gamepad.subprocess.run(['bash','-c',command],capture_output=True,text=True)
            self.assertEqual(result.returncode,1,'keep the original installation failure')
            self.assertFalse(output.exists(),'failure reporting must not stop an already restarted input service')
            self.assertIn('阶段：idle',result.stderr)


if __name__=='__main__':unittest.main()
