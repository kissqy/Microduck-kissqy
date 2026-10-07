"""Read-only management results must survive diagnostics on the warm relay."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

from controls import ControlError
from service_control import ServiceTransport
from system_log import SystemLog


class ManagementReadbackTests(unittest.TestCase):
    def test_catalog_json_survives_stderr_and_same_warm_process_reads_again(self):
        catalog = {'models': [{'slot': 'walk', 'id': 'walk-id'}],
                   'management_actions': ['advanced-parameters'],
                   'default_servo_parameters': {'kp': 3, 'kd': 0, 'torque_limit': 681}}
        script = "import sys;print('startup diagnostic',file=sys.stderr);print(sys.argv[1])"
        with tempfile.TemporaryDirectory() as directory:
            log = SystemLog(directory)
            transport = ServiceTransport('', '/unused', log)
            try:
                for _ in range(2):
                    result = transport._manage([sys.executable, '-c', script, json.dumps(catalog)], privileged=False)
                    self.assertEqual(result, catalog)
                    if _ == 0: process = transport.channel.proc
                    else: self.assertIs(transport.channel.proc, process)
                log.flush()
                self.assertIn('startup diagnostic', log.path.read_text())
            finally:
                transport.channel.close()
                log.close()

    def test_failed_command_keeps_actual_stderr_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            log = SystemLog(directory)
            transport = ServiceTransport('', '/unused', log)
            try:
                with self.assertRaisesRegex(ControlError, 'missing saved configuration'):
                    transport._manage([sys.executable, '-c',
                        "import sys;print('ordinary progress');print('missing saved configuration',file=sys.stderr);sys.exit(1)"], privileged=False)
                log.flush()
                self.assertIn('ordinary progress', log.path.read_text())
            finally:
                transport.channel.close()
                log.close()


if __name__ == '__main__':
    unittest.main()
