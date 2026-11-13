"""M6-C PCM detection, converted to ALSA's signed 16-bit output; stdlib only."""
import math
import struct


def detect_pcm_dtype(data):
    usable=len(data)-(len(data)%4)
    if usable<256:return None
    sample=data[:min(usable,8192)]
    values=struct.unpack('<%df'%(len(sample)//4),sample)
    small=sum(math.isfinite(v) and abs(v)<=1.5 for v in values)
    active=sum(math.isfinite(v) and 1e-7<abs(v)<=1.5 for v in values)
    if small/len(values)>=.995 and active/len(values)>=.02:return 'float32'
    if any(abs(v)>=4 for v in struct.unpack('<%dh'%(len(sample)//2),sample)):return 'int16'
    return None


class PcmDecoder:
    def __init__(self):self.dtype=None;self.pending=bytearray()

    def feed(self,data,final=False):
        self.pending.extend(data)
        if self.dtype is None:self.dtype=detect_pcm_dtype(self.pending)
        if self.dtype is None:
            if not final:return b''
            self.dtype='int16'
        width=4 if self.dtype=='float32' else 2
        usable=len(self.pending)-len(self.pending)%width
        block=bytes(self.pending[:usable]);del self.pending[:usable]
        if self.dtype=='int16':return block
        values=struct.unpack('<%df'%(len(block)//4),block)
        pcm=[round(max(-1,min(1,v))*32767) if math.isfinite(v) else 0 for v in values]
        return struct.pack('<%dh'%len(pcm),*pcm)

    def discard(self):self.pending.clear()
