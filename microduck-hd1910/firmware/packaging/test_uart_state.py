import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('uart_state_test',Path(__file__).with_name('uart-service.py'))
uart=importlib.util.module_from_spec(spec);spec.loader.exec_module(uart)

class UartCacheTests(unittest.TestCase):
 def test_bad_cache_fails_for_complete_service_rebuild(self):
  with tempfile.TemporaryDirectory() as tmp:
   uart.STATE=Path(tmp)/'state.json'
   for bad in (b'',b'\xff',b'{',b'[]',b'null'):
    uart.STATE.write_bytes(bad)
    with self.assertRaises((ValueError,UnicodeError)):uart.load_state()
    self.assertEqual(uart.STATE.read_bytes(),bad)
 def test_valid_state_round_trip_and_missing_state(self):
  with tempfile.TemporaryDirectory() as tmp:
   uart.STATE=Path(tmp)/'state.json'
   self.assertIsNone(uart.load_state())
   value={'boot_id':'test-boot','irq':42,'trigger_before':'8','affinity_before':'3'}
   uart.atomic_state(value)
   self.assertEqual(uart.load_state(),value)

if __name__=='__main__':unittest.main()
