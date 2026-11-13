"""Zero/HAT ALSA PCM streams. Imported on PCs without opening any local device."""
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import sys
import threading
import time
import json


class AudioError(RuntimeError):
    pass


def hat_device(setup=Path('/opt/robot/feetech-ft5-r5/voice-device.json')):
    try:
        card=json.loads(setup.read_text())['card']
    except (OSError, ValueError, KeyError):
        card='aic3104'
    if not isinstance(card,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',card):
        raise AudioError('HAT 声卡配置无效')
    return 'plughw:'+card


class _ALSA:
    def __init__(self, device, stop_event, capture):
        self.device=device or hat_device()
        if not isinstance(self.device,str) or not re.fullmatch(r'plughw:[A-Za-z0-9_-]+',self.device):
            raise AudioError('只允许使用 HAT 配置的 ALSA 声卡')
        self.stop=stop_event if stop_event is not None else threading.Event()
        self.capture=capture
        self.proc=None
        self.errors=[]
        self.error_thread=None
        self.playback_until=0.0

    def __enter__(self):
        if not sys.platform.startswith('linux'):
            raise AudioError('HAT 录放音只能在 Zero 上运行')
        if self.capture:
            self._open()
        return self

    def _open(self):
        if self.stop.is_set():
            return
        executable=shutil.which('arecord' if self.capture else 'aplay')
        if not executable:
            raise AudioError('Zero 缺少系统 ALSA 音频命令，请使用已配置 HAT 音频的系统镜像。')
        argv=[executable,'-q','-D',self.device,'-t','raw','-f','S16_LE',
              '-c','1','-r','16000' if self.capture else '24000',
              '--buffer-time=120000','--period-time=20000']
        self.errors=[]
        self.playback_until=time.monotonic()
        self.proc=subprocess.Popen(argv, stdin=subprocess.DEVNULL if self.capture else subprocess.PIPE,
            stdout=subprocess.PIPE if self.capture else subprocess.DEVNULL,
            stderr=subprocess.PIPE,bufsize=0)
        proc=self.proc
        def drain():
            try:
                for line in proc.stderr:
                    self.errors.append(line.decode(errors='replace').strip()[:400])
                    del self.errors[:-8]
            except (OSError,ValueError):pass
        self.error_thread=threading.Thread(target=drain,daemon=True)
        self.error_thread.start()
        os.set_blocking((proc.stdout if self.capture else proc.stdin).fileno(),False)

    def _error(self, detail):
        if self.error_thread:self.error_thread.join(.05)
        tail='；'.join(self.errors[-3:])
        advice='。HAT 声卡正被其他音频程序占用。' if 'Device or resource busy' in tail else ''
        raise AudioError(detail+('：'+tail if tail else '')+advice)

    def __exit__(self,*args):
        self.close()

    def close(self, drain=False, cancel_event=None):
        proc,self.proc=self.proc,None
        if not proc:return True
        cancelled=lambda:self.stop.is_set() or bool(cancel_event and cancel_event.is_set())
        was_cancelled=cancelled()
        timed_out=False
        if drain and not self.capture and proc.stdin:
            proc.stdin.close()
            # EOF lets aplay play its pipe/device buffers out naturally. A fixed
            # one-second wait can kill audible tail audio and manufacture EINTR.
            deadline=max(time.monotonic()+3,self.playback_until+1)
            while proc.poll() is None:
                if was_cancelled or cancelled():
                    was_cancelled=True
                    break
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    timed_out=True
                    break
                try:proc.wait(timeout=min(.05,remaining))
                except subprocess.TimeoutExpired:pass
        was_cancelled=was_cancelled or cancelled()
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=.5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=.5)
        for stream in (proc.stdin,proc.stdout):
            if stream:
                try:stream.close()
                except (OSError,ValueError):pass
        if self.error_thread:self.error_thread.join(.5)
        if proc.stderr:proc.stderr.close()
        if drain and not was_cancelled:
            if timed_out:self._error('等待 HAT 播放结束超时，已释放本次播放进程')
            if proc.returncode:self._error('HAT 扬声器播放失败')
        return not was_cancelled and not timed_out


