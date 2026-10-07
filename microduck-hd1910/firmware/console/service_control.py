"""Finite commissioning jobs via robotd; relax uses an independent connection."""
import json
import math
import re
import shlex
import subprocess
import sys
import threading
import time
import secrets
import tempfile
import tarfile
from pathlib import Path

from service_channel import ServiceChannel
from controls import ControlError
from session_sequences import SequenceWindow
from service_data import BUILD
from management_profile import SLOTS, ACTION_INFO, supports_feature
from ssh_connect import ssh_command, ssh_process_options
from sudo_credential import SudoCredential
from telemetry import IDS
from firmware_packages import PreparedFirmware, bundle_info

ROOT = Path(__file__).resolve().parent
STOP_ACTIONS = {"relax", "reboot", "shutdown"}
MANAGEMENT_ACTIONS = {"set-pad-settings", "set-action-scale", "switch-mode", "reconnect-service", "upgrade-service", "reboot", "shutdown"}
MAX_MODEL = 64 * 1024 * 1024
HOME_TIMEOUT = 12.0
HOME_RESTORE_TIMEOUT = 5.0
HOME_POLL_INTERVAL = .1
HOME_TOLERANCE_DEG = 5.0
HOME_CONFIRM_SAMPLES = 3
def home_feedback(snapshot):
    """Describe measured Home readiness; an accepted RPC or elapsed ramp is not arrival."""
    report = snapshot.get("bus") or {}
    native = report.get("native") or {}
    hd1910 = native.get("hd1910") or {}
    def result(phase, message, **detail):
        return {"phase": phase, "ready": phase == "ready", "message": message, **detail}
    if (not snapshot.get("service_sample_fresh") or report.get("fresh_sample") is not True
            or report.get("mode") != "motion" or report.get("phase") != "control"):
        return result("waiting_feedback", "等待运动模式的新鲜反馈，尚未确认 Home")
    if report.get("policy_enabled") is not False:
        return result("policy_active", "策略正在运行，当前不是 Home 保持")
    torque = native.get("torque_state_confirmed")
    if torque is False:
        if hd1910.get("restore_pending") is True and hd1910.get("temporary_gains_applied") is False:
            return result("restore_pending", "临时 P/D 待恢复；点击 Home 将先恢复参数，再请求站起")
        return result("torque_off", "扭矩 OFF，尚未回到 Home")
    if torque is not True or report.get("torque_off_pending"):
        return result("torque_unknown", "等待确认扭矩状态，尚未确认 Home")
    if report.get("homed") is not True:
        return result("homing", "扭矩已开启，正在回到 Home")
    rows = snapshot.get("servos") or []
    # Use the service's actual targets, not the console's old official Home angles.
    # Self-trained Home comes from the active deployment contract.
    if (snapshot.get("channels", {}).get("state", {}).get("status") != "live"
            or native.get("all_joints_fresh") is False
            or len(rows) != len(IDS) or {r.get("id") for r in rows} != set(IDS)
            or any(r.get("status") != "live" or r.get("calibrated") is not True
                   or any(isinstance(r.get(k), bool) or not isinstance(r.get(k), (int, float))
                          or not math.isfinite(r[k]) for k in ("angle_deg", "target_deg")) for r in rows)):
        return result("waiting_feedback", "服务已结束 Home 缓动，等待 15 个关节的位置和目标反馈")
    errors = {r["id"]: abs(r["angle_deg"] - r["target_deg"]) for r in rows}
    missing = [id for id in IDS if errors[id] > HOME_TOLERANCE_DEG]
    details = {"confirmed_ids": [id for id in IDS if id not in missing],
               "unreached_ids": missing, "max_error_deg": max(errors.values()),
               "tolerance_deg": HOME_TOLERANCE_DEG}
    if missing:
        return result("target_error", "尚未到位：ID " + ", ".join(map(str, missing))
                      + f"；最大偏差 {max(errors.values()):.1f}°（到位阈值 {HOME_TOLERANCE_DEG:g}°）", **details)
    return result("ready", "15 个关节已到 Home，扭矩 ON", **details)


