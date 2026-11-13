"""Apply and release the optional 720p15 continuous-camera quality.

Only mediad is restarted when the quality changes. Sensor AE/IQ, motion services,
all unrelated TOML values and comments are retained. A release restores only the
quality this operation actually changed, with a guard against independent edits.
"""
import copy
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import tomllib

QUALITY = '720p15'


def run(*args):
    result = subprocess.run(['systemctl', *args], capture_output=True, text=True, timeout=20)
    if result.returncode:raise RuntimeError(result.stderr.strip() or '摄像头服务操作失败')
    return result.stdout.strip()


def config_path(description):
    match = re.search(r'argv\[\]=(.*?)\s*;\s*ignore_errors=', description, re.S)
    if not match:raise ValueError('无法读取摄像头启动命令，保留当前帧率')
    args = shlex.split(match.group(1))
    if not args or Path(args[0]).name != 'mediad':
        raise ValueError('摄像头使用自定义包装程序，保留当前帧率')
    values = []
    for i, arg in enumerate(args):
        if arg == '--config':
            if i+1 == len(args):raise ValueError('摄像头配置路径无效')
            values.append(args[i+1])
        elif arg.startswith('--config='):values.append(arg.split('=',1)[1])
    if len(values)>1:raise ValueError('摄像头有多个配置路径，保留当前帧率')
    path = Path(values[0] if values else '/etc/robot/robotd.toml')
    if not path.is_absolute():raise ValueError('摄像头配置路径不是绝对路径，保留当前帧率')
    return path.resolve()


def quality_text(text, quality=QUALITY, *, remove_empty_media=False):
    before = tomllib.loads(text)
    current = before.get('media',{})
    if not isinstance(current,dict):raise ValueError('摄像头配置格式无效')
    if quality is not None and (not isinstance(quality,str) or not 1<=len(quality)<=80):
        raise ValueError('摄像头质量配置无效')
    if current.get('quality') == quality:return text
    expected = copy.deepcopy(before)
    if quality is None:
        expected.setdefault('media',{}).pop('quality',None)
        if remove_empty_media and not expected['media']:expected.pop('media')
    else:expected.setdefault('media',{})['quality']=quality
    headers = list(re.finditer(r'(?m)^[ \t]*\[([^\]\n]+)\][ \t]*(?:#[^\n]*)?$',text))
    media = [h for h in headers if h.group(1).strip() == 'media']
    if media:
        head = media[0];end = next((h.start() for h in headers if h.start()>head.start()),len(text))
        body = text[head.end():end]
        pattern = r'(?m)^([ \t]*quality[ \t]*=[ \t]*)(?:"[^"\n]*"|\'[^\'\n]*\')([ \t]*(?:#[^\n]*)?)$'
        replacement=(lambda m:m[1]+json.dumps(quality)+m[2]) if quality is not None else (lambda m:m[2].lstrip())
        body, count = re.subn(pattern,replacement,body)
        if not count:
            if 'quality' in current:raise ValueError('摄像头配置格式无法原样保留，未修改帧率')
            if quality is not None:body='\nquality = '+json.dumps(quality)+body
        header='' if 'media' not in expected else text[head.start():head.end()]
        candidate = text[:head.start()]+header+body+text[end:]
    elif 'media' not in before:
        candidate=text.rstrip()+'\n\n[media]\nquality = '+json.dumps(quality)+'\n'
    else:
        raise ValueError('摄像头配置格式无法原样保留，未修改帧率')
    if tomllib.loads(candidate)!=expected:raise ValueError('摄像头配置校验失败，未修改帧率')
    return candidate


