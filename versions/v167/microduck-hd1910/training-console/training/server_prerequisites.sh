#!/bin/bash
# Run only for an explicit deployment. Password (if needed by sudo) is stdin.
set -eu
md_workspace=${1:-~/microduck-training-ssh}
md_mode=${2:-server}
case "$md_workspace" in '~/'*) md_workspace="$HOME/${md_workspace#\~/}";; esac
md_updated=0
md_sudo_mode=
md_sudo_password=
trap 'unset md_sudo_password' EXIT
md_progress() { printf 'MICRODUCK_SETUP %s\n' "$1"; }
md_install() {
    command -v apt-get >/dev/null 2>&1 || { echo '自动准备系统组件需要Ubuntu/Debian的apt-get。' >&2; exit 41; }
    if [ "$(id -u)" = 0 ]; then
        md_sudo_mode=root
    elif [ -z "$md_sudo_mode" ]; then
        command -v sudo >/dev/null 2>&1 || { echo '自动安装缺少组件需要root或sudo权限。' >&2; exit 42; }
        if sudo -n true 2>/dev/null; then
            md_sudo_mode=cached
        else
            IFS= read -r md_sudo_password || true
            [ -n "$md_sudo_password" ] || { echo '缺少系统组件，当前账户需要sudo密码；可使用密码登录或root账户部署。' >&2; exit 43; }
            md_sudo_mode=password
        fi
    fi
    md_progress "正在一次性安装缺少的系统组件：$*"
    if [ "$md_updated" = 0 ]; then
        case "$md_sudo_mode" in
            root) env DEBIAN_FRONTEND=noninteractive apt-get update ;;
            cached) sudo -n env DEBIAN_FRONTEND=noninteractive apt-get update ;;
            password) printf '%s\n' "$md_sudo_password" | sudo -S -p '' env DEBIAN_FRONTEND=noninteractive apt-get update ;;
        esac
        md_updated=1
    fi
    case "$md_sudo_mode" in
        root) env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$@" ;;
        cached) sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$@" ;;
        password) printf '%s\n' "$md_sudo_password" | sudo -S -p '' env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$@" ;;
    esac
}
md_progress '正在检查Python、git、证书及已有uv…'
if ! command -v python3 >/dev/null 2>&1; then
    md_initial=(python3 python3-venv git ca-certificates)
    if [ "$md_mode" != wsl ]; then md_initial+=(libgomp1 libegl1 libgl1); fi
    md_install "${md_initial[@]}"
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || {
    echo '训练中控需要Python3.10+；请使用Ubuntu22.04/24.04或更新版本的镜像。' >&2; exit 44;
}
md_uv=
for md_candidate in "$(command -v uv || true)" "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" "$md_workspace/bootstrap/bin/uv"; do
    if [ -n "$md_candidate" ] && [ -x "$md_candidate" ] && "$md_candidate" --version >/dev/null 2>&1; then md_uv=$md_candidate; break; fi
done
md_packages=()
command -v git >/dev/null 2>&1 || md_packages+=(git)
[ -s /etc/ssl/certs/ca-certificates.crt ] || md_packages+=(ca-certificates)
if [ -z "$md_uv" ] && ! python3 -c 'import venv,ensurepip' >/dev/null 2>&1; then
    md_version=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
    md_packages+=("python${md_version}-venv" python3-venv)
fi
if [ "$md_mode" != wsl ]; then
    mapfile -t md_libraries < <(python3 -c 'from ctypes.util import find_library
for library,package in [("gomp","libgomp1"),("EGL","libegl1"),("GL","libgl1")]:
    if not find_library(library): print(package)')
    md_packages+=("${md_libraries[@]}")
fi
if [ "${#md_packages[@]}" -gt 0 ]; then md_install "${md_packages[@]}"; fi
command -v git >/dev/null 2>&1 || { echo 'git准备失败。' >&2; exit 45; }
if [ -z "$md_uv" ]; then
    python3 -c 'import venv,ensurepip' || { echo 'Python venv组件仍不可用。' >&2; exit 46; }
    md_progress '系统组件已就绪，接下来准备uv和固定版本训练环境…'
else
    md_progress '系统组件已就绪，将复用已有uv和训练环境…'
fi
