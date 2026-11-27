#!/usr/bin/env python3
"""把本机交叉编译出的固件装到机器上：备份 → 推送 → 安装 → （可选）重启 → 检查 → 回滚。

**默认只看不改。** 真正执行要 `--apply`；重新拉起 `robotd` 还要再加 `--restart`，
因为那一下会卸力，机器人会倒——必须有人在场、并且明确同意。

沿用 `ducknet/deploy_ble_provisioning.sh` 的落点：二进制默认进
`/opt/robot/daemon/current/bin`，unit 进 `/etc/systemd/system`，`btd` 的 sysusers 进
`/usr/lib/sysusers.d`。**但每个二进制装到哪里以 systemd 的 `ExecStart` 为准**：R17 用
drop-in 把 `robotd` 指向 `/opt/robot/feetech-ft5-r5/robotd`，装到 `current/bin` 是不生效的。

机器人 IP 走 DHCP，会随网络变化；**每次执行前先用 ducknet 只读 `net.status` 确认当前地址**，
不要沿用旧 IP。

用法（`<机器人IP>` 换成刚查到的地址）：

    python3 deploy_robot.py duck@<机器人IP>                    # 打印计划
    python3 deploy_robot.py duck@<机器人IP> --apply            # 安装，不重启
    python3 deploy_robot.py duck@<机器人IP> --apply --restart  # 安装并重启三个服务
    python3 deploy_robot.py duck@<机器人IP> --rollback         # 恢复最近一次备份

退出码：0 成功；1 某一步失败；2 参数/环境问题。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

BIN_DIR = "/opt/robot/daemon/current/bin"
UNIT_DIR = "/etc/systemd/system"
SYSUSERS_DIR = "/usr/lib/sysusers.d"
REMOTE_STAGE = "/tmp/duck-fw-deploy"
DEFAULT_BACKUP_DIR = "/home/duck/duck-firmware-backup"

#: 装到板上的二进制。`robotctl` 一起换，否则它与 robotd 的协议版本会对不上。
BINARIES = ["robotd", "robotctl", "btd", "configd"]

#: 二进制 → 服务单元。`robotctl` 没有单元，按默认目录装。
UNITS = {"robotd": "robotd", "btd": "btd", "configd": "configd"}

HERE = Path(__file__).resolve().parent
FIRMWARE = HERE.parents[1]
DEFAULT_BIN_DIR = HERE.parents[2] / ".build" / "firmware" / "bin"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Microduck 固件部署（机器人端）")
    parser.add_argument("target", help="user@host，例如 duck@<机器人IP>（先查 net.status 确认）")
    parser.add_argument("--bin-dir", default=str(DEFAULT_BIN_DIR), help="本机固件产物目录")
    parser.add_argument("--apply", action="store_true", help="真的执行（默认只打印）")
    parser.add_argument("--restart", action="store_true",
                        help="安装后重启 configd/btd/robotd；robotd 重启会卸力")
    parser.add_argument("--rollback", action="store_true", help="从最近一次备份恢复，然后退出")
    parser.add_argument("--backup-dir", default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--no-units", action="store_true", help="只换二进制，不动 unit 文件")
    return parser.parse_args()


def log(message: str) -> None:
    print(f"\033[1m== {message}\033[0m")


def warn(message: str) -> None:
    print(f"\033[33m[warn]\033[0m {message}")


def die(message: str) -> None:
    print(f"\033[31m[err]\033[0m {message}", file=sys.stderr)
    raise SystemExit(2)


def remote(target: str, command: str, *, apply: bool, check: bool = True) -> subprocess.CompletedProcess[str]:
    """在机器人上跑一条命令；dry-run 只打印。"""
    if not apply:
        print(f"  [dry-run] ssh {target} {command}")
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", target, command],
        check=check, text=True, capture_output=True,
    )


def push(target: str, paths: list[Path], *, apply: bool) -> None:
    if not apply:
        for path in paths:
            print(f"  [dry-run] scp {path} {target}:{REMOTE_STAGE}/")
        return
    subprocess.run(
        ["ssh", "-o", "BatchMode=yes", target, f"rm -rf {REMOTE_STAGE} && mkdir -p {REMOTE_STAGE}"],
        check=True,
    )
    subprocess.run(
        ["scp", "-q", "-o", "BatchMode=yes", *map(str, paths), f"{target}:{REMOTE_STAGE}/"],
        check=True,
    )


def preflight(target: str, *, apply: bool) -> None:
    log("检查目标机")
    result = remote(
        target,
        "hostname; uname -m; ldd --version | head -1; "
        "systemctl is-active robotd btd configd 2>/dev/null || true",
        apply=apply,
    )
    if apply:
        print("  " + result.stdout.strip().replace("\n", "\n  "))
        if "aarch64" not in result.stdout:
            die("目标机不是 aarch64")
    result = remote(target, "sudo -n true", apply=apply, check=False)
    if apply and result.returncode != 0:
        die("目标机 sudo 需要密码；本脚本要求免密 sudo")


def check_local(bin_dir: Path) -> list[Path]:
    log(f"检查本机产物 {bin_dir}")
    missing = [name for name in BINARIES if not (bin_dir / name).is_file()]
    if missing:
        die("缺少：" + ", ".join(missing) + "；先跑 microduck-hd1910/tools/build-firmware.sh")
    for name in BINARIES:
        path = bin_dir / name
        result = subprocess.run(["file", "-b", str(path)], text=True, capture_output=True)
        if "aarch64" not in result.stdout.lower() and "ARM aarch64" not in result.stdout:
            warn(f"{name} 看起来不是 AArch64：{result.stdout.strip()}")
    return [bin_dir / name for name in BINARIES]


def resolve_paths(target: str, *, apply: bool) -> dict[str, str]:
    """每个二进制在板上**实际被执行**的路径。

    不能假设都在 `BIN_DIR`：这台 R17 用 drop-in（`robotd.service.d/zzzz-r17-*.conf`）把
    `ExecStart` 换成了 `/opt/robot/feetech-ft5-r5/robotd`，装到 `current/bin/robotd` 不会
    生效，重启后跑的还是旧文件。所以每次部署前问一下 systemd。
    """
    paths = {name: f"{BIN_DIR}/{name}" for name in BINARIES}
    for name, unit in UNITS.items():
        result = remote(target, f"systemctl show {unit} -p ExecStart --value",
                        apply=apply, check=False)
        if not apply:
            continue
        for token in result.stdout.split():
            if token.startswith("path="):
                candidate = token[len("path="):]
                if candidate.rsplit("/", 1)[-1] == name:
                    paths[name] = candidate
    return paths


def backup(target: str, backup_dir: str, paths: dict[str, str], *, apply: bool) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    archive = f"{backup_dir}/duck-firmware-{stamp}.tar.gz"
    files = " ".join(paths[name] for name in BINARIES)
    log(f"备份板上二进制 → {archive}")
    remote(
        target,
        f"sudo -n mkdir -p {backup_dir} && "
        f"sudo -n tar -czPf {archive} {files} && "
        f"sudo -n chown $(id -u):$(id -g) {archive}",
        apply=apply,
    )
    return archive


def rollback(target: str, backup_dir: str, *, apply: bool, restart: bool) -> None:
    log("查找最近一次备份")
    result = remote(target, f"ls -1t {backup_dir}/duck-firmware-*.tar.gz 2>/dev/null | head -1",
                    apply=apply)
    archive = result.stdout.strip() if apply else f"{backup_dir}/duck-firmware-<最新>.tar.gz"
    if apply and not archive:
        die(f"{backup_dir} 里没有备份")
    log(f"恢复 {archive}")
    remote(target, f"sudo -n tar -xzPf {archive}", apply=apply)
    if restart:
        restart_services(target, ["configd", "btd", "robotd"], apply=apply)
    verify(target, apply=apply)


def install(target: str, binaries: list[Path], paths: dict[str, str], *, apply: bool,
            units: bool) -> None:
    payload = list(binaries)
    if units:
        payload += [FIRMWARE / "btd/systemd/btd.service",
                    FIRMWARE / "configd/systemd/configd.service",
                    FIRMWARE / "btd/systemd/sysusers.d/btd.conf"]
        for path in payload[len(binaries):]:
            if not path.is_file():
                die(f"缺少 unit 文件 {path}")
    push(target, payload, apply=apply)

    log("安装二进制与 unit")
    commands = [f"install -d -m 0755 {paths[name].rsplit('/', 1)[0]}"
                for name in BINARIES]
    commands += [f"install -m 0755 {REMOTE_STAGE}/{binary.name} {paths[binary.name]}"
                 for binary in binaries]
    if units:
        commands += [
            f"install -m 0644 {REMOTE_STAGE}/btd.conf {SYSUSERS_DIR}/btd.conf",
            "systemd-sysusers",
            f"install -m 0644 {REMOTE_STAGE}/btd.service {UNIT_DIR}/btd.service",
            f"install -m 0644 {REMOTE_STAGE}/configd.service {UNIT_DIR}/configd.service",
            "systemctl daemon-reload",
        ]
    remote(target, "sudo -n sh -c '" + " && ".join(commands) + "'", apply=apply)


def restart_services(target: str, services: list[str], *, apply: bool) -> None:
    log("重启服务：" + " ".join(services))
    if not apply:
        print(f"  [dry-run] ssh {target} systemctl restart {' '.join(services)}")
        return
    # 一次一个，顺序固定：configd 先（btd 的 PIN 从它来），robotd 最后。
    for service in services:
        subprocess.run(["ssh", "-o", "BatchMode=yes", target, f"sudo -n systemctl restart {service}"],
                       check=True)


def verify(target: str, *, apply: bool) -> None:
    log("检查服务状态")
    result = remote(
        target,
        "systemctl is-active robotd btd configd; "
        "journalctl -u btd -n 5 --no-pager 2>/dev/null | tail -5",
        apply=apply, check=False,
    )
    if apply:
        print("  " + result.stdout.strip().replace("\n", "\n  "))
        if "inactive" in result.stdout or "failed" in result.stdout:
            warn("有服务未运行；确认后可用 --rollback 回退")


def main() -> int:
    args = parse_args()
    bin_dir = Path(args.bin_dir).resolve()
    if not shutil.which("ssh") or not shutil.which("scp"):
        die("本机缺 ssh/scp")
    if not args.apply:
        warn("这是 dry-run；加 --apply 才会真的安装")
    if args.restart and not args.apply:
        warn("--restart 在 dry-run 下只打印")

    preflight(args.target, apply=args.apply)
    if args.rollback:
        rollback(args.target, args.backup_dir, apply=args.apply, restart=args.restart)
        return 0

    binaries = check_local(bin_dir)
    paths = resolve_paths(args.target, apply=args.apply)
    if args.apply:
        for name in BINARIES:
            print(f"  {name} → {paths[name]}")
    backup(args.target, args.backup_dir, paths, apply=args.apply)
    install(args.target, binaries, paths, apply=args.apply, units=not args.no_units)
    if args.restart:
        restart_services(args.target, ["configd", "btd", "robotd"], apply=args.apply)
        verify(args.target, apply=args.apply)
    else:
        warn("未重启：新二进制要等 `systemctl restart configd btd robotd` 才生效；"
             "robotd 重启会卸力，确认机器人在座/被扶稳后再加 --restart")
    log("完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
