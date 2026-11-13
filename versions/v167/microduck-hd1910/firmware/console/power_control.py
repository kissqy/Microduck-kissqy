"""Submit OS power directly; the operating system owns shutdown and reboot."""
import json
import subprocess
import sys


def run(*args, timeout=5):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or '系统电源指令失败')[-1500:])
    return result.stdout


def power(action, runner=run):
    if action not in ('reboot','shutdown'):
        raise ValueError('电源操作无效')
    runner('/usr/bin/systemctl','--no-block',
           'reboot' if action=='reboot' else 'poweroff',timeout=5)
    return {'power_action':action,'scheduled':True,'delay_seconds':0,
            'verified_by':'systemctl accepted power request',
            'message':'Zero '+('重启' if action=='reboot' else '关机')+'指令已直接提交'}


if __name__=='__main__':
    try: print(json.dumps(power(sys.argv[1]),ensure_ascii=False))
    except Exception as exc: print(str(exc),file=sys.stderr);sys.exit(1)
