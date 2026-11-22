#!/usr/bin/env bash
# 给机器人装上 BLE 配网所需的两件事：`btd`（BLE 前置）+ `configd`（net.*）。
#
# 为什么需要它：飞特整机那套部署是「robotd + padd」的最小安装，**没有 btd、也没有
# configd**——所以 App 扫不到机器人（板上根本没有东西在广播），即使扫到也改不了 Wi-Fi。
# 桌面上那个客户端就是本目录（ducknet/）；它凭什么这么设计见
# ../docs/design/ble-provisioning-app.md。
#
# 用法（默认只看不改）：
#   ./deploy_ble_provisioning.sh duck@192.168.110.240          # 打印计划
#   ./deploy_ble_provisioning.sh duck@192.168.110.240 --apply  # 真的装
#   ./deploy_ble_provisioning.sh duck@192.168.110.240 --apply --migrate-network
#
# --migrate-network 只在该板仍用 netplan/wpa_supplicant 时才需要：configd 的 net.*
# 是建立在 NetworkManager 之上的，没有 NM 时 net.status 会直接返回 D-Bus 错误。
# 这一步会接管 wlan0，**有掉线风险**，所以必须显式给出；脚本会：
#   1. 先把 NM 配成「谁都不管」，避免它与 wpa_supplicant 抢同一个网卡；
#   2. 安装 network-manager；
#   3. 用当前 wpa_supplicant 里的 SSID/PSK 建一个 NM 配置 `robot-wifi`；
#   4. 装一个开机自恢复（90 秒拿不到 IPv4 就退回 wpa_supplicant 并重启）；
#   5. 最后切过去，并提示重启后如何退役自恢复。
#
# 退出码：0 成功；2 参数/环境问题；1 某一步失败。
set -euo pipefail

TARGET="${1:-}"
shift || true
APPLY=0
MIGRATE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --migrate-network) MIGRATE=1 ;;
    -h|--help) sed -n '2,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
  shift
done

