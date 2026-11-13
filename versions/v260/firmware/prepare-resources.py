#!/usr/bin/env python3
"""Restore only hashed packaging resources from the companion V260 firmware."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parent

def prepare(path):
    metadata=json.loads((ROOT/'packaging/BUILD.json').read_text())
    expected=json.loads((ROOT/'SOURCE-IDENTITY.json').read_text())['firmware_tar_sha256']
    with zipfile.ZipFile(path) as z:
        names=[n for n in z.namelist() if Path(n).name=='Microduck-Robotd-FT6-R17.tar.gz']
        if len(names)!=1:raise ValueError('ZIP 内需要唯一的 V260 固件 tar.gz')
        payload=z.read(names[0])
    if hashlib.sha256(payload).hexdigest()!=expected:raise ValueError('固件载荷 SHA256 不匹配')
    manifest=json.loads((ROOT/'packaging/RESOURCE-MANIFEST.json').read_text())
    with tarfile.open(fileobj=io.BytesIO(payload)) as t:
        for name,entry in manifest.items():
            target=ROOT/'packaging'/name
            if not target.resolve().is_relative_to((ROOT/'packaging').resolve()):raise ValueError('资源路径无效')
            data=t.extractfile('Microduck-Robotd-FT6-R17/'+name).read()
            if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:
                raise ValueError('资源校验失败：'+name)
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            if data.startswith(b'\x7fELF'):target.chmod(0o755)
    print('已恢复并校验 '+str(len(manifest))+' 个 V260 编译载荷、模型与运行库资源。')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware_zip',type=Path)
    prepare(parser.parse_args().firmware_zip)
