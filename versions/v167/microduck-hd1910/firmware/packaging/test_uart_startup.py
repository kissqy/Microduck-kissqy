"""Exercise the startup handshake that failed on the physical upgrade."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock,patch
import runtime
from release_identity import BUILD
spec=importlib.util.spec_from_file_location('uart_startup',Path(__file__).with_name('uart-service.py'))
uart=importlib.util.module_from_spec(spec);spec.loader.exec_module(uart)

class StartupTests(unittest.TestCase):
 def test_same_identity_releases_barrier_only_after_settings_readback(self):
  self.assertEqual(uart.BUILD,runtime.BUILD)
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);trigger=root/'fifo';trigger.write_text('8\n');boot=root/'boot';boot.write_text('current-boot')
   affinity=root/'irq/42/smp_affinity_list';affinity.parent.mkdir(parents=True);affinity.write_text('0-3\n')
   record=Mock();loader=Mock();module=SimpleNamespace(record=record)
   bus={'build':BUILD,'mode':'commissioning','phase':'configuring_uart'}
   def reply(pid,method='robot.busStatus'):
    self.assertEqual(pid,123)
    if method=='robot.uartConfigured':
     self.assertEqual(trigger.read_text().strip(),'1');self.assertEqual(affinity.read_text().strip(),'3')
     return {'accepted':True}
    return bus
   with patch.object(uart,'STATE',root/'state.json'),patch.object(uart,'TRIGGER',trigger),patch.object(uart,'BOOT',boot),patch.object(uart,'IRQ_ROOT',root/'irq'),patch.object(uart,'identify',return_value=(42,'verified')),patch.object(uart,'cached_bus',side_effect=reply) as rpc,patch('importlib.util.spec_from_file_location',return_value=SimpleNamespace(loader=loader)),patch('importlib.util.module_from_spec',return_value=module):
    uart.apply(123,'commissioning');self.assertEqual(uart.load_state()['last_applied']['pid'],123)
   self.assertEqual(rpc.call_count,2);record.assert_called_once()
 def test_wrong_build_is_an_explicit_error_and_never_changes_fifo(self):
  with patch.object(uart,'cached_bus',return_value={'build':'1fa8438-feetech-ft6-control.1','mode':'commissioning','phase':'configuring_uart'}),patch.object(uart,'identify',side_effect=AssertionError('no hardware write')):
   with self.assertRaisesRegex(ValueError,'配套版本不一致'):uart.apply(123,'commissioning')

if __name__=='__main__':unittest.main()
