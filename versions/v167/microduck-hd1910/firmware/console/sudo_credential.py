"""Remember a Zero sudo credential for the current console user.

On Windows the saved bytes are protected by the user's DPAPI key. Other
platforms retain the credential only until the console exits. Never expose
the password through a status response, recording, URL, or command line.
"""
import hashlib
import os
import sys
import tempfile
from pathlib import Path


def _windows_protect(data, decrypt=False):
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_byte))]

    source = ctypes.create_string_buffer(data)
    incoming = Blob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
    outgoing = Blob()
    dll = ctypes.WinDLL('crypt32', use_last_error=True)
    method = dll.CryptUnprotectData if decrypt else dll.CryptProtectData
    method.argtypes = ([ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                        ctypes.POINTER(Blob)] if decrypt else
                       [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.POINTER(Blob),
                        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                        ctypes.POINTER(Blob)])
    method.restype = wintypes.BOOL
    if not method(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise OSError(ctypes.get_last_error(), 'Windows credential protection failed')
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        local_free = ctypes.WinDLL('kernel32', use_last_error=True).LocalFree
        local_free.argtypes = [ctypes.c_void_p]
        local_free.restype = ctypes.c_void_p
        local_free(ctypes.cast(outgoing.data, ctypes.c_void_p))


class SudoCredential:
    def __init__(self, target):
        self.value = None
        self.persistent = sys.platform == 'win32' and bool(os.environ.get('APPDATA'))
        self.path = None
        if self.persistent:
            key = hashlib.sha256((target or 'local').encode('utf-8')).hexdigest()[:24]
            self.path = Path(os.environ['APPDATA']) / 'Microduck Console' / ('sudo-' + key + '.bin')
            self.get()

    def get(self):
        if self.value is not None:
            return self.value
        if self.path:
            try:
                value = _windows_protect(self.path.read_bytes(), decrypt=True).decode('utf-8')
                if 0 < len(value) <= 256 and not any(c in value for c in '\r\n\0'):
                    self.value = value
            except (OSError, UnicodeError, ValueError):
                pass
        return self.value

    def remember(self, value):
        self.value = value
        if not self.path:
            return
        try:
            cipher = _windows_protect(value.encode('utf-8'))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix='.sudo-', dir=self.path.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(cipher)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        except OSError:
            # A failed local save must not turn a successful service switch
            # into an apparent movement failure. The process still remembers.
            self.persistent = False

    def forget(self):
        self.value = None
        if self.path:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                raise OSError('无法删除本机保存的 sudo 密码') from None

    @property
    def saved(self):
        return self.value is not None

    @property
    def scope(self):
        return 'windows-user' if self.persistent else 'console-session'
