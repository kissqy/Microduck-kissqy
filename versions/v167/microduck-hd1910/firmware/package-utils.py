#!/usr/bin/env python3
"""Current release package integrity helpers."""
import hashlib,io,json,re,shutil,subprocess,tarfile,zipfile
from pathlib import Path

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def content_hash(raw):return hashlib.sha256(raw).hexdigest()


def write_json(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def files_in(root):
    return sorted((p for p in root.rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.suffix!='.pyc'),key=lambda p:p.relative_to(root).as_posix())


def read_elf(path,existing):
    obj=dict(existing)
    obj['bytes']=path.stat().st_size
    obj['sha256']=digest(path)
    import subprocess
    if shutil.which('readelf'):
        dynamic=subprocess.run(['readelf','-d',str(path)],capture_output=True,text=True,check=True).stdout
        deps=re.findall(r'\(NEEDED\).*?\[(.*?)\]',dynamic)
        obj['needed']=deps
        versions=subprocess.run(['readelf','-V',str(path)],capture_output=True,text=True,check=True).stdout
        obj['glibc_versions']=sorted(set(re.findall(r'GLIBC_(\d+\.\d+)',versions)),key=lambda s:tuple(map(int,s.split('.'))))
        if any(tuple(map(int,x.split('.')))> (2,41) for x in obj['glibc_versions']):
            raise ValueError(f'{path.name}: 链接到了比 Zero 的 glibc 2.41 更新的 ABI')
    return obj


def extract_trusted_zip(zip_path, temp_dir):
    with zipfile.ZipFile(zip_path) as z:
        for row in z.infolist():
            path=Path(row.filename)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('source zip invalid path')
        z.extractall(temp_dir)


def extract_trusted_tar(data, temp_dir):
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as t:
        for row in t:
            path=Path(row.name)
            if path.is_absolute() or '..' in path.parts or not row.isfile():
                raise ValueError('baseline tar contains unexpected entry')
        t.extractall(temp_dir,filter='data')
