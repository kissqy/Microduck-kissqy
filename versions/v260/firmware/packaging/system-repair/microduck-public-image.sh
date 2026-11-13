#!/usr/bin/env bash
# Microduck/Radxa ZERO 3W public-image onboarding, file-level privacy cleanup.
# Commands: install | test | status | seal | --seal-now (internal)
# R5 adds a captive-portal HTTP/DNS discovery path, without touching robotd.
set -Eeuo pipefail
umask 077

PROGRAM='/usr/local/sbin/microduck-public-image'
PORTAL='/usr/local/libexec/microduck-setup-portal.py'
UNIT='/etc/systemd/system/microduck-setup.service'
# Historical keyfile path is retained so R5 updates existing R4 hotspot in place.
HOTSPOT_FILE='/etc/NetworkManager/system-connections/Microduck-Setup.nmconnection'
WIFI_DIR='/etc/NetworkManager/system-connections'
AP_NAME='Microduck-kissqy'
AP_PASSWORD='12345678'
AP_IP='10.42.0.1'
PORT='8088'
DEFAULT_USER='radxa'

log(){ printf '[Microduck] %s\n' "$*"; }
die(){ printf '[Microduck] 错误：%s\n' "$*" >&2; exit 1; }
need_root(){ [ "$(id -u)" -eq 0 ] || die '请使用 sudo bash ... 执行。'; }
need_cmd(){ command -v "$1" >/dev/null 2>&1 || die "缺少命令 $1。"; }

find_wifi_iface(){
  nmcli -t -f DEVICE,TYPE device status | awk -F: '$2=="wifi" {print $1; exit}'
}
check_environment(){
  need_cmd nmcli; need_cmd python3; need_cmd systemctl; need_cmd systemd-run
  need_cmd chpasswd; need_cmd ssh-keygen; need_cmd usermod
  [ -f /etc/os-release ] || die '不是标准 Linux 系统。'
  systemctl is-active --quiet NetworkManager.service || die 'NetworkManager 没有运行；脚本不会修改网络。'
  getent passwd "$DEFAULT_USER" >/dev/null || die "未找到账户 $DEFAULT_USER，停止以免误锁其他账户。"
  IFACE="$(find_wifi_iface)"
  [ -n "$IFACE" ] || die '未发现 NetworkManager 管理的 Wi-Fi 网卡。'
  if [ -r "/sys/class/net/$IFACE/address" ]; then :; else die "找不到无线网卡 $IFACE。"; fi
  local supports
  supports="$(nmcli -g WIFI-PROPERTIES.AP device show "$IFACE" 2>/dev/null | head -n1 || true)"
  if [ "$supports" = 'no' ]; then die "$IFACE 的驱动报告不支持 AP 热点，不能安全发布无 SSH 镜像。"; fi
  command -v dnsmasq >/dev/null 2>&1 || die '缺少 dnsmasq-base；请重新执行 install 自动安装依赖。'
  log "检测：NetworkManager 正常 / Wi-Fi $IFACE / AP 能力 ${supports:-未报告（需先实机验证）}。"
}

extra_accounts(){
  awk -F: '$3>=1000 && $3<60000 && $1!="nobody" && $1!="radxa" {print $1}' /etc/passwd
}
legacy_wifi_files(){
  local path
  for path in /etc/wpa_supplicant /etc/iwd /var/lib/iwd /etc/netplan /etc/network/interfaces /etc/network/interfaces.d; do
    [ -e "$path" ] || continue
    if [ -d "$path" ]; then
      grep -lREm1 '(^|[[:space:]])(ssid|psk|password):?[[:space:]]*[=:]' "$path" 2>/dev/null || true
      find "$path" -maxdepth 1 -type f \( -name '*.psk' -o -name '*.8021x' \) -print 2>/dev/null || true
    elif grep -qEi '(^|[[:space:]])(ssid|psk|password):?[[:space:]]*[=:]' "$path"; then
      printf '%s\n' "$path"
    fi
  done
}

wifi_uuids_to_remove(){
  local uuid type name
  while IFS=: read -r uuid type; do
    [ "$type" = '802-11-wireless' ] || [ "$type" = 'wifi' ] || continue
    name="$(nmcli -g connection.id connection show uuid "$uuid" 2>/dev/null || true)"
    [ "$name" = "$AP_NAME" ] && continue
    [ -n "$uuid" ] && printf '%s\n' "$uuid"
  done < <(nmcli -t -f UUID,TYPE connection show)
}

status(){
  check_environment
  log "热点配置：$([ -f "$HOTSPOT_FILE" ] && echo 已准备 || echo 未安装)"
  log "首次配网服务：$(systemctl is-enabled microduck-setup.service 2>/dev/null || echo 未启用)"
  log "当前 Wi-Fi：$(nmcli -t -f DEVICE,STATE device status | awk -F: -v w="$IFACE" '$1==w {print $2;exit}')（不展示 SSID）"
  local count others
  count="$(wifi_uuids_to_remove | wc -l)"; count="${count//[[:space:]]/}"
  log "需要在制作公开镜像时清除的 Wi-Fi 配置：${count} 个（不展示 SSID 和密码）"
  others="$(extra_accounts)"
  [ -z "$others" ] || log "其他用户账户（脚本不会删除）：$others"
  local legacy
  legacy="$(legacy_wifi_files)"
  [ -z "$legacy" ] || { log '检测到非 NetworkManager Wi-Fi 凭据；公开前需单独处理：'; printf '%s\n' "$legacy"; }
  log "首次配网页地址：http://${AP_IP}:${PORT}（需要手机先连 $AP_NAME）"
  log '自动配网提示：R5 支持 Android/iPhone/Windows 的 Captive Portal HTTP 检测；是否弹窗取决于手机系统。'
}

