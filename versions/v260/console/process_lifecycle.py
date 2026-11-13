"""Own only children launched here; shutdown never searches for SSH/Python names.

Windows children start suspended, enter their own non-inheritable kill-on-close
job, and only then run. Descendants such as askpass inherit that job. An abrupt
parent death between CreateProcess and job assignment can still leave a suspended
child; this retains ordinary Popen rather than replacing CreateProcess.
"""
import atexit
import ctypes
import os
import subprocess
import tempfile
import threading


# Windows DWORD/LONG are 32-bit even on a 64-bit host. Explicit widths also let
# the ABI and failure paths be checked on the Linux development host.
_DWORD = ctypes.c_uint32
_LONG = ctypes.c_int32
_HANDLE = ctypes.c_void_p
_SIZE_T = ctypes.c_size_t
_BOOL = ctypes.c_int32
_CREATE_SUSPENDED = 0x00000004
_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_EXTENDED_LIMIT_INFORMATION = 9
_SNAPTHREAD = 0x00000004
_THREAD_SUSPEND_RESUME = 0x0002
_ERROR_NO_MORE_FILES = 18
_INVALID_HANDLE = ctypes.c_void_p(-1).value


class _BasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ('PerProcessUserTimeLimit', ctypes.c_int64),
        ('PerJobUserTimeLimit', ctypes.c_int64),
        ('LimitFlags', _DWORD),
        ('MinimumWorkingSetSize', _SIZE_T),
        ('MaximumWorkingSetSize', _SIZE_T),
        ('ActiveProcessLimit', _DWORD),
        ('Affinity', _SIZE_T),
        ('PriorityClass', _DWORD),
        ('SchedulingClass', _DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        'ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
        'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ('BasicLimitInformation', _BasicLimitInformation),
        ('IoInfo', _IoCounters),
        ('ProcessMemoryLimit', _SIZE_T),
        ('JobMemoryLimit', _SIZE_T),
        ('PeakProcessMemoryUsed', _SIZE_T),
        ('PeakJobMemoryUsed', _SIZE_T),
    ]


class _ThreadEntry(ctypes.Structure):
    _fields_ = [
        ('dwSize', _DWORD), ('cntUsage', _DWORD), ('th32ThreadID', _DWORD),
        ('th32OwnerProcessID', _DWORD), ('tpBasePri', _LONG),
        ('tpDeltaPri', _LONG), ('dwFlags', _DWORD),
    ]


