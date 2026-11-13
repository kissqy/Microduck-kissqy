"""R10: wait for networking, connect saved Wi-Fi, otherwise start the AP.

Only initial startup retries. Once Wi-Fi or the AP is ready, there is no
runtime recovery, decision file or automatic restart. The historical module
filename keeps the existing deployment path compatible.
"""
import configparser
import ipaddress
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

REVISION = 'R10-boot-only'
PROFILE = Path('/etc/NetworkManager/system-connections/Microduck-Setup.nmconnection')
READY_SECONDS = 60
SAVED_WIFI_SECONDS = 60
AP_ATTEMPTS = 3


def clean_error(value):
    text = ' '.join(str(value or '').split())[-300:]
    return re.sub(r'(?i)((?:password|psk|secret)\s*[=:]\s*)\S+', r'\1<redacted>', text)


class WifiStartup:
    def __init__(self, env, profile=None):
        self.env = env
        self.clock = env['time']
        self.profile = Path(profile) if profile is not None else PROFILE
        self.interface = None

    def log(self, message):
        print('[Microduck Wi-Fi R10] ' + message, flush=True)

    def command(self, *args, timeout=6):
        result = self.env['run'](*args, wait=max(.1, float(timeout)))
        if result.returncode:
            raise RuntimeError(clean_error(result.stderr or result.stdout or '网络管理命令未完成'))
        return result.stdout.strip()

    def wait_wireless(self, timeout=READY_SECONDS):
        if self.interface is not None:
            return self.interface
        deadline = self.clock.monotonic() + timeout
        requested = self.env.get('INTERFACE', 'auto')
        while self.clock.monotonic() < deadline:
            try:
                self.command('nmcli', 'radio', 'wifi', 'on')
                rows = self.command('nmcli', '-t', '-e', 'no', '-f', 'DEVICE,TYPE,STATE', 'device', 'status')
                for row in rows.splitlines():
                    fields = row.split(':', 2)
                    if len(fields) != 3 or fields[1] != 'wifi':
                        continue
                    interface, _, state = fields
                    if requested != 'auto' and interface != requested:
                        continue
                    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', interface):
                        continue
                    if state in ('unmanaged', 'unavailable', 'unknown'):
                        continue
                    try:
                        capability = self.command('nmcli', '-g', 'WIFI-PROPERTIES.AP', 'device', 'show', interface)
                    except (OSError, RuntimeError, subprocess.TimeoutExpired):
                        capability = ''
                    if capability == 'no':
                        raise RuntimeError('当前无线网卡未提供热点能力')
                    self.interface = interface
                    self.env['INTERFACE'] = interface
                    return interface
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass
            self.clock.sleep(2)
        raise RuntimeError('NetworkManager 或无线网卡尚未就绪，继续等待')

    def read_state(self, timeout=6):
        text = self.command('nmcli', '-t', '-e', 'no', '-f', 'GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS',
                            'device', 'show', self.env['INTERFACE'], timeout=timeout)
        state, connection, addresses = None, '', []
        for row in text.splitlines():
            key, _, value = row.partition(':')
            if key == 'GENERAL.STATE':
                match = re.match(r'\s*(\d+)', value)
                state = int(match[1]) if match else None
            elif key == 'GENERAL.CONNECTION':
                connection = value.strip()
            elif key.startswith('IP4.ADDRESS'):
                try:
                    address = ipaddress.IPv4Interface(value.strip()).ip
                    if not address.is_unspecified and not address.is_loopback:
                        addresses.append(str(address))
                except ValueError:
                    pass
        return state, connection, addresses

    def home_ready(self, timeout=6):
        state, connection, addresses = self.read_state(timeout)
        return state == 100 and connection not in ('', '--', 'lo', self.env['AP_NAME']) and bool(addresses)

    def saved_wifi_profiles(self):
        rows = self.command('nmcli', '-t', '-e', 'no', '-f', 'UUID,TYPE', 'connection', 'show')
        profiles = []
        for row in rows.splitlines():
            identity, _, kind = row.partition(':')
            if kind not in ('wifi', '802-11-wireless'):
                continue
            identity = str(uuid.UUID(identity))
            mode = self.command('nmcli', '-g', '802-11-wireless.mode', 'connection', 'show', 'uuid', identity)
            if mode in ('', '--', 'infrastructure'):
                profiles.append(identity)
        return profiles

    def wait_for_saved_wifi(self, timeout=SAVED_WIFI_SECONDS):
        if self.home_ready():
            return True
        profiles = self.saved_wifi_profiles()
        deadline = self.clock.monotonic() + timeout
        for identity in profiles:
            if self.home_ready():
                return True
            remaining = deadline - self.clock.monotonic()
            if remaining <= 0:
                break
            try:
                seconds = max(1, min(20, int(remaining)))
                self.command('nmcli', '--wait', str(seconds), 'connection', 'up', 'uuid', identity,
                             'ifname', self.env['INTERFACE'], timeout=min(remaining + 1, 22))
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass
        return self.home_ready()

    def ensure_profile(self):
        """Prepare this project's AP; repair old settings without a blocking gate."""
        config = configparser.ConfigParser(interpolation=None)
        try:
            config.read_string(self.profile.read_text(encoding='utf-8'))
            identity = str(uuid.UUID(config['connection']['uuid']))
        except (OSError, ValueError, KeyError, UnicodeError, configparser.Error):
            config = configparser.ConfigParser(interpolation=None)
            identity = str(uuid.uuid4())
        password = config.get('wifi-security', 'psk', fallback='12345678')
        if (any(c in password for c in '\r\n\0') or not
                (8 <= len(password.encode('utf-8')) <= 63 or re.fullmatch(r'[0-9a-fA-F]{64}', password))):
            password = '12345678'
        section = 'wifi' if config.has_section('wifi') else '802-11-wireless'
        if (config.get('connection', 'id', fallback='') == self.env['AP_NAME']
                and config.get('connection', 'type', fallback='') in ('wifi', '802-11-wireless')
                and config.get(section, 'mode', fallback='') == 'ap'
                and bool(config.get(section, 'ssid', fallback=''))
                and config.get('wifi-security', 'key-mgmt', fallback='') in ('wpa-psk', 'sae')
                and config.get('wifi-security', 'psk', fallback='') == password
                and config.get('ipv4', 'method', fallback='') == 'shared'
                and config.get('ipv4', 'address1', fallback='').split('/', 1)[0] == self.env['SETUP_IP']):
            if self.profile.stat().st_mode & 0o777 != 0o600:
                self.profile.chmod(0o600)
            self.command('nmcli', 'connection', 'load', str(self.profile))
            return identity
        content = ('[connection]\nid=' + self.env['AP_NAME'] + '\nuuid=' + identity +
                   '\ntype=wifi\nautoconnect=false\n\n[wifi]\nmode=ap\nssid=' + self.env['AP_NAME'] +
                   '\nband=bg\nsecurity=802-11-wireless-security\n\n[wifi-security]\nkey-mgmt=wpa-psk\npsk=' + password +
                   '\n\n[ipv4]\nmethod=shared\naddress1=' + self.env['SETUP_IP'] + '/24\n\n[ipv6]\nmethod=disabled\n')
        self.profile.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='.Microduck-Setup-', dir=self.profile.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(content); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.profile)
        finally:
            Path(temporary).unlink(missing_ok=True)
        self.command('nmcli', 'connection', 'load', str(self.profile))
        return identity

    def hotspot_ready(self):
        state, connection, addresses = self.read_state()
        return state == 100 and connection == self.env['AP_NAME'] and self.env['SETUP_IP'] in addresses

    def activate_hotspot(self):
        self.wait_wireless()
        if self.hotspot_ready():
            return
        for attempt in range(AP_ATTEMPTS):
            try:
                identity = self.ensure_profile()
                self.command('nmcli', '--wait', '20', 'connection', 'up', 'uuid', identity,
                             'ifname', self.env['INTERFACE'], timeout=24)
                if self.hotspot_ready():
                    return
                raise RuntimeError('热点尚未获得配网地址')
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                self.log('热点启动未完成：' + clean_error(error))
                if attempt + 1 < AP_ATTEMPTS:
                    self.clock.sleep(2)
        raise RuntimeError('热点还未启动，回到开机就绪等待后再试')

    def run_boot(self, serve_portal):
        requested = self.env.get('INTERFACE', 'auto')
        while True:
            try:
                self.wait_wireless()
                if self.wait_for_saved_wifi():
                    self.log('已连上 Wi-Fi，开机检查结束')
                    return False
                self.env['show_hotspot_with_captive']()
                self.log('没有连上 Wi-Fi，热点已开启，开机检查结束')
                break
            except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
                self.log('开机网络尚未准备完成：' + clean_error(error))
                self.interface = None
                self.env['INTERFACE'] = requested
                self.clock.sleep(3)
        # HTTP handles explicit setup requests only. Its exit or failure never
        # re-enters startup and never reactivates the hotspot.
        serve_portal()
        return True


def install(env):
    startup = WifiStartup(env)
    for name in ('wait_wireless', 'home_ready', 'activate_hotspot'):
        env[name] = getattr(startup, name)
    env['_wifi_startup_boot'] = startup
