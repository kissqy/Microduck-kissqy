"""Consume robotd's existing startup events once; never probe the motor bus."""
import argparse
import ctypes
import errno
import json
import os
from pathlib import Path
import select
import socket
import struct
import sys
import time


class StartupFailure(RuntimeError):
    pass


def ready(report):
    steps = report.get('steps', {})
    return all(isinstance(steps.get(str(n)), dict) and steps[str(n)].get('status') == 'success'
               for n in range(1, 5))


def receive(peer, emit=lambda report: None, cancelled=None, timeout=None):
    """One subscription; read timeouts only permit cancellation, never send probes."""
    deadline = None if timeout is None else time.monotonic() + timeout
    peer.sendall(b'{"jsonrpc":"2.0","id":1,"method":"robot.startupSubscribe"}\n')
    pending = bytearray()
    last = {}
    while cancelled is None or not cancelled():
        remaining = None if deadline is None else deadline - time.monotonic()
        if remaining is not None and remaining <= 0:
            waiting = next((f'第 {n}/4 步：{v.get("detail", "尚未完成")}'
                            for n, v in last.get('steps', {}).items() if v.get('status') != 'success'), '未收到启动状态')
            raise TimeoutError('robotd 启动等待超时；' + waiting + '；未停止或重启 robotd')
        peer.settimeout((min(.5, remaining) if remaining is not None else .5) if cancelled is not None else remaining)
        try:
            chunk = peer.recv(65536)
        except socket.timeout:
            continue
        if not chunk:
            raise EOFError('robotd 启动事件连接已关闭，尚未确认全部四步完成')
        pending.extend(chunk)
        while b'\n' in pending:
            line, _, tail = pending.partition(b'\n')
            pending = bytearray(tail)
            if len(line) > 65536:
                raise ValueError('启动状态响应超出长度限制')
            row = json.loads(line)
            if not isinstance(row, dict) or row.get('error'):
                raise ValueError('启动状态响应失败：' + str(row))
            report = row.get('result') if row.get('id') == 1 else row.get('params') if row.get('method') == 'robot.startup' else None
            if not isinstance(report, dict) or not isinstance(report.get('steps'), dict):
                raise ValueError('启动状态字段无效')
            if any(n not in {'1', '2', '3', '4'} or not isinstance(v, dict)
                   or v.get('status') not in {'starting', 'waiting', 'success', 'failed'}
                   or not isinstance(v.get('detail', ''), str) for n, v in report['steps'].items()):
                raise ValueError('启动步骤字段无效')
            if cancelled is not None and cancelled():
                raise ConnectionAbortedError('启动事件等待已取消')
            if report != last:
                emit(report)
                last = report
            failure = next(((n, v) for n, v in report['steps'].items() if v['status'] == 'failed'), None)
            if failure:
                raise StartupFailure(f'robotd 第 {failure[0]}/4 步失败：{failure[1].get("detail", "未返回原因")}')
            if ready(report):
                return report
        if len(pending) > 65536:
            raise ValueError('启动状态响应超出长度限制')
    raise ConnectionAbortedError('启动事件等待已取消')


def connect_local(path, timeout=None):
    """Watch socket creation before connecting, so Type=exec startup cannot race bind."""
    path = Path(path)
    libc = ctypes.CDLL(None, use_errno=True)
    fd = libc.inotify_init1(os.O_CLOEXEC | os.O_NONBLOCK)
    if fd < 0:
        raise OSError(ctypes.get_errno(), '无法订阅 IPC 文件创建事件')
    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        # Create/move/attribute notifications are passive; there is no stat loop.
        if libc.inotify_add_watch(fd, os.fsencode(path.parent), 0x100 | 0x80 | 0x4) < 0:
            raise OSError(ctypes.get_errno(), '无法订阅 IPC 所在目录')
        while True:
            peer = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                peer.connect(str(path))
                return peer
            except OSError as exc:
                peer.close()
                last_error=exc
                if exc.errno not in {errno.ENOENT, errno.ECONNREFUSED, errno.EACCES}:
                    raise
            relevant = False
            while not relevant:
                remaining = None if deadline is None else max(0, deadline - time.monotonic())
                if not select.select([fd], [], [], remaining)[0]:
                    raise TimeoutError('robotd IPC 尚未就绪；最后连接原因：'+str(last_error)+'；未停止或重启 robotd')
                events = os.read(fd, 65536)
                at = 0
                while at < len(events):
                    _, mask, _, size = struct.unpack_from('iIII', events, at)
                    name = events[at + 16:at + 16 + size].split(b'\0', 1)[0]
                    relevant |= name == os.fsencode(path.name) or bool(mask & 0x4000)
                    at += 16 + size
    finally:
        os.close(fd)


def wait_local(path='/run/robotd.sock', timeout=None, emit=lambda report: None):
    started = time.monotonic()
    with connect_local(path, timeout) as peer:
        remaining = None if timeout is None else max(.001, timeout - (time.monotonic() - started))
        return receive(peer, emit, timeout=remaining)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket', default='/run/robotd.sock')
    parser.add_argument('--timeout', type=float)
    parser.add_argument('--install-log', action='store_true')
    parser.add_argument('--exec', dest='command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    emit = (lambda report: print(json.dumps({'robotd_startup': report}, ensure_ascii=False), flush=True)) if args.install_log else lambda report: None
    try:
        wait_local(args.socket, args.timeout, emit)
        if args.command:
            # The temporary waiter is replaced by the original native process.
            print('robotd 四步已完成；启动 ' + Path(args.command[0]).name, flush=True)
            os.execv(args.command[0], args.command)
    except (OSError, EOFError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 78
    return 0


if __name__ == '__main__':
    sys.exit(main())