def atomic_write(path, data, previous_stat=None):
    fd, temporary = tempfile.mkstemp(prefix='.ai-camera-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as output:
            os.fchmod(output.fileno(),stat.S_IMODE(previous_stat.st_mode) if previous_stat else 0o644)
            if previous_stat and hasattr(os,'fchown'):
                os.fchown(output.fileno(),previous_stat.st_uid,previous_stat.st_gid)
            output.write(data);output.flush();os.fsync(output.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def apply_text(path, previous, candidate, command):
    """Commit one validated config edit, rolling back only our exact bytes."""
    if previous == candidate:return False
    info=path.stat() if previous is not None else None
    if (path.read_bytes() if path.exists() else None) != previous:
        raise RuntimeError('摄像头配置已被其他操作修改，请重试')
    if candidate is None:path.unlink()
    else:atomic_write(path,candidate,info)
    try:command('restart','mediad.service')
    except Exception as failure:
        # Do not overwrite an independent edit made while systemd was running.
        if (path.read_bytes() if path.exists() else None)==candidate:
            if previous is None:path.unlink()
            else:atomic_write(path,previous,info)
            try:command('restart','mediad.service')
            except Exception as rollback:
                raise RuntimeError('摄像头配置已恢复，但服务恢复失败：'+str(rollback)) from failure
        raise
    return True


def prepare(command=run):
    path=config_path(command('show','mediad.service','--property=ExecStart','--value'))
    previous=path.read_bytes() if path.exists() else None
    text=previous.decode('utf-8') if previous is not None else ''
    before=tomllib.loads(text)
    candidate=quality_text(text).encode('utf-8')
    changed=apply_text(path,previous,candidate,command)
    media=before.get('media',{})
    restore={'config_path':str(path),'previous_quality':media.get('quality'),
             'had_quality':'quality' in media,'had_media':'media' in before,
             'had_file':previous is not None,'applied_quality':QUALITY} if changed else None
    return {'accepted':True,'quality':QUALITY,'target_fps':15,'width':1280,'height':720,
            'changed':changed,'restore':restore,
            'message':'摄像头常开 · 目标 720p / 15 帧，实际帧率见视频回读'}


def restore(snapshot, command=run):
    keys={'config_path','previous_quality','had_quality','had_media','had_file','applied_quality'}
    if (not isinstance(snapshot,dict) or set(snapshot)!=keys
            or snapshot['applied_quality']!=QUALITY
            or not isinstance(snapshot['config_path'],str)
            or any(type(snapshot[name]) is not bool for name in ('had_quality','had_media','had_file'))
            or (snapshot['had_quality'] and not isinstance(snapshot['previous_quality'],str))
            or (not snapshot['had_quality'] and snapshot['previous_quality'] is not None)):
        raise ValueError('摄像头恢复信息无效')
    path=config_path(command('show','mediad.service','--property=ExecStart','--value'))
    if str(path)!=snapshot['config_path']:
        return {'accepted':True,'restored':False,'message':'摄像头配置路径已变更，保留当前设置'}
    previous=path.read_bytes() if path.exists() else None
    text=previous.decode('utf-8') if previous is not None else ''
    before=tomllib.loads(text)
    if before.get('media',{}).get('quality')!=snapshot['applied_quality']:
        return {'accepted':True,'restored':False,'message':'摄像头质量已由其他操作修改，保留当前设置'}
    candidate=quality_text(text,snapshot['previous_quality'],
                           remove_empty_media=not snapshot['had_media']).encode('utf-8')
    if not snapshot['had_file'] and not candidate.strip():candidate=None
    changed=apply_text(path,previous,candidate,command)
    quality=tomllib.loads(candidate.decode('utf-8') if candidate is not None else '').get('media',{}).get('quality','720p30')
    return {'accepted':True,'restored':changed,'quality':quality,
            'message':'摄像头已恢复开启常开前的质量；采集按当前预览和拍照需求运行'}


def main():
    if len(sys.argv)==1:return prepare()
    request=json.loads(sys.argv[1])
    if (not isinstance(request,dict) or set(request)!={'action','restore'}
            or request['action']!='restore'):raise ValueError('摄像头操作无效')
    return restore(request['restore'])


if __name__=='__main__':
    try:print(json.dumps(main(),ensure_ascii=False))
    except Exception as error:
        print(str(error),file=sys.stderr);sys.exit(1)
