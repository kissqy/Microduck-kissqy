"""One explicit GameSir recovery transaction; stdlib only, run on the Zero over SSH."""
import ctypes
import fcntl
import json
import os
from pathlib import Path
import re
import select
import socket
import subprocess
import struct
import sys
import time

NAME = 'GameSir-Nova 2 Lite'
VIRTUAL = 'Xbox 360 Controller (GameSir Nova 2 Lite)'
HID = '00001124-0000-1000-8000-00805f9b34fb'
MAC = r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}'
INPUTS = ('gamesir-xboxd.service', 'padd.service')
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
DEADLINE = None


class RepairError(Exception):
    def __init__(self, message, phase='failed'):
        super().__init__(message)
        self.phase = phase


def emit(phase, message, status='success', **extra):
    print(json.dumps({'pad_repair_progress': {'phase': phase, 'status': status, 'message': message, **extra}},
                     ensure_ascii=False), file=sys.stderr, flush=True)


def run(*args, timeout=10, check=True):
    timeout = time_budget(timeout)
    result = subprocess.run(args, capture_output=True, text=True, errors='replace',
                            timeout=timeout, env={**os.environ, 'LC_ALL': 'C'})
    output = ANSI.sub('', result.stdout + '\n' + result.stderr).strip()
    if check and result.returncode:
        raise RepairError(f'{args[0]} 未成功：{output[-700:]}')
    return output


def time_budget(timeout):
    if DEADLINE is None:
        return timeout
    left = DEADLINE - time.monotonic()
    if left <= 0:
        raise RepairError('本次修复已达到 120 秒时间上限。服务会恢复，请核对手柄配对状态后重试。', 'timeout')
    return min(timeout, left)


def property_value(text, name):
    match = re.search(r'^\s*' + re.escape(name) + r':\s*(.*?)\s*$', text, re.M)
    return match.group(1) if match else None


def devices(text):
    return {
        address: NAME for address in re.findall(r'^Device (' + MAC + r') ' + re.escape(NAME) + r'\s*$', text, re.M)}


def loaded(unit):
    return run('systemctl', 'show', unit, '-p', 'LoadState', '--value', check=False) == 'loaded'


def active(unit):
    return run('systemctl', 'is-active', unit, check=False) == 'active'


