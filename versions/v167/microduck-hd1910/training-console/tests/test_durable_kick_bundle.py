"""Regression: the durable trainer bundles every import before any expensive GPU step.

Both foot variants use the detached WSL/SSH path, not the direct viewer path.
This regression runs the *real* durable payload packer and worker staging logic
in an isolated temp directory without modifying the official training engine.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from training import durable_manager, worker


KICK_TASKS = (
    ('Mjlab-BallKickLeft-Flat-MicroDuck', 'kick_left', False),
    ('Mjlab-BallKickLeft-Flat-Backlash-MicroDuck', 'kick_left', True),
    ('Mjlab-BallKick-Flat-MicroDuck', 'kick_right', False),
    ('Mjlab-BallKick-Flat-Backlash-MicroDuck', 'kick_right', True),
)


def unpack_assignment(source, variable):
    for statement in ast.parse(source).body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == variable
            for target in statement.targets
        ):
            return ast.literal_eval(statement.value)
    raise AssertionError('missing embedded assignment: ' + variable)


class DurableKickBundleTests(unittest.TestCase):
    def test_left_and_right_foot_have_complete_durable_stage_and_import(self):
        """Would fail on CalibUI2: durable_manager omitted config_audit.py."""
        for number, (task, role, backlash) in enumerate(KICK_TASKS):
            with self.subTest(task=task):
                request = {
                    'op': 'train', 'engine': 'official_0151',
                    'task': task, 'num_envs': 4096, 'iterations': 10000,
                    'training_firmware_p': 5, 'training_action_scale': 1.0,
                }
                job = {'id': f'{number:016x}', 'request': request}
                monitor_script = durable_manager.monitor_payload(job, create=True).decode('utf-8')
                durable_request = unpack_assignment(monitor_script, 'DURABLE_REQUEST')
                source = durable_request['source']
                bundle = unpack_assignment(source, 'WORKER_BUNDLE')
                self.assertEqual(unpack_assignment(source, 'WORKER_REQUEST'), request)
                self.assertIn('config_audit.py', bundle)
                self.assertEqual(bundle['config_audit.py'],
                                 (Path(durable_manager.__file__).parent / 'config_audit.py').read_text(encoding='utf-8'))
                self.assertTrue(all(bundle[name] for name in bundle))

                def check_staged(actual_req, staged):
                    self.assertEqual(actual_req, request)
                    for name, contents in bundle.items():
                        self.assertEqual((staged / name).read_text(encoding='utf-8'), contents)
                    # This is the actual import that failed in the user-reported job.
                    # No GPU, repo, SSH or official source is needed for this gate.
                    code = ('import sys;sys.path.insert(0,sys.argv[1]);'
                            'import runtime_adapter;from official_spec import TASKS;'
                            'task=sys.argv[2];info=TASKS[task];'
                            'assert info["role"]==sys.argv[3];'
                            'assert info["backlash"]==(sys.argv[4]=="1");'
                            'assert callable(runtime_adapter.audit_configuration)')
                    result = subprocess.run([sys.executable, '-I', '-c', code,
                                             str(staged), task, role, '1' if backlash else '0'],
                                            capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr)

                with patch.dict(worker.__dict__, {'WORKER_BUNDLE': bundle}):
                    with patch.object(worker, 'controls'), patch.object(worker, 'run_prepared', side_effect=check_staged):
                        worker.run(request)

    def test_durable_and_non_durable_have_identical_adapter_files(self):
        """New adapter imports cannot silently work in viewers but fail in training."""
        job = {'id': 'a' * 16, 'request': {'op': 'train', 'task': KICK_TASKS[0][0]}}
        durable = unpack_assignment(
            unpack_assignment(durable_manager.monitor_payload(job, create=True).decode(), 'DURABLE_REQUEST')['source'],
            'WORKER_BUNDLE')
        parent = Path(durable_manager.__file__).parent
        worker_source = (parent / 'worker.py').read_text(encoding='utf-8')
        desktop_source = (parent.parent / 'training_console.py').read_text(encoding='utf-8')
        def source_manifest(source):
            candidates = []
            for node in ast.walk(ast.parse(source)):
                expr = None
                if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == 'name':
                    expr = node.iter
                if isinstance(node, ast.comprehension) and isinstance(node.target, ast.Name) and node.target.id == 'name':
                    expr = node.iter
                if isinstance(expr, ast.Tuple):
                    names = ast.literal_eval(expr)
                    if 'runtime_adapter.py' in names and 'official_spec.py' in names:
                        candidates.append(names)
            self.assertEqual(len(candidates), 1, 'must find exactly one deployed runtime manifest')
            return set(candidates[0])
        self.assertEqual(set(durable), source_manifest(worker_source))
        self.assertEqual(set(durable), source_manifest(desktop_source))
        self.assertTrue(all((parent / name).is_file() for name in durable))


if __name__ == '__main__':
    unittest.main()