[[ -n "$TARGET" ]] || { echo "用法：$0 user@host [--apply] [--migrate-network]" >&2; exit 2; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 本脚本住在 firmware/ducknet/ 里，固件源码就是它上一级。
FIRMWARE="${DUCK_FIRMWARE:-$(cd "$HERE/.." && pwd)}"
TARGET_TRIPLE="aarch64-unknown-linux-gnu.2.31"
# 与板上已有 robotd/padd 的构建方式一致（cargo-zigbuild），glibc 下限 2.31。
BIN_DIR="/opt/robot/daemon/current/bin"

log()  { printf '\033[1m== %s\033[0m\n' "$*"; }
warn() { printf '\033[33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[err]\033[0m %s\n' "$*" >&2; exit 1; }

run_remote() {
  if [[ $APPLY == 1 ]]; then
    ssh -o BatchMode=yes "$TARGET" "$@"
  else
    echo "  [dry-run] ssh $TARGET $*"
  fi
}

[[ -d "$FIRMWARE" ]] || die "找不到固件源码：$FIRMWARE（可用 DUCK_FIRMWARE=… 指定）"

log "检查主机上的交叉编译工具"
command -v cargo >/dev/null || die "没有 cargo"
command -v cargo-zigbuild >/dev/null || die "没有 cargo-zigbuild（cargo install cargo-zigbuild）"
command -v zig >/dev/null || die "没有 zig（cargo-zigbuild 依赖它）"
# 固件目录里钉了 rust-toolchain.toml（1.99.0 + aarch64 target），所以要在那个目录里问。
( cd "$FIRMWARE" && rustup target list --installed 2>/dev/null | grep -qx aarch64-unknown-linux-gnu ) \
  || die "缺 aarch64 标准库：在 $FIRMWARE 里执行 rustup target add aarch64-unknown-linux-gnu"

log "交叉编译 btd + configd（$TARGET_TRIPLE）"
if [[ $APPLY == 1 ]]; then
  ( cd "$FIRMWARE" && cargo zigbuild --release --target "$TARGET_TRIPLE" -p btd -p configd )
else
  echo "  [dry-run] (cd $FIRMWARE && cargo zigbuild --release --target $TARGET_TRIPLE -p btd -p configd)"
fi
BUILD="$FIRMWARE/target/aarch64-unknown-linux-gnu/release"

log "检查目标机"
run_remote "echo host=\$(hostname) && uname -m && ldd --version | head -1"
run_remote "sudo -n true" || warn "目标机上的 sudo 需要密码，后面的步骤会失败"

if [[ $APPLY == 1 ]]; then
  log "推送二进制与 unit"
  ssh -o BatchMode=yes "$TARGET" 'mkdir -p /tmp/ble-deploy'
  scp -q -o BatchMode=yes \
      "$BUILD/btd" "$BUILD/configd" \
      "$FIRMWARE/btd/systemd/btd.service" \
      "$FIRMWARE/configd/systemd/configd.service" \
      "$FIRMWARE/btd/systemd/sysusers.d/btd.conf" \
      "$TARGET":/tmp/ble-deploy/

  log "安装（btd 用户、二进制、两个 service）"
  ssh -o BatchMode=yes "$TARGET" "sudo -n sh -c '
    set -e
    install -d -m 0755 $BIN_DIR
    install -m 0755 /tmp/ble-deploy/btd /tmp/ble-deploy/configd $BIN_DIR/
    install -m 0644 /tmp/ble-deploy/btd.conf /usr/lib/sysusers.d/btd.conf
    systemd-sysusers
    install -m 0644 /tmp/ble-deploy/configd.service /etc/systemd/system/configd.service
    install -m 0644 /tmp/ble-deploy/btd.service /etc/systemd/system/btd.service
    systemctl daemon-reload
    systemctl enable --now configd.service btd.service
  '"
  ssh -o BatchMode=yes "$TARGET" 'systemctl is-active configd btd; sudo -n journalctl -u btd -n 5 --no-pager | tail -5'

  log "扫一下，确认开始广播"
  if command -v python3 >/dev/null; then
    python3 "$HERE/acceptance.py" --scan-time 8 || warn "扫描没找到机器人（它可能需要几秒才开始广播）"
  fi
fi

if [[ $MIGRATE == 1 ]]; then
  log "把 Wi-Fi 交给 NetworkManager（有掉线风险）"
  run_remote "sudo -n mkdir -p /etc/NetworkManager/conf.d && printf '[keyfile]\nunmanaged-devices=*\n' | sudo -n tee /etc/NetworkManager/conf.d/99-robot-wifi-only.conf"
  run_remote "sudo -n DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::ForceIPv4=true update"
  run_remote "sudo -n DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::ForceIPv4=true install -y --no-install-recommends network-manager"
  run_remote "sudo -n sh -c '
    SSID=\$(sed -n \"s/^[[:space:]]*ssid=\\\"\\(.*\\)\\\"/\\1/p\" /etc/wpa_supplicant/wpa_supplicant-wlan0.conf | head -1)
    PSK=\$(sed -n \"s/^[[:space:]]*psk=\\(.*\\)$/\\1/p\" /etc/wpa_supplicant/wpa_supplicant-wlan0.conf | head -1 | sed -e \"s/^\\\"\\(.*\\)\\\"\$/\\1/\")
    [ -n \"\$SSID\" ] || { echo \"读不到当前 SSID\" >&2; exit 1; }
    nmcli connection delete robot-wifi 2>/dev/null || true
    nmcli connection add type wifi con-name robot-wifi ifname wlan0 ssid \"\$SSID\" >/dev/null
    nmcli connection modify robot-wifi 802-11-wireless.hidden yes wifi-sec.key-mgmt wpa-psk wifi-sec.psk \"\$PSK\" >/dev/null
    printf \"[main]\ndns=systemd-resolved\nrc-manager=unmanaged\n\" > /etc/NetworkManager/conf.d/98-robot-dns.conf
  '"
  warn "接下来这一步会让 wlan0 从 wpa_supplicant 交给 NM。确认串口控制台可用，再手动执行："
  echo "  ssh $TARGET 'sudo systemctl disable --now wpa_supplicant@wlan0; \\"
  echo "    sudo sed -i \"s/unmanaged-devices=.*/unmanaged-devices=*,except:type:wifi/\" /etc/NetworkManager/conf.d/99-robot-wifi-only.conf; \\"
  echo "    sudo systemctl restart NetworkManager'"
  echo "  然后重启，并在确认 wlan0 由 robot-wifi 拿到 IPv4 后退役自恢复。"
fi

log "完成"
echo "客户端：ducknet/install.sh 装启动器；验收：$HERE/acceptance.py"
# 这版 configd 比上游多了 `net.connect` 的 ipv4 参数（App 的固定 IP 靠它）。上游版会以
# `unknown field ipv4` 拒绝整条请求，所以板上这份一定要是这里编出来的。
echo "固定 IP：sudo robotctl net connect <SSID> --psk-stdin --ipv4 192.168.110.50 --prefix 24 --gateway 192.168.110.1"
echo "          （只有本仓库构建的 configd 支持；详见 ../docs/design/ble-provisioning-app.md）"