def rpc(method):
    with socket.socket(socket.AF_UNIX) as peer:
        peer.settimeout(time_budget(3))
        peer.connect('/run/robotd.sock')
        peer.sendall((json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': {}}) + '\n').encode())
        with peer.makefile('rb') as reader:
            line = reader.readline(262145)
    response = json.loads(line)
    if response.get('id') != 1 or response.get('error') or 'result' not in response:
        raise RepairError('机器人未确认停止：' + str(response.get('error', '回执无效')))
    result = response['result']
    if isinstance(result, dict) and result.get('accepted') is False:
        raise RepairError('机器人拒绝停止：' + str(result.get('reason', '未确认')))
    return result


def stop_motion():
    if not active('robotd.service'):
        return
    emit('relaxing', '先停止运动并卸力；完成后不会自动 HOME。', 'waiting')
    rpc('robot.relax')
    end = time.monotonic() + time_budget(8)
    while time.monotonic() < end:
        report = rpc('robot.busStatus')
        if not isinstance(report, dict):
            raise RepairError('机器人停止状态回执无效')
        if not report.get('torque_off_pending') and (
                report.get('mode') == 'commissioning' and report.get('torque_state') == 'off'
                or report.get('mode') == 'motion' and report.get('native', {}).get('torque_state_confirmed') is False):
            return
        # A failed, never-started control loop cannot report fresh torque. No UART is opened here.
        if report.get('phase') == 'configuration_error' and report.get('cycle', 0) == 0:
            return
        time.sleep(.2)
    raise RepairError('未确认机器人卸力。请扶稳机身，先点“停止并松开”，再修复手柄。', 'relax_unconfirmed')


class BluetoothSession:
    """Keep agent and discovery owned by the same client until pair/connect finishes."""
    def __init__(self):
        self.proc = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, bufsize=0,
                                     env={**os.environ, 'LC_ALL': 'C', 'TERM': 'dumb'})
        self.read(.3)

    def read(self, timeout):
        if self.proc.poll() is not None:
            raise RepairError('bluetoothctl 已退出；本次操作已停止')
        if not select.select([self.proc.stdout], [], [], timeout)[0]:
            return ''
        data = os.read(self.proc.stdout.fileno(), 16384).decode('utf-8', errors='replace')
        text = ANSI.sub('', data).replace('\r', '\n')
        return text

    def command(self, command, success, timeout=8):
        timeout = time_budget(timeout)
        drain_until = time.monotonic() + .2
        while time.monotonic() < drain_until and self.read(0):
            pass
        self.proc.stdin.write((command + '\n').encode())
        self.proc.stdin.flush()
        text = ''
        end = time.monotonic() + time_budget(timeout)
        while time.monotonic() < end:
            text = (text + self.read(min(.5, max(0, end - time.monotonic()))))[-32768:]
            if any(marker in text for marker in success):
                return text
            if command.startswith('pair ') and 'Accept pairing (yes/no)' in text:
                # This agent is only registered for our client's explicit Pair call, never made global/default.
                self.proc.stdin.write(b'yes\n')
                self.proc.stdin.flush()
                text = ''
            if 'Enter PIN code' in text or 'Enter passkey' in text or 'Confirm passkey' in text:
                raise RepairError('手柄请求了 PIN/密码确认。请核对 A+HOME 模式后重新修复。')
            if re.search(r'Failed|not available|No default controller|Invalid command|AuthenticationCanceled', text):
                raise RepairError(f'{command}：{text.strip()[-900:]}')
        raise RepairError(f'{command} 等待回执超时：{text.strip()[-500:]}')

    def close(self):
        try:
            self.proc.stdin.write(b'quit\n')
            self.proc.stdin.flush()
            self.proc.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()
            self.proc.wait(timeout=3)
        finally:
            self.proc.stdin.close()
            self.proc.stdout.close()


def info(address):
    return run('bluetoothctl', 'info', address, check=False)


def connected(address):
    text = info(address)
    return property_value(text, 'Connected') == 'yes' and property_value(text, 'Paired') == 'yes'


def connect_hid(session, address):
    # Pair() can leave the temporary ACL link connected without opening HID.
    # Connected: yes alone must never skip this explicit profile connection.
    emit('bluetooth', '使用已完成的配对连接 HID 输入通道一次。', 'waiting')
    try:
        session.command('connect ' + address + ' ' + HID,
                        ['Connection successful', 'org.bluez.Error.AlreadyConnected'], timeout=20)
    except (RepairError, subprocess.TimeoutExpired) as exc:
        raise RepairError('HID 输入连接失败：' + str(exc) + '；目标配对已保留，未重启 robotd。',
                          'connect_failed') from exc


def reset_adapter(session):
    emit('adapter', '重新配对：切换蓝牙适配器电源一次。', 'waiting')
    try:
        try:
            session.command('power off', ['Changing power off succeeded', 'Powered: no', 'PowerState: off'])
        except RepairError:
            # BlueZ may report Failed after the controller has actually powered off.
            if property_value(run('bluetoothctl', 'show'), 'Powered') != 'no':
                raise
        session.command('power on', ['Changing power on succeeded'])
        state = run('bluetoothctl', 'show')
        if property_value(state, 'Powered') != 'yes' or property_value(state, 'PowerState') in ('off', 'on-disabling'):
            raise RepairError('蓝牙电源回读状态异常：' + state[-600:])
    except RepairError as exc:
        # A failed power-off request may still complete asynchronously; leave the adapter on if possible.
        try:
            session.command('power on', ['Changing power on succeeded'])
        except RepairError:
            pass
        raise RepairError('蓝牙适配器电源未恢复：' + str(exc) + '；本次操作已停止，未自动重启 Zero。', 'adapter_failed') from exc
    emit('adapter', '蓝牙适配器电源已恢复并确认开启。')


def pair_device(session, address):
    session.command('agent off', ['Agent unregistered', 'No agent is registered'])
    session.command('agent NoInputNoOutput', ['Agent registered', 'Agent is already registered'])
    session.command('pairable on', ['Changing pairable on succeeded'])
    emit('scanning', '等待处于配对模式的 Nova 2 Lite；最多扫描 15 秒。', 'waiting')
    try:
        session.command('scan on', ['Discovery started'])
    except RepairError as exc:
        phase = 'scan_busy' if 'InProgress' in str(exc) else 'scan_failed'
        raise RepairError('蓝牙扫描未启动：' + str(exc) + '；请结束其他蓝牙扫描后重试，未自动重启系统。', phase) from exc
    end = time.monotonic() + time_budget(15)
    fresh = set()
    text = ''
    while time.monotonic() < end:
        text = (text + session.read(max(0, end - time.monotonic())))[-32768:]
        fresh.update(re.findall(r'(?:\[NEW\] )?Device (' + MAC + r') ' + re.escape(NAME) + r'\s*(?:\n|$)', text))
        fresh.update(re.findall(r'\[CHG\] Device (' + MAC + r') Name: ' + re.escape(NAME) + r'\s*(?:\n|$)', text))
        if address in fresh or not address and fresh:
            break
    # Devices may be emitted across read chunks; after a reset/removal the cache also contains newly found names.
    found = fresh or set(devices(run('bluetoothctl', 'devices')))
    if address:
        if address not in found:
            raise RepairError('未发现所选手柄。确认 A+HOME 模式，并按住 HOME+截图键进入配对后重试。', 'not_found')
    elif len(found) == 1:
        address = next(iter(found))
    elif len(found) > 1:
        raise RepairError('发现多只 Nova 2 Lite，请在修复面板填写目标 MAC：' + '、'.join(sorted(found)), 'choose_device')
    else:
        raise RepairError('未发现 GameSir-Nova 2 Lite。手柄需进入 A+HOME 模式；慢闪时按住 HOME+截图键 2–3 秒。', 'not_found')
    emit('scanning', '已发现目标手柄 ' + address + '。')
    session.command('scan off', ['Discovery stopped'])
    emit('pairing', '正在配对 ' + address + '。', 'waiting')
    session.command('pair ' + address, ['Pairing successful'], timeout=30)
    session.command('trust ' + address, ['trust succeeded'])
    emit('pairing', '目标手柄已配对并设为可信。')
    return address


def bridge_state():
    text = Path('/proc/bus/input/devices').read_text(errors='replace')
    nodes = []
    for block in text.split('\n\n'):
        if 'Name="' + VIRTUAL + '"' in block:
            nodes.extend('/dev/input/' + name for name in re.findall(r'\bevent\d+\b', block))
    bridge_active, padd_active = active(INPUTS[0]), active(INPUTS[1])
    padd_open = False
    padd_waiting, bridge_waiting = False, False
    if bridge_active and not nodes:
        pid = run('systemctl', 'show', INPUTS[0], '-p', 'MainPID', '--value', check=False).strip()
        if pid.isdecimal() and int(pid) > 0:
            try:
                bridge_waiting = b'startup_gate.py' in (Path('/proc') / pid / 'cmdline').read_bytes()
            except FileNotFoundError:
                pass
    if padd_active and nodes:
        pid = run('systemctl', 'show', INPUTS[1], '-p', 'MainPID', '--value', check=False).strip()
        if pid.isdecimal() and int(pid) > 0:
            try:
                padd_waiting = b'startup_gate.py' in (Path('/proc') / pid / 'cmdline').read_bytes()
                for fd in (Path('/proc') / pid / 'fd').iterdir():
                    try:
                        padd_open |= os.readlink(fd) in nodes
                    except FileNotFoundError:
                        pass
            except (FileNotFoundError, ProcessLookupError):
                pass  # A service can change process while this one-off read runs.
    return {'physical': ('Name="' + NAME + '"') in text,
            'virtual': bool(nodes), 'bridge_active': bridge_active, 'padd_active': padd_active,
            'padd_open': padd_open, 'padd_waiting': padd_waiting, 'bridge_waiting': bridge_waiting}


class InputWatch:
    """Temporary input-node watcher used only by an explicit repair request."""
    def __init__(self, root=Path('/dev')):
        self.root = Path(root)

    def __enter__(self):
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.fd = self.libc.inotify_init1(os.O_CLOEXEC | os.O_NONBLOCK)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), '无法等待输入设备热插拔')
        self.child = -1
        try:
            if self.libc.inotify_add_watch(self.fd, os.fsencode(self.root), 0x100 | 0x80) < 0:
                raise OSError(ctypes.get_errno(), '无法订阅输入目录创建')
            self.add_child()
        except BaseException:
            os.close(self.fd); raise
        return self

    def add_child(self):
        if self.child < 0:
            # OPEN observes padd opening the new Xbox node, without probing it ourselves.
            self.child = self.libc.inotify_add_watch(self.fd, os.fsencode(self.root/'input'), 0x100 | 0x80 | 0x4 | 0x20 | 0x200 | 0x400)

    def wait(self, timeout):
        end = time.monotonic() + time_budget(timeout)
        while time.monotonic() < end:
            if not select.select([self.fd], [], [], max(0, end - time.monotonic()))[0]:
                return False
            events = os.read(self.fd, 65536)
            at, relevant = 0, False
            while at < len(events):
                wd, mask, _, size = struct.unpack_from('iIII', events, at)
                name = events[at+16:at+16+size].split(b'\0', 1)[0]
                if mask & 0x8000 and wd == self.child:
                    self.child = -1
                if name == b'input':
                    self.add_child(); relevant = True
                relevant |= wd == self.child and name.startswith(b'event') or bool(mask & 0x4000)
                at += 16 + size
            if relevant:
                return True
        return False

    def __exit__(self, *_):
        os.close(self.fd)


