"""One-shot opt-in for the existing native chorale; run on Zero via service SSH."""
import copy
import json
from pathlib import Path
import socket
import subprocess
import sys
import tomllib

BASE = Path('/opt/robot/feetech-ft5-r5')
CONFIG = Path('/etc/robot/feetech-ft5/robotd.toml')


def enabled_config(data):
    result = copy.deepcopy(data)
    result.setdefault('chorale', {})['accept'] = True
    result.setdefault('audio', {})['enabled'] = True
    return result


def rpc(path, method):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(path)
        client.sendall((json.dumps({'jsonrpc': '2.0', 'id': 1,
                                   'method': method, 'params': {}}) + '\n').encode())
        with client.makefile('rb') as stream:
            reply = json.loads(stream.readline(262145))
    if reply.get('error'):
        raise RuntimeError(reply['error'].get('message', str(reply['error'])))
    if reply.get('id') != 1 or not isinstance(reply.get('result'), dict):
        raise RuntimeError('机器人服务回执无效')
    return reply['result']


def torque_off(report):
    native = report.get('native') or report
    return (not report.get('torque_off_pending') and
            (report.get('torque_state') == 'off' if report.get('mode') == 'commissioning'
             else native.get('torque_state_confirmed') is False))


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or '命令失败：' + ' '.join(args))
    return result.stdout.strip()


def prepare(path='/run/robotd.sock', config=CONFIG):
    # No relax, HOME or enable is implicit in a sound feature.
    if not torque_off(rpc(path, 'robot.busStatus')):
        raise RuntimeError('首次启用会重启 robotd；请先让鸭子坐稳并点击“停止并松开”，确认扭矩 OFF')
    for unit in ('bluetooth.service', 'btd.service'):
        if run('systemctl', 'show', unit, '--property=LoadState', '--value') != 'loaded':
            raise RuntimeError('缺少 ' + unit + '；当前基础系统未安装官方蓝牙合唱通道，请把此提示发来排查')
    data = tomllib.loads(config.read_text(encoding='utf-8'))
    bank = Path(data.get('audio', {}).get('bank', '/var/lib/robot/sounds'))
    if not (bank / '.seed').is_file() or not any(bank.rglob('*.wav')):
        raise RuntimeError('原生音库尚未准备好；请先用“升级固件”安装本包的声音组件，再启用合唱')
    run('systemctl', 'start', 'bluetooth.service')
    run('systemctl', 'enable', '--now', 'btd.service')
    for unit in ('bluetooth.service', 'btd.service'):
        if run('systemctl', 'is-active', unit) != 'active':
            raise RuntimeError(unit + ' 尚未正常运行')
    sys.path.insert(0, str(BASE))
    from configure import atomic_write, dumps
    updated = enabled_config(data)
    text = dumps(updated)
    if tomllib.loads(text) != updated:
        raise RuntimeError('合唱配置序列化失败，未写入')
    atomic_write(config, text)
    # A previous attempt may have saved the file but failed to restart; retry applies it too.
    run('systemctl', 'restart', 'robotd.service')
    return {'accepted': True, 'message': '合唱已启用，蓝牙合唱服务已运行并设为开机启动。等待数据恢复后，两只各点“开始合唱”；不会自动 HOME 或开始运动。'}


if __name__ == '__main__':
    try:
        print(json.dumps(prepare(sys.argv[1] if len(sys.argv) > 1 else '/run/robotd.sock'), ensure_ascii=False))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
