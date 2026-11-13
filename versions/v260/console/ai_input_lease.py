"""One bounded AI action may temporarily pause ordinary padd input.

This capability belongs to one action, not the voice session. It is separate
from actual speaker playback's mouth-only pause and never enables the robot.
"""
import json
import os
from pathlib import Path
import re
import threading
import time
import uuid

DIRECTORY=Path('/run/padd/ai-input')
REPORT=Path('/run/padd/input-settings.json')
TTL_MS=750
MAX_FUTURE_MS=1500
MAX_ACTION_S=20
ACTION_TOOLS=frozenset(('perform_skill','sit_down','stand_up','walk_short',
                        'stop_moving','body_pose','head_pose','head_expression',
                        'mouth_pose','express_emotion'))
REASONS={'not-drive':'实体手柄未处于行走控制模式',
         'recorder-busy':'手柄正在录制、保存或回放，请结束后再执行 AI 动作',
         'not-neutral':'请先松开实体手柄摇杆、扳机和按键',
         'imu-head':'请先关闭实体手柄 IMU 头部跟随',
         'pose-active':'实体手柄身体姿态尚未复位，请先回行走模式并松杆',
         'busy':'已有另一个 AI 动作占用输入',
         'manual-start':'实体手柄 Start 已中断 AI 动作',
         'manual-select':'实体手柄 Select 已中断 AI 动作'}


def padd_running():
    """Missing/old reports must not let a running old padd get a fake ACK."""
    try:
        pid=json.loads(REPORT.read_text())['pid']
        if type(pid) is int and pid>0 and Path('/proc',str(pid),'comm').read_text().strip()=='padd':return True
    except (OSError,ValueError,TypeError,KeyError):pass
    try:
        for proc in Path('/proc').iterdir():
            if not proc.name.isdecimal():continue
            try:
                if (proc/'comm').read_text().strip()=='padd':return True
            except PermissionError:return True
            except OSError:pass
    except OSError:
        # A platform without /proc cannot establish that the service is absent.
        return True
    return False


def _read(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'r') as stream:
        value=stream.read(128)
    if len(value)>=128:raise ValueError('输入租约文件过长')
    return value.strip()


def _cancel_reason(path):
    try:reason=_read(path)
    except FileNotFoundError:return None
    except (OSError,ValueError):return 'AI 输入租约已取消'
    return REASONS.get(reason,'AI 输入租约已取消：'+reason)


def validate_input_token(token,*,directory=DIRECTORY,requires_ack=padd_running,exact=False):
    if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{32}',token):
        raise ValueError('AI 输入租约编号无效')
    directory=Path(directory)
    if directory.is_symlink():raise ValueError('AI 输入租约目录无效')
    reason=_cancel_reason(directory/(token+'.cancel'))
    if reason:raise ValueError(reason)
    try:
        expiry=int(_read(directory/(token+'.lease')))
        ack=int(_read(directory/(token+'.ack')))
        now=time.monotonic_ns()//1_000_000
        if not 0<expiry-now<=MAX_FUTURE_MS or not 0<ack-now<=MAX_FUTURE_MS:
            raise ValueError('AI 输入租约已过期')
        if ack>expiry or exact and ack!=expiry:raise ValueError('实体手柄尚未确认本次 AI 输入租约')
        # A no-padd self-ACK stops being valid immediately if a padd appears.
        if (directory/(token+'.solo')).exists() and requires_ack():
            raise ValueError('实体手柄服务已启动，需重新确认输入租约')
    except (OSError,TypeError) as exc:
        raise ValueError('AI 输入租约或确认已失效') from exc
    # Recheck after reading both files: cancellation always beats an old ACK.
    reason=_cancel_reason(directory/(token+'.cancel'))
    if reason:raise ValueError(reason)
    return expiry


