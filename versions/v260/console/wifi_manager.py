"""On-demand NetworkManager maintenance over the console's existing SSH channel.

This source stays in the PC package. It neither installs firmware nor replaces
the existing boot/hotspot services. Requests arrive on stdin; secrets never
appear in process arguments or result objects.
"""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import time


RUNTIME = Path('/run/microduck-console-wifi')
PROFILE_DIR = Path('/etc/NetworkManager/system-connections')
UUID_RE = re.compile(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z')
JOB_RE = re.compile(r'[0-9a-f]{24}\Z')


class WifiError(Exception):
    pass


def split_fields(line):
    """Decode nmcli --terse --escape yes, including escaped : and backslash."""
    fields, current = [], []
    i = 0
    while i < len(line):
        char = line[i]
        if char == '\\' and i + 1 < len(line) and line[i + 1] in ':\\':
            current.append(line[i + 1]); i += 2; continue
        if char == ':':
            fields.append(''.join(current)); current = []
        else:
            current.append(char)
        i += 1
    fields.append(''.join(current))
    return fields


def decode_value(value):
    # Values produced by --get-values have no colon delimiter.
    return ''.join(split_fields(value)) if '\\' in value else value


def valid_ssid(value):
    return (isinstance(value, str) and 1 <= len(value.encode('utf-8')) <= 32
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


def run(*args, timeout=15):
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=timeout,
                                env={**os.environ, 'LC_ALL': 'C', 'LANG': 'C'})
    except FileNotFoundError:
        raise WifiError('Zero 缺少网络管理工具，请检查 NetworkManager 是否已安装') from None
    except subprocess.TimeoutExpired:
        raise WifiError('Wi-Fi 操作超时，请检查 Zero 网络状态后刷新') from None
    if result.returncode:
        # NetworkManager stderr can contain arbitrary SSIDs and secret-agent
        # diagnostics. Keep it out of receipts and the PC system log.
        raise WifiError('Wi-Fi 操作未完成，请检查网络、密码和无线网卡状态后重试')
    return result.stdout


def private_dir(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise WifiError('Wi-Fi 临时任务目录权限异常，请重启 Zero 后重试')


def private_write(path, value):
    data = value.encode() if isinstance(value, str) else json.dumps(value, ensure_ascii=False).encode()
    temporary = path.with_name('.' + path.name + '-' + secrets.token_hex(6))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def operation_lock(runtime=RUNTIME):
    private_dir(runtime)
    fd = os.open(runtime / 'operation.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise WifiError('已有 Wi-Fi 操作正在执行，请稍后刷新') from None
        yield


class Manager:
    def __init__(self, runner=run, runtime=RUNTIME, profile_dir=PROFILE_DIR):
        self.run, self.runtime, self.profile_dir = runner, Path(runtime), Path(profile_dir)

    def interface(self):
        rows = self.run('nmcli', '-t', '-e', 'yes', '-f', 'DEVICE,TYPE,STATE', 'device', 'status')
        wifi = [split_fields(line) for line in rows.splitlines()]
        wifi = [r for r in wifi if len(r) == 3 and r[1] == 'wifi' and re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', r[0])]
        if not wifi:
            raise WifiError('Zero 未找到可用 Wi-Fi 网卡，请检查无线网卡和 NetworkManager')
        return next((r[0] for r in wifi if r[2] == 'connected'), wifi[0][0])

    def active_uuid(self, interface):
        rows = self.run('nmcli', '-t', '-e', 'yes', '-f', 'UUID,TYPE,DEVICE', 'connection', 'show', '--active')
        for line in rows.splitlines():
            row = split_fields(line)
            if len(row) == 3 and row[1] in ('wifi', '802-11-wireless') and row[2] == interface and UUID_RE.fullmatch(row[0]):
                return row[0].lower()
        return ''

    def profiles(self):
        persistent = persistent_uuids(self.profile_dir)
        rows = self.run('nmcli', '-t', '-e', 'yes', '-f', 'UUID,TYPE', 'connection', 'show')
        profiles = []
        for line in rows.splitlines():
            row = split_fields(line)
            if len(row) != 2 or row[1] not in ('wifi', '802-11-wireless') or not UUID_RE.fullmatch(row[0]):
                continue
            identity = row[0].lower()
            if identity not in persistent:
                continue
            values = self.run('nmcli', '-t', '-e', 'yes', '-g',
                              '802-11-wireless.ssid,802-11-wireless.mode,802-11-wireless-security.key-mgmt',
                              'connection', 'show', 'uuid', identity).splitlines()
            if len(values) != 3:
                raise WifiError('已保存 Wi-Fi 的回读格式异常，请刷新列表后重试')
            ssid, mode, security = map(decode_value, values)
            if mode not in ('', '--', 'infrastructure') or not valid_ssid(ssid):
                continue
            profiles.append({'uuid': identity, 'ssid': ssid, 'security': security if security != '--' else ''})
        return profiles

    def access_points(self, interface, scan=False):
        rows = self.run('nmcli', '-t', '-e', 'yes', '-f', 'SSID,SIGNAL,SECURITY',
                        'device', 'wifi', 'list', '--rescan', 'yes' if scan else 'no',
                        'ifname', interface, timeout=35 if scan else 15)
        best = {}
        for line in rows.splitlines():
            row = split_fields(line)
            if len(row) != 3 or not valid_ssid(row[0]):
                continue
            try:
                signal = max(0, min(100, int(row[1])))
            except ValueError:
                continue
            ap = {'ssid': row[0], 'signal': signal, 'security': '' if row[2] == '--' else row[2]}
            if row[0] not in best or signal > best[row[0]]['signal']:
                best[row[0]] = ap
        return best

    def status(self, scan=False):
        interface = self.interface()
        active = self.active_uuid(interface)
        addresses = parse_ipv4_addresses(self.run('nmcli', '-g', 'IP4.ADDRESS', 'device', 'show', interface))
        profiles = self.profiles()
        aps = self.access_points(interface, scan)
        networks = []
        known = set()
        for profile in profiles:
            ssid = profile['ssid']; known.add(ssid)
            remaining = {p['ssid'] for p in profiles if p['uuid'] != profile['uuid']}
            ap = aps.get(ssid, {})
            networks.append({**profile, 'signal': ap.get('signal'),
                             'security': ap.get('security', profile['security']),
                             'saved': True, 'connected': profile['uuid'] == active,
                             'can_forget': bool(remaining), 'in_range': ssid in aps})
        for ssid, ap in aps.items():
            if ssid not in known:
                networks.append({**ap, 'uuid': '', 'saved': False, 'connected': False,
                                 'can_forget': False, 'in_range': True})
        networks.sort(key=lambda n: (not n['connected'], not n['saved'], -(n['signal'] or 0), n['ssid'], n['uuid']))
        return {'accepted': True, 'interface': interface, 'active_uuid': active,
                'ipv4_addresses': addresses,
                'connected_ssid': next((p['ssid'] for p in profiles if p['uuid'] == active), ''),
                'saved_network_count': len(known), 'networks': networks}

    def busy(self):
        pending = self.runtime / 'pending.json'
        if not pending.exists():
            return False
        try:
            item = json.loads(pending.read_text())
            state = self.job(item.get('job_id', ''))
            return state['phase'] in ('scheduled', 'running')
        except (ValueError, KeyError, OSError, WifiError):
            raise WifiError('已有 Wi-Fi 任务状态异常，请重启 Zero 后重试') from None

    def forget(self, identity):
        if not isinstance(identity, str) or not UUID_RE.fullmatch(identity):
            raise WifiError('请选择已保存的 Wi-Fi 后再取消保存')
        identity = identity.lower()
        with operation_lock(self.runtime):
            if self.busy():
                raise WifiError('已有 Wi-Fi 连接任务，请等待完成后再取消保存')
            # Re-read while holding a process-wide lock. A stale UI or two
            # simultaneous requests can never bypass the final-network guard.
            profiles = self.profiles()
            if not any(p['uuid'] == identity for p in profiles):
                raise WifiError('该 Wi-Fi 已不存在或不是可取消保存的普通网络，请刷新列表')
            if not {p['ssid'] for p in profiles if p['uuid'] != identity}:
                raise WifiError('至少需要保留一个已保存的 Wi-Fi，不能取消保存最后一个')
            interface = self.interface()
            if self.active_uuid(interface) == identity:
                profile = next(p for p in profiles if p['uuid'] == identity)
                return self.schedule({'operation': 'forget', 'uuid': identity,
                                      'ssid': profile['ssid'], 'interface': interface,
                                      'profile_dir': str(self.profile_dir)})
            self.run('nmcli', '--wait', '15', 'connection', 'delete', 'uuid', identity, timeout=20)
            return {'accepted': True, 'message': '已取消保存所选 Wi-Fi',
                    'saved_network_count': len({p['ssid'] for p in self.profiles()})}

    def connect(self, payload):
        ssid, identity, password = payload.get('ssid'), payload.get('uuid', ''), payload.get('password', '')
        if not valid_ssid(ssid) or not isinstance(identity, str) or identity and not UUID_RE.fullmatch(identity):
            raise WifiError('Wi-Fi 名称或保存记录无效，请刷新列表后选择')
        if not isinstance(password, str) or len(password.encode('utf-8')) > 256 or any(c in password for c in '\r\n\0'):
            raise WifiError('Wi-Fi 密码格式无效')
        with operation_lock(self.runtime):
            if self.busy():
                raise WifiError('已有 Wi-Fi 连接任务，请等待完成后再连接')
            state = self.status()
            identity = identity.lower()
            selected = next((n for n in state['networks'] if n['ssid'] == ssid and n['uuid'] == identity), None)
            if selected is None:
                raise WifiError('所选 Wi-Fi 已变化或不在扫描列表中，请重新扫描')
            key_mgmt = ''
            if not identity:
                security = selected['security'].upper()
                if any(word in security for word in ('802.1X', 'EAP', 'WEP', 'OWE')):
                    raise WifiError('此 Wi-Fi 需要企业认证或特殊加密，请先在 Zero 配置后再连接')
                if security:
                    if not any(word in security for word in ('WPA', 'SAE', 'PSK')):
                        raise WifiError('暂不支持此 Wi-Fi 的加密方式')
                    raw_length = len(password.encode('utf-8'))
                    if not (8 <= raw_length <= 63 or re.fullmatch(r'[0-9A-Fa-f]{64}', password)):
                        raise WifiError('请输入 8–63 字节的 Wi-Fi 密码，或 64 位十六进制密钥')
                    key_mgmt = 'sae' if 'SAE' in security or 'WPA3' in security and not any(s in security for s in ('WPA1', 'WPA2')) else 'wpa-psk'
                elif password:
                    raise WifiError('此 Wi-Fi 为开放网络，无需输入密码')
            elif password:
                raise WifiError('已保存的 Wi-Fi 使用原有密码，请留空后连接')
            return self.schedule({'operation': 'connect', 'ssid': ssid, 'uuid': identity, 'password': password,
                                  'key_mgmt': key_mgmt, 'interface': state['interface'],
                                  'previous_uuid': state['active_uuid'], 'profile_dir': str(self.profile_dir)})

    def schedule(self, request):
        # Caller owns operation_lock. The unit survives the SSH transport and
        # returns a receipt before either network mutation is attempted.
        job_id = secrets.token_hex(12)
        task_dir = self.runtime / job_id
        private_dir(task_dir)
        private_write(task_dir / 'request.json', request)
        private_write(task_dir / 'worker.py', WORKER_SOURCE + '\nworker_main(sys.argv[1])\n')
        # ExecStopPost only removes the temporary request/code. Boot-only
        # hotspot decisions are never restarted by ordinary network operations.
        recovery = ('#!/bin/sh\nrm -f -- "' + str(task_dir / 'request.json') + '" "' + str(task_dir / 'worker.py') + '"\n')
        private_write(task_dir / 'recover.sh', recovery)
        operation = request['operation']
        initial = {'accepted': True, 'job_id': job_id, 'phase': 'scheduled',
                   'message': ('取消保存任务已提交；当前连接可能断开，请留意 Zero 的新 IP' if operation == 'forget'
                               else '连接任务已提交，正在等待切换 Wi-Fi；切换后 IP 可能变化'),
                   'created_at': time.time()}
        private_write(task_dir / 'status.json', initial)
        try:
            self.run('systemd-run', '--quiet', '--collect', '--unit=microduck-console-wifi-' + job_id,
                     '--on-active=2s', '--property=Type=oneshot', '--property=TimeoutStartSec=180',
                     '--property=TimeoutStopSec=30',
                     '--property=ExecStopPost=/bin/sh ' + str(task_dir / 'recover.sh'),
                     'python3', str(task_dir / 'worker.py'), str(task_dir), timeout=15)
        except Exception:
            for path in task_dir.iterdir():
                path.unlink()
            task_dir.rmdir()
            raise
        private_write(self.runtime / 'pending.json', {'job_id': job_id})
        return {**initial, 'scheduled': True}

    def job(self, job_id):
        if not isinstance(job_id, str) or not JOB_RE.fullmatch(job_id):
            raise WifiError('Wi-Fi 任务标识无效，请刷新列表')
        try:
            state = json.loads((self.runtime / job_id / 'status.json').read_text())
        except (OSError, ValueError):
            raise WifiError('未找到此 Wi-Fi 任务，Zero 可能已重启，请刷新列表') from None
        if state.get('phase') in ('scheduled', 'running') and time.time() - state.get('created_at', 0) > 220:
            state.update(phase='failed', message='Wi-Fi 任务未在规定时间内完成，请检查实际网络状态后刷新')
        return {k: state[k] for k in ('accepted', 'job_id', 'phase', 'message', 'ipv4_addresses') if k in state}


# This short detached worker is copied only into /run for the submitted task.
# It contains no credentials in its source or arguments. Its request disappears
# even if activation fails; the surviving status has no password.
WORKER_SOURCE = r'''
import configparser,fcntl,ipaddress,json,os,stat,subprocess,sys,time,uuid
from pathlib import Path

def parse_ipv4_addresses(text):
    addresses=[]
    for line in text.splitlines():
        try: address=ipaddress.IPv4Interface(line.strip()).ip
        except (ValueError,TypeError): continue
        value=str(address)
        if value not in addresses: addresses.append(value)
    return addresses

def nm(*args, timeout=55):
    p=subprocess.run(['nmcli',*args],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                     timeout=timeout,env={**os.environ,'LC_ALL':'C','LANG':'C'})
    if p.returncode: raise RuntimeError('network operation failed')

def write_private(path,text):
    tmp=path.with_name('.'+path.name+'-'+uuid.uuid4().hex)
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'w') as f: f.write(text);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally: tmp.unlink(missing_ok=True)

def key_escape(text):
    return text.replace('\\','\\\\').replace(' ','\\s').replace('\t','\\t')

def persistent_uuids(primary):
    found=set()
    paths=[Path(primary)]
    if str(primary)=='/etc/NetworkManager/system-connections':
        paths.append(Path('/usr/lib/NetworkManager/system-connections'))
    for directory in paths:
        if not directory.exists(): continue
        for path in directory.iterdir():
            if path.is_symlink() or not path.is_file(): continue
            c=configparser.RawConfigParser(interpolation=None,strict=False)
            try:
                if path.stat().st_size>256*1024: continue
                c.read_string(path.read_text())
                connection=c['connection']
                wireless=c['wifi'] if 'wifi' in c else c['802-11-wireless']
                if connection.get('type') not in ('wifi','802-11-wireless'): continue
                if wireless.get('mode','infrastructure')!='infrastructure' or not wireless.get('ssid'): continue
                found.add(str(uuid.UUID(connection['uuid'])))
            except (OSError,ValueError,KeyError,configparser.Error): continue
    return found

def forget_saved(identity,primary):
    persistent=persistent_uuids(primary)
    p=subprocess.run(['nmcli','-t','-e','yes','-f','UUID,TYPE','connection','show'],
                     capture_output=True,text=True,timeout=15,env={**os.environ,'LC_ALL':'C'})
    if p.returncode: raise RuntimeError('saved profiles unavailable')
    profiles=[]
    for line in p.stdout.splitlines():
        fields=line.split(':')
        if len(fields)!=2 or fields[1] not in ('wifi','802-11-wireless') or fields[0] not in persistent: continue
        q=subprocess.run(['nmcli','-g','802-11-wireless.mode','connection','show','uuid',fields[0]],
                         capture_output=True,text=True,timeout=10,env={**os.environ,'LC_ALL':'C'})
        if q.returncode: raise RuntimeError('saved profile unavailable')
        if q.stdout.strip() in ('','--','infrastructure'): profiles.append(fields[0])
    if identity not in profiles: raise ValueError('所选 Wi-Fi 已不存在，请刷新列表')
    if len([p for p in profiles if p!=identity])<1:
        raise ValueError('至少需要保留一个已保存的 Wi-Fi，不能取消保存最后一个')
    nm('--wait','15','connection','delete','uuid',identity,timeout=20)

def worker_main(directory):
    task=Path(directory);request=task/'request.json';created='';profile=None;cfg={}
    status=json.loads((task/'status.json').read_text())
    def report(phase,message):
        status.update(phase=phase,message=message)
        write_private(task/'status.json',json.dumps(status,ensure_ascii=False))
    fd=os.open(task.parent/'operation.lock',os.O_RDWR|os.O_NOFOLLOW)
    with os.fdopen(fd,'r+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:
            cfg=json.loads(request.read_text())
            if cfg.get('operation')=='forget':
                report('running','正在取消保存当前 Wi-Fi；连接可能断开')
                forget_saved(cfg['uuid'],cfg['profile_dir'])
                report('forgotten','已取消保存所选 Wi-Fi，其他已保存网络仍保留；请根据实际 IP 重连中控')
                return
            report('running','正在连接所选 Wi-Fi，切换后 IP 可能变化')
            identity=cfg['uuid']
            if not identity:
                identity=str(uuid.uuid4());created=identity
                profile=Path(cfg['profile_dir'])/('microduck-console-'+identity+'.nmconnection')
                text=('[connection]\nid=Microduck Console '+identity+'\nuuid='+identity+
                      '\ntype=wifi\nautoconnect=true\n\n[wifi]\nmode=infrastructure\nssid='+
                      ';'.join(str(b) for b in cfg['ssid'].encode('utf-8'))+';\n')
                if cfg['key_mgmt']:
                    text+='\n[wifi-security]\nkey-mgmt='+cfg['key_mgmt']+'\npsk='+key_escape(cfg['password'])+'\n'
                text+='\n[ipv4]\nmethod=auto\n\n[ipv6]\nmethod=auto\n'
                write_private(profile,text)
                nm('connection','load',str(profile),timeout=15)
            nm('--wait','45','connection','up','uuid',identity,'ifname',cfg['interface'],timeout=55)
            # A successful activation alone is not enough: confirm this UUID is
            # active on the selected wireless interface and has an IPv4 address.
            p=subprocess.run(['nmcli','-t','-e','yes','-f','UUID,DEVICE','connection','show','--active'],
                             capture_output=True,text=True,timeout=10,env={**os.environ,'LC_ALL':'C'})
            rows=p.stdout.splitlines()
            if p.returncode or identity+':'+cfg['interface'] not in rows: raise RuntimeError('wrong active profile')
            p=subprocess.run(['nmcli','-g','IP4.ADDRESS','device','show',cfg['interface']],
                             capture_output=True,text=True,timeout=10,env={**os.environ,'LC_ALL':'C'})
            addresses=parse_ipv4_addresses(p.stdout)
            if p.returncode or not addresses: raise RuntimeError('no IPv4 address')
            status['ipv4_addresses']=addresses
            report('connected','已连接所选 Wi-Fi；如果中控断开，请填写 Zero 的新 IP 后重连')
        except Exception as error:
            if created:
                try: nm('--wait','10','connection','delete','uuid',created,timeout=15)
                except Exception: pass
                if profile: profile.unlink(missing_ok=True)
            restored=False
            if cfg.get('previous_uuid'):
                try:
                    nm('--wait','20','connection','up','uuid',cfg['previous_uuid'],'ifname',cfg['interface'],timeout=25)
                    restored=True
                except Exception: pass
            if cfg.get('operation')=='forget':
                report('failed',str(error) if isinstance(error,ValueError) else '取消保存未完成，请刷新检查实际保存列表')
            else:
                report('failed','Wi-Fi 连接失败，请检查密码和信号；'+('已恢复原网络连接' if restored else '原有 Wi-Fi 保存信息已保留，请刷新检查实际连接'))
        finally:
            request.unlink(missing_ok=True)
            (task/'worker.py').unlink(missing_ok=True)
'''

# Use the identical persistent-profile parser in the foreground and detached
# worker. Reading these files never sends their password values to the PC.
_worker_helpers = {}
exec(WORKER_SOURCE, _worker_helpers)
persistent_uuids = _worker_helpers['persistent_uuids']
parse_ipv4_addresses = _worker_helpers['parse_ipv4_addresses']


def execute(payload, manager=None):
    if not isinstance(payload, dict):
        raise WifiError('Wi-Fi 请求格式无效')
    fields = {'status': {'action'}, 'scan': {'action'}, 'connect': {'action', 'ssid', 'uuid', 'password'},
              'forget': {'action', 'uuid'}, 'job': {'action', 'job_id'}}
    action = payload.get('action')
    if action not in fields or set(payload) - fields[action]:
        raise WifiError('Wi-Fi 操作或参数不受支持')
    manager = manager or Manager()
    if action in ('status', 'scan'):
        return manager.status(scan=action == 'scan')
    if action == 'connect':
        return manager.connect(payload)
    if action == 'forget':
        return manager.forget(payload.get('uuid'))
    return manager.job(payload.get('job_id'))


def main():
    try:
        if os.geteuid() != 0:
            raise WifiError('Wi-Fi 操作需要 Zero sudo 权限，请填写 SSH / sudo 密码后重试')
        raw = sys.stdin.read(12289)
        if len(raw.encode('utf-8')) > 12288:
            raise WifiError('Wi-Fi 请求过长')
        # sudo -S may leave its input line unread when a credential was cached.
        # The PC always sends the single-line JSON request last.
        lines = [line for line in raw.splitlines() if line.strip()]
        if not lines:
            raise WifiError('未收到 Wi-Fi 操作请求')
        result = execute(json.loads(lines[-1]))
    except WifiError as exc:
        result = {'accepted': False, 'error': str(exc), 'message': str(exc)}
    except (OSError, ValueError, UnicodeError):
        result = {'accepted': False, 'error': 'Wi-Fi 配置读写失败，请检查 Zero 文件系统和网络状态',
                  'message': 'Wi-Fi 配置读写失败，请检查 Zero 文件系统和网络状态'}
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
