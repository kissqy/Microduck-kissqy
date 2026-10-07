"""Session-wide SSH log: bounded page tail, complete output on disk."""
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
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / ('system-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3) + '.log')
        self.stream = self.path.open('a', encoding='utf-8')
        self.lock = threading.RLock()
        self.entries = deque(maxlen=3000)
        self.counter = 0
        self.secrets = set()
        self.pending = queue.SimpleQueue()
        self.error = ''
        self.worker = threading.Thread(target=self._write, daemon=True)
        self.worker.start()

    def hide(self, value):
        if value:
            with self.lock: self.secrets.add(value)

    def add(self, source, text):
        with self.lock:
            text = str(text)
            for value in self.secrets: text = text.replace(value, '[已隐藏]')
            text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
            self.counter += 1
            item = {'seq':self.counter, 'at':time.time(), 'source':source, 'text':text}
            self.entries.append(item)
            self.pending.put(item)
            return item['seq']

    def _write(self):
        while True:
            item = self.pending.get()
            if item is None: break
            if isinstance(item, threading.Event):
                self.stream.flush(); item.set(); continue
            try:
                stamp = datetime.fromtimestamp(item['at']).astimezone().isoformat(timespec='milliseconds')
                self.stream.write(f"[{stamp}] [{item['source']}] " + item['text'].rstrip('\n') + '\n')
                self.stream.flush()
            except OSError as exc: self.error = str(exc)
        self.stream.close()

    def tail(self, after=0, limit=200):
        with self.lock:
            entries = [dict(x) for x in self.entries if x['seq'] > after][:limit]
            return {'entries':entries, 'cursor':entries[-1]['seq'] if entries else after,
                    'has_more':bool(entries and entries[-1]['seq'] < self.counter),
                    'gap':bool(self.entries and after and after < self.entries[0]['seq']-1),
                    'error':self.error, 'filename':self.path.name}

    def flush(self):
        event = threading.Event(); self.pending.put(event); event.wait(5)

    def close(self):
        self.pending.put(None); self.worker.join(timeout=5)


def describe(command):
    """Never log request credentials, uploaded source or full telemetry frames."""
    if command.get('kind') == 'manage':
        import shlex
        return shlex.join(command['argv'])
    return json.dumps({k:v for k,v in command.items() if k not in {'input','channel_id','client','owner','sudo_password'}}, ensure_ascii=False)