write_hotspot_profile(){
  local uuid
  mkdir -p "$WIFI_DIR"
  if [ -e "$HOTSPOT_FILE" ]; then
    [ -f "$HOTSPOT_FILE" ] || die '已有同名热点配置，但不是普通文件。'
    uuid="$(sed -n 's/^uuid=//p' "$HOTSPOT_FILE" | head -n1)"
    [ -n "$uuid" ] || die '现有热点配置缺少 UUID，禁止覆盖。'
  else
    uuid="$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)"
  fi
  cat >"$HOTSPOT_FILE" <<EOF
[connection]
id=$AP_NAME
uuid=$uuid
type=wifi
interface-name=$IFACE
autoconnect=false

[wifi]
mode=ap
ssid=$AP_NAME
security=802-11-wireless-security
band=bg

[wifi-security]
key-mgmt=wpa-psk
psk=$AP_PASSWORD

[ipv4]
method=shared
address1=$AP_IP/24

[ipv6]
method=disabled
EOF
  chown root:root "$HOTSPOT_FILE"
  chmod 600 "$HOTSPOT_FILE"
  nmcli connection load "$HOTSPOT_FILE" >/dev/null || die 'NetworkManager 拒绝热点配置。请查看 sudo journalctl -u NetworkManager。'
  log '热点配置已写入，但没有激活，也没有断开现有 Wi-Fi。'
}

# R5: Only during 'install', automatically install missing non-network-stack
# dependencies. Never reinstall/restart NetworkManager: current SSH depends on it.
install_dependencies(){
  need_cmd nmcli
  need_cmd systemctl
  systemctl is-active --quiet NetworkManager.service ||
    die 'NetworkManager 未运行；为保护当前网络，不自动修改网络管理方式。'

  local -a packages=()
  command -v python3 >/dev/null 2>&1    || packages+=(python3)
  command -v dnsmasq >/dev/null 2>&1    || packages+=(dnsmasq-base)
  command -v ssh-keygen >/dev/null 2>&1 || packages+=(openssh-client)
  if ! command -v chpasswd >/dev/null 2>&1 ||
     ! command -v usermod >/dev/null 2>&1; then
    packages+=(passwd)
  fi

  if [ "${#packages[@]}" -eq 0 ]; then
    log 'R5 依赖检查通过，均已安装；无需调用 apt。'
    return 0
  fi

  [ -x /usr/bin/apt-get ] ||
    die "缺少 ${packages[*]}，但没有 apt-get；此脚本只支持 Debian/Armbian 的 apt 环境。"
  [ -e /etc/debian_version ] ||
    die '当前不是 Debian/Armbian 系统，停止自动安装，以免影响网络。'

  log "R5 自动安装缺失依赖：${packages[*]}"
  log '安装过程需要已有的家庭 Wi-Fi/网络，不会主动切换热点或重启机器人服务。'
  if ! (
    export DEBIAN_FRONTEND=noninteractive
    export APT_LISTCHANGES_FRONTEND=none
    export NEEDRESTART_MODE=l
    /usr/bin/apt-get update &&
    /usr/bin/apt-get install -y --no-install-recommends "${packages[@]}"
  ); then
    die 'apt 自动安装失败：请检查 Zero 网络连接和软件源。未执行热点/隐私清理。'
  fi
  log '依赖自动安装完成，继续安装 Microduck 配网服务。'
}

install(){
  install_dependencies
  check_environment
  log 'Microduck Wi-Fi R10 boot-only'
  mkdir -p /usr/local/libexec /usr/local/sbin
  local origin
  origin="$(readlink -f -- "$0")"
  if [ "$origin" != "$PROGRAM" ]; then
    /usr/bin/install -o root -g root -m 700 "$origin" "$PROGRAM"
  fi
  # The portal is bundled below in this one-file installer.
  sed -n '/^#__PORTAL_BEGIN__$/,/^#__PORTAL_END__$/p' "$PROGRAM" | sed '1d;$d' >"$PORTAL"
  [ -s "$PORTAL" ] || die '安装脚本缺少嵌入式 Portal 代码。'
  chown root:root "$PORTAL"; chmod 700 "$PORTAL"
  local startup_module="$(dirname -- "$origin")/microduck_wifi_r7.py"
  [ -f "$startup_module" ] || startup_module=/usr/local/libexec/microduck_wifi_r7.py
  [ -f "$startup_module" ] || die "缺少 R7 热点启动模块。"
  if [ "$(readlink -f -- "$startup_module")" != /usr/local/libexec/microduck_wifi_r7.py ]; then
    /usr/bin/install -m 600 "$startup_module" /usr/local/libexec/microduck_wifi_r7.py
  fi
  # Remove only the exact old R8 notification components owned by this project.
  python3 - <<'REMOVE_R8'
import hashlib
from pathlib import Path
owned = {
 '/usr/local/libexec/microduck_wifi_events.py': 'c31ad55f443db1c7fa1cbe7febbaabb359228b65cb4b62e47ebfc0080500a185',
 '/etc/NetworkManager/dispatcher.d/90-microduck-hotspot': '33e6b289a97c531903c0e5d3c11c3b290fec3a83043efe9f41fe2d2727c91786',
}
for name, digest in owned.items():
    path = Path(name)
    if path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
        path.unlink()
REMOVE_R8
  python3 -m py_compile "$PORTAL" || die 'Portal Python 语法检查失败。'
  write_hotspot_profile
  cat >"$UNIT" <<EOF
[Unit]
Description=Microduck R10 boot-only saved-Wi-Fi check and setup portal
Wants=NetworkManager.service
After=NetworkManager.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 $PORTAL --serve auto
Restart=no
Environment=LC_ALL=C
NoNewPrivileges=no

[Install]
WantedBy=multi-user.target
EOF
  chmod 644 "$UNIT"
  systemctl daemon-reload
  systemctl enable microduck-setup.service >/dev/null
  mkdir -p /var/lib/microduck-wifi-setup
  chmod 700 /var/lib/microduck-wifi-setup
  touch /var/lib/microduck-wifi-setup/skip-until-sealed
  chmod 600 /var/lib/microduck-wifi-setup/skip-until-sealed
  log '安装完成：只启用下次开机的配网服务，当前 Wi-Fi / SSH / robotd 均不重启。'
  log '接下来先运行：sudo bash microduck-public-image.sh test（验证热点，然后自动恢复原 Wi-Fi）'
  log '测试通过后运行：sudo bash microduck-public-image.sh seal（清理并自动关机）'
}

test_hotspot(){
  check_environment
  [ -f "$PORTAL" ] && [ -f "$HOTSPOT_FILE" ] && [ -f "$UNIT" ] || die '请先执行 install。'
  [ ! -e /run/microduck-wifi-test-restore ] || die '检测到尚未结束的热点测试；请等待自动恢复。'
  [ "$(nmcli -g WIFI-PROPERTIES.AP device show "$IFACE" 2>/dev/null | head -n1 || true)" = 'yes' ] || die '驱动没有明确报告支持热点 AP 模式；先通过串口或实机确认。'
  local current uuid
  current="$(nmcli -g GENERAL.CONNECTION device show "$IFACE" 2>/dev/null | head -n1 || true)"
  [ -n "$current" ] && [ "$current" != '--' ] && [ "$current" != "$AP_NAME" ] || die '当前没有已连接家庭 Wi-Fi，不能自动恢复；请用串口测试。'
  uuid="$(nmcli -g connection.uuid connection show "$current" 2>/dev/null | head -n1 || true)"
  [[ "$uuid" =~ ^[a-fA-F0-9-]{36}$ ]] || die '无法确定当前家庭 Wi-Fi 连接 UUID，放弃临时切换。'
  printf '%s\n%s\n' "$IFACE" "$uuid" > /run/microduck-wifi-test-restore
  chmod 600 /run/microduck-wifi-test-restore
  rm -f /var/lib/microduck-wifi-setup/ap-verified
  # Arrange unconditional restore first. It runs even after SSH drops.
  systemd-run --quiet --unit=microduck-ap-restore --on-active=150s "$PROGRAM" --restore-test || die '无法创建自动恢复定时器。'
  systemctl stop microduck-setup.service
  systemd-run --quiet --unit=microduck-ap-test --on-active=5s "$PROGRAM" --test-now || die '测试启动失败；自动恢复任务仍会按时执行。'
  log '5 秒后临时切换为 Microduck-kissqy，当前 SSH 会暂时断开。'
  log '手机连接热点 Microduck-kissqy（密码 12345678）；多数手机会提示打开配网页面。'
  log '如未弹出，请手动访问 http://10.42.0.1:8088；也可尝试 http://10.42.0.1。'
  log '在网页点击“我已看到配网页面”，150 秒后系统自动恢复当前 Wi-Fi。'
  log '请不要在测试期间提交真正的家庭 Wi-Fi 信息。'
}
restore_test(){
  local iface uuid
  if [ -s /run/microduck-wifi-test-restore ]; then
    { IFS= read -r iface; IFS= read -r uuid; } < /run/microduck-wifi-test-restore
    systemctl stop microduck-ap-test.service 2>/dev/null || true
    nmcli --wait 40 connection up uuid "$uuid" ifname "$iface" >/dev/null 2>&1 || true
    rm -f /run/microduck-wifi-test-restore
    # If the test process was SIGTERM'ed by systemd, it did not run Python finally.
    # Only remove our own one-file dnsmasq rule, never user/network settings.
    local dns_file='/etc/NetworkManager/dnsmasq-shared.d/99-microduck-firstboot-captive.conf'
    # R4 marker deliberately retained in R5 to remove old DNS rule safely.
    if [ -f "$dns_file" ] && [ "$(cat "$dns_file")" = $'# Microduck First-Boot R4 captive DNS (only while Microduck-Setup AP is active)\naddress=/#/10.42.0.1' ]; then
      rm -f -- "$dns_file"
    fi
    systemctl start microduck-setup.service
  fi
}

preflight_seal(){
  check_environment
  [ -f "$PORTAL" ] && [ -f "$HOTSPOT_FILE" ] && [ -f "$UNIT" ] || die '尚未 install 完整配网服务。'
  systemctl is-enabled --quiet microduck-setup.service || die '首次配网服务未启用。'
  [ -f /var/lib/microduck-wifi-setup/ap-verified ] || die '还没有验证热点。请先执行 sudo bash microduck-public-image.sh test，手机打开网页点“确认”。'
  [ ! -e /run/microduck-wifi-test-restore ] || die '热点测试尚未恢复；等待 150 秒后再封存。'
  [ -z "$(extra_accounts)" ] || die '发现 radxa 以外的普通账户；请先人工清理或确认，防止其密码留在镜像中。'
  local legacy
  legacy="$(legacy_wifi_files)"
  [ -z "$legacy" ] || die "发现其他 Wi-Fi 配置；请先手工检查这些文件（仅显示路径）：\n$legacy"
  local keyfile
  for keyfile in /home/*/.aws/credentials /home/*/.config/gh/hosts.yml /home/*/.git-credentials \
        /home/*/.netrc /home/*/.npmrc /home/*/.pypirc /home/*/.config/rclone/rclone.conf \
        /home/*/.cache/huggingface/token /root/.aws/credentials /root/.config/gh/hosts.yml \
        /root/.git-credentials /root/.netrc /root/.npmrc /root/.pypirc; do
    [ -e "$keyfile" ] && die "检测到第三方认证信息 $keyfile。为避免误删，此次拒绝自动封存；请先删除或迁移后重新检查。"
  done
  # This is intentionally scoped to the expected user; the image must not clone other private users.
  log '预检通过：将清除 Wi-Fi/SSH 私钥/设备密钥/常见历史日志，并锁定旧 radxa 密码。'
  log '注意：这不能保证原始镜像已删除的数据扇区中不存在历史隐私信息。'
}

seal(){
  preflight_seal
  printf '\n严重提醒：15 秒后清理当前机器并自动关机；当前 SSH 会断开。\n'
  printf '该操作只能对准备公开的镜像副本执行，不能对你日常使用的鸭子执行。\n'
  printf '确认你已经单独备份原始镜像，并在串口/显示器或实机验证过 Wi-Fi AP 能力。\n'
  read -r -p '确认请输入 PUBLISH：' reply
  [ "$reply" = 'PUBLISH' ] || die '未确认，不执行任何清理。'
  systemctl is-active --quiet microduck-image-seal.timer 2>/dev/null && die '封存任务已经安排。'
  systemd-run --quiet --unit=microduck-image-seal --on-active=15s "$PROGRAM" --seal-now
  log '已安排 15 秒后封存并关机。请不要再继续操作网络。'
  log '待 Zero 完全断电，取出存储介质，再在电脑上备份成公开镜像。'
}

