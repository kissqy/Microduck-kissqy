"""Accept only firmware bytes matched to this console's shipped release."""
import hashlib
import json
from pathlib import Path
import secrets
import tempfile
import zipfile

from controls import ControlError
from release_identity import BUILD, CONSOLE_VERSION

ROOT = Path(__file__).resolve().parent
ARCHIVE_NAME = 'Microduck-Robotd-FT6-R17.tar.gz'
MAX_FIRMWARE = 64 * 1024 * 1024


def bundle_info():
    metadata = json.loads((ROOT/'BUILD_MANIFEST.json').read_text())
    archive = ROOT/'updates'/ARCHIVE_NAME
    if metadata['service_build'] != BUILD or metadata['console_version'] != CONSOLE_VERSION:
        raise ControlError('中控清单与版本不一致，请完整解压本版中控', 409)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != metadata['service_package_sha256']:
        raise ControlError('随包固件 SHA256 校验失败，请重新解压完整中控', 409)
    return {'verified':True,'build':BUILD,'console_version':CONSOLE_VERSION,'official_version':'0.15.1',
            'sha256':digest,'models':metadata['models'],'bytes':archive.stat().st_size}


class PreparedFirmware:
    def __init__(self, name, stream, size, owner):
        if not isinstance(name,str) or Path(name).name != name or not name.lower().endswith('.zip') or len(name)>180:
            raise ControlError('请选择本版固件 ZIP 或完整中控 ZIP',400)
        if type(size) is not int or not 0<size<=MAX_FIRMWARE:
            raise ControlError('固件 ZIP 上限 64 MiB',400)
        self.directory = tempfile.TemporaryDirectory(prefix='microduck-firmware-')
        try:
            upload=Path(self.directory.name)/'upload.zip'
            with upload.open('xb') as output:
                left=size
                while left:
                    chunk=stream.read(min(left,1024*1024))
                    if not chunk:raise ControlError('固件 ZIP 上传未完成',400)
                    output.write(chunk);left-=len(chunk)
            info=bundle_info()
            self.path=Path(self.directory.name)/ARCHIVE_NAME
            with zipfile.ZipFile(upload) as package:
                entries=package.infolist()
                candidates=[entry for entry in entries if Path(entry.filename).name==ARCHIVE_NAME]
                if len(entries)>512 or len(candidates)!=1:
                    raise ControlError('ZIP 中必须包含唯一的本版 R17 固件包',400)
                entry=candidates[0]
                if entry.flag_bits&1 or not 0<entry.file_size<=32*1024*1024:
                    raise ControlError('固件包长度或加密格式不受支持',400)
                # Read one known payload; never extract user-supplied paths or execute its code.
                digest=hashlib.sha256()
                with package.open(entry) as source,self.path.open('xb') as output:
                    for chunk in iter(lambda:source.read(1024*1024),b''):
                        output.write(chunk);digest.update(chunk)
            if digest.hexdigest()!=info['sha256']:
                raise ControlError('本地固件与本版中控不匹配，未刷入。请使用 v'+CONSOLE_VERSION+' 配套包',409)
            upload.unlink()
            self.owner=owner;self.token=secrets.token_hex(32)
            self.info={**info,'token':self.token,'name':name}
        except (zipfile.BadZipFile,zipfile.LargeZipFile,RuntimeError) as exc:
            self.close();raise ControlError('无法读取固件 ZIP：'+str(exc),400) from exc
        except Exception:
            self.close();raise

    def close(self):
        self.directory.cleanup()
