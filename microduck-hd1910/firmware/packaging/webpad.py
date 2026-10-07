#!/usr/bin/env python3
"""Browser input -> standard Xbox evdev device -> unmodified official padd.

Only input events are written. No robot IPC, serial bus, policy or motor commands.
The Xbox descriptor follows R17 GameSir R7 exactly (no digital trigger keys).
"""
import fcntl, grp, json, math, os, selectors, socket, struct, time, threading
from collections import deque
from pad_settings import load
import pad_settings
from pathlib import Path

NAME='Microduck R17 Web Xbox'
SOCKET=Path('/run/microduck-webpad/input.sock')
BUTTONS={'a':0x130,'b':0x131,'x':0x133,'y':0x134,'lb':0x136,'rb':0x137,
         'select':0x13a,'start':0x13b,'guide':0x13c,'ls':0x13d,'rs':0x13e}
AXES={'lx':0,'ly':1,'lt':2,'rx':3,'ry':4,'rt':5,'dx':16,'dy':17}
KEYS=list(BUTTONS.values())
TIMEOUT=.6
IDLE_EXIT=2.0

class PadTap:
    """Read-only official acknowledgement: preserve the first button edge at hotplug."""
    def __init__(self):
        self.name=None;self.generation=0
        threading.Thread(target=self.watch,daemon=True).start()
    def watch(self):
        while True:
            try:
                with socket.socket(socket.AF_UNIX) as s:
                    s.settimeout(1);s.connect('/run/padd/pad.sock')
                    s.sendall(b'{"jsonrpc":"2.0","id":1,"method":"pad.input"}\n')
                    buffer=bytearray()
                    while True:
                        try:chunk=s.recv(65536)
                        except socket.timeout:continue
                        if not chunk:raise ConnectionError('padd closed')
                        buffer.extend(chunk)
                        if len(buffer)>262144:raise ValueError('pad tap overflow')
                        while b'\n' in buffer:
                            line,_,rest=buffer.partition(b'\n');buffer=bytearray(rest)
                            params=json.loads(line).get('params',{})
                            if params.get('report')=='attached':
                                self.name=params['device']['name'];self.generation+=1
                            elif params.get('report')=='detached':self.name=None;self.generation+=1
            except (OSError,ValueError,KeyError):
                self.name=None;self.generation+=1
                threading.Event().wait(1)

def validate(frame):
    if not isinstance(frame,dict) or set(frame)-{'axes','buttons'}:raise ValueError('无效手柄状态')
    axes=frame.get('axes',{});buttons=frame.get('buttons',[])
    if not isinstance(axes,dict) or set(axes)-set(AXES):raise ValueError('无效手柄轴')
    if not isinstance(buttons,list) or len(buttons)>len(BUTTONS) or any(k not in BUTTONS for k in buttons) or len(set(buttons))!=len(buttons):raise ValueError('无效手柄按键')
    out={}
    for k in AXES:
        v=axes.get(k,0)
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('手柄轴必须是有限数值')
        lo=0 if k in ('lt','rt') else -1
        if not lo<=v<=1 or k in ('dx','dy') and v not in (-1,0,1):raise ValueError('手柄轴越界')
        out[k]=float(v)
    return out,set(buttons)

def bit_set(path):
    words=path.read_text().split()
    return sum(int(w,16)<<(64*i) for i,w in enumerate(reversed(words)))

def real_gamepads(root=Path('/sys/class/input')):
    found=[]
    for node in root.glob('event*/device'):
        try:
            name=(node/'name').read_text().strip()
            if name==NAME:continue
            keys=bit_set(node/'capabilities/key');axes=bit_set(node/'capabilities/abs')
            if keys & (1<<0x130) and axes & 3 == 3:
                found.append({'name':name,'event':node.parent.name})
        except (OSError,ValueError):continue
    return found

class InputMonitor:
    """Kernel hotplug wakeups; retain the old scan frequency if unavailable."""
    def __init__(self):
        self.socket=None
        try:
            peer=socket.socket(socket.AF_NETLINK,socket.SOCK_DGRAM,15)
            peer.bind((0,1));peer.setblocking(False);self.socket=peer
        except OSError:
            if 'peer' in locals():peer.close()
    def changed(self):
        changed=False
        if self.socket is None:return changed
        for _ in range(64):
            try:message=self.socket.recv(16384)
            except BlockingIOError:break
            except OSError:break
            if b'SUBSYSTEM=input\0' in message:changed=True
        return changed
    def close(self):
        if self.socket is not None:self.socket.close()

class DeviceCache:
    def __init__(self,scanner=real_gamepads,monitor=None,clock=time.monotonic):
        self.scanner,self.monitor,self.clock=scanner,monitor,clock
        self.next_scan=0;self.value=[]
    def invalidate(self):self.next_scan=0
    def __call__(self):
        if self.monitor is not None and self.monitor.changed():self.invalidate()
        now=self.clock()
        if now>=self.next_scan:
            self.value=self.scanner()
            self.next_scan=now+(1 if self.monitor is not None and self.monitor.socket is not None else .02)
        return self.value

