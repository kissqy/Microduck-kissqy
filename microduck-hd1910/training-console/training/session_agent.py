"""Private stdio broker in Linux/WSL. No network listener or environment probes."""
import base64
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time

WRITE = threading.Lock()
CHILDREN = {}
LOCK = threading.Lock()


def emit(message):
    with WRITE:
        sys.stdout.write(json.dumps(message, separators=(',', ':')) + '\n')
        sys.stdout.flush()


def start(message):
    key = message['id']
    code = base64.b64decode(message['code'])
    # Read exactly the source bytes; remaining stdin belongs to this job's controls.
    boot = ("import os\ncode=bytearray()\nwhile len(code)<%d:\n"
            " chunk=os.read(0,%d-len(code))\n"
            " if not chunk: raise SystemExit('session source closed')\n"
            " code.extend(chunk)\n"
            "exec(compile(code,'<training-session-job>','exec'))") % (len(code),len(code))
    proc = subprocess.Popen([sys.executable, '-u', '-c', boot], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    inputs = queue.Queue()
    inputs.put(code)
    with LOCK:
        CHILDREN[key] = (proc, inputs)

    def write_input():
        try:
            while True:
                data = inputs.get()
                if data is None:
                    break
                proc.stdin.write(data)
                proc.stdin.flush()
        except (OSError, ValueError):
            pass
        finally:
            try: proc.stdin.close()
            except (OSError, ValueError): pass

    def read_output():
        try:
            while True:
                data = os.read(proc.stdout.fileno(), 65536)
                if not data: break
                emit({'id': key, 'type': 'data', 'data': base64.b64encode(data).decode('ascii')})
            emit({'id': key, 'type': 'exit', 'code': proc.wait()})
        except (OSError, ValueError):
            pass
        finally:
            inputs.put(None)
            proc.stdout.close()
            with LOCK: CHILDREN.pop(key, None)

    threading.Thread(target=write_input, daemon=True).start()
    threading.Thread(target=read_output, daemon=True).start()


def kill_job(proc):
    """Kill only this job and its descendants, including detached GPU groups."""
    if proc.poll() is not None:return
    # Freeze parents before traversing: a worker cannot launch another child
    # between discovery and termination. Linux/WSL both expose /proc.
    from pathlib import Path
    stopped=[]
    namespace=os.readlink('/proc/self/ns/pid')
    def children(pid):
        # /proc may be mounted from an outer PID namespace (containers).
        # Never pass a /proc directory name straight to kill() in that case.
        entries=[]
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():continue
            try:
                if os.readlink(entry/'ns/pid')!=namespace:continue
                status={line.split(':',1)[0]:line.split(':',1)[1].strip()
                        for line in (entry/'status').read_text().splitlines() if ':' in line}
                local=int(status.get('NSpid',entry.name).split()[-1])
                entries.append((int(entry.name),local,int(status['PPid'])))
            except (OSError,ValueError,KeyError):continue
        parent=next((outer for outer,local,_ in entries if local==pid),None)
        return [local for _,local,ppid in entries if parent is not None and ppid==parent]
    def freeze(pid):
        try:os.kill(pid,signal.SIGSTOP)
        except ProcessLookupError:return
        stopped.append(pid)
        for child in children(pid):freeze(child)
    try:freeze(proc.pid)
    finally:
        for pid in reversed(stopped):
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass


def main():
    emit({'type': 'ready', 'pid': os.getpid()})
    try:
        for line in sys.stdin.buffer:
            message = json.loads(line)
            op = message.get('op')
            if op == 'shutdown': break
            if op == 'start':
                try: start(message)
                except Exception as error:
                    emit({'id': message['id'], 'type': 'error', 'message': str(error)})
                continue
            with LOCK: child = CHILDREN.get(message.get('id'))
            if not child: continue
            proc, inputs = child
            if op == 'input': inputs.put(base64.b64decode(message['data']))
            elif op == 'eof': inputs.put(None)
            elif op == 'kill':
                kill_job(proc)
    finally:
        # EOF makes each worker stop its own GPU/viewer children cleanly.
        with LOCK: children = list(CHILDREN.values())
        for proc, inputs in children: inputs.put(None)
        deadline = time.monotonic() + 15
        for proc, _ in children:
            try: proc.wait(timeout=max(.1, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                kill_job(proc)


if __name__ == '__main__':
    main()
