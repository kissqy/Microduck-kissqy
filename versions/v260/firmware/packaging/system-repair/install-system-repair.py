#!/usr/bin/env python3
"""Install and read back the bundled onboarding files and Armbian boot fix.

Existing Wi-Fi connections and robot configuration are retained. Installation
never restarts Wi-Fi or starts the onboarding service in the current session.
"""
import argparse
import importlib.util
import hashlib
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PROGRAM = 'usr/local/sbin/microduck-public-image'
PORTAL = 'usr/local/libexec/microduck-setup-portal.py'
UNIT = 'etc/systemd/system/microduck-setup.service'
R7_MODULE = 'usr/local/libexec/microduck_wifi_r7.py'
USB_GADGET = 'usr/local/sbin/microduck-usb-gadget'
USB_UNIT = 'etc/systemd/system/microduck-usb-gadget.service'
USB_PROFILE = 'etc/NetworkManager/system-connections/Microduck-USB.nmconnection'
USB_NM_POLICY = 'etc/NetworkManager/conf.d/zzz-microduck-usb-network.conf'
USB_UDEV_RULE = 'etc/udev/rules.d/90-microduck-usb-managed.rules'
USB_ENABLE_LINK = 'etc/systemd/system/multi-user.target.wants/microduck-usb-gadget.service'
USB_ENABLE_TARGET = '../microduck-usb-gadget.service'
LEGACY = {
    'usr/local/libexec/microduck_wifi_events.py': 'c31ad55f443db1c7fa1cbe7febbaabb359228b65cb4b62e47ebfc0080500a185',
    'etc/NetworkManager/dispatcher.d/90-microduck-hotspot': '33e6b289a97c531903c0e5d3c11c3b290fec3a83043efe9f41fe2d2727c91786',
}
BOOT_SCRIPT = 'usr/lib/armbian/armbian-hardware-optimization'
BOOT_ENV = 'boot/armbianEnv.txt'
REVISION = 'V260-control102-R10'