class InputLease:
    def __init__(self,cancelled,*,directory=DIRECTORY,requires_ack=padd_running):
        self.cancelled=cancelled;self.directory=Path(directory);self.requires_ack=requires_ack
        self.token=uuid.uuid4().hex
        self.path=self.directory/(self.token+'.lease');self.ack=self.path.with_suffix('.ack')
        self.solo=self.path.with_suffix('.solo')
        self.closed=threading.Event();self.lock=threading.RLock();self.worker=None
        self.started=time.monotonic();self.acquired=False;self.error=''

    def _prepare(self):
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o755)
        if self.directory.is_symlink():raise ValueError('AI 输入租约目录无效')
        if os.geteuid()==0 and self.directory==DIRECTORY:
            import grp,pwd
            try:account=pwd.getpwnam('padd')
            except KeyError:return
            shared=grp.getgrnam('robot')
            os.chown(self.directory,account.pw_uid,shared.gr_gid);os.chmod(self.directory,0o770)

    def _write(self,path,value):
        temporary=path.with_suffix(path.suffix+'.tmp')
        try:
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o644)
            with os.fdopen(fd,'w') as stream:
                os.fchmod(stream.fileno(),0o644)
                stream.write(str(value)+'\n')
            os.replace(temporary,path)
        finally:
            try:temporary.unlink()
            except FileNotFoundError:pass

    def _refresh(self):
        if self.acquired:self.ensure_current()
        reason=_cancel_reason(self.path.with_suffix('.cancel'))
        if reason:raise ValueError(reason)
        expiry=time.monotonic_ns()//1_000_000+TTL_MS
        self._write(self.path,expiry)
        if not self.requires_ack():
            self._write(self.solo,expiry)
            self._write(self.ack,expiry)
        elif self.solo.exists():
            self.solo.unlink()
            try:self.ack.unlink()
            except FileNotFoundError:pass

    def ensure_current(self):
        if self.error:raise ValueError(self.error)
        if self.closed.is_set() or self.cancelled():raise ValueError('AI 动作已取消')
        if time.monotonic()-self.started>=MAX_ACTION_S:raise ValueError('AI 动作输入租约超时')
        return validate_input_token(self.token,directory=self.directory,requires_ack=self.requires_ack)

    def acquire(self):
        try:
            with self.lock:
                if self.closed.is_set() or self.cancelled():raise ValueError('AI 动作已取消')
                self._prepare();self._refresh()
                self.worker=threading.Thread(target=self._renew,name='AI-Input-Pause',daemon=True)
                self.worker.start()
            deadline=time.monotonic()+1.2
            while time.monotonic()<deadline:
                if self.closed.is_set() or self.cancelled():raise ValueError(self.error or 'AI 动作已取消')
                reason=_cancel_reason(self.path.with_suffix('.cancel'))
                if reason:raise ValueError(reason)
                try:
                    validate_input_token(self.token,directory=self.directory,requires_ack=self.requires_ack,exact=True)
                    self.acquired=True
                    return self
                except ValueError:pass
                self.closed.wait(.01)
            raise ValueError('实体手柄未确认暂停输入，请安装本版配套手柄更新')
        except Exception:
            self.close();raise

    def _renew(self):
        while not self.closed.wait(.2):
            try:
                with self.lock:
                    if self.closed.is_set():return
                    if self.cancelled() or time.monotonic()-self.started>=MAX_ACTION_S:
                        raise ValueError('AI 动作已取消或输入租约超时')
                    self._refresh()
            except (OSError,ValueError) as exc:
                self.error=str(exc);self.close();return

    def close(self):
        self.closed.set()
        with self.lock:
            for path in (self.path,self.ack,self.solo):
                try:path.unlink()
                except FileNotFoundError:pass
        if self.worker and self.worker is not threading.current_thread():self.worker.join(.3)
        # A deleted lease already invalidates late RPCs/ACKs. This token is never
        # reused, so after renewal stops its cancellation file can be reclaimed.
        try:self.path.with_suffix('.cancel').unlink()
        except FileNotFoundError:pass
