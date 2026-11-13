#!/usr/bin/env python3
"""Restore the exact V260 resources from its unmodified runtime ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent
SHA='eda880d910db4b462e64ed778b1bf5bea471ca9ef46e45bb4ff6bcc85b6097c3'

def prepare(path):
    path=Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=SHA:
        raise ValueError('需要原始 V260 中控运行包，SHA256 不匹配')
    manifest=json.loads((ROOT/'RESOURCE-MANIFEST.json').read_text())
    with zipfile.ZipFile(path) as z:
        for name,entry in manifest.items():
            target=ROOT/name
            if not target.resolve().is_relative_to(ROOT.resolve()):raise ValueError('资源路径无效')
            data=z.read('Microduck-Console-Studio-V260/'+name)
            if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:
                raise ValueError('资源校验失败：'+name)
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    print('已恢复并校验 '+str(len(manifest))+' 个运行资源；源码未改动。')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('console_zip',type=Path)
    prepare(parser.parse_args().console_zip)
