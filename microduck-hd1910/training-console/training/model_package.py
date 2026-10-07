"""Portable model download helper, also runs under WSL's standard-library Python."""
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

LIMIT = 512 * 1024 * 1024

def model_package(request):
    policy = Path(request['artifact']).expanduser()
    if not policy.is_file():
        raise ValueError('ONNX 文件不存在，可能已移动或删除；请重新导出所选检查点。')
    if policy.stat().st_size > LIMIT:
        raise ValueError('ONNX 超出 512 MB 下载上限。')
    data = policy.read_bytes()
    if hashlib.sha256(data).hexdigest() != request['sha256']:
        raise ValueError('ONNX 内容与导出记录不一致；请重新导出。')
    archive = policy.with_suffix('.zip')
    if archive.is_file():
        if archive.stat().st_size > LIMIT:
            raise ValueError('模型包超过 512 MB 下载上限。')
        packed = archive.read_bytes()
    else:
        # Old exports can retain the ONNX while the adjacent ZIP is absent.
        # Rebuild from the same recorded files, never a newly selected model.
        checkpoint = Path(request['checkpoint']).expanduser() if request.get('checkpoint') else None
        if not checkpoint or not checkpoint.is_file():
            raise ValueError('模型包缺失且源检查点不存在；请重新导出。')
        if checkpoint.stat().st_size + len(data) > LIMIT:
            raise ValueError('模型及检查点超过 512 MB 下载上限。')
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('policy.onnx', data)
            z.write(checkpoint, 'checkpoint.pt')
            contract = policy.with_suffix('.contract.json')
            if contract.is_file(): z.write(contract, 'deployment-contract.json')
            z.writestr('training-request.json', json.dumps(request.get('training_request', {}), ensure_ascii=False, indent=2))
            manifest = policy.with_suffix('.manifest.json')
            if manifest.is_file():
                z.write(manifest, 'manifest.json')
                for suffix, name in [('.deployment.toml', 'deployment-profile.toml'), ('.deployment.md', '使用说明.md')]:
                    sidecar = policy.with_suffix(suffix)
                    if not sidecar.is_file():
                        raise ValueError('新版模型的部署参数不完整，请重新导出。')
                    z.write(sidecar, name)
                snapshot = policy.with_suffix('.training.json')
                if snapshot.is_file():
                    z.write(snapshot, 'training-config.json')
                elif json.loads(manifest.read_text(encoding='utf-8')).get('export_contract_revision', 1) >= 2:
                    raise ValueError('新版模型缺少原训练配置快照，请重新导出。')
                params = checkpoint.parent / 'params'
                if params.is_dir():
                    for source in params.glob('*'):
                        if source.is_file(): z.write(source, 'upstream-params/' + source.name)
            else:
                if request.get('training_request', {}).get('engine') == 'official_0151':
                    raise ValueError('新版模型缺少官方 manifest，请重新导出。')
                z.writestr('manifest.json', json.dumps({'onnx_sha256':request['sha256'], 'repacked':True, 'deployment_verified':False}))
        packed = out.getvalue()
    try:
        with zipfile.ZipFile(io.BytesIO(packed)) as z:
            if sum(i.file_size for i in z.infolist()) > LIMIT:
                raise ValueError('解压内容超过 512 MB 下载上限。')
            if 'policy.onnx' not in z.namelist() or 'checkpoint.pt' not in z.namelist():
                raise ValueError('模型包缺少 ONNX 或检查点，请重新导出。')
            if hashlib.sha256(z.read('policy.onnx')).hexdigest() != request['sha256']:
                raise ValueError('模型包内 ONNX 与导出记录不一致，请重新导出。')
            if z.testzip(): raise ValueError('模型包校验失败，请重新导出。')
    except (zipfile.BadZipFile, RuntimeError, EOFError) as error:
        raise ValueError('模型包不是有效 ZIP，请重新导出。') from error
    return packed

if __name__ == '__main__':
    try: sys.stdout.buffer.write(model_package(json.loads(sys.stdin.read())))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