def prepare_hotspot_dependencies():
    """Provision the existing NM shared-mode helper during installation only."""
    executable = shutil.which('dnsmasq')
    installed = False
    if executable is None:
        print('[Microduck] 安装热点所需的 dnsmasq-base。', flush=True)
        env = {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive', 'LC_ALL': 'C'}
        subprocess.run(['apt-get', 'update'], check=True, env=env)
        subprocess.run(['apt-get', 'install', '-y', '--no-install-recommends',
                        'dnsmasq-base'], check=True, env=env)
        installed = True
        executable = shutil.which('dnsmasq')
    if executable is None:
        raise RuntimeError('热点依赖安装未完成：仍找不到 dnsmasq，固件安装未完成。')
    subprocess.run([executable, '--version'], check=True, capture_output=True,
                   text=True, timeout=10)
    return {'package': 'dnsmasq-base', 'executable': executable,
            'installed_now': installed, 'verified': True}


def repair_module():
    spec = importlib.util.spec_from_file_location('v167_armbian_repair', HERE / 'repair-armbian-env.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



def verify_portal_entry(portal):
    """Load the actual complete program before installing; --help does no I/O."""
    result = subprocess.run([sys.executable, '-c', portal.decode('utf-8'), '--help'],
                            env={**os.environ, 'PYTHONPATH': str(HERE), 'LC_ALL': 'C'},
                            capture_output=True, text=True, timeout=20)
    if result.returncode:
        detail = result.stderr.strip().splitlines()
        raise RuntimeError('配网程序完整入口检查失败：' + (detail[-1] if detail else '无有效回执'))


def check(root):
    program = (HERE / 'microduck-public-image.sh').read_bytes()
    portal = program.split(b'#__PORTAL_BEGIN__\n', 1)[1].split(b'#__PORTAL_END__', 1)[0]
    verify_portal_entry(portal)
    bundled = {
        R7_MODULE: ((HERE / 'microduck_wifi_r7.py').read_bytes(), 0o600),
        PROGRAM: (program, 0o700),
        PORTAL: (portal, 0o700),
        UNIT: ((HERE / 'microduck-setup.service').read_bytes(), 0o644),
        USB_GADGET: ((HERE / 'microduck-usb-gadget').read_bytes(), 0o755),
        USB_UNIT: ((HERE / 'microduck-usb-gadget.service').read_bytes(), 0o644),
        USB_PROFILE: ((HERE / 'Microduck-USB.nmconnection').read_bytes(), 0o600),
        USB_NM_POLICY: ((HERE / 'zzz-microduck-usb-network.conf').read_bytes(), 0o644),
        USB_UDEV_RULE: ((HERE / '90-microduck-usb-managed.rules').read_bytes(), 0o644),
    }
    changes = []
    for name, (updated, mode) in bundled.items():
        path = root / name
        original = path.read_bytes() if path.is_file() else b''
        current = path.stat() if path.is_file() else None
        metadata = SimpleNamespace(
            st_uid=os.geteuid(), st_gid=os.getegid(), st_mode=0o100000 | mode)
        if (updated != original or current is None
                or current.st_mode & 0o7777 != mode
                or current.st_uid != metadata.st_uid or current.st_gid != metadata.st_gid):
            changes.append((name, original, updated, metadata))
    dns_dir = root / 'etc/NetworkManager/dnsmasq-shared.d'
    for path in sorted(dns_dir.glob('99-microduck-firstboot-captive.conf.*.new')):
        if path.is_file() and not path.is_symlink():
            changes.append((path.relative_to(root).as_posix(), path.read_bytes(), None, None))
    for name, digest in LEGACY.items():
        path = root / name
        if path.is_file() and not path.is_symlink():
            original = path.read_bytes()
            if hashlib.sha256(original).hexdigest() == digest:
                changes.append((name, original, None, None))
    module = repair_module()
    try:
        boot = module.repair(root / BOOT_SCRIPT, root / BOOT_ENV,
                             root / 'var/backups/microduck-armbian-env', apply=False)
    except ValueError as error:
        # Only the known old Armbian writer needs this optional patch.
        boot = {'status': 'skipped', 'detail': str(error)}
    enable_link = root / USB_ENABLE_LINK
    usb_link_needs_repair = not (
        enable_link.is_symlink() and os.readlink(enable_link) == USB_ENABLE_TARGET)
    return module, changes, boot, usb_link_needs_repair


def apply(root, live=False):
    dependency = prepare_hotspot_dependencies() if live else None
    module, changes, boot, usb_link_needs_repair = check(root)
    if boot['status'] != 'skipped':
        boot = module.repair(root / BOOT_SCRIPT, root / BOOT_ENV,
                             root / 'var/backups/microduck-armbian-env', apply=True)
    for name, original, updated, metadata in changes:
        path = root / name
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if updated is None:
            path.unlink()
        else:
            module.atomic_write(path, updated, metadata)
    if usb_link_needs_repair:
        link = root / USB_ENABLE_LINK
        link.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if link.is_dir() and not link.is_symlink():
            raise RuntimeError('USB 网络服务启用路径是目录，拒绝替换。')
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(USB_ENABLE_TARGET)
    wants = root / 'etc/systemd/system/multi-user.target.wants'
    wants.mkdir(mode=0o755, parents=True, exist_ok=True)
    link = wants / 'microduck-setup.service'
    if not link.is_symlink() and not link.exists():
        link.symlink_to('../microduck-setup.service')
    if live and (usb_link_needs_repair
                 or any(name in {UNIT, USB_UNIT} for name, *_ in changes)):
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
    _, remaining, _, link_still_needs_repair = check(root)
    if remaining or link_still_needs_repair:
        unresolved = ['/'+row[0] for row in remaining]
        if link_still_needs_repair:
            unresolved.append('/'+USB_ENABLE_LINK)
        raise RuntimeError('系统联网组件安装后读回不一致：' + '、'.join(unresolved))
    return {'repair': REVISION, 'wifi': 'R10-boot-connect-or-hotspot',
            'boot': boot['status'], 'boot_detail': boot.get('detail'),
            'changed': ['/' + row[0] for row in changes]
                       + (['/' + USB_ENABLE_LINK] if usb_link_needs_repair else []),
            'wifi_restarted': False, 'motion_commands_sent': False,
            'readback_verified': True, 'portal_import_verified': True,
            'usb_ethernet': 'installed; activates on next reboot',
            'hotspot_dependency': dependency,
            'effective': 'next reboot; installation does not restart the current network'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--prepare-dependencies', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.prepare_dependencies:
        if root != Path('/') or os.geteuid() != 0:
            parser.error('热点依赖需在目标 Zero 上使用 sudo 安装。')
        result = {'repair': REVISION, 'hotspot_dependency': prepare_hotspot_dependencies()}
    elif args.check:
        _, changes, boot, usb_link_needs_repair = check(root)
        result = {'repair': REVISION, 'boot': boot['status'],
                  'wifi': 'needs-install' if changes else 'already-installed',
                  'usb_ethernet': 'needs-install' if changes or usb_link_needs_repair else 'installed',
                  'changed': []}
    else:
        if root == Path('/') and os.geteuid() != 0:
            parser.error('请使用 sudo 安装系统修复')
        result = apply(root, live=root == Path('/'))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
