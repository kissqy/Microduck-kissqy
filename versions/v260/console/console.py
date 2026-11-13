#!/usr/bin/env python3
"""Local hardware console with explicit manual controls for frozen Microduck 590b986."""
import argparse
import csv
import hashlib
import io
import json
import mimetypes
import re
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs

from telemetry import BASELINE, VERSION, HOME, IDS, NAMES, LABELS, Store
from controls import Controller, ControlError
from ssh_connect import normalize_target, SSHConnectError
from process_lifecycle import close_owned_processes

ROOT = Path(__file__).resolve().parent








def handler_for(store, config, controller=None, service_controller=None, connection=None, ai_hub=None):
    static_cache={}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if args and str(args[0]).startswith(("GET /api/", "POST /api/control ")):
                return
            super().log_message(fmt, *args)

        def reply(self, body, status=200, mime="application/json", attachment=None, cache="no-store", etag=None):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
            try:
                self.send_response(status)
                self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") or mime == "application/json" else ""))
                if status!=304:self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", cache)
                if etag:self.send_header('ETag',etag)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Cross-Origin-Resource-Policy", "same-origin")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' ws: wss:; media-src 'self' blob:; img-src 'self' data: blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
                if attachment:
                    self.send_header("Content-Disposition", 'attachment; filename="' + attachment + '"')
                self.end_headers()
                if status!=304:self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                # The browser cancelled this response. Close only this HTTP
                # connection; never retry a control request or hide bus errors.
                self.close_connection = True

        def do_POST(self):
            endpoint = connection if self.path == "/api/connection" else store if self.path == "/api/inspection" and config.get("service_enabled") else service_controller if self.path in ("/api/service", "/api/service/connection", "/api/service/models", "/api/service/firmware", "/api/service/firmware/upload", "/api/service/diagnostic", "/api/service/wifi") else controller if self.path == "/api/control" else ai_hub if self.path.startswith("/api/ai/") else None
            if endpoint is None:
                return self.reply({"error": "当前模式不提供此控制接口"}, 405)
            host = self.headers.get("Host", "")
            if host.split(":")[0].lower() not in ("127.0.0.1", "localhost", config["bind"].lower()):
                return self.reply({"error": "Host 不在允许列表"}, 403)
            if self.headers.get("Origin") != "http://" + host:
                return self.reply({"error": "禁止跨站控制"}, 403)
            token = config.get("control_token", "")
            if not token or not secrets.compare_digest(self.headers.get("X-Control-Token", ""), token):
                return self.reply({"error": "页面控制凭据无效，请刷新本页"}, 403)
            if self.path == "/api/service/firmware/upload":
                try:
                    if self.headers.get_content_type() != "application/octet-stream" or self.headers.get("Transfer-Encoding"):
                        raise ControlError("上传须提供文件及准确长度", 400)
                    size = int(self.headers.get("Content-Length", "-1"))
                    self.connection.settimeout(60)
                    return self.reply(service_controller.prepare_firmware(unquote(self.headers.get('X-Firmware-Name','')),
                        self.rfile,size,self.headers.get('X-Firmware-Client','')))

                except (ControlError, ValueError, OSError) as exc:
                    return self.reply({"error":str(exc)}, getattr(exc, "status", 503))
            if self.headers.get_content_type() != "application/json" or self.headers.get("Transfer-Encoding"):
                return self.reply({"error": "控制请求须使用 JSON"}, 400)
            try:
                size = int(self.headers.get("Content-Length", "0"))
                max_size=24576 if self.path in ('/api/ai/configure','/api/ai/voices') else 4096
                if not 0 < size <= max_size: return self.reply({"error": "控制请求长度无效"}, 400)
                self.connection.settimeout(2)
                payload = json.loads(self.rfile.read(size))
            except (ValueError, OSError):
                return self.reply({"error": "无法读取控制请求"}, 400)
            try:
                if self.path == '/api/service/wifi' and not isinstance(payload, dict):
                    return self.reply({'error':'Wi-Fi 请求必须是对象'}, 400)
                if connection and not connection.active and self.path in ('/api/control', '/api/service', '/api/service/models', '/api/service/connection', '/api/service/diagnostic', '/api/service/wifi'):
                    if self.path != '/api/service' or payload.get('command', {}).get('action') != 'forget-sudo-password':
                        return self.reply({'error':'SSH 尚未连接，请在摄像头上方连接 Zero'}, 503)
                if self.path.startswith('/api/ai/') and ai_hub:
                    if self.path == '/api/ai/configure':return self.reply(ai_hub.configure(payload))
                    if self.path == '/api/ai/voices':return self.reply(ai_hub.set_voices(payload))
                    if self.path == '/api/ai/voice':return self.reply(ai_hub.set_voice(payload))
                    if self.path == '/api/ai/start':return self.reply(ai_hub.start())
                    if self.path == '/api/ai/stop':return self.reply(ai_hub.stop())
                    if self.path == '/api/ai/audio':return self.reply(ai_hub.set_audio(payload))
                    if self.path == '/api/ai/speech':return self.reply(ai_hub.set_speech(payload))
                    if self.path == '/api/ai/camera-mode':return self.reply(ai_hub.set_camera_mode(payload))
                    if self.path == '/api/ai/commit':return self.reply(ai_hub.commit_input())
                    if self.path == '/api/ai/vision':return self.reply(ai_hub.inspect_scene(payload))
                    if self.path == '/api/ai/skills':return self.reply({'skills':ai_hub.load_skills()})
                    return self.reply({'error':'AI操作不支持'},404)
                if self.path == "/api/service/models": return self.reply(service_controller.models())
                if self.path == "/api/service/diagnostic": return self.reply(service_controller.diagnose(payload))
                if self.path == "/api/service/wifi": return self.reply(service_controller.wifi(payload))
                if self.path == "/api/service/connection": return self.reply(service_controller.connection())
                if self.path == "/api/service/firmware": return self.reply(service_controller.firmware_info())
                return self.reply(endpoint.handle(payload))
            except ValueError as exc:
                return self.reply({"error": str(exc)}, 400)
            except ControlError as exc:
                endpoint.error = str(exc)
                return self.reply({"error": str(exc)}, exc.status)
            except Exception as exc:
                endpoint.error = str(exc) or type(exc).__name__
                return self.reply({"error": "控制连接中断或未收到回执；动作不会自动重发，请检查启动终端和 SSH 连接。"}, 503)

        def do_GET(self):
            # Bind is loopback by default; defend against DNS rebinding even locally.
            host = self.headers.get("Host", "").split(":")[0].lower()
            if host not in ("127.0.0.1", "localhost", config["bind"].lower()):
                return self.reply({"error": "Host 不在允许列表"}, 403)
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                return self.reply({"error": "禁止跨站读取"}, 403)
            path = unquote(urlparse(self.path).path)
            if ai_hub and path == '/api/ai/status':return self.reply(ai_hub.status())
            if ai_hub and path == '/api/ai/devices':return self.reply(ai_hub.audio_devices())
            if ai_hub and path == '/api/ai/vision/frame':
                capture_id=parse_qs(urlparse(self.path).query).get('id',[''])[0]
                frame=ai_hub.get_vision_frame(capture_id)
                if frame is None:return self.reply({'error':'这帧图片已更新或尚未收到'},404)
                return self.reply(frame,mime='image/jpeg' if frame[:2]==b'\xff\xd8' else 'image/png')
            if ai_hub and path == '/api/ai/log/download':
                return self.reply(ai_hub.trace_file.read_bytes(),mime='application/x-ndjson',attachment=ai_hub.trace_file.name)
            if ai_hub and path == '/api/ai/log':
                q=parse_qs(urlparse(self.path).query)
                try:
                    after=int(q.get('after',['0'])[0]);limit=int(q.get('limit',['200'])[0])
                    if after<0 or not 1<=limit<=400:raise ValueError()
                except ValueError:return self.reply({'error':'AI日志分页参数无效'},400)
                return self.reply(ai_hub.tail(after,limit))
            if ai_hub and path == '/api/ai/stream':
                try:after=max(0,int(parse_qs(urlparse(self.path).query).get('after',['0'])[0]))
                except ValueError:return self.reply({'error':'游标无效'},400)
                resume=self.headers.get('Last-Event-ID')
                if resume:
                    try:after=max(0,int(resume))
                    except ValueError:pass  # Recover old builds' accidental provider UUID cursors.
                try:
                    self.send_response(200)
                    self.send_header('Content-Type','text/event-stream; charset=utf-8')
                    self.send_header('Cache-Control','no-store')
                    self.send_header('X-Accel-Buffering','no')
                    self.send_header('X-Content-Type-Options','nosniff')
                    self.end_headers()
                    for event in ai_hub.stream(after):
                        if event is None:data=': heartbeat\n\n'
                        elif event.get('kind')=='assistant_audio_replay':
                            data='event: audio\ndata: '+json.dumps(event,ensure_ascii=False)+'\n\n'
                        else:data='id: '+str(event['id'])+'\ndata: '+json.dumps(event,ensure_ascii=False)+'\n\n'
                        self.wfile.write(data.encode('utf-8'));self.wfile.flush()
                except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError,OSError):pass
                return
            if path == '/api/control/socket':
                from control_socket import upgrade
                return upgrade(self, config, controller)
            if path == '/api/telemetry/socket':
                from raw_telemetry import upgrade
                hub = getattr(store, 'raw_hub', None)
                if hub is None: return self.reply({'error':'当前模式不提供原始遥测'}, 405)
                sent_aux = {}
                def auxiliary():
                    if sent_aux.get('generation') != hub.generation:
                        sent_aux.clear(); sent_aux['generation'] = hub.generation
                    snapshot = store.peek()
                    with store.lock:
                        extra = {'service_operation':store.service_operation,
                                 'connection_paused':store.connection_paused.is_set(),
                                 'inspection_active':store.inspection_active,
                                 'gait_capture':store.clock() < store.gait_capture_until}
                        commands = store.service_commands
                        key = (len(commands), id(commands[-1]) if commands else None)
                        if sent_aux.get('commands') != key:
                            extra['service_commands'] = list(commands)
                            sent_aux['commands'] = key
                        calibration = store.data.get('calibration')
                        if calibration is not None and sent_aux.get('calibration') is not calibration:
                            extra['calibration'] = calibration
                            sent_aux['calibration'] = calibration
                    return {**extra,
                            'control':controller.status(snapshot) if controller else {'available':False,'connected':False},
                            'service_control':service_controller.status(snapshot) if service_controller else {'available':False},
                            'connection':connection.status() if connection else None}
                return upgrade(self, config, hub, auxiliary)
            if path == "/api/config":
                return self.reply({**config, "baseline": BASELINE, "version": VERSION, "ids": IDS,
                                   "names": NAMES, "labels": LABELS, "home": HOME})
            if path == "/api/snapshot":
                snapshot = store.snapshot()
                return self.reply({**snapshot, "control": controller.status(snapshot) if controller else {"available": False, "connected": False},
                                   "service_control": service_controller.status(snapshot) if service_controller else {"available": False},
                                   "connection": connection.status() if connection else None})
            if path == '/api/system-log':
                log=getattr(store,'system_log',None)
                if not log: return self.reply({'entries':[],'cursor':0,'has_more':False,'error':''})
                query=parse_qs(urlparse(self.path).query)
                try:
                    after=int(query.get('after',['0'])[0]);limit=int(query.get('limit',['200'])[0])
                    if after<0 or not 1<=limit<=400: raise ValueError()
                except ValueError: return self.reply({'error':'日志分页参数无效'},400)
                return self.reply(log.tail(after,limit))
            if path == '/api/system-log/download':
                log=getattr(store,'system_log',None)
                if not log: return self.reply({'error':'尚无系统日志'},404)
                return self.reply(log.download(),mime='text/plain',attachment=log.path.name)
            if path == "/api/recording":
                return self.reply(store.recording(), attachment="microduck-recording.json")
            if path == "/api/servos.csv":
                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow(["mode", "timestamp", "id", "joint", "status", "angle_deg", "target_deg", "error_deg", "current_ma", "temperature_c", "voltage_v", "velocity_rpm", "current_ratio_percent", "position_raw", "speed_raw", "load_raw", "current_raw", "torque_enabled"])
                snap = store.snapshot()
                for row in snap["servos"]:
                    writer.writerow([snap["mode"], snap["at"], row["id"], row["name"], row["status"]] +
                                    [row.get(k, "") for k in ("angle_deg", "target_deg", "error_deg", "current_ma", "temperature_c", "voltage_v", "velocity_rpm", "current_ratio_percent", "position_raw", "speed_raw", "load_raw", "current_raw", "torque_enabled")])
                return self.reply(("\ufeff" + buf.getvalue()).encode("utf-8"), mime="text/csv", attachment="microduck-servos.csv")
            if path.startswith("/api/"):
                return self.reply({"error": "没有此接口"}, 404)
            requested = "index.html" if path == "/" else path.lstrip("/")
            p = (ROOT / "static" / requested).resolve()
            if not p.is_relative_to((ROOT / "static").resolve()) or not p.is_file():
                return self.reply({"error": "Not found"}, 404)
            mime = "text/javascript" if p.suffix in (".js", ".mjs") else mimetypes.guess_type(str(p))[0] or "application/octet-stream"
            stat=p.stat()
            key=(str(p),stat.st_size,stat.st_mtime_ns)
            entry=static_cache.get(str(p))
            if entry is None or entry[0]!=key:
                body=p.read_bytes();etag='"'+hashlib.sha256(body).hexdigest()+'"'
                entry=(key,body,etag);static_cache[str(p)]=entry
            _,body,etag=entry
            cache='private, no-cache'
            if self.headers.get('If-None-Match')==etag:
                return self.reply(b'',status=304,mime=mime,cache=cache,etag=etag)
            self.reply(body,mime=mime,cache=cache,etag=etag)
    return Handler


