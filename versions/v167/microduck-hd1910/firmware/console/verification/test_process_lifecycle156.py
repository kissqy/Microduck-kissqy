"""Linux process evidence and simulated Win32 contracts; no real Windows claim."""
import ctypes
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import process_lifecycle as lifecycle


class Function:
    def __init__(self, callback):
        self.callback = callback
        self.argtypes = self.restype = None

    def __call__(self, *args):
        return self.callback(*args)


class Process:
    def __init__(self, pid=41, *, alive=True, events=None):
        self.pid = pid
        self._handle = (1 << 35) + pid
        self.alive = alive
        self.suspended = True
        self.events = events if events is not None else []
        self.stdin, self.stdout, self.stderr = io.BytesIO(), io.BytesIO(), io.BytesIO()
        self.returncode = None if alive else 0

    def wait(self, timeout=None):
        self.events.append(('wait', self.pid, timeout))
        if self.alive:
            raise subprocess.TimeoutExpired('owned-child', timeout)
        return self.returncode

    def terminate(self):
        self.events.append(('terminate', self.pid))
        self.alive = False
        self.returncode = -15

    def kill(self):
        self.events.append(('kill', self.pid))
        self.alive = False
        self.returncode = -9


class Kernel:
    """Fake only API outcomes; ctypes structures and lifecycle ordering are real."""
    def __init__(self, failure=None, threads=None):
        self.failure = failure
        self.events = []
        self.error = 5
        self.job_count = 0
        self.jobs = {}
        self.roots = {}
        self.descendants = {}
        self.closed = []
        self.threads = threads if threads is not None else [(991, 999), (417, 41)]
        self.thread_index = 0
        for name in (
                'CreateJobObjectW', 'SetInformationJobObject', 'AssignProcessToJobObject',
                'CloseHandle', 'CreateToolhelp32Snapshot', 'Thread32First', 'Thread32Next',
                'OpenThread', 'ResumeThread'):
            setattr(self, name, Function(getattr(self, '_' + name)))

    def _CreateJobObjectW(self, security, name):
        self.events.append(('create-job', security, name))
        if self.failure == 'create':
            return 0
        self.job_count += 1
        handle = (1 << 34) + self.job_count
        self.jobs[handle] = None
        return handle

    def _SetInformationJobObject(self, handle, kind, address, size):
        info = ctypes.cast(address, ctypes.POINTER(lifecycle._ExtendedLimitInformation)).contents
        self.events.append(('limits', handle, kind, size, info.BasicLimitInformation.LimitFlags))
        return self.failure != 'limits'

    def _AssignProcessToJobObject(self, job, handle):
        self.events.append(('assign', job, handle))
        if self.failure == 'assign':
            return 0
        self.jobs[job] = self.roots[handle]
        return 1

    def _CloseHandle(self, handle):
        self.events.append(('close', handle))
        self.closed.append(handle)
        proc = self.jobs.get(handle)
        if proc is not None:
            proc.alive = False
            proc.returncode = -9
            for descendant in self.descendants.get(proc.pid, []):
                descendant.alive = False
        return 1

    def _CreateToolhelp32Snapshot(self, flags, pid):
        self.events.append(('snapshot', flags, pid))
        return lifecycle._INVALID_HANDLE if self.failure == 'snapshot' else 501

    def _entry(self, address):
        entry = ctypes.cast(address, ctypes.POINTER(lifecycle._ThreadEntry)).contents
        if entry.dwSize != ctypes.sizeof(lifecycle._ThreadEntry):
            raise AssertionError('dwSize must be initialized for each enumeration call')
        tid, pid = self.threads[self.thread_index]
        entry.th32ThreadID, entry.th32OwnerProcessID = tid, pid
        if self.failure == 'short-entry':
            entry.dwSize = 8

    def _Thread32First(self, snapshot, address):
        self.events.append(('first', snapshot))
        self.thread_index = 0
        if self.failure == 'first' or not self.threads:
            return 0
        self._entry(address)
        return 1

    def _Thread32Next(self, snapshot, address):
        self.thread_index += 1
        if self.failure == 'next':
            return 0
        if self.thread_index == len(self.threads):
            self.error = lifecycle._ERROR_NO_MORE_FILES
            return 0
        self._entry(address)
        return 1

    def _OpenThread(self, access, inherit, tid):
        self.events.append(('open-thread', access, inherit, tid))
        return 0 if self.failure == 'open-thread' else 601

    def _ResumeThread(self, handle):
        self.events.append(('resume', handle))
        if self.failure == 'resume':
            return 0xFFFFFFFF
        if self.failure == 'already-running':
            return 0
        if self.failure == 'still-suspended':
            return 2
        for proc in self.roots.values():
            proc.suspended = False
            self.descendants[proc.pid] = [Process(proc.pid + 1000)]
        return 1

    def popen(self, *args, **kwargs):
        self.events.append(('popen', args, kwargs))
        if self.failure == 'popen':
            raise FileNotFoundError('missing SSH executable')
        proc = Process(events=self.events)
        self.roots[proc._handle] = proc
        return proc

    def owner(self):
        api = lifecycle._WindowsApi(self, lambda: self.error)
        return lifecycle._ProcessOwner(windows=True, api=api, popen=self.popen)


