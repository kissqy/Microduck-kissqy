"""Temporary servo-test extension; deleting its JSON restores the original gains."""
import json,re
from configure import atomic_write

def validate_servo(kp,kd,torque_limit):
    values=dict(zip(('kp','kd','torque_limit'),(kp,kd,torque_limit)))
    for name,maximum in (('kp',255),('kd',255),('torque_limit',1000)):
        text=str(values[name])
        if not re.fullmatch(r'[0-9]+',text) or not 0<=int(text)<=maximum:
            raise ValueError(f'{name} 必须为 0 到 {maximum} 的整数')
        values[name]=int(text)
    return values

def load(config):
    path=config.with_name('servo-test-parameters.json')
    return json.loads(path.read_text()) if path.exists() else None

def save(config,values):
    atomic_write(config.with_name('servo-test-parameters.json'),json.dumps(values,ensure_ascii=False)+'\n')
