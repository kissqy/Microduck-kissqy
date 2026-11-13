import hashlib
import importlib.util
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
            self.assertFalse(any('systemctl' in str(call) for call in runner.call_args_list))
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