class WindowsContractTests(unittest.TestCase):
    def test_documented_abi_widths_offsets_and_handle_signatures(self):
        self.assertEqual(ctypes.sizeof(lifecycle._DWORD), 4)
        self.assertEqual(ctypes.sizeof(lifecycle._LONG), 4)
        self.assertEqual(ctypes.sizeof(lifecycle._ThreadEntry), 28)
        self.assertEqual(lifecycle._ThreadEntry.th32OwnerProcessID.offset, 12)
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            self.assertEqual(ctypes.sizeof(lifecycle._BasicLimitInformation), 64)
            self.assertEqual(ctypes.sizeof(lifecycle._ExtendedLimitInformation), 144)
            self.assertEqual(lifecycle._BasicLimitInformation.MinimumWorkingSetSize.offset, 24)
        kernel = Kernel()
        kernel.owner()
        self.assertIs(kernel.CreateJobObjectW.restype, ctypes.c_void_p)
        self.assertIs(kernel.OpenThread.restype, ctypes.c_void_p)
        self.assertIs(kernel.ResumeThread.restype, ctypes.c_uint32)
        self.assertEqual(kernel.AssignProcessToJobObject.argtypes, [ctypes.c_void_p] * 2)

    def test_assignment_precedes_resume_and_retirement_kills_only_private_tree(self):
        kernel = Kernel()
        owner = kernel.owner()
        unrelated_browser, unrelated_ssh = Process(909), Process(910)
        with mock.patch.object(lifecycle, '_owner', owner):
            proc = lifecycle.spawn_process(['ssh.exe', 'robot'], creationflags=0x08000000)
            names = [event[0] for event in kernel.events]
            self.assertLess(names.index('popen'), names.index('assign'))
            self.assertLess(names.index('assign'), names.index('resume'))
            self.assertFalse(proc.suspended)
            options = next(e[2] for e in kernel.events if e[0] == 'popen')
            self.assertEqual(options['creationflags'], 0x08000004)
            self.assertEqual(options['cwd'], tempfile.gettempdir())
            limits = next(e for e in kernel.events if e[0] == 'limits')
            self.assertEqual(limits[2:], (9, ctypes.sizeof(lifecycle._ExtendedLimitInformation), 0x2000))
            self.assertIn(('open-thread', 0x2, False, 417), kernel.events)
            self.assertFalse(any(e[0] == 'open-thread' and e[-1] == 991 for e in kernel.events))
            descendants = kernel.descendants[proc.pid]
            lifecycle.retire_process(proc, grace=0)
            self.assertFalse(proc.alive)
            self.assertTrue(all(not p.alive for p in descendants))
            self.assertFalse(owner.processes)
            self.assertTrue(unrelated_browser.alive)
            self.assertTrue(unrelated_ssh.alive)
            self.assertTrue(all(s.closed for s in (proc.stdin, proc.stdout, proc.stderr)))
            self.assertEqual(kernel.closed.count(501), 1)
            self.assertEqual(kernel.closed.count(601), 1)
            lifecycle.retire_process(proc, grace=0)
            self.assertEqual(kernel.closed.count(limits[1]), 1)

    def test_failure_never_returns_unassigned_or_stuck_suspended_child(self):
        for failure in ('create', 'limits', 'popen', 'assign', 'snapshot', 'first',
                        'next', 'short-entry', 'open-thread', 'resume',
                        'already-running', 'still-suspended'):
            with self.subTest(failure=failure):
                kernel = Kernel(failure)
                owner = kernel.owner()
                with self.assertRaises(OSError):
                    owner.spawn(['ssh.exe'])
                self.assertFalse(owner.processes)
                self.assertTrue(all(not p.alive for p in kernel.roots.values()))
                self.assertTrue(all(s.closed for p in kernel.roots.values()
                                    for s in (p.stdin, p.stdout, p.stderr)))
                names = [e[0] for e in kernel.events]
                if failure in ('create', 'limits'):
                    self.assertNotIn('popen', names)
                if failure in ('assign', 'snapshot', 'first', 'next', 'short-entry', 'open-thread'):
                    self.assertNotIn('resume', names)
                if failure != 'create':
                    self.assertIn((1 << 34) + 1, kernel.closed)
                if failure in ('resume', 'already-running', 'still-suspended'):
                    self.assertIn(601, kernel.closed)
                    self.assertIn(501, kernel.closed)

    def test_missing_or_ambiguous_child_thread_is_not_resumed(self):
        for threads in ([(101, 999)], [(101, 41), (102, 41)]):
            with self.subTest(threads=threads):
                kernel = Kernel(threads=threads)
                owner = kernel.owner()
                with self.assertRaisesRegex(OSError, 'initial thread'):
                    owner.spawn(['ssh.exe'])
                self.assertFalse(any(e[0] == 'resume' for e in kernel.events))
                self.assertTrue(all(not p.alive for p in kernel.roots.values()))
                self.assertIn(501, kernel.closed)

    def test_owner_close_kills_askpass_and_permanently_refuses_late_launch(self):
        kernel = Kernel()
        owner = kernel.owner()
        with mock.patch.object(lifecycle, '_owner', owner):
            proc = lifecycle.spawn_process(['ssh.exe'])
            descendants = kernel.descendants[proc.pid]
            lifecycle.close_owned_processes()
            self.assertFalse(proc.alive)
            self.assertTrue(all(not p.alive for p in descendants))
            self.assertTrue(owner.closed)
            self.assertFalse(owner.processes)
            before = list(kernel.events)
            with self.assertRaisesRegex(RuntimeError, '退出'):
                lifecycle.spawn_process(['ssh.exe'])
            self.assertEqual(kernel.events, before)
            lifecycle.close_owned_processes()
            self.assertEqual(kernel.events, before)

    def test_retire_does_not_accumulate_old_roots_or_job_handles(self):
        kernel = Kernel()
        owner = kernel.owner()
        with mock.patch.object(lifecycle, '_owner', owner):
            for _ in range(24):
                proc = lifecycle.spawn_process(['ssh.exe'])
                lifecycle.retire_process(proc, grace=0)
                self.assertFalse(owner.processes)
            self.assertEqual(kernel.job_count, 24)
            jobs_closed = [h for h in kernel.closed if h in kernel.jobs]
            self.assertEqual(len(jobs_closed), 24)