def input_ready(state):
    return all(state.get(k) is True for k in ('physical', 'virtual', 'bridge_active', 'padd_active', 'padd_open'))


def finish_input():
    with InputWatch() as watch:
        state = bridge_state()
        # Start only missing services; never rewrite enable/disable settings.
        for unit, key in zip(INPUTS, ('bridge_active', 'padd_active')):
            if not state[key]:
                run('systemctl', 'start', unit, timeout=20)
            elif unit == INPUTS[0] and state['physical'] and not state['virtual'] and not state['bridge_waiting']:
                run('systemctl', 'restart', unit, timeout=20)
                emit('bridge_service', '只重启缺少虚拟 Xbox 的 GameSir 桥接服务；未操作其他服务。')
            elif unit == INPUTS[1] and state['virtual'] and not state['padd_open'] and not state['padd_waiting']:
                run('systemctl', 'restart', unit, timeout=20)
                emit('padd_service', '只重启尚未打开虚拟 Xbox 的 padd；未操作 robotd。')
        end = time.monotonic() + time_budget(8)
        while True:
            state = bridge_state()
            if input_ready(state) or time.monotonic() >= end:
                return state
            emit('input', '等待实体输入、虚拟 Xbox 与 padd 接入事件。', 'waiting', evidence=state)
            if not watch.wait(max(0, end - time.monotonic())):
                return bridge_state()


