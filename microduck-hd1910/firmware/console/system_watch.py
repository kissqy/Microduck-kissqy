"""Poll the board for service and hardware state, on its own channel.

`system_probe.py` is pushed as source over the SSH channel that is already
warm; nothing is installed on the board and no `sudo` is used. Results land in a
`units` channel rather than inside `system`, because in the deployed `--feetech`
mode `system` is robotd's own telemetry (through the raw byte channel) — two
producers writing one dict would keep erasing each other.

Nothing here starts or stops a service. This is a read-only sampler; the page's
only write is `systemctl enable|disable`, which goes through the service
controller like every other management action.
"""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Two seconds matches the collector's own cadence and is far faster than a unit
# can change state; the page's TTL is looser so one slow answer is not "unknown".
INTERVAL = 2.0
TIMEOUT = 20


class SystemWatch:
    def __init__(self, store, unit_names, transport=None, log=None, interval=INTERVAL):
        self.store, self.names = store, tuple(unit_names)
        self.transport, self.log = transport, log
        self.interval = interval
        self.error = None

    def _source(self):
        return (ROOT / "system_probe.py").read_text(encoding="utf-8")

    def _request(self):
        return json.dumps({"units": list(self.names)})

    def sample(self):
        """One reading, from the board (SSH) or from this machine (local mode)."""
        request = self._request()
        if self.transport is not None:
            return self.transport._manage(
                ["python3", "-u", "-c", self._source(), request],
                privileged=False, record_output=False)
        result = subprocess.run([sys.executable, "-u", "-c", self._source(), request],
                                capture_output=True, text=True, timeout=TIMEOUT)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout or "").strip()[:300] or "探测脚本失败")
        return json.loads(result.stdout)

    def emit(self, event):
        self.store.ingest(event)

    def run(self, stop):
        while not stop.is_set():
            try:
                data = self.sample()
                if not isinstance(data, dict):
                    raise ValueError("探测回执不是对象")
                self.emit({"channel": "units", "data": data})
                if self.error:
                    # Report recovery once, then stay quiet: the channel's own
                    # TTL is what tells the page the numbers went stale.
                    if self.log: self.log.add('服务与硬件', '恢复 · ' + self.describe(data))
                    self.error = None
            except Exception as exc:
                message = str(exc) or type(exc).__name__
                if message != self.error:
                    self.error = message
                    if self.log: self.log.add('服务与硬件', '读取失败 · ' + message)
                self.emit({"channel": "units", "error": message})
            stop.wait(self.interval)

    @staticmethod
    def describe(data):
        rows = data.get("units") or []
        running = sum(1 for row in rows if row.get("active") == "active")
        hardware = data.get("hardware") or {}
        missing = [key for key, value in hardware.items() if value.get("present") is False]
        return "%d/%d 运行%s" % (running, len(rows),
                                 "；硬件缺失：" + "、".join(missing) if missing else "")

    def start(self, stop):
        thread = threading.Thread(target=self.run, args=(stop,), daemon=True)
        thread.start()
        return thread
