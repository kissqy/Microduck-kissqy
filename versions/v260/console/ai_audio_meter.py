"""Numeric level envelope from actual PCM16; no microphone access or dependencies."""
import math
import struct
import time


class AudioMeter:
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.last=None
        self.samples=0;self.energy=0;self.low=0;self.high=0
        self.packets=0

    def update(self,pcm):
        if not pcm or len(pcm)%2:raise ValueError('invalid PCM16 packet')
        for (value,) in struct.iter_unpack('<h',pcm):
            self.energy+=value*value;self.samples+=1
            self.low=min(self.low,value);self.high=max(self.high,value)
        self.packets+=1
        now=self.clock()
        if self.last is not None and now-self.last<.1:return None
        rms=math.sqrt(self.energy/self.samples)/32768
        peak=max(abs(self.low),abs(self.high))/32768
        result={'rms':round(rms,6),'peak':round(peak,6),
                'minimum':round(self.low/32768,6),'maximum':round(self.high/32768,6),
                'dbfs':round(max(-96,20*math.log10(max(rms,1e-12))),1),
                'packets':self.packets,'uploaded_seconds':round(self.packets*.02,2)}
        self.last=now;self.samples=0;self.energy=0;self.low=0;self.high=0
        return result
