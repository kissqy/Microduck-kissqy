"""Out-of-catalog task settings cannot block roller task submissions."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import training_console as tc
from studio import fresh_recipe
from training.official_spec import TASKS, CATALOG
ROOT=Path(__file__).resolve().parents[1]
ROLLER='Mjlab-Velocity-Flat-MicroDuck-Rollers'
BACKLASH='Mjlab-Velocity-Flat-Backlash-MicroDuck-Rollers'
UNAVAILABLE='Mjlab-Archived-Flat-MicroDuck'
UNAVAILABLE_BL='Mjlab-Archived-Flat-Backlash-MicroDuck'
class RecipeSyncTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.patch=patch.object(tc.BaseTrainingManager,'_run');self.patch.start();self.addCleanup(self.patch.stop)
  self.path=Path(self.tmp.name)
 def manager(self):
  m=tc.TrainingManager(self.path);self.addCleanup(m.close);return m
 def test_old_saved_recipe_discards_missing_tasks_without_backup(self):
  old=fresh_recipe();old['version']=22
  old['task_overrides']={UNAVAILABLE:[],UNAVAILABLE_BL:[{'path':['env','rewards','upright','weight'],'value':3}],ROLLER:[]}
  (self.path/'recipe.json').write_text(json.dumps(old),encoding='utf-8')
  m=self.manager()
  self.assertEqual(m.recipe['version'],23)
  self.assertEqual(m.recipe['task_overrides'],{ROLLER:[]})
  self.assertFalse((self.path/'recipe-before-retired-tasks.json').exists())
  self.assertTrue(m.save_recipe({'recipe':m.recipe})['okay'])
  for task in (ROLLER,BACKLASH):
   eid=m.queue_add({'task':task,'client_id':task})['entry_id']
   entry=next(e for e in m.training_queue['entries'] if e['id']==eid)
   self.assertEqual(entry['request']['training_action_scale'],1)
   self.assertEqual(entry['request']['training_firmware_p'],5)
  self.assertFalse(m.jobs)
 def test_stale_browser_tab_can_post_retired_key(self):
  m=self.manager();old=copy.deepcopy(m.recipe);old['task_overrides']={UNAVAILABLE:[],BACKLASH:[]}
  result=m.save_recipe({'recipe':old})
  self.assertTrue(result['okay'])
  self.assertNotIn(UNAVAILABLE,result['recipe']['task_overrides'])
  self.assertIn(BACKLASH,m.recipe['task_overrides'])
  m.queue_add({'task':BACKLASH,'client_id':'stale-tab'})
 def test_invalid_unknown_keys_and_types_remain_rejected(self):
  m=self.manager()
  for invalid in ({'Unknown-Task':[]},{ROLLER:1},[]):
   with self.subTest(invalid=invalid),self.assertRaisesRegex(ValueError,'动作参数'):
    m.save_recipe({'recipe':{**m.recipe,'task_overrides':invalid}})
 def test_roller_official_parameters_unchanged(self):
  self.assertEqual(CATALOG['version'],'1.5.27')
  catalog=json.loads((ROOT/'data/tasks.json').read_text())
  self.assertEqual(CATALOG,catalog)
  for task,backlash in ((ROLLER,False),(BACKLASH,True)):
   with self.subTest(task=task):
    s=json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text())['inspection']
    e=s['full']['env'];a=s['full']['agent']
    self.assertEqual(TASKS[task]['iterations'],50000)
    self.assertEqual(e['actions']['joint_pos']['scale'],1.0)
    self.assertIsNone(e['actions']['joint_pos']['clip'])
    self.assertEqual(e['commands']['twist']['ranges']['lin_vel_x'],[-.5,.6])
    self.assertEqual(e['commands']['twist']['ranges']['lin_vel_y'],[0.,0.])
    self.assertEqual(e['commands']['twist']['ranges']['ang_vel_z'],[0.,0.])
    self.assertEqual(a['max_iterations'],50000)
    self.assertEqual(a['num_steps_per_env'],24)
    self.assertEqual(a['algorithm']['entropy_coef'],.03)
    self.assertEqual([x['step'] for x in e['curriculum']['wheel_friction']['params']['ranges_stages']],[0,48000,84000,120000])
    self.assertEqual(s['model']['gear_backlash']['enabled'],backlash)
if __name__=='__main__':unittest.main()