def evidence(receipt, address):
    receipt.update(bridge_state(), address=address, bluetooth_connected=bool(address and connected(address)))
    return receipt


def report_input(receipt, failure=None):
    failed_layer = {'connect_failed': 'bluetooth', 'physical_unready': 'physical',
                    'bridge_unready': 'bridge', 'padd_unready': 'padd'}.get(getattr(failure, 'phase', None))
    for phase, key, good, bad in (
        ('bluetooth', 'bluetooth_connected', '目标手柄蓝牙已连接。', '目标手柄蓝牙未连接。'),
        ('physical', 'physical', '实体 GameSir 输入已出现。', '尚未出现实体 GameSir 输入。'),
        ('bridge', 'virtual', '虚拟 Xbox 已创建。', '尚未创建虚拟 Xbox。'),
        ('padd', 'padd_open', 'padd 已打开虚拟 Xbox 输入设备。', 'padd 尚未打开虚拟 Xbox；服务运行不代表已接入。')):
        if phase == failed_layer:
            bad = str(failure)
        ready = bool(receipt.get(key)) and phase != failed_layer
        emit(phase, good if ready else bad, 'success' if ready else 'failed', evidence=receipt)


def input_failure(state, bluetooth_connected):
    if not bluetooth_connected:
        return RepairError('等待输入接入时，目标手柄蓝牙已断开；目标配对已保留。'
                           '请保持手柄开机和 A+HOME 模式，再点“连接／修复”；未重启 robotd。', 'connect_failed')
    if not state['physical']:
        return RepairError('蓝牙已连接，但尚未出现实体 GameSir 输入设备；HID 接入未完成。'
                           '目标配对已保留，未重启 robotd。', 'physical_unready')
    if not state['virtual'] or not state['bridge_active']:
        if state.get('bridge_waiting'):
            return RepairError('实体手柄已接入；GameSir 桥接仍在等待主服务启动完成事件，'
                               '未重新配对或重启 robotd。', 'bridge_unready')
        return RepairError('实体手柄已接入，但 GameSir 桥接未创建虚拟 Xbox；'
                           '请查看桥接服务结果，未重启 robotd。', 'bridge_unready')
    if state.get('padd_waiting'):
        return RepairError('虚拟 Xbox 已创建；padd 仍在等待原有启动条件，未重启 robotd。', 'padd_unready')
    return RepairError('虚拟 Xbox 已创建，但 padd 尚未打开它；请查看 padd 服务结果，未重启 robotd。',
                       'padd_unready')