class NativeMicrophone(_ALSA):
    def __init__(self, device=None, stop_event=None):
        super().__init__(device,stop_event,True)

    def discard_pending(self):
        """Drop buffered old capture once when resuming after local playback."""
        proc=self.proc;discarded=0
        if not proc or self.stop.is_set():return discarded
        for _ in range(16):
            if self.stop.is_set() or not select.select([proc.stdout],[],[],0)[0]:break
            raw=os.read(proc.stdout.fileno(),65536)
            if not raw:break
            discarded+=len(raw)
        return discarded

    def read(self):
        packet=bytearray();deadline=time.monotonic()+3
        while not self.stop.is_set():
            proc=self.proc
            if not proc:self._error('HAT 麦克风已经关闭')
            ready,_,_=select.select([proc.stdout],[],[],.05)
            if ready:
                raw=os.read(proc.stdout.fileno(),640-len(packet))
                if not raw:self._error('HAT 麦克风音频流已结束')
                packet.extend(raw)
                if len(packet)==640:return bytes(packet)
            if time.monotonic()>deadline:self._error('HAT 麦克风 3 秒未返回音频')
        return b''


class NativeSpeaker(_ALSA):
    def __init__(self, device=None, stop_event=None, cancel_event=None):
        super().__init__(device,stop_event,False)
        self.cancel_event=cancel_event
        self.pcm_observer=None
        self._mouth_lease=None
        self._mouth_starting=False
        self._mouth_draining=False

    def _cancelled(self):
        return self.stop.is_set() or bool(self.cancel_event and self.cancel_event.is_set())

    def _mouth_playing(self):
        return (self._mouth_starting or self._mouth_draining or
                bool(self.proc and self.proc.poll() is None and time.monotonic()<self.playback_until+.15))

    def close(self,drain=False,cancel_event=None):
        self._mouth_draining=bool(drain)
        try:return super().close(drain=drain,cancel_event=cancel_event)
        finally:
            self._mouth_draining=False
            lease=getattr(self,'_mouth_lease',None)
            self._mouth_lease=None
            if lease:lease.close()

    def write(self, data):
        if len(data)%2:raise AudioError('HAT 收到未对齐的 PCM16 音频')
        if not data or self._cancelled():return False
        self._mouth_starting=True
        try:
            from ai_mouth_lease import MouthLease
            if self._mouth_lease is None:
                self._mouth_lease=MouthLease(self._mouth_playing,self._cancelled)
            self._mouth_lease.acquire()
        except Exception:
            self.close()
            raise
        finally:self._mouth_starting=False
        if not self.proc:self._open()
        view=memoryview(data);deadline=time.monotonic()+3
        while view and not self._cancelled():
            proc=self.proc
            if proc.poll() is not None:self._error('HAT 扬声器播放进程已结束')
            _,ready,_=select.select([],[proc.stdin],[],.05)
            if ready:
                try:count=os.write(proc.stdin.fileno(),view[:4096])
                except (BlockingIOError,InterruptedError):continue
                except BrokenPipeError:self._error('HAT 扬声器无法写入音频')
                starts=max(self.playback_until,time.monotonic())
                self.playback_until=starts+count/48000
                # Notification is nonblocking and cannot break audio on failure.
                # Its timestamp follows accepted PCM bytes, not cloud text timing.
                if self.pcm_observer:
                    try:self.pcm_observer(bytes(view[:count]),starts,count/48000)
                    except Exception:pass
                view=view[count:]
                deadline=time.monotonic()+3
            if time.monotonic()>deadline:self._error('HAT 扬声器写入超时')
        if self._cancelled():
            self.close()
            return False
        return True

    def finish(self):
        return self.close(drain=True,cancel_event=self.cancel_event)
