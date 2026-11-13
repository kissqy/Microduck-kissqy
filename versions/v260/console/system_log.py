"""Useful session events, repeated connection errors coalesced, bounded disk use."""
from collections import deque
from datetime import datetime
import json
from pathlib import Path
import queue
import re
import secrets
import threading
import time


class SystemLog:
    def __init__(self, directory, max_bytes=2*1024*1024):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / ('system-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3) + '.log')
        self.stream = self.path.open('a', encoding='utf-8')
        self.previous_path = self.path.with_suffix('.previous.log')
        self.max_bytes = max_bytes
        self.bytes_written = 0
        self.rotations = 0
        self.disk_lock = threading.RLock()
        self.head = []
        self.repeated = {}
        self.lock = threading.RLock()
        self.entries = deque(maxlen=3000)
        self.counter = 0
        self.secrets = set()
        self.pending = queue.SimpleQueue()
        self.error = ''
        self.closed = False
        self.worker = threading.Thread(target=self._write, daemon=True)
        self.worker.start()

    def hide(self, value):
        if value:
            with self.lock: self.secrets.add(value)

    def add(self, source, text):
        with self.lock:
            if self.closed: return self.counter
            text = str(text)
            for value in self.secrets: text = text.replace(value, '[已隐藏]')
            text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
            encoded = text.encode('utf-8')
            if len(encoded)>16384:
                text = encoded[:8192].decode('utf-8',errors='ignore') + f'\n[过长单条输出：原 {len(encoded)} 字节，仅保留首尾]\n' + encoded[-8192:].decode('utf-8',errors='ignore')
            # User operations are never deduplicated. Only identical transport
            # messages are summarized; new errors are always written immediately.
            if source in {'SSH 输出','SSH 字节通道','数据 SSH','数据 SSH 重连','管理 SSH 重连','网页手柄重连','原始遥测','手柄连接错误'}:
                now = time.time()
                old = self.repeated.get(source)
                if old and old['text'] == text and now-old['at'] < 60:
                    old['count'] += 1
                    old['last'] = now
                    return self.counter
                self._flush_repeat(source)
                self.repeated[source] = {'text':text,'at':now,'last':now,'count':0}
            return self._append(source, text)

    def _append(self, source, text):
        self.counter += 1
        item = {'seq':self.counter, 'at':time.time(), 'source':source, 'text':text}
        self.entries.append(item)
        if len(self.head)<64 and sum(len(x['text']) for x in self.head)<65536:self.head.append(item)
        self.pending.put(item)
        return item['seq']

    def _flush_repeat(self, source):
        old = self.repeated.get(source)
        if old and old['count']:
            stamp = datetime.fromtimestamp(old['last']).astimezone().isoformat(timespec='seconds')
            self._append(source, f"相同消息另重复 {old['count']} 次；最后发生 {stamp}：" + old['text'])
            old['count'] = 0

    @staticmethod
    def _line(item):
        stamp = datetime.fromtimestamp(item['at']).astimezone().isoformat(timespec='milliseconds')
        return f"[{stamp}] [{item['source']}] " + item['text'].rstrip('\n') + '\n'

    def _write(self):
        try:
            while True:
                item = self.pending.get()
                if item is None: break
                if isinstance(item, threading.Event):
                    try: self.stream.flush()
                    except (OSError, ValueError) as exc: self.error = str(exc)
                    finally: item.set()
                    continue
                try:
                    line = self._line(item)
                    encoded_size = len(line.encode('utf-8'))
                    with self.disk_lock:
                        if self.bytes_written and self.bytes_written + encoded_size > self.max_bytes:
                            self.stream.close()
                            self.path.replace(self.previous_path)
                            self.stream = self.path.open('w', encoding='utf-8')
                            self.bytes_written = 0
                            self.rotations += 1
                        self.stream.write(line)
                        self.bytes_written += encoded_size
                        self.stream.flush()
                except (OSError, ValueError) as exc: self.error = str(exc)
        finally:
            self.stream.close()

    def tail(self, after=0, limit=200):
        with self.lock:
            entries = [dict(x) for x in self.entries if x['seq'] > after][:limit]
            return {'entries':entries, 'cursor':entries[-1]['seq'] if entries else after,
                    'has_more':bool(entries and entries[-1]['seq'] < self.counter),
                    'gap':bool(self.entries and after and after < self.entries[0]['seq']-1),
                    'error':self.error, 'filename':self.path.name}

    def flush(self):
        with self.lock:
            if self.closed: return
            for source in self.repeated:self._flush_repeat(source)
            event = threading.Event(); self.pending.put(event)
        event.wait(5)

    def download(self):
        self.flush()
        with self.disk_lock:
            prefix = ''
            if self.rotations:
                prefix = '日志已轮换；保留会话开头和最近约 4 MiB。更早的中间记录已移除。\n' + ''.join(self._line(x) for x in self.head)
            previous = self.previous_path.read_bytes() if self.previous_path.exists() else b''
            return prefix.encode('utf-8') + previous + self.path.read_bytes()

    def close(self):
        with self.lock:
            if self.closed: return
            for source in self.repeated:self._flush_repeat(source)
            self.closed = True
            self.pending.put(None)
        self.worker.join(timeout=5)


def describe(command):
    """Never log request credentials, uploaded source or full telemetry frames."""
    if command.get('kind') == 'manage':
        import shlex
        argv = list(command['argv'])
        for index, value in enumerate(argv):
            if index and argv[index-1] == '-c' and ('python' in ' '.join(argv[:index]) or len(value)>500):
                argv[index] = '[内置脚本]'
        return shlex.join(argv)
    return json.dumps({k:v for k,v in command.items() if k not in {'input','channel_id','client','owner','sudo_password'}}, ensure_ascii=False)
