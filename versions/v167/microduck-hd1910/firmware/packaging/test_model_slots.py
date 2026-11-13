"""All current native action slots remain explicit in the built-in catalog."""
import io,json,shutil,tempfile,time,tomllib,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import model_packages as models,runtime
from configure import dumps
from service_control import ServiceController,ControlError,validate
ROOT=Path(__file__).resolve().parents[1]
class SlotTests(unittest.TestCase):

 def test_all_native_actions_including_empty_are_explicit(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);(b/'models').mkdir();cfg=b/'robotd.toml';cfg.write_text('[policy]\n')
   data=models.catalog(b,cfg)
   self.assertEqual([r['slot'] for r in data['slots']],list(models.SLOTS))
   self.assertTrue(all(r['model'] is None and ' / ' in r['label'] for r in data['slots']))
if __name__=='__main__':unittest.main()
