import importlib.util
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch
from configure import dumps

spec=importlib.util.spec_from_file_location('calibration_config',Path(__file__).with_name('calibration-config.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class CalibrationMigrationTests(unittest.TestCase):
    def test_retires_only_unused_fields_and_preserves_actual_calibration(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cal.toml'
            data=tomllib.loads(Path(__file__).with_name('hd1910-calibration.template.toml').read_text())
            data.update(command_acceleration_raw=64,command_speed_raw=100,speed_rad_s_per_count=0.0)
            data['joints'][0]['zero_raw']=2035
            data['imu_mount_quat']=[1.,0.,0.,0.]
            p.write_text(dumps(data))
            expected={k:v for k,v in data.items() if k not in module.RETIRED_FIELDS}
            self.assertEqual(module.migrate(p),list(module.RETIRED_FIELDS))
            self.assertEqual(tomllib.loads(p.read_text()),expected)
            before=p.read_bytes();self.assertEqual(module.migrate(p),[]);self.assertEqual(p.read_bytes(),before)
    def test_failed_atomic_replace_keeps_original_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cal.toml';p.write_text('command_speed_raw = 100\n')
            before=p.read_bytes()
            with patch.object(module.os,'replace',side_effect=OSError('simulated disk failure')):
                with self.assertRaises(OSError):module.migrate(p)
            self.assertEqual(p.read_bytes(),before)
            self.assertEqual(list(Path(d).iterdir()),[p])