class _WindowsApi:
    def __init__(self, kernel=None, last_error=None):
        self.kernel = kernel if kernel is not None else ctypes.WinDLL('kernel32', use_last_error=True)
        self.last_error = last_error if last_error is not None else ctypes.get_last_error
        signatures = {
            'CreateJobObjectW': ([_HANDLE, ctypes.c_wchar_p], _HANDLE),
            'SetInformationJobObject': ([_HANDLE, ctypes.c_int, _HANDLE, _DWORD], _BOOL),
            'AssignProcessToJobObject': ([_HANDLE, _HANDLE], _BOOL),
            'CloseHandle': ([_HANDLE], _BOOL),
            'CreateToolhelp32Snapshot': ([_DWORD, _DWORD], _HANDLE),
            'Thread32First': ([_HANDLE, ctypes.POINTER(_ThreadEntry)], _BOOL),
            'Thread32Next': ([_HANDLE, ctypes.POINTER(_ThreadEntry)], _BOOL),
            'OpenThread': ([_DWORD, _BOOL, _DWORD], _HANDLE),
            'ResumeThread': ([_HANDLE], _DWORD),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = args, result

    def error(self, operation):
        code = self.last_error()
        return OSError(code, f'{operation} failed (Windows error {code})')

    def close_handle(self, handle):
        if handle and not self.kernel.CloseHandle(handle):
            raise self.error('CloseHandle')

    def create_job(self):
        # NULL security attributes create a non-inheritable handle. Only this
        # owner retains it; passing it to children would defeat kill-on-close.
        handle = self.kernel.CreateJobObjectW(None, None)
        if not handle:
            raise self.error('CreateJobObjectW')
        job = _WindowsJob(self, handle)
        info = _ExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = _KILL_ON_JOB_CLOSE
        try:
            if not self.kernel.SetInformationJobObject(
                    handle, _JOB_EXTENDED_LIMIT_INFORMATION,
                    ctypes.byref(info), ctypes.sizeof(info)):
                raise self.error('SetInformationJobObject')
        except BaseException:
            job.close()
            raise
        return job

    def resume_initial_thread(self, pid):
        # Popen has already closed the primary thread handle. Enumerate once,
        # before that suspended child can run or create any further threads.
        snapshot = self.kernel.CreateToolhelp32Snapshot(_SNAPTHREAD, 0)
        if snapshot in (None, 0, -1, _INVALID_HANDLE):
            raise self.error('CreateToolhelp32Snapshot')
        try:
            entry = _ThreadEntry()
            entry.dwSize = ctypes.sizeof(entry)
            if not self.kernel.Thread32First(snapshot, ctypes.byref(entry)):
                raise self.error('Thread32First')
            threads = []
            while True:
                if entry.dwSize < _ThreadEntry.th32OwnerProcessID.offset + ctypes.sizeof(_DWORD):
                    raise OSError('Incomplete Windows thread snapshot')
                if entry.th32OwnerProcessID == pid:
                    threads.append(entry.th32ThreadID)
                entry.dwSize = ctypes.sizeof(entry)
                if not self.kernel.Thread32Next(snapshot, ctypes.byref(entry)):
                    if self.last_error() != _ERROR_NO_MORE_FILES:
                        raise self.error('Thread32Next')
                    break
            if len(threads) != 1:
                raise OSError('Cannot identify the suspended child initial thread')
            thread = self.kernel.OpenThread(_THREAD_SUSPEND_RESUME, False, threads[0])
            if not thread:
                raise self.error('OpenThread')
            try:
                count = self.kernel.ResumeThread(thread)
                if count == 0xFFFFFFFF:
                    raise self.error('ResumeThread')
                if count != 1:
                    raise OSError('Unexpected initial thread suspend count')
            finally:
                self.close_handle(thread)
        finally:
            self.close_handle(snapshot)


class _WindowsJob:
    def __init__(self, api, handle):
        self.api, self.handle = api, handle

    def assign(self, proc):
        if not self.api.kernel.AssignProcessToJobObject(self.handle, int(proc._handle)):
            raise self.api.error('AssignProcessToJobObject')

    def close(self):
        if self.handle is not None:
            self.api.close_handle(self.handle)
            self.handle = None

    def __del__(self):
        try:
            self.close()
        except (OSError, ValueError):
            pass


def _close_streams(proc):
    for name in ('stdin', 'stdout', 'stderr'):
        stream = getattr(proc, name, None)
        if stream is not None:
            try:
                stream.close()
            except (OSError, ValueError):
                pass


def _retire_root(proc, grace):
    # A buffered stdin can be locked by another thread blocked in write. Wait
    # and terminate before closing pipes, without adding a shutdown worker.
    try:
        proc.wait(timeout=max(0, grace))
        return
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass
    for action in ('terminate', 'kill'):
        try:
            getattr(proc, action)()
        except (OSError, ValueError):
            pass
        try:
            proc.wait(timeout=1)
            return
        except (subprocess.TimeoutExpired, OSError, ValueError):
            pass


class _ProcessOwner:
    def __init__(self, *, windows=None, api=None, popen=None):
        self.windows = os.name == 'nt' if windows is None else windows
        self.api, self.popen = api, popen
        self.lock = threading.RLock()
        self.closed = False
        # Retire removes naturally exited one-shot commands as well. This keeps
        # ownership bounded rather than accumulating historic Popen handles.
        self.processes = {}

    def spawn(self, *args, **kwargs):
        with self.lock:
            if self.closed:
                raise RuntimeError('中控正在退出，不能再建立子进程')
            if kwargs.get('cwd') is None:
                kwargs['cwd'] = tempfile.gettempdir()
            job = None
            proc = None
            try:
                if self.windows:
                    if self.api is None:
                        self.api = _WindowsApi()
                    job = self.api.create_job()
                    kwargs['creationflags'] = kwargs.get('creationflags', 0) | _CREATE_SUSPENDED
                proc = (self.popen or subprocess.Popen)(*args, **kwargs)
                if job is not None:
                    job.assign(proc)
                    self.api.resume_initial_thread(proc.pid)
                self.processes[proc] = job
                return proc
            except BaseException:
                # An assignment/resume failure never returns a suspended child.
                # Close its private job tree and reap the root before reporting.
                if job is not None:
                    try:
                        job.close()
                    except (OSError, ValueError):
                        pass
                if proc is not None:
                    _retire_root(proc, 0)
                    _close_streams(proc)
                raise

    def release(self, proc):
        with self.lock:
            return self.processes.pop(proc, None)

    def close(self):
        with self.lock:
            self.closed = True
            processes = list(self.processes.items())
            self.processes.clear()
        # Close every job before touching pipes, so askpass cannot keep another
        # child's stdout/stderr or buffered stdin blocked during owner shutdown.
        for _, job in processes:
            if job is not None:
                try:
                    job.close()
                except (OSError, ValueError):
                    pass
        for proc, _ in processes:
            _retire_root(proc, 0)
            _close_streams(proc)


_owner = _ProcessOwner()


def spawn_process(*args, **kwargs):
    """Popen-compatible launch owned here, with a system-temp default cwd."""
    return _owner.spawn(*args, **kwargs)


def retire_process(proc, grace=1):
    """Bounded graceful wait, then terminate this root and its owned Windows tree."""
    if proc is None:
        return
    try:
        _retire_root(proc, grace)
    finally:
        job = _owner.release(proc)
        if job is not None:
            try:
                job.close()
            except (OSError, ValueError):
                pass
        _close_streams(proc)


def close_owned_processes():
    """Permanently stop this factory and reclaim only the children it created."""
    _owner.close()


atexit.register(close_owned_processes)
