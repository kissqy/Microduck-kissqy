#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
  echo '需要 Python 3.10 或更新版本，请先安装 Python。'
  read -r -p '按回车退出' console_reply
  exit 1
fi
python3 training_console.py --open
