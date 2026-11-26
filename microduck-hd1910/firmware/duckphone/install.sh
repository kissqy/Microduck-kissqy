#!/usr/bin/env bash
# 把 duckphone 装到板子上并启动。
#
#   ./install.sh                 # 本机就是板子（duck@…）时直接装到 /opt/duckphone
#   ./install.sh duck@192.168.110.240   # 从电脑推到板子
#
# 只做三件事：同步文件、装 systemd 单元、打印地址与配对码。
# 不改 robotd 配置，不动机器人源码；卸载就是 `systemctl disable --now duckphone`。
set -euo pipefail

TARGET="${1:-}"
DEST=/opt/duckphone
UNIT=duckphone.service          # what it is called once installed
UNIT_SRC=systemd/$UNIT          # where it lives in this directory
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

run() {
  if [[ -n "$TARGET" ]]; then
    ssh "$TARGET" "$@"
  else
    bash -lc "$*"
  fi
}

echo "==> 检查 python3"
run "python3 -c 'import sys; print(sys.version.split()[0])'"

# 令牌目录必须先存在：单元里 ReadWritePaths=/etc/duckphone，
# 路径不存在 systemd 会直接拒绝启动；ProtectSystem=full 也不允许它自己创建 /etc 下的目录。
echo "==> 准备 /etc/duckphone"
run "sudo install -d -o duck -g duck -m 700 /etc/duckphone"

if ! command -v rsync >/dev/null 2>&1 && [[ -z "$TARGET" ]]; then
  echo "（本机没有 rsync，用 cp 兜底）"
fi

if [[ -n "$TARGET" ]]; then
  echo "==> 同步到 $TARGET:$DEST"
  ssh "$TARGET" "sudo mkdir -p $DEST && sudo chown \$(id -u):\$(id -g) $DEST"
  rsync -a --delete \
    --exclude '__pycache__' --exclude 'verification' --exclude 'design' \
    "$HERE"/server.py "$HERE"/rpc.py "$HERE"/ws.py "$HERE"/audio_director.py "$HERE"/audio_settings.py "$HERE"/head_gesture.py "$HERE"/static "$HERE"/README.md "$HERE"/README.en.md \
    "$TARGET:$DEST/"
  rsync -a "$HERE/$UNIT_SRC" "$TARGET:/tmp/$UNIT"
  run "sudo install -m 644 /tmp/$UNIT /etc/systemd/system/$UNIT"
  # 设计原型单独拷一份进 static，手机上就能评审（纯静态假数据，不连机器人）
  if [[ -f "$HERE/design/prototype.html" ]]; then
    ssh "$TARGET" "mkdir -p $DEST/static/design"
    rsync -a "$HERE/design/prototype.html" "$TARGET:$DEST/static/design/prototype.html"
  fi
else
  echo "==> 安装到 $DEST"
  sudo mkdir -p "$DEST"
  if command -v rsync >/dev/null 2>&1; then
    sudo rsync -a --delete \
      --exclude '__pycache__' --exclude 'verification' --exclude 'design' \
      "$HERE"/server.py "$HERE"/rpc.py "$HERE"/ws.py "$HERE"/audio_director.py "$HERE"/audio_settings.py "$HERE"/head_gesture.py "$HERE"/static "$HERE"/README.md "$HERE"/README.en.md \
      "$DEST/"
  else
    sudo rm -rf "$DEST/static"
    sudo cp -a "$HERE"/server.py "$HERE"/rpc.py "$HERE"/ws.py "$HERE"/audio_director.py "$HERE"/audio_settings.py "$HERE"/head_gesture.py "$HERE"/README.md "$HERE"/README.en.md "$DEST/"
    sudo cp -a "$HERE"/static "$DEST/"
  fi
  sudo install -m 644 "$HERE/$UNIT_SRC" "/etc/systemd/system/$UNIT"
  if [[ -f "$HERE/design/prototype.html" ]]; then
    sudo mkdir -p "$DEST/static/design"
    sudo install -m 644 "$HERE/design/prototype.html" "$DEST/static/design/prototype.html"
  fi
fi

# `enable --now` on an already-running unit is a no-op, so a redeploy would keep
# serving the old code until someone rebooted. Restart explicitly.
echo "==> 启动"
run "sudo systemctl daemon-reload && sudo systemctl enable $UNIT >/dev/null && sudo systemctl restart $UNIT && sleep 1.5 && systemctl --no-pager --lines=0 status $UNIT"

echo
echo "==> 地址"
run "hostname -I | tr ' ' '\n' | grep -E '^[0-9]+\.' | sed 's|^|  http://|; s|\$|:8001/|'"
echo
echo "==> 访问方式"
echo "  默认不需要配对码，手机连同一个 Wi-Fi 直接打开上面的地址即可。"
echo "  设计原型（评审用，假数据）：上面的地址后面换成 design/prototype.html"
run "sudo cat /etc/duckphone/token 2>/dev/null | sed 's/^/  配对码（仅在加 --auth 启动时才需要）：/'"
