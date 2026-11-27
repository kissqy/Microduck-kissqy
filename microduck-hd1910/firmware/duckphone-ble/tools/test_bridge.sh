#!/usr/bin/env bash
# 在无头 Chrome 里跑 ble-bridge.js 的自测。不需要蓝牙，也不需要 Android SDK。
#
# 用法：bash test_bridge.sh
# 退出码：0 全部通过；1 有 FAIL；2 环境问题。
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PAGE="$HERE/tests/bridge_test.html"

CHROME=""
for candidate in google-chrome google-chrome-stable chromium chromium-browser; do
  if command -v "$candidate" >/dev/null; then CHROME="$candidate"; break; fi
done
[[ -n "$CHROME" ]] || { echo "需要 Chrome/Chromium" >&2; exit 2; }

OUT="$(timeout 60 "$CHROME" --headless=new --disable-gpu --no-sandbox \
  --allow-file-access-from-files --virtual-time-budget=20000 --dump-dom \
  "file://$PAGE?bleAddress=AA:BB:CC:DD:EE:FF&blePin=000000&strip=1" 2>/dev/null)"

echo "$OUT" | sed -n '/<pre id="out">/,/<\/pre>/p' \
  | sed '1s/.*<pre id="out">//; $s/<\/pre>.*//'
if echo "$OUT" | grep -q "ALL PASS"; then
  exit 0
fi
echo "桥接自测失败" >&2
exit 1