remove_wifi_profiles(){
  local uuid
  while IFS= read -r uuid; do
    [ -n "$uuid" ] || continue
    nmcli connection delete uuid "$uuid" >/dev/null 2>&1 || true
  done < <(wifi_uuids_to_remove)
  # Recheck file residue in typical NetworkManager profile directories.
  local f
  shopt -s nullglob
  for f in "$WIFI_DIR"/*.nmconnection "$WIFI_DIR"/*wifi* "$WIFI_DIR"/*Wi-Fi*; do
    [ -f "$f" ] || continue
    [ "$f" = "$HOTSPOT_FILE" ] && continue
    if grep -Eq '(^type=(wifi|802-11-wireless)$|^\[wifi\]$|^\[802-11-wireless\]$)' "$f"; then
      rm -f -- "$f"
    fi
  done
  shopt -u nullglob
  nmcli connection reload >/dev/null 2>&1 || true
}

remove_private_history(){
  local home
  for home in /root /home/*; do
    [ -d "$home" ] || continue
    rm -rf -- "$home/.ssh"
    rm -f -- "$home/.bash_history" "$home/.zsh_history" "$home/.python_history" \
      "$home/.lesshst" "$home/.wget-hsts" "$home/.mysql_history" "$home/.sqlite_history" \
      "$home/.viminfo" "$home/.git-credentials" "$home/.netrc"
    # Never delete arbitrary .config/.cache directories: robot configs and training assets may live there.
  done
  rm -f /etc/ssh/ssh_host_* /etc/ssh/ssh_host_*.pub
  rm -f /etc/shadow- /etc/gshadow- /etc/shadow.bak /etc/gshadow.bak /var/backups/shadow.bak /var/backups/gshadow.bak
  # These backup files may contain old Linux password hashes.
  rm -f /var/lib/NetworkManager/secret_key /var/lib/NetworkManager/seen-bssids /var/lib/NetworkManager/timestamps
  find /var/lib/NetworkManager -maxdepth 1 -type f -name '*.lease' -delete 2>/dev/null || true
  if command -v journalctl >/dev/null 2>&1; then
    journalctl --rotate >/dev/null 2>&1 || true
    journalctl --vacuum-time=1s >/dev/null 2>&1 || true
  fi
  find /var/log -maxdepth 1 -type f \( -name 'auth.log*' -o -name 'syslog*' -o -name 'kern.log*' \
     -o -name 'daemon.log*' -o -name 'user.log*' \) -delete 2>/dev/null || true
  for f in /var/log/wtmp /var/log/btmp /var/log/lastlog; do [ -f "$f" ] && : > "$f"; done
  # Preserve all firmware, installed models, calibration and systemd service settings.
  rm -f /var/lib/microduck-wifi-setup/ap-verified /var/lib/microduck-wifi-setup/skip-until-sealed /var/lib/microduck-wifi-setup/provisioned
  truncate -s 0 /etc/machine-id
  [ -L /var/lib/dbus/machine-id ] || rm -f /var/lib/dbus/machine-id
}

seal_now(){
  # Runs as a systemd transient unit, detached from the interactive SSH session.
  log '开始执行公开镜像封存。'
  systemctl stop microduck-setup.service
  trap 'log "封存中遇到问题；仍将尝试关机。"; /usr/sbin/shutdown -h now || systemctl poweroff || true' ERR
  systemctl disable ssh.service ssh.socket 2>/dev/null || true
  # Stop interactive logins before purging their history; does not stop robotd.
  systemctl stop ssh.socket ssh.service 2>/dev/null || true
  # Replace old password hashes rather than merely prefixing the original hash with !.
  usermod -p '!' "$DEFAULT_USER"
  usermod -p '!' root
  remove_wifi_profiles
  remove_private_history
  sync
  log '封存完成；立即关机。新镜像首次开机必须先走 Microduck-kissqy，设置新的系统密码。'
  /usr/sbin/shutdown -h now || systemctl poweroff
}

usage(){
  cat <<EOF
Microduck Zero 3W 公开镜像准备脚本 R8
用法：sudo bash $(basename "$0") install | test | status | seal
  install  自动安装缺失的基础依赖，再安装首次配网热点；不主动切断当前 SSH
  test     临时测试热点 150 秒并自动恢复当前 Wi-Fi；手机确认后才允许 seal
  status   显示当前配网服务状态 / 脱敏配置检查
  seal     15 秒后清理当前镜像副本个人信息并关机（危险）
默认热点：$AP_NAME  密码：$AP_PASSWORD
配网地址：http://$AP_IP:$PORT（手机支持时自动弹出）
EOF
}

case "${1:-help}" in
  install) need_root;install;;
  status) need_root;status;;
  test) need_root;test_hotspot;;
  --test-now) need_root;IFACE="$(find_wifi_iface)";exec /usr/bin/python3 "$PORTAL" --serve --test "$IFACE";;
  --restore-test) need_root;restore_test;;
  seal) need_root;seal;;
  --seal-now) need_root;seal_now;;
  help|-h|--help)usage;;
  *)usage;exit 2;;
esac
exit 0

: <<'__MICRODUCK_PORTAL_PAYLOAD__'
#__PORTAL_BEGIN__
#!/usr/bin/env python3
"""Microduck R5 first-boot Wi-Fi onboarding, with captive portal discovery."""
from __future__ import annotations
import argparse
import base64
import html
import os
import pathlib
import secrets
import subprocess
import threading
import time
import uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

AP_NAME = 'Microduck-kissqy'
SETUP_IP = '10.42.0.1'
PORT = 8088
CAPTIVE_HTTP_PORT = 80
# NetworkManager's own per-shared-connection dnsmasq reads this directory.
# No second DNS/DHCP process is ever started.
DNS_SHARED_DIR = pathlib.Path('/etc/NetworkManager/dnsmasq-shared.d')
DNS_CAPTIVE_FILE = DNS_SHARED_DIR / '99-microduck-firstboot-captive.conf'
DNS_CAPTIVE_RULE = ('# Microduck First-Boot R4 captive DNS (only while Microduck-Setup AP is active)\n'
                    'address=/#/10.42.0.1\n')
HOME_ID = 'Microduck-Home'
WIFI_PATH = pathlib.Path('/etc/NetworkManager/system-connections/Microduck-Home.nmconnection')
LOCK = threading.Lock()
STATE = {'busy': False, 'error': '', 'success': False}
TOKEN = secrets.token_urlsafe(24)
TEST_MODE = False
VERIFIED_PATH = pathlib.Path('/var/lib/microduck-wifi-setup/ap-verified')
STAGING_PATH = VERIFIED_PATH.parent / 'skip-until-sealed'
PROVISIONED_PATH = VERIFIED_PATH.parent / 'provisioned'

# kissqy outdoor photo from docs/assets/showcase/outdoor-07-thumb.webp; embedded for offline onboarding.
# A single embedded WebP avoids extra files, fonts, CDNs and system-package changes.
def load_page_artwork(encoded):
    """Optional page decoration must never prevent network startup."""
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        print('[Microduck] 配网页面插图无法加载，已跳过；继续启动热点服务。', flush=True)
        return b''


MASCOT_WEBP = load_page_artwork(
    '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'
    'FqkR2mDL4xxJScvbv2EC0/mPnTXAACIzfAAA'
)
OPEN_SOURCE_URL = 'https://github.com/kissqy/Microduck-kissqy'


def run(*argv: str, wait: int = 30, check: bool = False, input_data: str | None = None):
    return subprocess.run(list(argv), input=input_data, text=True, capture_output=True,
                          timeout=wait, check=check)







def enable_captive_dns():
    """Prepare DNS before activating AP; no NM/dnsmasq service restarts.

    This file is dynamically present during the setup hotspot, not during
    ordinary home Wi-Fi usage. NetworkManager loads it into its *own* dnsmasq
    instance on the next shared-connection activation.
    """
    DNS_SHARED_DIR.mkdir(parents=True, exist_ok=True)
    # Older interrupted writes left visible .new files that dnsmasq loads.
    for stale in DNS_SHARED_DIR.glob(DNS_CAPTIVE_FILE.name + '.*.new'):
        stale.unlink(missing_ok=True)
    if DNS_CAPTIVE_FILE.exists():
        if DNS_CAPTIVE_FILE.read_text(encoding='utf-8') != DNS_CAPTIVE_RULE:
            raise RuntimeError('配网 DNS 配置文件已被修改，拒绝覆盖：' + str(DNS_CAPTIVE_FILE))
        return
    temp = DNS_CAPTIVE_FILE.with_name('.' + DNS_CAPTIVE_FILE.name + f'.{os.getpid()}.{secrets.token_hex(4)}.new')
    fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        # Configuration has no secrets; the NM-managed dnsmasq must be able to read it.
        os.chmod(temp, 0o644)
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            file.write(DNS_CAPTIVE_RULE)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, DNS_CAPTIVE_FILE)
    finally:
        try: temp.unlink(missing_ok=True)
        except OSError: pass
    # Validate full shared-dnsmasq configuration *without starting a DNS server*.
    try:
        result = run('dnsmasq', '--test', '--conf-file=/dev/null',
                     '--conf-dir=' + str(DNS_SHARED_DIR), wait=8)
    except (OSError, subprocess.TimeoutExpired) as error:
        disable_captive_dns()
        raise RuntimeError('验证热点 DNS 配置失败：' + str(error)) from error
    if result.returncode != 0:
        disable_captive_dns()
        raise RuntimeError('热点 DNS 配置不兼容：' + result.stderr[-300:])


def disable_captive_dns():
    """Never remove a different user's dnsmasq rules."""
    try:
        if DNS_CAPTIVE_FILE.read_text(encoding='utf-8') == DNS_CAPTIVE_RULE:
            DNS_CAPTIVE_FILE.unlink()
    except FileNotFoundError:
        return


def show_hotspot_with_captive():
    # Captive Portal is best-effort. A DNS parsing issue must NEVER prevent
    # the already-working R3 manual setup hotspot from becoming available.
    captive_ready = False
    try:
        enable_captive_dns()
        captive_ready = True
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'[Microduck] 自动配网 DNS 不可用：{error}；仍使用原 R3 手动配网地址。', flush=True)
    try:
        show_hotspot()
    except Exception:
        if captive_ready:
            disable_captive_dns()
        raise


def show_hotspot():
    activate_hotspot()


def secure_profile(ssid: str, password: str) -> str:
    # Reject INI delimiters/control characters rather than allow keyfile injection.
    if not 1 <= len(ssid.encode('utf-8')) <= 32 or any(c in '\r\n\0' for c in ssid):
        raise ValueError('Wi-Fi 名称长度需为 1–32 字节，且不能有换行')
    if not 8 <= len(password.encode('utf-8')) <= 63 or any(c in '\r\n\0' for c in password):
        raise ValueError('仅支持 WPA2/WPA3 家庭 Wi-Fi，密码长度应为 8–63 字符')
    if any(ord(c) < 32 or ord(c) == 127 for c in ssid + password) or '\\' in ssid + password:
        raise ValueError('当前配网版本不支持控制字符或反斜杠')
    if ssid.startswith(('#', ';')):
        raise ValueError('当前配网版本不支持以 # 或 ; 开头的 Wi-Fi 名称')
    if password.startswith(('#', ';')):
        raise ValueError('当前配网版本不支持以 # 或 ; 开头的 Wi-Fi 密码')
    identifier = str(uuid.uuid4())
    # Value is written into an owner-only keyfile; password never appears in command line.
    content = (f'[connection]\nid={HOME_ID}\nuuid={identifier}\ntype=wifi\n'
               f'interface-name={INTERFACE}\nautoconnect=true\nautoconnect-priority=100\n\n'
               f'[wifi]\nmode=infrastructure\nssid={ssid}\nsecurity=802-11-wireless-security\n\n'
               f'[wifi-security]\nkey-mgmt=wpa-psk\npsk={password}\n\n'
               '[ipv4]\nmethod=auto\n\n[ipv6]\nmethod=auto\n')
    tmp = WIFI_PATH.with_suffix('.new')
    tmp.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, WIFI_PATH)
    os.chmod(WIFI_PATH, 0o600)
    return identifier


def provision(ssid: str, password: str, system_password: str, server: ThreadingHTTPServer):
    try:
        # Update OS password via stdin, never as an argv argument. Old hash was erased by seal.
        change = run('chpasswd', input_data='radxa:' + system_password + '\n', wait=15)
        if change.returncode != 0:
            raise RuntimeError('无法更新 Linux 用户密码')
        existing = run('nmcli', '-g', 'connection.uuid', 'connection', 'show', HOME_ID, wait=6)
        if existing.returncode == 0:
            run('nmcli', 'connection', 'delete', HOME_ID, wait=12)
        identity = secure_profile(ssid, password)
        result = run('nmcli', 'connection', 'load', str(WIFI_PATH), wait=12)
        if result.returncode != 0:
            raise RuntimeError('NetworkManager 不接受新 Wi-Fi 配置')
        # HTTP response has already returned to the phone; switching will drop AP.
        time.sleep(3)
        result = run('nmcli', '--wait', '35', 'connection', 'up', 'uuid', identity,
                     'ifname', INTERFACE, wait=40)
        if result.returncode != 0 or not home_ready():
            raise RuntimeError('家庭 Wi-Fi 连接失败；请确认网络名称、2.4/5GHz 兼容性和密码')
        # Unique SSH host keys are generated after successful first provisioning.
        keys = run('ssh-keygen', '-A', wait=15)
        if keys.returncode != 0:
            raise RuntimeError('SSH Host Key 生成失败，请使用本地串口处理')
        enabled = run('systemctl', 'enable', 'ssh.service', wait=12)
        started = run('systemctl', 'start', 'ssh.service', wait=15)
        if enabled.returncode != 0 or started.returncode != 0:
            raise RuntimeError('SSH 服务启动失败；已准备恢复配网热点')
        PROVISIONED_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROVISIONED_PATH.write_text('configured\n', encoding='utf-8')
        os.chmod(PROVISIONED_PATH, 0o600)
        with LOCK:
            STATE.update(busy=False, error='', success=True)
        time.sleep(3)
        server.shutdown()
    except Exception as error:
        run('nmcli', 'connection', 'delete', HOME_ID, wait=12)
        try: WIFI_PATH.unlink(missing_ok=True)
        except OSError: pass
        try: show_hotspot()
        except Exception: pass
        with LOCK:
            STATE.update(busy=False, error=str(error), success=False)


class Handler(BaseHTTPRequestHandler):
    server_version = 'Microduck-kissqy'
    def log_message(self, fmt, *args):
        # Do not log Wi-Fi names, passwords or form bodies.
        return

    def send_html(self, content, status=200):
        body = content.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def page(self, text='', color='#b57b17', testing=False, verified=False):
        # R5 adds discovery separately. This form and its /connect + /verify semantics remain R3.
        with LOCK:
            busy, error, done = STATE['busy'], STATE['error'], STATE['success']
        if done and not testing:
            text = '连接成功。Microduck 已进入家庭 Wi-Fi 网络。'
        elif error and not testing:
            text = '连接未成功：' + error + '。请重新输入 Wi-Fi 信息。'
        notice = ('<p class="notice" role="status">' + html.escape(text) + '</p>') if text else ''
        if testing:
            intro = ('热点测试：手机如自动弹出配网窗口，可直接使用；如果未弹出，'
                     '手动打开 10.42.0.1:8088。看到鸭鸭后点击下方确认。')
            content = ('' if verified else '''<form method="post" action="/verify">
              <input type="hidden" name="token" value="'''+TOKEN+'''">
              <button type="submit">我已看到配网页面，确认测试通过</button>
            </form>''') + '''<p class="hint">测试模式不会修改家庭 Wi-Fi 和系统密码。
                约 150 秒后会自动恢复原来的家庭 Wi-Fi。</p>'''
        else:
            intro = '欢迎使用 kissqy 的 Microduck 飞特版。在这里设置 Wi-Fi，让鸭鸭连接你的网络。'
            if done:
                content = '<p class="success">设置完成，可以返回家庭 Wi-Fi 网络继续使用鸭鸭。</p>'
            else:
                content = '''<form method="post" action="/connect" autocomplete="off">
                  <input type="hidden" name="token" value="'''+TOKEN+'''">
                  <label for="wifi-ssid">Wi-Fi 名称（SSID）
                    <input id="wifi-ssid" name="ssid" required maxlength="32" autocomplete="off"
                      placeholder="请输入家庭 Wi-Fi 名称">
                  </label>
                  <label for="wifi-pass">Wi-Fi 密码
                    <input id="wifi-pass" name="password" type="password" required minlength="8"
                      autocomplete="off" placeholder="请输入家庭 Wi-Fi 密码">
                  </label>
                  <label for="linux-pass">新的 radxa 系统登录密码（至少 6 位）
                    <input id="linux-pass" name="system_password" type="password" required minlength="6" maxlength="128"
                      autocomplete="new-password" placeholder="设置新的 Linux 登录密码">
                  </label>
                  <button type="submit" '''+('disabled' if busy else '')+'''>保存并连接家庭 Wi-Fi →</button>
                </form>'''
            content += '''<p class="hint">提交后热点会暂时断开。如 Wi-Fi 密码有误，约 40 秒后
                重新连接 Microduck-kissqy 并刷新页面。</p>
                <p class="hint">安全提示：本热点使用公开初始密码，请在安全环境中进行首次配网。</p>'''
        return '''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#fff8ee">
  <title>kissqy · Microduck 重新配网</title>
  <style>
    :root { color-scheme: light; font-family: system-ui,-apple-system,"Microsoft YaHei",sans-serif;
            color:#4c3528; background:#fff8ee; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh;
      background:radial-gradient(circle at 22% 27%,#ffe3bf 0,transparent 40%),
                 linear-gradient(145deg,#fffdf8 0%,#fff0df 100%); }
    .shell { max-width:1160px; margin:0 auto; padding:20px 24px 34px; }
    header { display:flex; justify-content:space-between; align-items:center;
             flex-wrap:wrap; gap:9px; padding:6px 4px 18px; }
    .brand { color:#df5b20; font-size:34px; font-weight:800; letter-spacing:-.8px; line-height:1.12; }
    .brand i { font-style:normal; display:inline-block; margin-right:6px; }
    .brand small { display:block; margin:5px 0 0 43px; font-weight:500;
                   font-size:12px; color:#8a7565; letter-spacing:.5px; }
    .slogan { font-size:15px; font-weight:600; color:#8c705b; }
    .layout { display:grid; grid-template-columns:minmax(0, 1fr) minmax(350px, 1.04fr);
              align-items:center; gap:24px; }
    .mascot { display:flex; flex-direction:column; justify-content:center; align-items:center;
              margin:0; padding:0 2px 0 0; }
    .mascot img { width:100%; height:auto; max-width:600px; object-fit:contain;
                  border-radius:24px; user-select:none; box-shadow:0 16px 42px rgba(169,89,33,.12); }
    .mascot figcaption { margin:12px 0 10px; color:#8c705b; font-size:13px; font-weight:600; }
    .panel { background:rgba(255,255,255,.93); border:1px solid #f0ddc6;
             border-radius:28px; padding:33px 34px 24px;
             box-shadow:0 18px 55px rgba(169,89,33,.09); }
    h1 { margin:0 0 12px; font-size:clamp(23px, 2.7vw, 34px); letter-spacing:-.4px; }
    h1 span { color:#df5b20; }
    .intro { margin:0 0 21px; color:#8b7564; line-height:1.75; font-size:14px; }
    label { display:block; color:#604b3c; font-size:14px; font-weight:700;
            margin:13px 0; }
    input:not([type=hidden]) { display:block; width:100%; margin-top:7px;
            padding:13px 14px; border-radius:11px; background:#fff9f1;
            border:1px solid #e9d7c1; color:#4c3528; font:inherit; font-weight:400;
            outline-offset:2px; }
    input:focus-visible { border-color:#e3753e; outline:2px solid #ffdab8; }
    input::placeholder { color:#b09b89; }
    button { width:100%; margin-top:15px; border:0; border-radius:13px;
             background:linear-gradient(90deg,#dd5b20,#ec7534); color:white;
             font:700 17px system-ui,"Microsoft YaHei",sans-serif; padding:15px 12px;
             cursor:pointer; box-shadow:0 10px 25px rgba(222,91,32,.16); }
    button:disabled { background:#bba58e; box-shadow:none; cursor:wait; }
    .notice,.success { line-height:1.6; padding:11px 14px; border-radius:10px;
                       background:#fef6e6; color:#9a6000; overflow-wrap:anywhere; }
    .success { background:#effbef; color:#23642f; }
    .hint { font-size:12px; color:#9b8471; line-height:1.75; margin:12px 0 0; }
    .hotspot { text-align:center; color:#947963; font-size:13px; margin:17px 0; }
    .hotspot strong { color:#c35b29; }
    .github { margin-top:14px; border-radius:16px; padding:15px 16px; background:#fff2e1;
              border:1px solid #efd9bf; }
    .github .title { font-weight:800; margin-bottom:5px; font-size:14px; }
    .github a { display:block; color:#b85325; overflow-wrap:anywhere;
                word-break:break-word; font-size:13px; line-height:1.6; }
    .github small { display:block; font-size:12px; color:#9a7b62; margin-top:3px; }
    .foot { text-align:center; font-size:12px; color:#a58b72; margin:14px 0 0; }
    @media (max-width:780px) {
      .shell { padding:14px 13px 30px; }
      header { padding:2px 5px 12px; }
      .brand { font-size:25px; }
      .slogan { display:none; }
      .layout { grid-template-columns:1fr; gap:0; }
      .mascot { margin:0 auto 3px; width:100%; max-width:600px; }
      .mascot img { height:auto; width:100%; max-width:100%; border-radius:18px; }
      .panel { padding:22px 19px 19px; border-radius:21px; }
      h1 { font-size:24px; }
    }
    @media (prefers-reduced-motion:reduce) { * { scroll-behavior:auto!important; } }
  </style>
</head>
<body>
<div class="shell">
  <header>
    <div class="brand"><i aria-hidden="true">🦆</i>kissqy
      <small>Microduck 飞特版 · 桌面机器人</small></div>
    <div class="slogan">让鸭鸭，走进生活。</div>
  </header>
  <div class="layout">
    <figure class="mascot"><img src="/mascot.webp" width="1040" height="585"
      alt="四只 Microduck 小鸭，kissqy 开源仓库，一键系统，轻松配网" decoding="async">
      <figcaption>kissqy 开源仓库 · 一键系统 · 轻松配网</figcaption></figure>
    <main class="panel">
      <h1>连接你的 <span>kissqy 小鸭</span></h1>
      <p class="intro">''' + intro + '''</p>
      ''' + notice + content + '''
      <p class="hotspot">连接热点后通常会自动提示配置；未弹出请打开：<strong>10.42.0.1:8088</strong></p>
      <div class="github">
        <div class="title">✦ kissqy · 源码与复刻教程</div>
        <a href="https://github.com/kissqy/Microduck-kissqy" target="_blank"
          rel="noopener noreferrer">https://github.com/kissqy/Microduck-kissqy</a>
        <small>欢迎 Star ★ · 首次配网时无需访问互联网即可查看本页面。</small>
      </div>
    </main>
  </div>
  <div class="foot">kissqy · Microduck 飞特版</div>
</div>
</body></html>'''

    def send_mascot(self):
        self.send_response(200)
        self.send_header('Content-Type', 'image/webp')
        self.send_header('Content-Length', str(len(MASCOT_WEBP)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(MASCOT_WEBP)

    def do_GET(self):
        if self.path == '/mascot.webp':
            return self.send_mascot()
        if self.path not in ('/', '/status'):
            return self.send_html('Not found', 404)
        self.send_html(self.page(testing=TEST_MODE))

    def do_POST(self):
        if TEST_MODE:
            if self.path != '/verify': return self.send_html('Test mode only', 403)
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size < 1024: return self.send_html('Invalid request',400)
            data = parse_qs(self.rfile.read(size).decode('utf-8'))
            if data.get('token',[''])[0] != TOKEN: return self.send_html('Invalid form',403)
            VERIFIED_PATH.parent.mkdir(parents=True,exist_ok=True)
            VERIFIED_PATH.write_text('AP + DHCP + HTTP page confirmed; captive popup OS-dependent\n',encoding='utf-8')
            os.chmod(VERIFIED_PATH,0o600)
            return self.send_html(self.page('测试通过！等待约 150 秒恢复原来的家庭 Wi-Fi 后，再通过 SSH 执行 seal。', testing=True, verified=True))
        if self.path != '/connect' or self.headers.get_content_type() != 'application/x-www-form-urlencoded':
            return self.send_html('Bad request', 400)
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self.send_html('Invalid content length', 400)
        if not 0 < size <= 4096:
            return self.send_html('Form too large', 413)
        values = parse_qs(self.rfile.read(size).decode('utf-8', errors='strict'),keep_blank_values=True)
        if values.get('token', [''])[0] != TOKEN:
            return self.send_html(self.page('页面已过期，请重新刷新。'), 403)
        ssid, password, sys_pwd = (values.get(k, [''])[0] for k in ('ssid', 'password', 'system_password'))
        try:
            # Do not accept newline/control chars in the password passed to chpasswd.
            if not 6 <= len(sys_pwd) <= 128 or any(ord(c) < 32 or ord(c) == 127 for c in sys_pwd):
                raise ValueError('新系统密码必须为 6–128 位，不得包含控制字符')
            # validate before accepting. No profiles written until worker starts.
            if not 1 <= len(ssid.encode('utf-8')) <= 32 or not 8 <= len(password.encode('utf-8')) <= 63:
                raise ValueError('SSID 或 Wi-Fi 密码长度不正确')
            if any(ord(c)<32 or ord(c)==127 for c in ssid+password) or '\\' in ssid+password:
                raise ValueError('Wi-Fi 名称或密码含非法字符')
            if ssid.startswith(('#', ';')) or password.startswith(('#', ';')):
                raise ValueError('暂不支持以 # 或 ; 开头的名称/密码')
            with LOCK:
                if STATE.get('closing'):
                    return self.send_html(self.page('网络已切换，请稍后重新连接。'), 503)
                if STATE['busy']:
                    return self.send_html(self.page('正在连接，稍后刷新即可。'))
                STATE.update(busy=True,error='')
            threading.Thread(target=provision,args=(ssid,password,sys_pwd,self.server),daemon=True).start()
            return self.send_html(self.page('已收到配置，约 3 秒后尝试家庭 Wi-Fi。热点断开是正常的。'))
        except (ValueError, UnicodeError) as error:
            return self.send_html(self.page(str(error)), 400)


class CaptiveRedirectHandler(BaseHTTPRequestHandler):
    """HTTP connectivity probes must receive a *redirect*, not internet success.

    Android (generate_204), iOS (hotspot-detect), and Windows (connecttest)
    each send HTTP checks. They get a 302 to the actual local R3/R5 portal.
    HTTPS is never intercepted and there is deliberately no TLS spoofing.
    """
    server_version = 'Microduck-Captive-R5'

    def log_message(self, fmt, *args):
        # Do not log arbitrary domains or HTTP probe paths.
        return

    def redirect(self):
        self.send_response(302)
        self.send_header('Location', f'http://{SETUP_IP}:{PORT}/')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Content-Length', '0')
        self.send_header('Connection', 'close')
        self.end_headers()

    def do_GET(self):
        self.redirect()

    def do_HEAD(self):
        self.redirect()

    def do_POST(self):
        self.redirect()


def serve_setup_portal(testing=False):
    """Serve explicit setup requests; no network monitoring or AP recovery loop."""
    global TOKEN
    with LOCK:
        STATE.update(busy=False, error='', success=False, closing=False)
        TOKEN = secrets.token_urlsafe(24)
    server = None
    redirect_server = None
    try:
        server = ThreadingHTTPServer((SETUP_IP, PORT), Handler)
        try:
            redirect_server = ThreadingHTTPServer((SETUP_IP, CAPTIVE_HTTP_PORT), CaptiveRedirectHandler)
            threading.Thread(target=redirect_server.serve_forever,
                             kwargs={'poll_interval': .3}, daemon=True,
                             name='microduck-captive-http80').start()
        except OSError as error:
            print(f'[Microduck] HTTP 80 自动弹窗入口不可用：{error}；配网 8088 仍可使用。', flush=True)
        server.serve_forever(poll_interval=.3)
    finally:
        if redirect_server is not None:
            redirect_server.shutdown()
            redirect_server.server_close()
        if server is not None:
            server.server_close()
        disable_captive_dns()


def main():
    global INTERFACE, TEST_MODE
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve',action='store_true')
    parser.add_argument('--test',action='store_true')
    parser.add_argument('interface')
    args = parser.parse_args()
    INTERFACE = args.interface
    TEST_MODE = args.test
    if TEST_MODE:
        show_hotspot_with_captive()
        serve_setup_portal(testing=True)
        return
    _wifi_startup_boot.run_boot(serve_setup_portal)

# R10 reuses the existing provisioning form and AP I/O, with one boot decision.
from microduck_wifi_r7 import install as _install_wifi_startup
_install_wifi_startup(globals())

if __name__ == '__main__':
    main()
#__PORTAL_END__
__MICRODUCK_PORTAL_PAYLOAD__
