import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('runtime_identity',ROOT/'runtime.py')
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)

class IdentityTests(unittest.TestCase):
 def test_current_identity_and_no_restart_or_audio_failure_hooks(self):
  self.assertEqual(runtime.BUILD,__import__('json').loads((ROOT.parent/'BUILD.json').read_text())['build'])
  for mode in ('motion','commissioning'):
   unit=runtime.unit(mode)
   self.assertNotIn('rebuild-config.py',unit)
   self.assertNotIn('voice-setup.py',unit)
   self.assertIn('Restart=no',unit)
   self.assertIn('--uart-setup',unit)
   self.assertNotIn('verify-service',unit)

if __name__=='__main__':unittest.main()
