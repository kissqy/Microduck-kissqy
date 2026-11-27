#!/usr/bin/env bash
# 用 adb 安装并启动 App。
#
# 用法：
#   bash install_apk.sh                     # 装 .build/apk/ 里最新的一个
#   bash install_apk.sh path/to/app.apk
#   bash install_apk.sh --list              # 看设备
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APK_DIR="$HERE/../../../.build/apk"
PACKAGE="com.microduck.phone"
ACTIVITY="$PACKAGE/.MainActivity"

die() { printf '\033[31m[err]\033[0m %s\n' "$*" >&2; exit 2; }
command -v adb >/dev/null || die "没有 adb；装 Android SDK platform-tools"

if [[ "${1:-}" == "--list" ]]; then
  adb devices -l
  exit 0
fi

if [[ -n "${1:-}" ]]; then
  APK="$1"
else
  APK="$(ls -1t "$APK_DIR"/*.apk 2>/dev/null | head -1 || true)"
fi
[[ -n "${APK:-}" && -f "$APK" ]] || die "没有 APK：先跑 build_apk.sh，或把路径作为参数"

DEVICES="$(adb devices | awk 'NR>1 && $2=="device" {print $1}')"
[[ -n "$DEVICES" ]] || die "没有已授权的设备；打开 USB 调试并在手机上点“允许”"
COUNT="$(printf '%s\n' "$DEVICES" | wc -l)"
if [[ "$COUNT" -gt 1 ]]; then
  die "连接了多台设备，请先 adb -s <serial> … 或只留一台：$DEVICES"
fi

echo "== 安装 $APK"
adb install -r "$APK"
echo "== 启动 $ACTIVITY"
adb shell am start -n "$ACTIVITY"
echo
echo "看日志： adb logcat -s DuckBle DuckLink DuckWeb"
