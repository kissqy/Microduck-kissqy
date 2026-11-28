#!/usr/bin/env bash
# 安装 Microduck 蓝牙配网（Linux 桌面）。
#
#   ./install.sh                    # 默认装到 ~/.local
#   ./install.sh --venv /path/venv  # 指定 venv
#   ./install.sh --uninstall        # 卸载（保留源码）
#
# 只写三处：venv、~/.local/bin/ducknet、~/.local/share/applications/ducknet.desktop。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
VENV="${DUCKNET_VENV:-$HOME/.local/share/ducknet/venv}"
BIN_DIR="${HOME}/.local/bin"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
WRAPPER="${BIN_DIR}/ducknet"
DESKTOP="${APPS_DIR}/ducknet.desktop"

UNINSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv) VENV="$2"; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help)
      sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

log() { printf '\033[1m== %s\033[0m\n' "$*"; }
warn() { printf '\033[33m[warn]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[err]\033[0m %s\n' "$*" >&2; exit 1; }

if [[ "$UNINSTALL" == 1 ]]; then
  log "卸载"
  rm -f "$WRAPPER" "$DESKTOP"
  if [[ -d "$VENV" && "$VENV" == "$HOME/.local/share/ducknet/venv" ]]; then
    rm -rf "$VENV"
    rmdir "$(dirname "$VENV")" 2>/dev/null || true
  fi
  command -v update-desktop-database >/dev/null && update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
  echo "已删除启动器与桌面入口。源码仍在：$HERE"
  exit 0
fi

command -v "$PYTHON" >/dev/null || die "找不到 $PYTHON"
"$PYTHON" - <<'PY' || die "需要 Python 3.10 或更新版本"
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY

log "Python 环境：$VENV"
if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON" -m venv "$VENV" || die "创建 venv 失败；Debian/Ubuntu 可能需要先装 python3-venv"
else
  echo "已存在，复用"
fi

if ! "$VENV/bin/python" -c 'import pip' >/dev/null 2>&1; then
  echo "venv 里没有 pip，尝试 ensurepip"
  "$VENV/bin/python" -m ensurepip --upgrade >/dev/null 2>&1 || true
fi

log "安装依赖"
if ! "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --timeout 60 --retries 2 -r "$HERE/requirements.txt"; then
  warn "pip 安装失败。若是离线环境，可先在有网机器上装好 bleak 再拷贝 venv。"
  warn "演示模式（--demo）不依赖 bleak，仍可使用。"
fi

log "安装启动器：$WRAPPER"
mkdir -p "$BIN_DIR"
cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
exec "$VENV/bin/python" "$HERE/app.py" "\$@"
EOF
chmod +x "$WRAPPER"

log "安装桌面入口：$DESKTOP"
mkdir -p "$APPS_DIR"
sed "s|^Exec=ducknet$|Exec=$WRAPPER|" "$HERE/ducknet.desktop" > "$DESKTOP"
chmod 644 "$DESKTOP"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true

log "完成"
echo "运行：ducknet            （真机）"
echo "      ducknet --demo     （无蓝牙演示）"
echo "      $WRAPPER --demo    （不想改 PATH 时）"
echo "验收：$VENV/bin/python $HERE/acceptance.py --demo"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR 不在 PATH 里；把下面这行加进 ~/.bashrc：export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac
