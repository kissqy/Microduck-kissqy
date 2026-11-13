"""Exercise the deployed bash preflight without touching host packages."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'training/server_prerequisites.sh'


class PrerequisitesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'calls.jsonl'
        self.home = self.root / 'account'
        self.home.mkdir()
        self.environment = {**os.environ, 'PATH': str(self.bin), 'HOME': str(self.home)}
        self.secret = 'test sudo password $literal 中文'
        self.helper('python3', '''
code = sys.argv[2]
if 'import venv,ensurepip' in code:
    sys.exit(0 if (root / 'venv-ready').exists() else 1)
if 'print("%d.%d"' in code:
    print('3.12')
if 'from ctypes.util import find_library' in code and not (root / 'libs-ready').exists():
    print('libgomp1\\nlibegl1\\nlibgl1')
''')
        self.helper('git', 'pass')
        self.helper('id', "print('0')")
        self.helper('env', '''
args = sys.argv[1:]
while args and '=' in args[0]:
    key, value = args.pop(0).split('=', 1)
    os.environ[key] = value
os.execvp(args[0], args)
''')
        self.helper('apt-get', '''
with (root / 'calls.jsonl').open('a') as handle:
    handle.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1] == 'install':
    (root / 'venv-ready').touch()
    (root / 'libs-ready').touch()
''')

    def helper(self, name, body, directory=None):
        folder = directory or self.bin
        folder.mkdir(parents=True, exist_ok=True)
        file = folder / name
        file.write_text('#!' + sys.executable + '\nimport json, os, sys\nfrom pathlib import Path\nroot = Path(' + repr(str(self.root)) + ')\n' + body)
        file.chmod(0o755)

    def run_script(self, mode='server', password=''):
        return subprocess.run(['/bin/bash', str(SCRIPT), str(self.root / 'workspace'), mode],
                              input=password, text=True, capture_output=True,
                              env=self.environment, timeout=10)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_missing_ensurepip_and_libraries_installed_once(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual(calls[0], ['update'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][:3], ['install', '-y', '--no-install-recommends'])
        self.assertEqual(set(calls[1][3:]), {'python3.12-venv', 'python3-venv', 'libgomp1', 'libegl1', 'libgl1'})
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.calls(), calls, 'repeat deployment reinstalled ready packages')

    def test_cargo_uv_reused_without_installing_venv(self):
        self.helper('uv', "print('uv 0.9 fixture')", self.home / '.cargo/bin')
        (self.root / 'libs-ready').touch()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertIn('复用已有uv', result.stdout)

    def test_failed_bootstrap_uv_repaired(self):
        self.helper('uv', 'sys.exit(1)', self.root / 'workspace/bootstrap/bin')
        result = self.run_script('wsl')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[1][3:], ['python3.12-venv', 'python3-venv'])

    def test_sudo_password_from_stdin_never_in_arguments_or_output(self):
        self.helper('id', "print('1000')")
        self.helper('sudo', '''
if sys.argv[1] == '-n':
    sys.exit(1)
with (root / 'sudo.jsonl').open('a') as handle:
    handle.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.stdin.readline().rstrip('\\n') != ''' + repr(self.secret) + ''':
    sys.exit(1)
os.execvp(sys.argv[4], sys.argv[4:])
''')
        result = self.run_script(password=self.secret + '\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 2)
        self.assertNotIn(self.secret, result.stdout + result.stderr + (self.root / 'sudo.jsonl').read_text())

    def test_nonroot_without_sudo_password_fails_before_install(self):
        self.helper('id', "print('1000')")
        self.helper('sudo', 'sys.exit(1)')
        result = self.run_script()
        self.assertEqual(result.returncode, 43)
        self.assertEqual(self.calls(), [])


if __name__ == '__main__':
    unittest.main()
