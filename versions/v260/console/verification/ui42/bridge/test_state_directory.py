"""Installer-only test: no services/devices, and an existing clip is preserved."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

STAGE=Path('/workspace/scratch/0587ce872ec5/ui42_firmware_stage/Microduck-Robotd-FT6-R17')
sys.path.insert(0,str(STAGE))
spec=importlib.util.spec_from_file_location('ui42_gamepad_install',STAGE/'gamepad.py')
gamepad=importlib.util.module_from_spec(spec);spec.loader.exec_module(gamepad)

class StateDirectoryTests(unittest.TestCase):
    def test_upgrade_retains_last_recording_and_declares_writable_persistent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);base=root/'opt/robot/feetech-ft5-r5';base.mkdir(parents=True)
            (base/'padd.service').write_bytes((STAGE/'padd.service').read_bytes())
            last=root/'var/lib/padd/recordings/last.json';last.parent.mkdir(parents=True)
            original=b'{"fixture":"previous manual recording"}\n';last.write_bytes(original)
            drive_path=root/'drive.json';drive_path.write_text('{}')
            settings_path=root/'pad.json';settings_path.write_text('{}')
            fake_drive=SimpleNamespace(PATH=drive_path,load=lambda:.3)
            commands=[]
            with patch.object(gamepad,'ROOT',root),patch.object(gamepad,'BASE',base),\
                 patch.object(gamepad,'SETTINGS_PATH',settings_path),\
                 patch.object(gamepad,'load',return_value={'head_rad':2.5}),\
                 patch.object(gamepad,'run',side_effect=lambda *a,**kw:commands.append(a)),\
                 patch.dict(sys.modules,{'drive_settings':fake_drive}):
                for _ in range(2):gamepad.upgrade_client(deferred=True)
            self.assertEqual(last.read_bytes(),original)
            unit=(root/'etc/systemd/system/padd.service').read_text()
            dropin=(root/gamepad.PAD_DROPIN).read_text()
            self.assertIn('\nStateDirectory=padd\n',unit)
            self.assertIn('\nStateDirectory=padd\n',dropin)
            self.assertIn('\nRuntimeDirectory=padd\n',dropin)
            self.assertIn('ProtectSystem=strict',unit)
            self.assertNotIn('record-play',unit+dropin)
            self.assertNotIn('last.json',unit+dropin)
            self.assertFalse(any(cmd[:2]==('systemctl','restart') for cmd in commands))
            self.assertEqual([path.name for path in last.parent.iterdir()],['last.json'])

if __name__=='__main__':unittest.main()
