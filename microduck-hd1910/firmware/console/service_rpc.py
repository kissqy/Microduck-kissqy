"""Console service relay. Each RPC opens robotd IPC, never the motor port."""
import json
import socket
import subprocess
import sys
import threading


def execute(request, progress=None):
    if request.get('kind') == 'manage':
        command = request['argv']
        if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            raise ValueError('invalid management command')
        if progress:
            # Keep JSON stdout separate from diagnostics while streaming both
            # into the existing log. Merging them corrupts model/config replies.
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout,stderr = bytearray(),bytearray()
            def read_output(stream,output):
                for line in stream:
                    if len(output) < 512*1024: output.extend(line[:512*1024-len(output)])
                    progress(line.decode('utf-8', errors='replace'))
            readers=[threading.Thread(target=read_output,args=(stream,output),daemon=True)
                     for stream,output in ((process.stdout,stdout),(process.stderr,stderr))]
            for reader in readers:reader.start()
            try:
                process.stdin.write(request.get('input', '').encode());process.stdin.close()
                process.wait(timeout=min(300,max(5,request.get('timeout',120))))
            except subprocess.TimeoutExpired:
                process.kill();process.wait();raise
            finally:
                for reader in readers:reader.join(timeout=2)
                process.stdout.close();process.stderr.close()
            return {'returncode':process.returncode,'stdout':stdout.decode('utf-8',errors='replace'),'stderr':stderr.decode('utf-8',errors='replace')}
        result = subprocess.run(command, input=request.get('input', '').encode(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        return {'returncode':result.returncode,
                'stdout':result.stdout.decode('utf-8', errors='replace'),
                'stderr':result.stderr.decode('utf-8', errors='replace')}
    allowed = {'robot.busCommand', 'robot.relax', 'robot.init', 'robot.enable'}
    if request.get('method') not in allowed: raise ValueError('unsupported service method')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(min(300, max(5, request.get('timeout', 15))))
        s.connect(sys.argv[1])
        s.sendall((json.dumps({'jsonrpc':'2.0', 'id':1, 'method':request['method'],
                              'params':request.get('params', {})})+'\n').encode())
        with s.makefile('rb') as reader: line = reader.readline(262145)
    if not line.endswith(b'\n') or len(line) > 262144: raise ValueError('invalid service response')
    reply = json.loads(line)
    if reply.get('id') != 1: raise ValueError('service response id mismatch')
    return reply


def main():
    if '--stream' not in sys.argv:
        print(json.dumps(execute(json.loads(sys.stdin.buffer.readline(8193))), ensure_ascii=False), flush=True)
        return
    write_lock = threading.Lock()
    def emit(request, data):
        with write_lock: print(json.dumps({'channel_id':request['channel_id'],**data},ensure_ascii=False),flush=True)
    def handle(request):
        try:
            progress=(lambda line:emit(request,{'channel_progress':line})) if request.get('progress') else None
            emit(request,{'payload':execute(request,progress)})
        except Exception as exc: emit(request,{'channel_error':str(exc)})
    for line in sys.stdin.buffer:
        request = json.loads(line)
        # A long management or joint command must not block an explicit relax.
        threading.Thread(target=handle, args=(request,), daemon=True).start()


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(json.dumps({'error':{'message':str(exc)}}, ensure_ascii=False), flush=True)
        sys.exit(1)
