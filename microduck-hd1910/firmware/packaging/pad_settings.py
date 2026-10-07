"""Persistent R17 input preferences; official padd maps all actions."""
import json,math
from pathlib import Path
from configure import atomic_write
from management_profile import DEFAULTS
PATH=Path('/etc/robot/feetech-ft5/pad-settings.json')
LEGACY=Path('/var/lib/robot/feetech-ft5/r5/pad-settings.json')
DEFAULT=DEFAULTS['pad']
def validate(mouth_percent,head_rad):
    if type(mouth_percent) not in (int,float) or not math.isfinite(mouth_percent) or not 0<=mouth_percent<=100:raise ValueError('嘴巴幅度必须为 0～100%')
    if type(head_rad) not in (int,float) or head_rad not in (.5,1.,2.5):raise ValueError('头部幅度请选择 0.5、1.0 或官方 2.5 rad')
    return {'mouth_percent':float(mouth_percent),'head_rad':float(head_rad)}
def load(path=PATH):
    if not path.exists():
        if path==PATH and LEGACY.exists():return load(LEGACY)
        return DEFAULT.copy()
    data=json.loads(path.read_text());return validate(data['mouth_percent'],data['head_rad'])
def save(mouth_percent,head_rad,path=PATH):
    data=validate(mouth_percent,head_rad)
    atomic_write(path,json.dumps(data,ensure_ascii=False)+'\n');return data