class LinuxProcessTests(unittest.TestCase):
    @unittest.skipIf(os.name == 'nt', 'Linux process evidence')
    def test_real_child_runs_outside_package_and_unrelated_process_survives(self):
        owner = lifecycle._ProcessOwner(windows=False)
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                     cwd=tempfile.gettempdir())
        try:
            with mock.patch.object(lifecycle, '_owner', owner):
                proc = lifecycle.spawn_process(
                    [sys.executable, '-u', '-c', 'import os,sys; print(os.getcwd(),flush=True); sys.stdin.read()'],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(Path(proc.stdout.readline().decode().strip()).resolve(),
                                 Path(tempfile.gettempdir()).resolve())
                lifecycle.close_owned_processes()
                self.assertIsNotNone(proc.poll())
                self.assertIsNone(unrelated.poll())
                self.assertFalse(owner.processes)
                self.assertTrue(all(s.closed for s in (proc.stdin, proc.stdout, proc.stderr)))
        finally:
            unrelated.terminate()
            unrelated.wait(timeout=2)
            owner.close()

    @unittest.skipIf(os.name == 'nt', 'Linux process evidence')
    def test_exit_handler_reaps_child_without_explicit_cleanup_call(self):
        module_dir = str(Path(lifecycle.__file__).parent)
        with tempfile.TemporaryDirectory() as folder:
            pid_file = Path(folder) / 'owned.pid'
            code = (
                f'import sys; sys.path.insert(0,{module_dir!r}); '
                'from process_lifecycle import spawn_process; '
                'import subprocess; '
                "p=spawn_process([sys.executable,'-c','import time; time.sleep(60)'],"
                'stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE); '
                f'open({str(pid_file)!r},"w").write(str(p.pid))')
            result = subprocess.run([sys.executable, '-c', code], cwd=folder,
                                    capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            pid = int(pid_file.read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    @unittest.skipIf(os.name == 'nt', 'Linux pipe-lock evidence')
    def test_shutdown_releases_a_thread_blocked_writing_to_child_pipe(self):
        owner = lifecycle._ProcessOwner(windows=False)
        entered = threading.Event()
        errors = []
        with mock.patch.object(lifecycle, '_owner', owner):
            proc = lifecycle.spawn_process(
                [sys.executable, '-u', '-c', 'import time; print("ready",flush=True); time.sleep(60)'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(proc.stdout.readline().strip(), b'ready')
            def blocked_write():
                entered.set()
                try:
                    proc.stdin.write(b'x' * (4 * 1024 * 1024))
                except (OSError, ValueError) as exc:
                    errors.append(type(exc).__name__)
            writer = threading.Thread(target=blocked_write, daemon=True)
            writer.start()
            self.assertTrue(entered.wait(1))
            lifecycle.close_owned_processes()
            writer.join(timeout=2)
            self.assertFalse(writer.is_alive())
            self.assertIsNotNone(proc.poll())
            self.assertTrue(all(s.closed for s in (proc.stdin, proc.stdout, proc.stderr)))


class ShutdownOrderingTests(unittest.TestCase):
    def test_non_windows_preserves_explicit_cwd_and_ordinary_popen_options(self):
        process = Process(alive=False)
        popen = mock.Mock(return_value=process)
        owner = lifecycle._ProcessOwner(windows=False, popen=popen)
        proc = owner.spawn(['local-helper'], cwd='/explicit/work', env={'A': 'B'}, bufsize=0)
        self.assertIs(proc, process)
        self.assertEqual(popen.call_args.kwargs,
                         {'cwd': '/explicit/work', 'env': {'A': 'B'}, 'bufsize': 0})
        owner.close()

    def test_spawn_already_in_progress_is_owned_before_shutdown_drains_it(self):
        entered, release, closing = threading.Event(), threading.Event(), threading.Event()
        proc = Process()
        def popen(*args, **kwargs):
            entered.set()
            if not release.wait(2):
                raise AssertionError('test did not release spawn')
            return proc
        owner = lifecycle._ProcessOwner(windows=False, popen=popen)
        worker = threading.Thread(target=owner.spawn, args=(['child'],))
        def close():
            closing.set()
            owner.close()
        worker.start()
        self.assertTrue(entered.wait(1))
        shutdown = threading.Thread(target=close)
        shutdown.start()
        self.assertTrue(closing.wait(1))
        release.set()
        worker.join(timeout=2)
        shutdown.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(shutdown.is_alive())
        self.assertFalse(proc.alive)
        self.assertFalse(owner.processes)
        with self.assertRaises(RuntimeError):
            owner.spawn(['late-child'])

    def test_wait_terminate_and_stream_errors_still_escalate_and_close_other_handles(self):
        proc = Process()
        proc.wait = mock.Mock(side_effect=[subprocess.TimeoutExpired('child', 0), OSError('wait'), 0])
        proc.terminate = mock.Mock(side_effect=OSError('already terminated'))
        proc.kill = mock.Mock()
        proc.stdin.close = mock.Mock(side_effect=OSError('pipe'))
        owner = lifecycle._ProcessOwner(windows=False, popen=lambda *a, **k: proc)
        with mock.patch.object(lifecycle, '_owner', owner):
            owner.spawn(['child'])
            lifecycle.retire_process(proc, grace=0)
            proc.terminate.assert_called_once()
            proc.kill.assert_called_once()
            self.assertFalse(owner.processes)
            self.assertTrue(proc.stdout.closed)
            self.assertTrue(proc.stderr.closed)
            lifecycle.retire_process(None)


if __name__ == '__main__':
    unittest.main(verbosity=2)
