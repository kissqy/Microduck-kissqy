"""A short-lived, local HAT-playback pause for padd's mouth notification only."""
import json
import os
from pathlib import Path
import threading
import time
import uuid

DIRECTORY=Path('/run/padd/ai-mouth')
REPORT=Path('/run/padd/input-settings.json')
TTL_MS=750


def padd_running(report=REPORT):
    try:
        pid=json.loads(report.read_text())['pid']
        if type(pid) is not int or pid<=0:return False
        return Path('/proc',str(pid),'comm').read_text().strip()=='padd'
    except (OSError,ValueError,KeyError,TypeError):return False


class MouthLease:
    def __init__(self,active,cancelled,*,directory=DIRECTORY,requires_ack=padd_running):
        self.active=active;self.cancelled=cancelled
        self.directory=Path(directory);self.requires_ack=requires_ack
        self.token=uuid.uuid4().hex
        self.path=self.directory/(self.token+'.lease')
        self.ack=self.directory/(self.token+'.ack')
        self.lock=threading.RLock();self.closed=threading.Event();self.worker=None

    def _prepare(self):
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o755)
        if self.directory.is_symlink():raise RuntimeError('嘴巴暂停目录无效')
        # padd runs as its own system account inside RuntimeDirectory=padd.
        if os.geteuid()==0 and self.directory==DIRECTORY:
            import grp,pwd
            try:account=pwd.getpwnam('padd')
            except KeyError:return
            shared=grp.getgrnam('robot')
            os.chown(self.directory,account.pw_uid,shared.gr_gid)
            os.chmod(self.directory,0o770)

    def _refresh(self):
        expiry=time.monotonic_ns()//1_000_000+TTL_MS
        temporary=self.path.with_suffix('.tmp')
        try:
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o644)
            with os.fdopen(fd,'w') as stream:stream.write(str(expiry)+'\n')
            os.chmod(temporary,0o644)
            os.replace(temporary,self.path)
        finally:
            try:temporary.unlink()
            except FileNotFoundError:pass
        return expiry

    def _remove(self):
        for path in (self.path,self.ack):
            try:path.unlink()
            except FileNotFoundError:pass

    def acquire(self):
        with self.lock:
            if self.closed.is_set() or self.cancelled():raise RuntimeError('播音已取消')
            self._prepare();self._refresh()
            if self.worker is None or not self.worker.is_alive():
                self.worker=threading.Thread(target=self._renew,name='AI-Mouth-Pause',daemon=True)
                self.worker.start()
        deadline=time.monotonic()+1.2
        while not self.cancelled() and not self.closed.is_set():
            if not self.requires_ack():return
            try:
                expiry=int(self.path.read_text().strip())
                if int(self.ack.read_text().strip())==expiry and expiry>time.monotonic_ns()//1_000_000:
                    return
            except (OSError,ValueError):pass
            if time.monotonic()>=deadline:
                self.close()
                raise RuntimeError('手柄服务尚未确认让出嘴巴，请安装本版配套手柄更新')
            self.closed.wait(.01)
        self.close()
        raise RuntimeError('播音已取消')

    def _renew(self):
        while not self.closed.wait(.2):
            with self.lock:
                if self.closed.is_set():return
                try:
                    if not self.cancelled() and self.active():
                        self._prepare();self._refresh()
                    else:self._remove()
                except OSError:
                    # No stale infinite boolean: any last successful write expires.
                    continue

    def close(self):
        self.closed.set()
        with self.lock:self._remove()
        if self.worker and self.worker is not threading.current_thread():self.worker.join(.3)
