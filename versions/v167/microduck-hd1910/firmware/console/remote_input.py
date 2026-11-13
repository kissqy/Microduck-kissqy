"""One SSH session, official IPC intents, kernel hotplug arbitration. No idle polling."""
import json
import math
import os
from pathlib import Path
import selectors
import socket
import sys
import time

LEGACY_NAME = 'Microduck R17 Web Xbox'
BUTTONS = {'start', 'select', 'a', 'b', 'x', 'y', 'rb'}
AXES = {'lx', 'ly', 'rx', 'ry', 'lt', 'rt', 'dx', 'dy'}


def devices(root=Path('/sys/class/input')):
    """Called once after subscribing, then only on input hotplug events."""
    if not root.is_dir():
        raise OSError('Linux input 热插拔目录不存在')
    def bits(path):
        return sum(int(word,16) << (64*index) for index,word in enumerate(reversed(path.read_text().split())))
    result = []
    for node in sorted(root.glob('event*')):
        try:
            p = node / 'device'
            name = (p / 'name').read_text().strip()
            key, axes = bits(p / 'capabilities/key'), bits(p / 'capabilities/abs')
            if (key & ((1 << 0x130) | (1 << 0x120))) and axes & 3 == 3:
                result.append({'name': name, 'event': node.name, 'legacy_webpad': name == LEGACY_NAME})
        except FileNotFoundError:
            pass  # A node can disappear while processing its removal event.
    return result


def monitor():
    peer = socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM, 15)
    try:
        peer.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
        peer.bind((0, 1))
        peer.setblocking(False)
        return peer
    except BaseException:
        peer.close()
        raise


class ActionRefused(ValueError):
    pass


class Robot:
    def __init__(self, path):
        self.path, self.peer, self.reader, self.ident = path, None, None, 0
    def connect(self):
        if self.peer is None:
            peer = socket.socket(socket.AF_UNIX)
            try:
                peer.settimeout(.5)
                peer.connect(self.path)
                self.reader = peer.makefile('rb')
                self.peer = peer
            except BaseException:
                peer.close()
                raise
    def request(self, method, params=None):
        self.connect()
        self.ident += 1
        self.peer.sendall((json.dumps({'jsonrpc':'2.0','id':self.ident,'method':method,'params':params or {}})+'\n').encode())
        line = self.reader.readline(262145)
        if not line.endswith(b'\n') or len(line) > 262144:
            raise OSError('robotd IPC 已断开或响应无效')
        row = json.loads(line)
        if row.get('id') != self.ident:
            raise ValueError('robotd 回执编号不一致')
        if row.get('error'):
            error=row['error']
            raise ActionRefused(error.get('message',str(error)) if isinstance(error,dict) else str(error))
        result = row.get('result')
        if isinstance(result, dict) and result.get('accepted') is False:
            raise ActionRefused(result.get('reason') or 'robotd 拒绝动作')
        return result
    def notify(self, calls):
        if not calls:
            return
        self.connect()
        self.peer.sendall(b''.join((json.dumps({'jsonrpc':'2.0','method':method,'params':params})+'\n').encode() for method, params in calls))
    def close(self):
        if self.peer:
            self.peer.close()
        if self.reader:
            self.reader.close()
        self.peer = self.reader = None


