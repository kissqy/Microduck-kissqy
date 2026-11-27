#!/usr/bin/env bash
# 从原网页版单向复制页面到 App 的 assets。
#
# **只往一个方向写**：`firmware/duckphone/static/` → `firmware/duckphone-ble/assets/duckphone/`。
# 原网页版继续在 :8001 独立发布，App 用的是它的一份副本；在副本上改 UI 不会、也不许
# 回写原版。
#
# 用法：
#   bash sync-web.sh          # 复制
#   bash sync-web.sh --check  # 只报告差异（rsync dry-run）
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/../../duckphone/static"
DST="$HERE/../assets/duckphone"
MODE="${1:-apply}"

[[ -d "$SRC" ]] || { echo "找不到原网页版：$SRC" >&2; exit 2; }
command -v rsync >/dev/null || { echo "需要 rsync" >&2; exit 2; }
mkdir -p "$DST"

if [[ "$MODE" == --check ]]; then
  rsync -a --delete --dry-run --itemize-changes "$SRC/" "$DST/"
else
  rsync -a --delete "$SRC/" "$DST/"
  echo "已同步：$SRC → $DST"
  echo "注意：ble-bridge.js 与页面上的注入由 Android 侧负责，不在这个目录里生成。"
fi
