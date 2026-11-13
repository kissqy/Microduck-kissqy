import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('camera_setup', ROOT/'packaging/camera-setup.py')
camera = importlib.util.module_from_spec(spec)
spec.loader.exec_module(camera)


class CameraSetup(unittest.TestCase):
    def test_installed_flags_are_preserved(self):
        value = '{ path=/usr/bin/mediad ; argv[]=/usr/bin/mediad --camera --port 8443 --no-auto-exposure ; ignore_errors=no ; }'
        self.assertEqual(camera.installed_arguments(value)[1:], ['--camera','--port','8443','--no-auto-exposure'])

    def test_wrapper_is_refused_before_service_changes(self):
        with self.assertRaises(ValueError):
            camera.installed_arguments('{ argv[]=/bin/sh -c mediad ; ignore_errors=no ; }')

    def test_missing_command_is_refused(self):
        with self.assertRaises(ValueError): camera.installed_arguments('')

    def test_systemd_expansions_and_spaces_are_literal(self):
        self.assertEqual(camera.quote_argument('a b%$"\\c'), '"a b%%$$\\"\\\\c"')

    def test_newline_is_refused(self):
        with self.assertRaises(ValueError): camera.quote_argument('a\nb')

    def exercise(self, previous=None, fail=False):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name); (root/'mediad').write_bytes(b'fixture')
            directory=root/'unit'; directory.mkdir(); path=directory/'40-microduck-camera-demand.conf'
            if previous is not None: path.write_bytes(previous)
            calls=[]
            def command(*args):
                calls.append(args)
                if args[0]=='show':return '{ argv[]=/usr/bin/mediad --camera --port 8443 ; ignore_errors=no ; }'
                if fail and len(calls)==3:raise RuntimeError('restart failed')
                return ''
            if fail:
                with self.assertRaises(RuntimeError):camera.setup(root,command,directory)
                self.assertEqual(path.read_bytes() if path.exists() else None, previous)
            else:
                camera.setup(root,command,directory)
                self.assertIn(b'--camera',path.read_bytes());self.assertIn(b'--port',path.read_bytes())
            self.assertTrue(all('robotd.service' not in call and 'padd.service' not in call for call in calls))
            self.assertEqual(calls[2],('restart','mediad.service'))
    def test_only_mediad_is_restarted(self):self.exercise()
    def test_failed_new_override_is_removed(self):self.exercise(fail=True)
    def test_previous_camera_override_is_restored(self):self.exercise(previous=b'previous',fail=True)


if __name__=='__main__':unittest.main()
