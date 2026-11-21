import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_support import FW, PC

spec = importlib.util.spec_from_file_location('v230_system_install', FW / 'system-repair/install-system-repair.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class SystemInstallTests(unittest.TestCase):
    def test_usb_ethernet_install_is_idempotent_and_preserves_user_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            wifi_dir = root / 'etc/NetworkManager/system-connections'
            wifi_dir.mkdir(parents=True)
            home_wifi = wifi_dir / 'home.nmconnection'
            home_wifi.write_bytes(b'[wifi]\nssid=keep-this-ssid-fixture\npsk=keep-this-psk-fixture\n')
            home_wifi_before = home_wifi.read_bytes()
            wifi_policy = root / 'etc/NetworkManager/conf.d/99-robot-wifi-only.conf'
            wifi_policy.parent.mkdir(parents=True)
            wifi_policy.write_bytes(b'[keyfile]\nunmanaged-devices=*,except:type:wifi\n')
            wifi_policy_before = wifi_policy.read_bytes()

            r10 = root / 'etc/systemd/system/microduck-setup.service'
            r10.parent.mkdir(parents=True)
            r10.write_bytes((installer.HERE / 'microduck-setup.service').read_bytes())
            r10_before = r10.read_bytes()
            ssh_keys = root / 'home/radxa/.ssh/authorized_keys'
            ssh_keys.parent.mkdir(parents=True)
            ssh_keys.write_bytes(b'fixture-user-key-marker\n')
            ssh_keys_before = ssh_keys.read_bytes()
            model = root / 'opt/robot/models/walk/policy.onnx'
            model.parent.mkdir(parents=True)
            model.write_bytes(b'fixture-model-weights')
            model_before = model.read_bytes()

            link = root / installer.USB_ENABLE_LINK
            link.parent.mkdir(parents=True)
            link.symlink_to('../wrong-usb-unit.service')
            self.assertTrue(installer.check(root)[3])

            result = installer.apply(root, live=False)
            self.assertTrue(result['readback_verified'])
            self.assertFalse(result['wifi_restarted'])
            self.assertEqual(os.readlink(link), installer.USB_ENABLE_TARGET)
            self.assertEqual(home_wifi.read_bytes(), home_wifi_before)
            self.assertEqual(wifi_policy.read_bytes(), wifi_policy_before)
            self.assertEqual(r10.read_bytes(), r10_before)
            self.assertEqual(ssh_keys.read_bytes(), ssh_keys_before)
            self.assertEqual(model.read_bytes(), model_before)

            expected = {
                installer.USB_GADGET: 0o755,
                installer.USB_UNIT: 0o644,
                installer.USB_PROFILE: 0o600,
                installer.USB_NM_POLICY: 0o644,
                installer.USB_UDEV_RULE: 0o644,
            }
            package_files = json.loads((installer.HERE.parent / 'install-files.json').read_text())
            self.assertTrue({
                'system-repair/90-microduck-usb-managed.rules',
                'system-repair/Microduck-USB.nmconnection',
                'system-repair/microduck-usb-gadget',
                'system-repair/microduck-usb-gadget.service',
                'system-repair/zzz-microduck-usb-network.conf',
            }.issubset(set(package_files)))
            for name, mode in expected.items():
                installed = root / name
                bundled = installer.HERE / Path(name).name
                self.assertEqual(installed.read_bytes(), bundled.read_bytes())
                self.assertEqual(installed.stat().st_mode & 0o7777, mode)

            self.assertIn(b'except:interface-name:usb0',
                          (root / installer.USB_NM_POLICY).read_bytes())
            self.assertIn('Before=network-pre.target NetworkManager.service',
                          (root / installer.USB_UNIT).read_text())

            second = installer.apply(root, live=False)
            self.assertEqual(second['changed'], [])
            self.assertFalse(installer.check(root)[3])

            link.unlink()
            self.assertEqual(installer.check(root)[3], True)
            repaired = installer.apply(root, live=False)
            self.assertIn('/' + installer.USB_ENABLE_LINK, repaired['changed'])
            self.assertEqual(os.readlink(link), installer.USB_ENABLE_TARGET)

    def test_install_is_idempotent_keeps_home_network_and_patches_boot_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / installer.BOOT_SCRIPT; target.parent.mkdir(parents=True)
            target.write_bytes((Path(__file__).parent / 'fixtures/armbian-hardware-optimization-26.2.1.sh').read_bytes())
            boot = root / installer.BOOT_ENV; boot.parent.mkdir(parents=True)
            boot.write_bytes(b'rootdev=UUID=fixture\nrootfstype=ext4\nusbstoragequirks=0x2537:0x1066:u,0x2537:0x1068:u\n')
            boot_before = boot.read_bytes()
            home = root / 'etc/NetworkManager/system-connections/home.nmconnection'
            home.parent.mkdir(parents=True); home.write_bytes(b'[wifi]\nssid=fixture\npsk=private-fixture\n')
            home_before = home.read_bytes()
            with patch.object(installer.subprocess, 'run', wraps=installer.subprocess.run) as runner:
                result = installer.apply(root, live=False)
            self.assertEqual(result['boot'], 'fixed')
            self.assertFalse(result['wifi_restarted'])
            self.assertEqual(home.read_bytes(), home_before)
            self.assertEqual(boot.read_bytes(), boot_before)
            network_commands = {'systemctl', 'nmcli', 'ip'}
            self.assertFalse(any(call.args and call.args[0][0] in network_commands
                                 for call in runner.call_args_list))
            portal = root / installer.PORTAL
            self.assertIn(b'_install_wifi_startup(globals())', portal.read_bytes())
            compile(portal.read_bytes(), str(portal), 'exec')
            before = portal.stat().st_mtime_ns
            again = installer.apply(root, live=False)
            self.assertEqual(again['boot'], 'already-fixed')
            self.assertEqual(again['changed'], [])
            self.assertEqual(portal.stat().st_mtime_ns, before)

    def test_console_expected_bytes_equal_installed_portal_and_module(self):
        sys.path.insert(0, str(PC))
        import hotspot_control
        raw = (FW / 'system-repair/microduck-public-image.sh').read_bytes()
        self.assertEqual(raw, (PC / 'resources/wifi-r5/microduck-public-image.sh').read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), hotspot_control.R5_SHA256)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            installer.apply(root, live=False)
            self.assertEqual((root / installer.PORTAL).read_bytes(), hotspot_control.r5_portal(raw))
            self.assertEqual((root / installer.R7_MODULE).read_bytes(),
                             (PC / 'resources/wifi-r5/microduck_wifi_r7.py').read_bytes())


if __name__ == '__main__': unittest.main()
