"""ALSA PCM volume conversion; persistence belongs to the operating system."""
import math
from management_profile import DEFAULTS
DEFAULT_VOLUME=DEFAULTS['audio']['volume']
CONTROL='PCM Playback Volume'
MUTE_CONTROL='Line Playback Switch'

def validate(value):
    if type(value) is not int or not 0<=value<=100:raise ValueError('音量必须为 0～100 的整数')
    return value

def raw(value):
    value=validate(value)
    return 0 if value==0 else max(0,min(127,round(127+40*math.log10(value/100))))

def percent(value):
    return max(0,min(100,round(100*10**((value-127)/40))))