class Input:
    def __init__(self, robot, clock=time.monotonic):
        self.robot, self.clock = robot, clock
        self.real, self.owner, self.deadline, self.failure = [], None, None, None
        self.events = lambda: None
        self.event_epoch = 0
        self.reset()
    def reset(self):
        self.previous, self.mode = set(), 'drive'
        self.prev_lt = self.prev_rt = 0
        self.select_at, self.shutdown_sent = None, False
        self.bindings = None
    def status(self, accepted=True, reason=None):
        return {'accepted':accepted,'available':self.failure is None,'real_connected':bool(self.real),
                'real_devices':self.real,'owner':self.owner,'input_mode':self.mode,
                'interface':'official robotd IPC','event_authoritative':True,
                **({'reason':reason or self.failure} if reason or self.failure else {})}
    def release(self, takeover=False):
        # Clear only this session's continuous intent. Never fabricate Select's
        # release, relax, shutdown, HOME or policy-disable on disappearance.
        if self.owner:
            calls = []
            if self.mode == 'body':
                calls.append(('robot.pose', {'active':False}))
            if not takeover:
                calls += [('robot.move', {'vx':0,'vy':0,'vyaw':0}), ('robot.mouth', {'open':0})]
                if self.prev_lt >= .3:
                    calls.append(('robot.sound', {'tag':'wheee','hold':False}))
            try:
                self.robot.notify(calls)
            except (OSError, ValueError):
                self.robot.close()
        self.owner, self.deadline = None, None
        self.reset()
    def hotplug(self, current):
        changed = current != self.real
        if changed:self.event_epoch += 1
        self.real = current
        if current:
            self.release(takeover=True)
        return changed
    def expired(self):
        if self.deadline is not None and self.clock() >= self.deadline:
            self.release()
            return True
        return False
    def frame(self, data):
        if not isinstance(data,dict) or set(data) != {'axes','buttons'}:
            raise ValueError('手柄帧字段无效')
        axes, buttons = data['axes'], data['buttons']
        if not isinstance(axes,dict) or set(axes) != AXES:
            raise ValueError('摇杆字段无效')
        for key, value in axes.items():
            lower = 0 if key in ('lt','rt') else -1
            if type(value) not in (int,float) or not math.isfinite(value) or not lower <= value <= 1:
                raise ValueError('摇杆值无效')
            if key in ('dx','dy') and value not in (-1,0,1):
                raise ValueError('方向键值无效')
        if not isinstance(buttons,list) or len(buttons) != len(set(buttons)) or not set(buttons) <= BUTTONS:
            raise ValueError('按键字段无效')
        return axes, set(buttons)
    def command(self, request):
        if not isinstance(request,dict) or set(request)-{'action','owner','frame','context'}:
            raise ValueError('输入命令无效')
        owner, action = request.get('owner'), request.get('action')
        if action == 'reset' and set(request)=={'action'}:
            self.release(takeover=bool(self.real))
            self.robot.close()
            return self.status()
        if not isinstance(owner,str) or not 8 <= len(owner) <= 80:
            raise ValueError('输入来源无效')
        if action == 'close':
            if owner == self.owner:
                self.release(takeover=bool(self.real))
            return self.status()
        if action != 'state':
            raise ValueError('输入命令无效')
        axes, buttons = self.frame(request.get('frame'))
        self.events()
        if self.failure or self.real:
            return self.status(False, self.failure or '实体手柄已接管；网页输入已丢弃')
        if self.owner is not None and self.owner != owner:
            return self.status(False, '另一网页正在控制；等待其释放输入')
        self.owner = owner
        event_epoch = self.event_epoch
        active = bool(buttons) or any(axes.values())
        self.deadline = self.clock() + .6 if active else None
        context = request.get('context') or {}
        settings = context.get('settings') or {}
        head = settings.get('head_rad', 2.5)
        mouth = settings.get('mouth_percent', 100)
        if head not in (.5,1,2.5) or type(mouth) not in (int,float) or not math.isfinite(mouth) or not 0 <= mouth <= 100:
            raise ValueError('头部或嘴巴幅度无效')
        down = buttons - self.previous
        calls = []
        def intent(method, params=None):
            self.events()
            if self.real or self.failure or event_epoch != self.event_epoch:
                raise ValueError(self.failure or '实体手柄已接管；网页输入已丢弃')
            result=self.robot.request(method,params)
            self.events()
            if self.real or self.failure or event_epoch != self.event_epoch:
                raise ValueError(self.failure or '实体手柄已接管；网页后续输入已丢弃')
            return result
        if 'start' in down:
            # An explicit button action may read status once; no background probe.
            bus = intent('robot.busStatus')
            if bus.get('homed') is True:
                intent('robot.enable', {'on':False,'toggle':True})
            else:
                intent('robot.init')
        old_mode = self.mode
        if 'y' in down:
            self.mode = 'drive' if self.mode == 'head' else 'head'
        if 'b' in down:
            self.mode = 'drive' if self.mode == 'body' else 'body'
        if old_mode == 'body' and self.mode != 'body':
            calls.append(('robot.pose', {'active':False}))
        if 'select' in down:
            self.select_at, self.shutdown_sent = self.clock(), False
        if 'select' in buttons and self.select_at is not None and not self.shutdown_sent and self.clock()-self.select_at >= 2:
            intent('robot.shutdown')
            self.shutdown_sent = True
        if 'select' in self.previous and 'select' not in buttons:
            if self.select_at is not None and not self.shutdown_sent:
                intent('robot.relax')
            self.select_at = None
        # Bindings come from the authoritative feedback already received by the PC.
        if self.bindings is None and (down & {'a','x','rb'} or axes['dy'] == 1):
            report=intent('pad.bindings')
            self.bindings={row['button']:row['skill'] for row in report['bindings']}
        bindings = self.bindings or {}
        skills = [bindings.get(button) for button in down & {'a','x','rb'}]
        if axes['dy'] == 1 and 'dpad_down' not in self.previous:
            skills.append(bindings.get('dpad_down'))
        for skill in skills:
            if skill:
                intent('robot.do', {'skill':skill})
        if 'x' in buttons and 'x' not in down and bindings.get('x'):
            calls.append(('robot.do', {'skill':bindings['x']}))
        def stick(key):
            value = axes[key]
            return 0 if abs(value) < .1 else value
        lx, ly, rx, ry = stick('lx'), -stick('ly'), stick('rx'), -stick('ry')
        if self.mode == 'drive':
            calls.append(('robot.move', {'vx':ly*.3,'vy':-lx*.3,'vyaw':-rx*1.5}))
        else:
            calls.append(('robot.move', {'vx':0,'vy':0,'vyaw':0}))
            if self.mode == 'head':
                calls.append(('robot.head', {'neck_pitch':ry*head,'head_pitch':-ly*head,'head_yaw':-lx*head,'head_roll':rx*head}))
            else:
                calls.append(('robot.pose', {'z':ly*(.010 if ly >= 0 else .025),'pitch':ry*.2618,'roll':rx*.2618,'active':True}))
        lt, rt = axes['lt'], axes['rt']
        calls.append(('robot.mouth', {'open':max(lt,rt)*mouth/100}))
        if rt >= .3 and self.prev_rt < .3:
            calls.append(('robot.sound', {'tag':'chirp'}))
        if lt >= .3 or self.prev_lt >= .3:
            calls.append(('robot.sound', {'tag':'wheee','hold':lt >= .3}))
        self.events()
        if self.real or self.failure or event_epoch != self.event_epoch:
            return self.status(False,self.failure or '实体手柄已接管；网页输入已丢弃')
        if self.deadline is not None and self.clock() >= self.deadline:
            self.release()
            return self.status(False,'输入已过期，未补发；请重新操作')
        self.robot.notify(calls)
        self.previous = buttons | ({'dpad_down'} if axes['dy'] == 1 else set())
        self.prev_lt, self.prev_rt = lt, rt
        return self.status()


def run(path):
    def output(row):
        print(json.dumps(row,ensure_ascii=False,allow_nan=False),flush=True)
    control, peer = Input(Robot(path)), None
    selector, pending = selectors.DefaultSelector(), bytearray()
    try:
        peer = monitor()  # Subscribe before the initial snapshot; close the discovery gap.
        selector.register(peer, selectors.EVENT_READ, 'hotplug')
        selector.register(sys.stdin.buffer, selectors.EVENT_READ, 'input')
        control.hotplug(devices())
        output({'event':'status','payload':control.status()})
        def drain_events():
            # Drain delivered events only. Sysfs is read solely after an actual
            # kernel input notification; there is no periodic device discovery.
            changed = False
            try:
                while True:
                    event = peer.recv(65536)
                    if len(event) == 65536:
                        raise OSError('热插拔事件被截断')
                    fields = dict(part.split(b'=',1) for part in event.split(b'\0') if b'=' in part)
                    if fields.get(b'SUBSYSTEM') == b'input' and fields.get(b'ACTION') in (b'add',b'remove',b'change'):
                        changed = True
            except BlockingIOError:
                pass
            except OSError as exc:
                control.failure='输入事件监听失败：'+str(exc)
                control.release(takeover=bool(control.real))
                output({'event':'status','payload':control.status(False)})
                raise
            if changed:
                control.event_epoch += 1
                current=devices()
                if not control.hotplug(current):control.release(takeover=bool(current))
                output({'event':'status','payload':control.status()})
        control.events=drain_events
        while True:
            timeout = None if control.deadline is None else max(0,control.deadline-control.clock())
            events = selector.select(timeout)
            # Process every pending kernel notification before any web command.
            drain_events()
            if control.expired():
                output({'event':'status','payload':control.status(reason='输入租期已结束；旧动作已清除')})
            if not any(key.data == 'input' for key, _ in events):
                continue
            chunk = os.read(sys.stdin.fileno(),65536)
            if not chunk:
                break
            pending.extend(chunk)
            if len(pending) > 65536:
                raise ValueError('网页输入积压过多，已丢弃')
            while b'\n' in pending:
                line, _, pending = pending.partition(b'\n')
                row = json.loads(line)
                ident = row.get('id')
                try:
                    result = control.command(row.get('command'))
                except ActionRefused as exc:
                    control.release(takeover=bool(control.real))
                    result = control.status(False,str(exc))
                except (OSError,ValueError,TypeError,KeyError) as exc:
                    control.release(takeover=bool(control.real))
                    control.robot.close()
                    result = control.status(False,str(exc))
                output({'id':ident,'result':result})
    except (OSError,ValueError) as exc:
        control.failure = '输入事件监听失败，网页输入暂停：'+str(exc)
        control.release(takeover=bool(control.real))
        output({'event':'status','payload':control.status(False)})
    finally:
        control.release(takeover=bool(control.real))
        control.robot.close()
        selector.close()
        if peer:
            peer.close()


if __name__ == '__main__':
    run(sys.argv[1])