def repair(address='', operation='repair'):
    global DEADLINE
    DEADLINE = time.monotonic() + 120
    try:
        return _repair(address, operation)
    finally:
        DEADLINE = None


def _repair(address, operation):
    global DEADLINE
    if address and not re.fullmatch(MAC, address):
        raise RepairError('手柄 MAC 格式无效')
    if operation not in ('repair', 'pair'):
        raise RepairError('手柄操作无效')
    with open('/run/microduck-pad-repair.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RepairError('另一项手柄修复正在执行，请等待完成。', 'busy') from None
        emit('checking', '核对目标手柄与输入服务。', 'waiting')
        missing = [unit for unit in (*INPUTS, 'bluetooth.service') if not loaded(unit)]
        if missing:
            raise RepairError('未安装服务：' + '、'.join(missing) + '；请安装当前中控随包固件。', 'missing_service')
        known = devices(run('bluetoothctl', 'devices'))
        if not address and len(known) > 1:
            raise RepairError('有多只已记录手柄，请填写目标 MAC：' + '、'.join(sorted(known)), 'choose_device')
        address = address or next(iter(known), '')
        if address:
            text = info(address)
            name = property_value(text, 'Name')
            if name != NAME and (name is not None or property_value(text, 'Paired') == 'yes'):
                raise RepairError('所选设备不是 A+HOME 模式的 GameSir-Nova 2 Lite，未删除其配对。', 'wrong_device')
        emit('checking', '已确认目标手柄与已安装输入服务；' + (address or '尚无已记录手柄') + '。')
        session = None
        paused, phone_paused = False, False
        input_was_active = {}
        failure_reported = False
        receipt = {'status': 'error', 'operation': operation, 'address': address, 'message': '', 'warnings': []}
        try:
            evidence(receipt, address)
            if operation == 'repair' and receipt['bluetooth_connected'] and input_ready(receipt):
                receipt.update(status='completed', phase='ready', message='手柄连接正常；未停止服务、卸力或改动配对。')
                report_input(receipt)
                return receipt
            if operation == 'repair' and (not address or property_value(info(address), 'Paired') != 'yes'):
                receipt.update(status='completed', phase='pair_required', message='手柄尚未配对；请勾选“首次／重新配对”后执行配对。')
                emit('pair_required', receipt['message'], 'waiting', evidence=receipt)
                return receipt
            if operation == 'pair':
                # Only the explicitly selected pairing operation interrupts live inputs.
                input_was_active = {unit: active(unit) for unit in INPUTS}
                paused = True
                run('systemctl', 'stop', *INPUTS, timeout=20)
                robot_active = active('robotd.service')
                stop_motion()
                emit('pause_input', '配对期间实体输入已暂停；' + ('卸力流程已完成' if robot_active else 'robotd 未运行，未发送卸力指令') + '；未重启 robotd。')
                if loaded('btd.service') and active('btd.service'):
                    phone_paused = True
                    run('systemctl', 'stop', 'btd.service', timeout=15)
                    emit('phone_pause', '临时暂停原本运行的手机连接服务 btd；开机设置保持原样。')
                if not active('bluetooth.service'):
                    run('systemctl', 'start', 'bluetooth.service', timeout=15)
                session = BluetoothSession()
                session.command('power on', ['Changing power on succeeded'])
                if address and property_value(info(address), 'Name') == NAME:
                    session.command('remove ' + address, ['Device has been removed'])
                    emit('forget', '已按所选配对操作，仅删除 ' + address + ' 的旧记录／配对，包括未完成的配对记录。')
                reset_adapter(session)
                address = pair_device(session, address)
                receipt['address'] = address
                connect_hid(session, address)
            elif not receipt['bluetooth_connected'] or not receipt['physical']:
                if not active('bluetooth.service'):
                    run('systemctl', 'start', 'bluetooth.service', timeout=15)
                session = BluetoothSession()
                session.command('power on', ['Changing power on succeeded'])
                connect_hid(session, address)
            state = finish_input()
            receipt.update(address=address, **state, bluetooth_connected=connected(address))
            failure = input_failure(state, receipt['bluetooth_connected']) if not input_ready(state) or not receipt['bluetooth_connected'] else None
            report_input(receipt, failure)
            if failure:
                failure_reported = True
                raise failure
            receipt.update(status='completed', phase='ready', message='手柄连接已确认；蓝牙、实体输入、虚拟 Xbox 和 padd 均就绪。连接不自动 HOME 或启用策略。')
        except (RepairError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
            receipt.update(status='error', phase=getattr(exc, 'phase', 'failed'), message=str(exc))
            if not failure_reported:
                emit(receipt['phase'], receipt['message'], 'failed')
        finally:
            # Cleanup has its own per-command bounds, even when the main transaction exhausted its budget.
            DEADLINE = None
            if session is not None:
                try:
                    session.close()
                except Exception as exc:
                    receipt['warnings'].append('蓝牙会话关闭失败：' + str(exc))
            if paused:
                for unit, was_active in input_was_active.items():
                    try:
                        if was_active and not active(unit):
                            run('systemctl', 'start', unit, timeout=15)
                    except Exception as exc:
                        receipt['warnings'].append(unit + ' 恢复失败：' + str(exc))
            if phone_paused:
                try:
                    run('systemctl', 'start', 'btd.service', timeout=15)
                    if not active('btd.service'):
                        raise RepairError('未确认 active')
                    receipt['phone_service_restored'] = True
                    emit('phone_restore', '手机连接服务 btd 已恢复操作前的运行状态；未修改开机设置。')
                except Exception as exc:
                    receipt['warnings'].append('手机连接服务 btd 恢复失败：' + str(exc))
                    emit('phone_restore', receipt['warnings'][-1], 'failed')
            if receipt['warnings']:
                receipt['message'] += '；' + '；'.join(receipt['warnings'])
            if session is not None or paused or receipt['status'] == 'error':
                try:
                    evidence(receipt, address)
                    if receipt.get('phase') == 'ready' and (not receipt['bluetooth_connected'] or not input_ready(receipt)):
                        receipt.update(status='error', phase='connection_changed', message='操作结束后的手柄连接发生变化，请查看分层状态。')
                        emit('connection_changed', receipt['message'], 'failed', evidence=receipt)
                except Exception as exc:
                    receipt['warnings'].append('最终状态读取失败：' + str(exc))
                    receipt['message'] += '；' + receipt['warnings'][-1]
        return receipt


if __name__ == '__main__':
    try:
        request = json.loads(sys.argv[1])
        result = repair(request['address'], request['operation'])
    except Exception as exc:
        result = {'status': 'error', 'phase': getattr(exc, 'phase', 'failed'), 'message': str(exc)}
        emit(result['phase'], result['message'], 'failed')
    print(json.dumps(result, ensure_ascii=False), flush=True)