def numeric(value, lo, hi, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi or integer and type(value) is not int:
        raise ControlError("数值无效或超出允许范围", 400)
    return value


def validate(command):
    if not isinstance(command, dict): raise ControlError("指令必须为对象", 400)
    action = command.get("action")
    fields = {"relax": {"action"}, "reboot": {"action"}, "shutdown": {"action"},"resume-connection":{"action"},
              "init": {"action", "supported"},
              "switch-mode": {"action", "target", "supported"},
              "reconnect-service": {"action", "supported"},
              "upgrade-service": {"action", "supported", "firmware"},
              "set-action-scale": {"action", "model", "scale", "kp", "kd", "torque_limit", "supported"},
              "set-pad-settings": {"action", "mouth_percent", "head_rad", "supported"},
              "move": {"action", "id", "position", "duration_ms"},
              "center": {"action", "unassembled", "duration_ms"},
              "capture": {"action", "id", "angle_deg", "direction", "min_deg", "max_deg"},
              "verify-imu": {"action", "confirmed", "mount_wxyz"},
              "forget-sudo-password": {"action"}}
    if not isinstance(action, str) or action not in fields or (set(command) != fields[action]
            and not (action in MANAGEMENT_ACTIONS and set(command) == fields[action] | {"sudo_password"})):
        raise ControlError("指令或参数不受支持", 400)
    if "id" in command and (type(command["id"]) is not int or command["id"] not in IDS): raise ControlError("只能控制官方 15 个关节 ID", 400)
    if "duration_ms" in command: numeric(command["duration_ms"], 500, 10000, True)
    if action in ("init", "switch-mode", "set-pad-settings", "set-action-scale", "reconnect-service", "upgrade-service") and command["supported"] is not True: raise ControlError("请先确认服务操作", 400)
    if action == "switch-mode" and command["target"] not in ("commissioning", "motion"):
        raise ControlError("模式只能选择标定或运动", 400)
    if action == 'upgrade-service' and (not isinstance(command['firmware'],str)
            or not re.fullmatch(r'bundled|[a-f0-9]{64}',command['firmware'])):
        raise ControlError('固件选择无效，请重新校验本地包',400)
    if action in ("set-action-scale") and (not isinstance(command["model"], str)
            or not re.fullmatch(r"official|[a-f0-9]{32}", command["model"])):
        raise ControlError("模型标识无效，请刷新列表", 400)
    if action in ("set-action-scale",):
        numeric(command["kp"],0,255,True)
        numeric(command["kd"],0,255,True)
        numeric(command["torque_limit"],0,1000,True)
        numeric(command["scale"], 0.1, 1.0)
        if command["scale"] not in tuple(round(n/100,2) for n in range(10,101)):raise ControlError("请选择 0.10 到 1.00 的缩放值，步长 0.01",400)
    if action == "set-pad-settings":
        numeric(command["mouth_percent"],0,100)
        if type(command["head_rad"]) not in (int,float) or command["head_rad"] not in (.5,1.,2.5):raise ControlError("头部幅度选项无效",400)
    password = command.get("sudo_password")
    if password is not None and (not isinstance(password, str) or not 0 < len(password) <= 256
                                or any(c in password for c in "\r\n\0")):
        raise ControlError("Zero sudo 密码格式无效", 400)
    if action == "move": numeric(command["position"], 0, 4095, True)
    if action == "center" and command["unassembled"] is not True: raise ControlError("整组居中仅用于尚未装配的舵机", 400)
    if action == "capture":
        for k in ("angle_deg", "min_deg", "max_deg"): numeric(command[k], -360, 360)
        if type(command["direction"]) is not int or command["direction"] not in (-1, 1): raise ControlError("方向必须为 +1 或 -1", 400)
        if not command["min_deg"] <= command["angle_deg"] <= command["max_deg"] or command["min_deg"] >= command["max_deg"]:
            raise ControlError("已知角度必须在实际关节限位之内", 400)
    if action == "verify-imu":
        q = command["mount_wxyz"]
        if command["confirmed"] is not True: raise ControlError("请先核对机身安装方向", 400)
        if not isinstance(q, list) or len(q) != 4: raise ControlError("安装四元数需要 w、x、y、z 四个值", 400)
        for v in q: numeric(v, -1, 1)
        if abs(sum(v*v for v in q)-1) > 1e-6: raise ControlError("安装四元数必须为单位长度", 400)
    return command


class ServiceTransport:
    def __init__(self, target, socket_path, system_log=None):
        self.target, self.path = target, socket_path
        self.log = system_log
        self.credential = SudoCredential(target)
        self.channel = ServiceChannel(target, socket_path, system_log)

    def credential_status(self):
        return {"sudo_password_saved": self.credential.saved, "sudo_password_scope": self.credential.scope}

    def forget_sudo_password(self):
        self.credential.forget()

    def call(self, command):
        timeout = (command.get("duration_ms", 0)/1000)*(15 if command["action"] == "center" else 1)+(135 if command["action"] == "center" else 15)
        method = {"relax": "robot.relax", "init": "robot.init", "home-stop": "robot.enable"}.get(command["action"], "robot.busCommand")
        if self.log: self.log.add('服务 IPC', json.dumps({'method':method,'command':command},ensure_ascii=False))
        reply = self.channel.request({"method":method, "params":command if method == "robot.busCommand" else {"on":False} if method == "robot.enable" else {},
                                      "timeout":timeout}, timeout=timeout+12)
        if self.log: self.log.add('服务 IPC / 回执', json.dumps(reply,ensure_ascii=False))
        if reply.get("error"):
            error = reply["error"]
            raise ControlError(error.get("message", str(error)), 503)
        if reply.get("id") != 1 or "result" not in reply: raise ControlError("服务回执无效", 503)
        if isinstance(reply["result"], dict) and reply["result"].get("accepted") is False:
            raise ControlError(reply["result"].get("reason") or "robotd 拒绝了站姿请求", 409)
        return reply["result"]

    def manage(self, *args, password=None, privileged=True):
        """One fixed installed helper; shell arguments are quoted, credentials use stdin."""
        return self._manage(["/bin/bash", "/opt/robot/feetech-ft5-r5/service.sh", *args], password, privileged)

    def _manage(self, command, password=None, privileged=True, progress=None):
        supplied = password is not None
        password = (password if supplied else self.credential.get()) if privileged else None
        if privileged:
            command = ["sudo", "-n" if password is None else "-S", *([] if password is None else ["-p", ""]), "--", *command]
        if self.log:
            self.log.hide(password)
            self.log.add('SSH 命令', shlex.join(command))
        def clean(data):
            text = data
            if password: text = text.replace(password, "[已隐藏]")
            return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        streaming = bool(progress or self.log)
        def output_line(line):
            line=clean(line)
            if self.log: self.log.add('SSH 输出',line)
            if progress: progress(line)
        try:
            result = self.channel.request({'kind':'manage', 'argv':command,
                                           'input':password + "\n" if password is not None else '',
                                           **({'progress':True,'timeout':240 if progress else 120} if streaming else {})},
                                          timeout=255 if progress else 135,
                                          **({'progress':output_line} if streaming else {}))
        except TimeoutError:
            if self.log: self.log.add('SSH 错误','服务操作等待超时；指令未重发')
            raise ControlError("服务操作等待超时；请查看实时状态，未自动重试", 503) from None
        stderr, stdout = clean(result['stderr']).strip(), clean(result['stdout']).strip()
        if self.log:
            if not streaming and stdout: self.log.add('SSH 输出',stdout)
            if not streaming and stderr: self.log.add('SSH stderr',stderr)
            self.log.add('SSH 命令结束',f'退出码 {result["returncode"]}')
        output = stderr + "\n" + stdout
        if result["returncode"]:
            if any(x in output.lower() for x in ("password is required", "a terminal is required")):
                raise ControlError("请在机器人服务卡片输入 Zero sudo 密码，再操作一次", 409)
            if password is not None and any(x in output.lower() for x in ("incorrect password", "sorry, try again")):
                if not supplied: self.credential.forget()
                raise ControlError("Zero sudo 密码不正确；请重新输入", 403)
            # Keep the actual failure ahead of verbose calibration/progress output.
            detail = stderr[-2400:] if stderr else stdout[-2400:]
            raise ControlError("服务操作失败：" + (detail or "未返回原因"), 503)
        if supplied: self.credential.remember(password)
        output = stdout
        try: return json.loads(output)
        except ValueError:
            for line in reversed(output.splitlines()):
                try: receipt=json.loads(line)
                except ValueError:continue
                if isinstance(receipt,dict) and (isinstance(receipt.get('model_assignment'),dict) or receipt.get('upgrade_installed') is True):return receipt
            return {"message": output[-2000:], "verified_by": "service.sh"}

    def _ssh_run(self, command, timeout):
        if self.log: self.log.add('SSH 命令', self.target+' '+shlex.join(command))
        try:
            result=subprocess.run(ssh_command(self.target)+command,**ssh_process_options(self.target),capture_output=True,timeout=timeout)
            if self.log:
                for channel,output in [('stdout',result.stdout),('stderr',result.stderr)]:
                    if output: self.log.add('SSH '+channel,output.decode(errors='replace'))
                self.log.add('SSH 命令结束',f'退出码 {result.returncode}')
            return result
        except Exception as exc:
            if self.log: self.log.add('SSH 错误',str(exc))
            raise

    def power(self, action, password=None):
        """Send one OS command through the existing SSH management channel."""
        if action not in ('reboot', 'shutdown'): raise ControlError('电源操作无效', 400)
        from power_control import power as submit_power
        def submit(*argv, **_):
            return self._manage(list(argv),password=password)
        return submit_power(action,runner=submit)

    def upgrade(self, password=None, archive=None, progress=None):
        """Install only the fixed, bundled release; no user paths or remote code input."""
        name = 'Microduck-Robotd-FT6-R17'
        bundle_info()
        archive = Path(archive) if archive else ROOT / 'updates' / (name + '.tar.gz')
        if not archive.is_file(): raise ControlError('中控缺少配套 R17 服务包，请重新解压完整中控', 409)
        if not self.target:
            with tempfile.TemporaryDirectory(prefix='microduck-upgrade-') as directory:
                with tarfile.open(archive) as package: package.extractall(directory, filter='data')
                return self._manage(['/bin/bash', str(Path(directory)/name/'service.sh'), 'upgrade'], password,progress=progress)
        from staging_upload import StagingUpload
        if progress:progress('正在上传已校验的 R17 固件包到 Zero…\n')
        remote = StagingUpload(self.target,self.log)
        # mktemp owns an exclusive staging directory; only this directory is cleaned up.
        result = self._manage(['mktemp','-d','/tmp/microduck-upgrade-XXXXXXXXXXXX'],privileged=False)
        directory = result.get('message','').strip()
        if not re.fullmatch(r'/tmp/microduck-upgrade-[A-Za-z0-9]{12}', directory):
            raise ControlError('无法建立服务更新暂存目录', 503)
        try:
            remote_archive = directory + '/package.tar.gz'
            with archive.open('rb') as stream: remote.upload(remote_archive, stream, archive.stat().st_size)
            self._manage(['tar','-xzf',remote_archive,'-C',directory],privileged=False)
            return self._manage(['/bin/bash',directory+'/'+name+'/service.sh','upgrade'],password,progress=progress)
        finally:
            # Delete only our validated exclusive staging tree with the same
            # sudo authorization. Cleanup failure must not mask the install result.
            try:self._manage(['/bin/rm','-rf','--',directory],password)
            except (ControlError,OSError,RuntimeError,subprocess.TimeoutExpired) as exc:
                if self.log:self.log.add('升级暂存清理','清理未完成：'+str(exc))

    def switch_mode(self, target, password=None):
        return {**self.manage("enable" if target == "motion" else "disable", password=password), "mode": target}

    def import_model(self, name, stream, size, password=None,slot=None):
        remote_path = "/tmp/microduck-policy-" + secrets.token_hex(16) + ".zip"
        if self.target:
            from staging_upload import StagingUpload
            remote = StagingUpload(self.target,self.log)
            try:
                remote.upload(remote_path, stream, size)
                return self.manage("model-import", remote_path, name, slot, password=password)
            finally:
                # Only our randomly named staging file; never delete a user path here.
                try:
                    cleanup=self._ssh_run([shlex.join(["rm", "-f", "--", remote_path])],15)
                    if cleanup.returncode:raise OSError(cleanup.stderr.decode(errors='replace')[-500:])
                except (OSError,RuntimeError,subprocess.TimeoutExpired) as exc:
                    if self.log:self.log.add('模型暂存清理','清理未完成：'+str(exc))
        else:
            path = Path(remote_path)
            try:
                with path.open("xb") as output:
                    left = size
                    while left:
                        data = stream.read(min(left, 65536))
                        if not data: raise ControlError("模型上传中断", 400)
                        output.write(data); left -= len(data)
                return self.manage("model-import", str(path), name, slot, password=password)
            finally: path.unlink(missing_ok=True)


class ServiceController:
    def __init__(self, store, target=None, socket_path="/run/robotd.sock", transport=None,controls=None,warm=True):
        self.store, self.transport = store, transport or ServiceTransport(target, socket_path, getattr(store,'system_log',None))
        self.controls=controls
        self.lock = threading.RLock()
        self.sequences = SequenceWindow(limit=32)
        self.busy = False
        self.stopping = False
        self.closed = False
        self.cancel_epoch = 0
        self.error = ""
        self.job = None
        self.power_boot_id = None
        self.prepared_firmware = None
        if transport is None and warm:
            threading.Thread(target=self.transport.channel.warm, daemon=True).start()

    def status(self, snapshot=None):
        with self.lock:
            if snapshot is None:snapshot=getattr(self.store,'peek',self.store.snapshot)()
            if self.power_boot_id and self.stopping and self.job and self.job.get('action')=='reboot' and self.job.get("status") == "completed":
                system = snapshot.get("system", {})
                boot = system.get("boot_id")
                if boot and boot != self.power_boot_id:
                    self.stopping = False
                    self.store.service_operation = False
                    self.power_boot_id = None
                    self.job.setdefault("result", {})["reconnected"] = True
            credential = self.transport.credential_status() if hasattr(self.transport, 'credential_status') else {}
            return {"available": True, "busy": self.busy, "stopping": self.stopping, "job": {k:v for k,v in self.job.items() if k not in {'log','log_revision','log_truncated'}} if self.job else None,
                    **credential,
                    "home": home_feedback(snapshot),
                    "error": self.error}

    @staticmethod
    def _validate_home(snapshot):
        report = snapshot.get("bus") or {}
        native = report.get("native") or {}
        gravity = snapshot.get("imu", {}).get("gravity")
        if not supports_feature(report, "motion") or report.get("mode") != "motion":
            raise ControlError("请先切到机器人运动模式", 409)
        if (not snapshot.get("service_sample_fresh") or report.get("phase") != "control"
                or report.get("fresh_sample") is not True or type(report.get("policy_enabled")) is not bool):
            raise ControlError("运动循环或传感器未就绪，请先检查服务状态", 409)
        if type(native.get("torque_state_confirmed")) is not bool:
            raise ControlError("等待确认当前扭矩状态", 409)
        rows = snapshot.get("servos", [])
        if snapshot.get("calibrated_count") != 15 or len(rows) != 15 or any(r.get("status") != "live" for r in rows):
            raise ControlError("需要 15 颗已标定关节的实时反馈", 409)
        if (snapshot.get("imu", {}).get("status") != "live" or native.get("imu_mount_verified") is not True
                or not isinstance(gravity, list) or len(gravity) != 3 or not all(math.isfinite(v) for v in gravity)
                or gravity[2] > -0.8):
            raise ControlError("请将机身直立支撑，核对 IMU 重力方向和安装确认", 409)

    def _home_snapshot(self, epoch, origin=None):
        with self.lock:
            if self.closed or epoch != self.cancel_epoch:
                raise ControlError("Home 已取消")
            snapshot = self.store.snapshot()
        if origin:
            for name, old, new in (
                ("Zero", origin.get("system", {}).get("boot_id"), snapshot.get("system", {}).get("boot_id")),
                ("机器人服务", origin.get("bus", {}).get("native", {}).get("telemetry", {}).get("session"),
                 snapshot.get("bus", {}).get("native", {}).get("telemetry", {}).get("session")),
            ):
                if old is not None and new is not None and old != new:
                    raise ControlError(name + "已重启，本次 Home 未确认完成")
        return snapshot

    def _home_progress(self, job, phase, message):
        with self.lock:
            if job.get("phase") != phase:
                job.update(phase=phase, message=message)
                self.store.record_service_command(job)

    @staticmethod
    def _accepted_home_reply(answer, operation):
        if not isinstance(answer, dict) or answer.get("accepted") is not True:
            reason = answer.get("reason") if isinstance(answer, dict) else None
            raise ControlError(reason or f"服务未接收{operation}请求")

    def _run_home(self, command, job, epoch):
        origin = self._home_snapshot(epoch)
        self._validate_home(origin)
        restored = False
        if home_feedback(origin)["phase"] == "restore_pending":
            # Only restore temporary gains on an already OFF robot. ON goes straight
            # to init: never unload a standing robot as part of this recovery.
            self._home_progress(job, "restoring", "扭矩已确认 OFF，正在恢复上次未完成的临时 P/D 参数")
            answer = self.transport.call({"action": "relax"})
            self._accepted_home_reply(answer, "参数恢复")
            deadline = time.monotonic() + HOME_RESTORE_TIMEOUT
            while True:
                snapshot = self._home_snapshot(epoch, origin)
                report = snapshot.get("bus") or {}
                native = report.get("native") or {}
                hd1910 = native.get("hd1910") or {}
                if (snapshot.get("service_sample_fresh") and report.get("mode") == "motion"
                        and report.get("phase") == "control" and report.get("policy_enabled") is False
                        and native.get("torque_state_confirmed") is False
                        and hd1910.get("restore_pending") is False and hd1910.get("temporary_gains_applied") is False):
                    restored = True
                    break
                if time.monotonic() >= deadline:
                    raise ControlError("临时 P/D 恢复未确认成功；未发送 Home。请查看 HAT 服务日志，不要反复点击")
                time.sleep(HOME_POLL_INTERVAL)
        before = self._home_snapshot(epoch, origin)
        self._validate_home(before)
        if home_feedback(before)["ready"]:
            self._home_progress(job, "ready", "当前已到 Home，确认实时反馈")
            return {**self._wait_home_result(epoch, before, job), "restored_temporary_gains":restored}
        # Official padd Start-off uses robot.enable(on=false), with direct Home targets.
        # Only limp / non-policy repositioning needs the daemon's robot.init ramp.
        request = {"action":"home-stop"} if before["bus"]["policy_enabled"] else command
        self._home_progress(job, "requesting", "正在提交 Home 请求，等待服务执行")
        answer = self.transport.call(request)
        self._accepted_home_reply(answer, "Home")
        self._home_progress(job, "accepted", "Home 请求已接收，等待扭矩开启和关节到位")
        result = self._wait_home_result(epoch, before, job)
        return {**result, "restored_temporary_gains": restored}

    def _wait_home_result(self, epoch, origin, job):
        deadline = time.monotonic() + HOME_TIMEOUT
        confirmed = 0
        last_cycle = origin.get("bus", {}).get("cycle", -1)
        last_state_t = origin.get("state", {}).get("t", -1)
        last_feedback = None
        policy_stopped = origin.get("bus", {}).get("policy_enabled") is False
        while True:
            snapshot = self._home_snapshot(epoch, origin)
            report = snapshot.get("bus") or {}
            feedback = home_feedback(snapshot)
            if feedback["phase"] == "restore_pending":
                raise ControlError("Home 未执行：临时 P/D 设置或回读未完成，扭矩仍为 OFF；"
                                   "再次点 Home 将先尝试恢复参数。持续失败请查看 HAT 服务日志")
            if report.get("policy_enabled") is False: policy_stopped = True
            if report.get("mode") != "motion" or policy_stopped and report.get("policy_enabled") is True:
                raise ControlError("运行模式或策略状态已改变，本次 Home 未确认完成")
            cycle = report.get("cycle")
            state_t = snapshot.get("state", {}).get("t")
            if not feedback["ready"]:
                confirmed = 0
            # Cached/duplicated frames must not count as three arrival samples.
            elif (isinstance(cycle, (int, float)) and isinstance(state_t, (int, float))
                  and cycle > last_cycle and state_t > last_state_t):
                confirmed += 1
                last_cycle, last_state_t = cycle, state_t
                if confirmed >= HOME_CONFIRM_SAMPLES:
                    return {"homed": True, "torque": "on", "message": feedback["message"],
                            "confirmed_ids": feedback["confirmed_ids"], "max_error_deg": feedback["max_error_deg"],
                            "tolerance_deg": HOME_TOLERANCE_DEG, "confirmed_samples": confirmed}
            if feedback["phase"] != last_feedback:
                self._home_progress(job, feedback["phase"], feedback["message"] if not feedback["ready"]
                                    else "关节已接近 Home，正在确认连续到位反馈")
                last_feedback = feedback["phase"]
            if time.monotonic() >= deadline:
                detail = feedback["message"] if not feedback["ready"] else "未收到连续更新的到位反馈"
                raise ControlError("Home 未确认完成：" + detail + "。请检查实际姿态和服务日志")
            time.sleep(HOME_POLL_INTERVAL)


    def handle(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"client", "seq", "command"}: raise ControlError("请求格式错误", 400)
        client, seq = payload["client"], payload["seq"]
        if not isinstance(client, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{8,80}", client) or type(seq) is not int or not 0 <= seq <= 2**53:
            raise ControlError("页面标识或序号无效", 400)
        command = validate(payload["command"])
        sudo_password = command.get("sudo_password")
        # Jobs are visible in snapshots and recordings; keep credentials out.
        command = {key: value for key, value in command.items() if key != "sudo_password"}
        action = command["action"]
        with self.lock:
            if self.closed: raise ControlError("中控已关闭")
            try:self.sequences.accept(client,seq)
            except ValueError as exc:raise ControlError(str(exc)) from None
            paused=getattr(self.store,'connection_paused',None)
            if action=='resume-connection':
                if self.busy or self.job and self.job.get('status')=='running':raise ControlError('请等待当前操作完成',409)
                if paused is not None:paused.clear()
                if self.controls:self.controls.resume_connections()
                self.stopping=False;self.store.service_operation=False;self.power_boot_id=None
                answer={'accepted':True,'message':'已恢复连接，等待 Zero 上线；不会自动 HOME 或启用策略'}
                self.job={'action':action,'status':'completed','at':time.time(),'command':command,'result':answer}
                self.store.record_service_command(self.job)
                return answer
            if action == 'forget-sudo-password':
                if self.busy: raise ControlError('请等待当前服务操作结束后再删除密码', 409)
                if hasattr(self.transport, 'forget_sudo_password'):
                    self.transport.forget_sudo_password()
                return {"accepted": True, "message": "已删除保存的 Zero sudo 密码"}
            if action not in {"reboot","shutdown","upgrade-service"} and paused is not None and paused.is_set():raise ControlError('Zero 关机后自动连接已暂停，请先点击恢复连接',409)
            if action not in STOP_ACTIONS:
                if self.busy or self.stopping and action != 'upgrade-service': raise ControlError("已有操作执行中，请等待反馈或停止并松开")
                snapshot = self.store.snapshot()
                report = snapshot.get("bus", {})
                recovery = action in {"reconnect-service", "upgrade-service", "set-action-scale"} or action == 'switch-mode'
                if not recovery and not supports_feature(report, "supported"): raise ControlError("等待适配的正式服务提供状态")
                # HAT recovery and deployment must work without motor feedback.
                if not recovery and not snapshot.get("service_sample_fresh"):
                    raise ControlError("等待适配的正式服务提供新鲜数据")
                if action == "switch-mode":
                    if (not supports_feature(report, 'management') and snapshot.get('service_sample_fresh') and self.job and self.job.get("action") == "switch-mode" and self.job.get("status") == "completed"
                            and self.job.get("command", {}).get("target") != report.get("mode")):
                        raise ControlError("切换脚本已完成；请等待新模式的实时反馈，勿重复切换", 409)
                    native = report.get("native") or {}
                    if report.get("mode") == command["target"] and snapshot.get('service_sample_fresh'):
                        raise ControlError("当前已经是所选模式", 409)
                    torque_off = (report.get("torque_state") == "off" if report.get("mode") == "commissioning"
                                  else native.get("torque_state_confirmed") is False)
                    if supports_feature(report, "supported") and not supports_feature(report, "management") and (not torque_off or report.get("torque_off_pending")):
                        raise ControlError("请先支撑机身并停止并松开，等待扭矩 OFF", 409)
                    if command["target"] == "motion" and supports_feature(report, "supported") and not supports_feature(report, "management") and (
                            snapshot.get("calibrated_count") != 15 or native.get("imu_mount_verified") is not True
                            and report.get("imu_mount_verified") is not True):
                        raise ControlError("请先完成 15 个关节标定和 IMU 安装确认", 409)
                elif action in {"reconnect-service", "upgrade-service", "set-pad-settings", "set-action-scale"}:
                    if action == 'upgrade-service' and command['firmware'] != 'bundled':
                        prepared=self.prepared_firmware
                        if not prepared or prepared.owner!=client or not secrets.compare_digest(prepared.token,command['firmware']):
                            raise ControlError('本地固件校验已失效，请重新选择 ZIP',409)
                    if action == 'set-pad-settings' and not supports_feature(report, 'live_pad_settings'):raise ControlError('请先安装本版配套服务，再使用运行中幅度设置',409)
                    if action != 'upgrade-service'  and supports_feature(report, "supported") and not supports_feature(report, "management"):
                        raise ControlError("连接与模型管理需要配套 R17 服务", 409)
                elif action == "init":
                    self._validate_home(snapshot)

                else:
                    if report.get("mode") != "commissioning": raise ControlError("逐关节操作需要服务处于 commissioning 模式")
                    if report.get("phase") != "ready" or report.get("torque_state") != "off": raise ControlError("请先停止并松开，等待服务确认停扭矩")
                if action == "move":
                    row = next(r for r in snapshot["servos"] if r["id"] == command["id"])
                    if row["status"] != "live": raise ControlError("所选关节没有实时反馈")
                    if row.get("calibrated"):
                        cal = row["calibration"]
                        angle = (command["position"]-cal["zero_raw"])*2*math.pi/4096*cal["direction"]
                        if not cal["min_rad"] <= angle <= cal["max_rad"]: raise ControlError("目标超过该关节已保存的机械限位")
                if action == "center" and snapshot.get("saved_calibrated_count", snapshot.get("calibrated_count", 0)): raise ControlError("已有标定的关节；整组居中仅供未装配时使用")
                self.busy = True
            else:
                if self.stopping and (action not in {"reboot", "shutdown"} or
                        self.job and self.job.get("action") in {"reboot", "shutdown"}):
                    raise ControlError("已有停止或电源操作执行中，请等待回执")
                self.stopping = True
                if action in {"reboot", "shutdown"}: self.power_boot_id = self.store.snapshot().get("system", {}).get("boot_id")
                self.cancel_epoch += 1
            self.store.service_operation = action != "set-pad-settings"
            job = {"action": action, "status": "running", "at": time.time(), "command": command}
            self.job, self.error = job, ""
            self.store.record_service_command(job)
            threading.Thread(target=self._execute, args=(command, job, self.cancel_epoch, sudo_password), daemon=True).start()
            return {"accepted": True, "message": "指令已提交；以服务回执和实时反馈为准"}

    def _execute(self, command, job, epoch, sudo_password=None):
        recover_input = False
        try:
            with self.lock:
                if command["action"] not in STOP_ACTIONS and (self.closed or epoch != self.cancel_epoch):
                    raise ControlError("指令在发送前已取消")
            if command["action"] == "switch-mode":
                answer = self.transport.switch_mode(command["target"], sudo_password)
            elif command["action"] == "upgrade-service":
                prepared=self.prepared_firmware if command['firmware']!='bundled' else None
                def progress(line):
                    with self.lock:
                        log=job.get('log','')
                        if len(log)<512*1024:job['log']=(log+line)[:512*1024]
                        if len(log)+len(line)>512*1024:job['log_truncated']=True
                        job['log_revision']=job.get('log_revision',0)+1
                progress('开始升级 R17 / 0.15.1；保留本机标定，不自动 HOME 或启用策略。\n')
                answer = self.transport.upgrade(sudo_password,archive=prepared.path if prepared else None,progress=progress)
                with self.lock:
                    if epoch == self.cancel_epoch:
                        self.stopping=False
                        self.power_boot_id=None
                        paused=getattr(self.store,'connection_paused',None)
                        if paused is not None:paused.clear()
            elif command["action"] == "reconnect-service":
                answer = self.transport.manage('reconnect', password=sudo_password)
            elif command["action"] == "set-pad-settings":
                answer = self.transport.manage("pad-settings", str(command["mouth_percent"]), str(command["head_rad"]), password=sudo_password)
            elif command["action"] == "set-action-scale":
                answer = self.transport.manage("action-scale", command["model"], str(command["scale"]), str(command["kp"]), str(command["kd"]), str(command["torque_limit"]), password=sudo_password)
            elif command["action"] in {"reboot", "shutdown"}:
                answer = self.transport.power(command["action"], password=sudo_password)
                if not isinstance(answer,dict) or answer.get('scheduled') is not True :
                    raise ControlError('未取得系统电源指令提交确认，请查看系统日志',503)
                if command['action']=='shutdown':
                    paused=getattr(self.store,'connection_paused',None)
                    if paused is not None:paused.set()
                    if self.controls:self.controls.suspend_connections()
                    if hasattr(self.transport,'channel'):self.transport.channel.disconnect()
                    if getattr(self.store,'system_log',None):self.store.system_log.add('系统关机','已提交关机；采集、手柄和服务自动连接已暂停。上电后点击恢复连接。')
                else:
                    paused=getattr(self.store,'connection_paused',None)
                    if paused is not None:paused.clear()
                    if self.controls:self.controls.resume_connections()
            elif command["action"] == "init":
                answer = self._run_home(command, job, epoch)
            else:
                answer = self.transport.call(command)
            if self.controls and command['action'] in {'upgrade-service','reconnect-service','switch-mode','set-action-scale'} and (command['action']!='upgrade-service' or epoch==self.cancel_epoch):
                if command['action']=='upgrade-service':self.controls.resume_connections()
                answer=self._with_input_pending(answer)
                recover_input = True
            with self.lock:
                if command["action"] == "init" and (self.closed or epoch != self.cancel_epoch):
                    raise ControlError("Home 已取消")
                job.update(status="completed", result=answer)
            if isinstance(answer, dict) and isinstance(answer.get("calibration"), dict):
                data = answer if "joints" in answer["calibration"] else answer["calibration"]
                self.store.ingest({"channel": "calibration", "data": data})
        except Exception as exc:
            with self.lock:
                job.update(status="error", error=str(exc))
                if getattr(self.store,'system_log',None): self.store.system_log.add('服务操作错误',str(exc))
                if self.job is job: self.error = str(exc)
        finally:
            with self.lock: cancelled = epoch != self.cancel_epoch or self.closed
            if ((cancelled or job["status"] == "error") and command["action"] in ("move", "center")):
                try: self.transport.call({"action": "relax"})
                except Exception: pass
            with self.lock:
                self.store.record_service_command(job)
                if command["action"] in STOP_ACTIONS: self.stopping = command["action"] in {"reboot", "shutdown"} and job.get("status") == "completed"
                else: self.busy = False
                self.store.service_operation = self.busy or self.stopping
        if recover_input and job.get('status')=='completed':
            self._start_input_recovery(job,epoch)

    @staticmethod
    def _with_input_pending(answer):
        return {**(answer if isinstance(answer,dict) else {'result':answer}),
                'operation':{'status':'completed'},
                'input':{'status':'recovering','webpad_reconnected':False,'message':'主操作已完成，手柄连接正在恢复'}}

    def _start_input_recovery(self,job,epoch):
        # This only restores the input transport; it never repeats the completed
        # mode/model/install command or carries held input into a new daemon.
        def recover():
            error=''
            for attempt in range(5):
                with self.lock:
                    if self.closed or epoch!=self.cancel_epoch or self.stopping or self.job is not None and self.job is not job:return
                try:
                    if attempt==0:answer=self.controls.reconnect_after_service()
                    elif hasattr(self.controls,'refresh_after_service'):answer=self.controls.refresh_after_service()
                    else:break
                    state={**answer,'status':'ready','message':'手柄连接已恢复'}
                    error=''
                except Exception as exc:
                    error=str(exc)
                    state={'status':'recovering','webpad_reconnected':False,'error':error,'message':'主操作已完成，等待手柄接口恢复'}
                with self.lock:
                    if self.closed or epoch!=self.cancel_epoch or self.job is not None and self.job is not job:return
                    job['result']={**job['result'],'input':state}
                if not error:return
                if attempt<4:time.sleep(min(.25*2**attempt,2))
            with self.lock:
                if self.closed or epoch!=self.cancel_epoch or self.job is not None and self.job is not job:return
                job['result']={**job['result'],'input':{'status':'error','webpad_reconnected':False,'error':error,'message':'主操作已完成；手柄暂不可用，页面会继续恢复连接'}}
                self.store.record_service_command(job)
            if getattr(self.store,'system_log',None):self.store.system_log.add('手柄恢复',error)
        threading.Thread(target=recover,daemon=True).start()

    def models(self):
        if getattr(self.store,'connection_paused',None) and self.store.connection_paused.is_set():raise ControlError('Zero 关机后自动连接已暂停',409)
        if not supports_feature(self.store.snapshot().get("bus", {}), "management"):
            connection=self.transport.manage('connection', privileged=False)
            if connection.get('management_revision') != 'R17':
                raise ControlError("模型管理需要配套 R17 服务", 409)
        return self.transport.manage("models", privileged=False)

    def connection(self):
        if getattr(self.store,'connection_paused',None) and self.store.connection_paused.is_set():raise ControlError('Zero 关机后自动连接已暂停',409)
        return self.transport.manage('connection', privileged=False)

    def firmware_info(self):
        return bundle_info()

    def prepare_firmware(self, name, stream, size, owner):
        if not isinstance(owner,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}',owner):
            raise ControlError('页面标识无效',400)
        with self.lock:
            if self.closed or self.busy or self.stopping:raise ControlError('请等待当前服务操作完成',409)
            self.busy=self.store.service_operation=True
        try:
            prepared=PreparedFirmware(name,stream,size,owner)
            with self.lock:
                if self.closed:
                    prepared.close();raise ControlError('中控已关闭',409)
                if self.prepared_firmware:self.prepared_firmware.close()
                self.prepared_firmware=prepared
            return prepared.info
        except (ValueError,OSError,tarfile.TarError) as exc:
            raise ControlError('固件 ZIP 校验失败：'+str(exc),400) from exc
        finally:
            with self.lock:
                self.busy=False;self.store.service_operation=self.stopping

    def import_model(self, name, stream, size, password=None,slot=None):
        if slot not in SLOTS:raise ControlError('请先选择官方动作，再导入对应模型',400)
        if not ACTION_INFO[slot]['import_supported']:raise ControlError(ACTION_INFO[slot]['support_message'],400)
        if not isinstance(name, str) or Path(name).name != name or not name.lower().endswith('.zip') or len(name) > 180:
            raise ControlError("请选择训练台导出的完整 .zip 模型包", 400)
        if not 0 < size <= MAX_MODEL: raise ControlError("完整模型 ZIP 上限 64 MiB", 400)
        if password is not None and (not 0 < len(password) <= 256 or any(c in password for c in "\r\n\0")):
            raise ControlError("Zero sudo 密码格式无效", 400)
        with self.lock:
            if self.closed or self.busy or self.stopping: raise ControlError("请等待当前服务操作完成", 409)
            if not supports_feature(self.store.snapshot().get("bus", {}), "management"):
                raise ControlError("请先安装 R17 自训服务", 409)
            self.busy = self.store.service_operation = True
            job = {"action":"import-model", "status":"running", "at":time.time(), "command":{"name":name,"slot":slot}}
            self.job = job
        try:
            result = self.transport.import_model(name, stream, size, password,slot=slot)
            receipt=result.get('model_assignment') if isinstance(result,dict) else None
            if not isinstance(receipt,dict) or receipt.get('slot')!=slot or receipt.get('saved_verified') is not True or receipt.get('mode') not in ('motion','commissioning') or receipt.get('mode')=='motion' and receipt.get('running_verified') is not True:
                raise ControlError('未确认所选动作模型的绑定及运行加载；请安装本版随包固件并查看日志',503)
            if self.controls:result=self._with_input_pending(result)
            job.update(status="completed", result=result)
            return result
        except Exception as exc:
            job.update(status="error", error=str(exc))
            if getattr(self.store,'system_log',None): self.store.system_log.add('服务操作错误',str(exc))
            raise
        finally:
            with self.lock:
                self.busy = False
                self.store.service_operation = self.stopping
                self.store.record_service_command(job)
            if self.controls and job.get('status')=='completed':self._start_input_recovery(job,self.cancel_epoch)

    def close(self):
        with self.lock:
            self.closed = True
            self.cancel_epoch += 1
            moving = self.busy
        if moving:
            try: self.transport.call({"action": "relax"})
            except Exception: pass
        if hasattr(self.transport, "channel"):
            self.transport.channel.close()
        if self.prepared_firmware:self.prepared_firmware.close()
