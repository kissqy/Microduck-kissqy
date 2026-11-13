"""Keep Doubao credentials in this computer's user configuration directory."""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
from ssh_connect import preferences_path
from ai_persona import DEFAULT_PERSONA, validate_persona, upgrade_default_rules
from ai_vision import validate_vision
from ai_voices import catalog,voice_id


DEFAULT_VOICE = 'zh_female_vv_jupiter_bigtts'
CAMERA_MODE_REVISION = 1


def validate_credentials(key, voice):
    if not isinstance(key, str) or (key and not 10 <= len(key.strip()) <= 300):
        raise ValueError('豆包密钥无效')
    voice_id(voice)
    return key.strip(), voice


class AIPreferences:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else preferences_path().with_name('ai-voice.json')

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None
        if not isinstance(data, dict) or data.get('schema') != 1:
            raise ValueError('本地语音配置格式无效')
        key = data.get('api_key')
        if data.get('key_storage') == 'windows-dpapi':
            if sys.platform != 'win32':
                raise ValueError('此密钥需在原 Windows 用户下读取')
            from sudo_credential import _windows_protect
            key = _windows_protect(base64.b64decode(key, validate=True), decrypt=True).decode('utf-8')
        elif data.get('key_storage') != 'local-user':
            raise ValueError('本地语音配置格式无效')
        key, voice = validate_credentials(key, data.get('voice_id'))
        persona = upgrade_default_rules(validate_persona(data.get('persona', DEFAULT_PERSONA)))
        result = {'api_key': key, 'voice_id': voice, 'persona': persona}
        if 'voices' in data:result['voices']=catalog(data['voices'],voice)
        if 'vision' in data:
            try:
                vision = data['vision']
                if not isinstance(vision, dict):raise ValueError('本地视觉配置格式无效')
                vision_key = vision.get('api_key', '')
                if data['key_storage'] == 'windows-dpapi':
                    vision_key = _windows_protect(base64.b64decode(vision_key, validate=True), decrypt=True).decode('utf-8')
                migrated = vision.get('camera_mode_revision') != CAMERA_MODE_REVISION
                enabled = False if migrated else vision.get('enabled',False)
                result['vision'] = validate_vision(vision_key, vision.get('model'), enabled,vision.get('backlight',False))
                if migrated:
                    # The old enabled flag authorized recognition, not continuous
                    # capture. Keep encrypted credentials byte-for-byte while
                    # applying the new off-by-default camera meaning once.
                    data['vision'] = {**vision,'enabled':False,'camera_mode_revision':CAMERA_MODE_REVISION}
                    try:self._write(data)
                    except OSError:
                        result['vision_configuration_error'] = '摄像头常开已默认关闭，但本机配置更新失败；密钥和识图功能已保留。'
            except (OSError,ValueError,TypeError,KeyError):
                result['vision'] = validate_vision()
                result['vision_configuration_error'] = '本机视觉配置无法读取，请重新填写；已保留语音配置。'
        return result

    def save(self, key, voice, persona=DEFAULT_PERSONA, *, vision=None, voices=None):
        key, voice = validate_credentials(key, voice)
        persona = validate_persona(persona)
        if vision is not None:vision = validate_vision(**vision)
        storage = 'local-user'
        if sys.platform == 'win32':
            from sudo_credential import _windows_protect
            key = base64.b64encode(_windows_protect(key.encode('utf-8'))).decode('ascii')
            storage = 'windows-dpapi'
        data = {'schema': 1, 'api_key': key, 'key_storage': storage, 'voice_id': voice, 'persona': persona}
        if voices is not None:data['voices']=catalog(voices,voice)
        if vision is not None:
            vision['camera_mode_revision'] = CAMERA_MODE_REVISION
            if sys.platform == 'win32':
                vision['api_key'] = base64.b64encode(_windows_protect(vision['api_key'].encode('utf-8'))).decode('ascii')
            data['vision'] = vision
        self._write(data)

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.ai-voice-', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
