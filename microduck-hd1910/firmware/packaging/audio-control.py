#!/usr/bin/env python3
"""One finite native ALSA operation; no input socket or resident audio worker."""
import argparse
import json
import sys
from remote_audio import NativeAudio


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['status','set-volume'])
    parser.add_argument('volume',nargs='?',type=int)
    args=parser.parse_args()
    def diagnostic(event):
        if event.get('event')=='system_log':
            print(event.get('source','音量')+': '+event.get('text',''),file=sys.stderr,flush=True)
    audio=NativeAudio(None,diagnostic,initialize=False)
    if args.action=='status':
        audio.initialize()
        result={'accepted':True,'audio':audio.status()}
    else:
        if args.volume is None:parser.error('set-volume requires a volume')
        result=audio.set_volume(args.volume)
        result['audio']=audio.status()
    print(json.dumps(result,ensure_ascii=False,allow_nan=False),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(1)
