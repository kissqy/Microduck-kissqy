#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
exec python3 console.py --dashboard --feetech --open
