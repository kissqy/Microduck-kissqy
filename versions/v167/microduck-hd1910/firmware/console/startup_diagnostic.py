"""One requested, read-only boot/UART/network report; never opens ttyS2."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

COMMANDS = (
    ('services', ['systemctl', 'show', 'robotd.service', 'padd.service', 'gamesir-xboxd.service',
                  'NetworkManager.service', 'bluetooth.service', 'btd.service',
                  'ssh.service', 'sshd.service',
                  '-p', 'Id', '-p', 'ActiveState', '-p', 'SubState', '-p', 'MainPID',
                  '-p', 'Result', '-p', 'ExecMainStatus', '-p', 'ExecStart']),
    ('uart_owner', ['fuser', '/dev/ttyS2']),
    ('network_addresses', ['ip', '-brief', 'address']),
    ('network_routes', ['ip', 'route']),
    ('bluetooth', ['bluetoothctl', 'show']),
    ('robot_boot_log', ['journalctl', '-b', '-u', 'robotd.service', '-n', '100', '--no-pager', '-o', 'short-monotonic']),
    ('radio_network_log', ['journalctl', '-b', '-u', 'NetworkManager.service', '-u', 'bluetooth.service', '-u', 'btd.service', '-n', '100', '--no-pager', '-o', 'short-monotonic']),
    ('kernel_boot_log', ['journalctl', '-k', '-b', '-n', '150', '--no-pager', '-o', 'short-monotonic']),
    ('previous_kernel_log', ['journalctl', '-k', '-b', '-1', '-n', '100', '--no-pager', '-o', 'short-monotonic']),
    ('listening_sockets', ['ss', '-ltnp']),
    ('ssh_boot_log', ['journalctl', '-b', '-u', 'ssh.service', '-u', 'sshd.service', '-n', '80', '--no-pager', '-o', 'short-monotonic']),
)


def collect():
    sections = []
    for name, command in COMMANDS:
        try:
            result = subprocess.run(command, capture_output=True, text=True, errors='replace', timeout=5)
            text = (result.stdout + '\n' + result.stderr).strip()[-24000:]
            sections.append({'name': name, 'exit_code': result.returncode, 'text': text})
        except (OSError, subprocess.TimeoutExpired) as exc:
            sections.append({'name': name, 'error': str(exc)})
    for name, path in (('boot_id', '/proc/sys/kernel/random/boot_id'),
                       ('uart_fifo', '/sys/class/tty/ttyS2/rx_trig_bytes'),
                       ('uart_state', '/var/lib/robot/feetech-ft5/r5/uart-state.json'),
                       ('serial_driver', '/proc/tty/driver/serial')):
        try:
            sections.append({'name': name, 'text': Path(path).read_text(errors='replace')[:24000]})
        except OSError as exc:
            sections.append({'name': name, 'error': str(exc)})
    return {'message': '启动、UART 与网络诊断已收集，可下载 JSON。',
            'diagnostic': {'schema': 'microduck-startup-diagnostic/v1',
                           'created_at': datetime.now(timezone.utc).isoformat(), 'sections': sections}}


if __name__ == '__main__':
    print(json.dumps(collect(), ensure_ascii=False), flush=True)