def prompt_port(default=8090):
    print("多只鸭子：每只单独打开一个窗口，使用不同端口，例如 8090、8091、8092。", flush=True)
    while True:
        value = input(f"中控端口 [{default}]，直接回车使用默认值：").strip()
        if not value:
            return default
        if re.fullmatch(r"[0-9]{1,5}", value) and 1 <= int(value) <= 65535:
            return int(value)
        print("请输入 1～65535 的整数端口。", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--ssh", metavar="USER@HOST", help="启动后连接指定 Zero SSH 地址")
    modes.add_argument("--dashboard", action="store_true", help="直接打开中控，在页面填写 SSH 地址和密码连接")
    parser.add_argument("--feetech", action="store_true", help="HD1910 + FT6 正式 robotd 服务；不直接占用串口")
    parser.add_argument("--robotd-socket", default="/run/robotd.sock")
    parser.add_argument("--tofd-socket", default="/run/tofd/tof.sock")
    parser.add_argument("--camera-host", default="duck-10e4.local")
    parser.add_argument("--camera-port", type=int, default=8443)
    parser.add_argument("--hz", type=int, choices=range(1, 51), default=50,
                        help="本地兼容采集频率；SSH原始流固定跟随机器人50Hz")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--prompt-port", action="store_true", help="启动时输入中控端口，回车默认 8090")
    parser.add_argument("--bind", default="127.0.0.1", help="仅支持绑定本机 IPv4；使用 SSH 转发供本机浏览器访问")
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args(argv)
    if args.prompt_port:
        try: args.port = prompt_port(args.port if 1 <= args.port <= 65535 else 8090)
        except (EOFError, KeyboardInterrupt):
            print("\n已取消启动。", flush=True)
            return 0
    if args.bind != "127.0.0.1":
        parser.error("为保护未认证的诊断数据，只绑定 127.0.0.1；可使用 ssh -L 8090:127.0.0.1:8090")
    if args.ssh:
        try: args.ssh = normalize_target(args.ssh)
        except SSHConnectError as exc: parser.error(str(exc))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.camera_host) or not 1 <= args.camera_port <= 65535:
        parser.error("摄像头主机/端口无效")
    if not 1 <= args.port <= 65535:
        parser.error("端口无效")
    mode = "service" if args.feetech else "ssh" if args.ssh else "local"
    control_enabled = mode in ("ssh", "local", "service")
    store, stop = Store(mode, control_enabled=control_enabled), threading.Event()
    from system_log import SystemLog
    store.system_log=SystemLog(ROOT/'logs')
    store.system_log.add('中控启动',f'R17 v{VERSION} · {mode} · 默认显示启动四步、操作结果与失败原因')
    controller = Controller(store, args.ssh, args.robotd_socket) if control_enabled else None
    service_controller = None
    if mode == "service":
        from service_control import ServiceController
        service_controller = ServiceController(store, args.ssh, args.robotd_socket,controls=controller,warm=False)
        controller.attach_service_transport(service_controller.transport)
    config = {"bind": args.bind, "camera_host": args.camera_host, "camera_port": args.camera_port,
              "mode": mode, "hz": args.hz, "control_enabled": control_enabled,
              "ssh_target": args.ssh,
              "service_enabled": mode == "service",
              "control_token": secrets.token_urlsafe(32) if control_enabled else ""}
    agent_config = {"robotd_socket": args.robotd_socket, "tofd_socket": args.tofd_socket,
                    "hz": args.hz, "service": mode == "service"}
    connection = None
    if args.dashboard or args.ssh:
        from connection import Connection
        from raw_telemetry import Hub, raw_loop
        store.raw_hub = Hub()
        agent_config['hub'] = store.raw_hub
        agent_config['robotd_restarting'] = store.robotd_restarting
        agent_config['install_handoff'] = store.install_handoff
        config['raw_telemetry'] = True
        connection = Connection(store, config, controller, service_controller, raw_loop, agent_config)
    else:
        import agent
    from ai_runtime import AIHub
    ai_hub = AIHub(store, controller, service_controller, connection)
    def record():
        while not stop.wait(.1):
            store.snapshot()
    url = f"http://127.0.0.1:{args.port}"
    access = "SERVICE CONTROL" if mode == "service" else "MANUAL CONTROL" if control_enabled else "READ ONLY"
    server = None
    try:
        try:
            server = ThreadingHTTPServer((args.bind, args.port), handler_for(store, config, controller, service_controller, connection, ai_hub))
        except OSError:
            print(f"无法启动本地端口 {args.port}，端口可能已被占用。多只鸭子请分别使用 8090、8091、8092；重新启动并换一个端口。", flush=True)
            return 2
        server.daemon_threads = True
        if connection:
            if args.ssh: connection.handle({'action':'connect','target':args.ssh})
        else:
            threading.Thread(target=agent.run, args=(agent_config, store.ingest, stop), daemon=True).start()
        if mode != "service" and not connection: threading.Thread(target=record, daemon=True).start()
        print(f"Microduck Console {VERSION} / {mode.upper()} / {access}\n{url}\n基线 {BASELINE}\n启动不发送动作；实机操作需在页面手动触发。Ctrl+C 退出。", flush=True)
        if args.open:
            webbrowser.open(url)
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        store.connection_paused.set()
        # One failed teardown must not retain another connection or the log file.
        cleanups = [ai_hub.close] + [owner.close for owner in (service_controller, connection, controller) if owner]
        if server: cleanups.append(server.server_close)
        cleanups.extend((close_owned_processes, store.system_log.close))
        for close in cleanups:
            try: close()
            except Exception as exc: print(f'退出清理未完成：{exc}', file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
