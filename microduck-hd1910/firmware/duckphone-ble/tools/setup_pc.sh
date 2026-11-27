#!/usr/bin/env bash
# 准备 PC 侧的验收环境：一个只装 bleak 的 venv，外加检查 adb / Chrome / ssh。
#
# 用法：
#   bash setup_pc.sh            # 创建 tools/.venv-ble 并安装依赖
#   bash setup_pc.sh --check    # 只检查，不安装
#
# 为什么单独一个 venv：系统的 Python 不允许 pip 安装（PEP 668），而验收脚本只需要
# 一个包；把它关在 tools/.venv-ble 里，删掉目录就等于卸载干净。
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/.venv-ble"
MODE=install
case "${1:-}" in
  "" ) ;;
  --check) MODE=check ;;
  -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "未知参数：$1" >&2; exit 2 ;;
esac

fail=0
check() { printf '%-22s %s\n' "$1" "$2"; }
note_missing() { printf '\033[33m[missing]\033[0m %s\n' "$1"; fail=$((fail + 1)); }

echo "== 检查本机工具"
python3 --version || { note_missing "python3"; }
command -v ssh >/dev/null && check ssh "$(ssh -V 2>&1 | head -1)" || note_missing "ssh"
command -v scp >/dev/null && check scp ok || note_missing "scp"
if command -v adb >/dev/null; then
  check adb "$(adb version | head -1)"
else
  note_missing "adb（Android SDK platform-tools）"
fi
for browser in chromium chromium-browser google-chrome; do
  if command -v "$browser" >/dev/null; then check browser "$(command -v "$browser")"; break; fi
done
command -v zig >/dev/null && check zig "$(zig version)" || echo "  zig 未装（只在交叉编译固件时需要）"

if [[ "$MODE" == check ]]; then
  [[ $fail == 0 ]] && echo "检查通过" || echo "$fail 项缺失" >&2
  exit $(( fail == 0 ? 0 : 1 ))
fi

echo "== 创建 $VENV"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV/bin/python" -m pip install -r "$HERE/requirements.txt"

echo "== 安装完成"
"$VENV/bin/python" - <<'PY'
from importlib.metadata import version
print(f"bleak {version('bleak')}")
PY
cat <<EOF

用这个解释器跑验收：
  $VENV/bin/python $HERE/probe_ble.py
  $VENV/bin/python $HERE/acceptance.py --name <机器人名> --pin <PIN>
EOF