class SettingsCache:
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.next_check=0;self.key=object();self.value=None;self.error=None
    def __call__(self):
        now=self.clock()
        if now>=self.next_check:
            self.next_check=now+.1
            path=pad_settings.PATH if pad_settings.PATH.exists() else pad_settings.LEGACY
            try:
                info=path.stat();key=(info.st_dev,info.st_ino,info.st_mtime_ns,info.st_size)
            except FileNotFoundError:key=None
            if key!=self.key:
                self.key=key
                try:self.value=load();self.error=None
                except (OSError,ValueError,KeyError) as exc:self.value=None;self.error=exc
        if self.error is not None:raise self.error
        return dict(self.value)

class Xbox:
    def __init__(self):
        self.fd=os.open('/dev/uinput',os.O_WRONLY|os.O_NONBLOCK)
        self.last={}
        try:
            for event in (0,1,3):fcntl.ioctl(self.fd,0x40045564,event)
            for key in KEYS:fcntl.ioctl(self.fd,0x40045565,key)
            for axis in AXES.values():fcntl.ioctl(self.fd,0x40045567,axis)
            for name,axis in AXES.items():
                low,high,flat=(-32768,32767,128)
                if name in ('lt','rt'):low,high,flat=0,255,0
                if name in ('dx','dy'):low,high,flat=-1,1,0
                fcntl.ioctl(self.fd,0x401c5504,struct.pack('HHiiiiii',axis,0,0,low,high,0,flat,0))
            fcntl.ioctl(self.fd,0x405c5503,struct.pack('HHHH80sI',3,0x045e,0x028e,0x0114,NAME.encode(),0))
            fcntl.ioctl(self.fd,0x5501)
            self.send({},set())
        except Exception:
            os.close(self.fd);raise
    def send(self,axes,buttons):
        report={}
        for k,code in AXES.items():
            v=axes.get(k,0)
            raw=round(v*255) if k in ('lt','rt') else int(v) if k in ('dx','dy') else round(v*(32767 if v>=0 else 32768))
            report[(3,code)]=raw
        report.update({(1,code):int(k in buttons) for k,code in BUTTONS.items()})
        events=[struct.pack('llHHi',0,0,kind,code,value) for (kind,code),value in report.items() if self.last.get((kind,code))!=value]
        if events:
            events.append(struct.pack('llHHi',0,0,0,0,0));os.write(self.fd,b''.join(events));self.last=report
    def close(self):
        # Destroy rather than fabricating Select release or robot commands during takeover.
        fcntl.ioctl(self.fd,0x5502);os.close(self.fd)

class Bridge:
    def __init__(self,device_factory=Xbox,devices=real_gamepads,clock=time.monotonic,ready=lambda pad:True,settings_loader=None):
        self.factory=device_factory;self.devices=devices;self.clock=clock;self.ready=ready;self.pending=deque()
        self.pad=None;self.owner=None;self.deadline=0;self.real=[];self.neutral=True
        self.settings_loader=settings_loader or SettingsCache(clock)
    def revoke(self):
        if self.pad:self.pad.close()
        self.pad=None;self.owner=None;self.deadline=0
        self.pending.clear()
    def poll(self):
        self.real=self.devices()
        if self.real:self.revoke()
        elif self.owner and self.clock()>=self.deadline:
            if self.neutral and not self.pending:self.owner=None;self.deadline=0
            else:self.revoke()
        elif self.pad and self.pending and self.ready(self.pad):self.send(*self.pending.popleft())
    def send(self,axes,buttons):
        self.pad.send(axes,buttons)
        self.neutral=not buttons and not any(axes.values())
    def status(self):
        try:settings=self.settings_loader();settings_error=''
        except (OSError,ValueError,KeyError) as exc:settings=None;settings_error=str(exc)
        return {'available':True,'real_connected':bool(self.real),'real_devices':self.real,
                'source':'physical' if self.real else 'web' if self.owner else 'none',
                'settings':settings,'settings_error':settings_error,'web_active':self.owner is not None,'owner':self.owner,'interface':'Xbox evdev -> official padd'}
    def handle(self,req):
        self.poll()
        if not isinstance(req,dict) or req.get('action') not in ('status','state','close'):raise ValueError('无效手柄请求')
        action=req['action'];owner=req.get('owner')
        if action=='status':return {'accepted':True,**self.status()}
        if not isinstance(owner,str) or not 8<=len(owner)<=180:raise ValueError('无效网页输入来源')
        if action=='close':
            if self.owner==owner:self.revoke()
            return {'accepted':True,**self.status()}
        axes,buttons=validate(req.get('frame'))
        # Raw triggers reach official sound thresholds; padd caps only robot.mouth.
        if self.real:return {'accepted':False,'reason':'真实手柄已接管，网页动作输入暂停',**self.status()}
        if self.owner and self.owner!=owner:return {'accepted':False,'reason':'另一网页正在使用手柄',**self.status()}
        # Unsupported model buttons are left unbound in official [pad] config.
        if self.pad is None:self.pad=self.factory()
        self.owner=owner;self.deadline=self.clock()+TIMEOUT
        if len(self.pending)>=32:self.revoke();raise ValueError('官方 padd 未确认网页手柄接入，请检查 padd 服务')
        if self.pending or not self.ready(self.pad):self.pending.append((axes,buttons))
        else:self.send(axes,buttons)
        return {'accepted':True,**self.status()}

def activated_listener():
    """systemd owns the listening path across this worker's idle exits."""
    try:active=int(os.environ.get('LISTEN_PID','0'))==os.getpid() and int(os.environ.get('LISTEN_FDS','0'))==1
    except ValueError:active=False
    if active:
        peer=socket.socket(fileno=3)
        os.environ.pop('LISTEN_PID',None);os.environ.pop('LISTEN_FDS',None)
        return peer,True
    SOCKET.parent.mkdir(parents=True,exist_ok=True);SOCKET.unlink(missing_ok=True)
    peer=socket.socket(socket.AF_UNIX)
    try:
        peer.bind(str(SOCKET));os.chown(SOCKET,0,grp.getgrnam('robot').gr_gid);os.chmod(SOCKET,0o660)
        peer.listen(8)
        return peer,False
    except Exception:
        peer.close()
        raise


def serve():
    tap=PadTap()
    def create():
        generation=tap.generation;pad=Xbox();pad.tap_generation=generation;return pad
    monitor=InputMonitor();devices=DeviceCache(monitor=monitor)
    bridge=Bridge(device_factory=create,devices=devices,ready=lambda pad:tap.name==NAME and tap.generation>pad.tap_generation)
    selector=selectors.DefaultSelector()
    listener,activated=activated_listener()
    last_input=time.monotonic()
    with listener:
        listener.setblocking(False);selector.register(listener,selectors.EVENT_READ)
        if monitor.socket is not None:selector.register(monitor.socket,selectors.EVENT_READ)
        clients={}
        def drop(client):
            selector.unregister(client);state=clients.pop(client,None);client.close()
            if state and state.get('owner') is not None and state['owner']==bridge.owner:bridge.revoke()
        try:
            while True:
                bridge.poll()
                if (activated and bridge.owner is None and time.monotonic()-last_input>=IDLE_EXIT
                        and not any(state['out'] for state in clients.values())):
                    return
                for client,state in list(clients.items()):
                    if time.monotonic()>=state['deadline']:drop(client)
                for key,mask in selector.select(.02):
                    if key.fileobj is monitor.socket:
                        devices.invalidate();bridge.poll();continue
                    if key.fileobj is listener:
                        client,_=listener.accept()
                        if len(clients)>=8:client.close();continue
                        client.setblocking(False);clients[client]={'buffer':bytearray(),'out':b'','deadline':time.monotonic()+.5,'owner':None};selector.register(client,selectors.EVENT_READ)
                        continue
                    client=key.fileobj
                    if client not in clients:continue
                    complete=True
                    try:
                        state=clients[client]
                        if mask & selectors.EVENT_WRITE:
                            sent=client.send(state['out']);state['out']=state['out'][sent:]
                            if not state['out']:
                                selector.modify(client,selectors.EVENT_READ);state['deadline']=time.monotonic()+10
                            complete=False;continue
                        chunk=client.recv(8192)
                        if not chunk:raise ConnectionError()
                        buffer=state['buffer'];buffer.extend(chunk)
                        if len(buffer)>8192:raise ValueError('请求过长')
                        if b'\n' not in buffer:complete=False;continue
                        line,_,tail=buffer.partition(b'\n')
                        if tail:raise ValueError('请等待上一条手柄回执')
                        try:
                            request=json.loads(line)
                            answer=bridge.handle(request)
                            if request.get('action')=='state' and answer.get('accepted'):
                                state['owner']=request.get('owner');last_input=time.monotonic()
                            elif request.get('action')=='close' and answer.get('accepted'):
                                state['owner']=answer.get('owner')
                        except (ValueError,OSError) as e:answer={'accepted':False,'reason':str(e),**bridge.status()}
                        state['out']=(json.dumps(answer,ensure_ascii=False)+'\n').encode()
                        if len(state['out'])>65536:raise ValueError('回执过长')
                        state['buffer']=bytearray();state['deadline']=time.monotonic()+.15
                        selector.modify(client,selectors.EVENT_WRITE)
                        complete=False
                    except BlockingIOError:complete=False
                    except (OSError,ValueError,ConnectionError):pass
                    else:pass
                    finally:
                        if complete:drop(client)
        finally:
            bridge.revoke()
            for client in clients:client.close()
            monitor.close();selector.close()
            if not activated:SOCKET.unlink(missing_ok=True)

if __name__=='__main__':serve()
