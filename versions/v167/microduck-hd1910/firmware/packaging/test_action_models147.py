"""Current unfiltered action exports keep their original contracts and legacy support."""
import copy
import hashlib
import json
import shutil
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

import model_packages as models
from configure import dumps

ROOT=Path(__file__).resolve().parents[1]
IDS={'roulade':'59e15d7b04d0c40e9b11b8a70bdecae6',
     'ground_pick':'b14e3a8b56ddbb8d2d831e727774a168'}
TASKS={'roulade':'Mjlab-Roulade-Flat-MicroDuck',
       'ground_pick':'Mjlab-GroundPick-Flat-Backlash-MicroDuck'}

class ActionExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original={slot:{name:(ROOT/'policies'/slot/name).read_bytes()
                            for name in ('policy.onnx',*models.SOURCE_FILES)
                            if (ROOT/'policies'/slot/name).is_file()} for slot in IDS}

    def changed(self,slot,change):
        files=self.original[slot].copy();contract=json.loads(files['deployment-contract.json'])
        change(contract);files['deployment-contract.json']=json.dumps(contract).encode()
        return files

    def test_genuine_new_exports_need_no_contract_rewrite_or_legacy_ema_field(self):
        for slot,files in self.original.items():
            with self.subTest(slot=slot):
                before=files.copy();info=models.validate_export(files);contract=info['contract']
                self.assertEqual(files,before);self.assertEqual(info['id'],IDS[slot])
                self.assertEqual(hashlib.sha256(files['policy.onnx']).hexdigest()[:32],IDS[slot])
                self.assertEqual(info['task'],TASKS[slot]);self.assertEqual(info['slot'],slot)
                self.assertNotIn('action_ema_old_weight',contract)
                self.assertFalse(contract['action_filter']['enabled'])
                self.assertEqual(info['policy_settings'],contract['required_policy_settings'])
                self.assertNotIn('action_scale',info['policy_settings'])
                self.assertNotIn('execution_profile',info)
                request=json.loads(files['training-request.json'])
                self.assertEqual(request['source_iteration'],9999)
                self.assertEqual(request['policy_parameters']['training_action_scale'],1.0)

    def test_ground_pick_phase_and_roulade_window_are_preserved(self):
        pick=models.validate_export(self.original['ground_pick'])
        manifest=json.loads(self.original['ground_pick']['manifest.json'])
        self.assertEqual(pick['policy_settings']['ground_pick_period'],4.0)
        self.assertEqual(manifest['command']['end_phase'],.7)
        self.assertEqual(manifest['duration_s'],2.8);self.assertFalse(manifest['chain'])
        roll=models.validate_export(self.original['roulade'])
        self.assertEqual(roll['skill'],{'name':'roulade','duration':1.0,'chain':True,
                         'command':[0.,0.,0.],'unwind':[0.,0.,0.],'unwind_s':0.,
                         'params':{'action_scale':1.0,'gain_ratio':1.0}})

    def test_legacy_deployed_action_contracts_remain_loadable(self):
        for directory,slot,ident in (
                ('ground-pick-legacy','ground_pick','2b69fa681ed06f7ded9e2a2d12ba5c67'),
                ('roulade-legacy','roulade','8fdaf12c7478a8314a63647a466bfa34')):
            with self.subTest(slot=slot):
                info=models.verify_directory(ROOT/'test-data'/directory)
                self.assertEqual(info['id'],ident);self.assertEqual(info['slot'],slot)
                self.assertNotIn('policy_settings',info)
                self.assertIn('action_ema_old_weight',info['contract'])

    def test_backlash_observation_selection_is_independent_of_target_filter(self):
        for slot in IDS:
            for key in ('joint_pos','joint_vel'):
                for suffix in ('_rel_backlash' if slot=='roulade' else '_rel',
                               '_rel_backlash_fake' if slot=='ground_pick' else '_rel_fake'):
                    changed=self.changed(slot,lambda c:c['observations']['terms'][key]['func'].update(callable='module.'+key+suffix))
                    with self.subTest(slot=slot,key=key,suffix=suffix),self.assertRaisesRegex(ValueError,'相对 HOME'):
                        models.validate_export(changed)
                suffix='_rel_backlash' if slot=='ground_pick' else '_rel'
                changed=self.changed(slot,lambda c:c['observations']['terms'][key]['func'].update(callable='module.fake_'+key+suffix))
                with self.subTest(slot=slot,key=key,prefix='fake'),self.assertRaisesRegex(ValueError,'相对 HOME'):
                    models.validate_export(changed)

    def test_current_scale_is_task_specific_and_cannot_use_walk_global_scale(self):
        for slot in IDS:
            scale_key=slot+'_action_scale'
            for value in (True,None,.7,float('nan')):
                files=self.changed(slot,lambda c:c['required_policy_settings'].update({scale_key:value,'action_scale':1.0}))
                with self.subTest(slot=slot,value=value),self.assertRaisesRegex(ValueError,'缩放合同'):
                    models.validate_export(files)
            files=self.changed(slot,lambda c:c['required_policy_settings'].pop(scale_key))
            with self.subTest(slot=slot),self.assertRaisesRegex(ValueError,'缩放合同'):
                models.validate_export(files)

    def test_roulade_current_revision_cannot_downgrade_to_legacy_ema_semantics(self):
        for mutation in ('null_filter','remove_filter','remove_revision','null_revision'):
            def change(c):
                c['action_ema_old_weight']=0.0
                if mutation=='null_filter':c['action_filter']=None
                elif mutation=='remove_filter':c.pop('action_filter')
                elif mutation=='remove_revision':
                    c.pop('export_contract_revision');c['action_filter']=None
                else:
                    c['export_contract_revision']=None;c.pop('action_filter')
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                models.validate_export(self.changed('roulade',change))

    def test_new_action_filter_fields_and_ema_are_validated(self):
        for slot in IDS:
            for part,key,value in [('action_filter','head_alpha',.5),('action_filter','legs_alpha',True),
                                   ('action_filter','enabled',1),('action_filter','version',True),
                                   ('action_filter','previous_action_observation','filtered_target'),
                                   ('required_policy_settings','head_lowpass',True),
                                   ('required_policy_settings','legs_lowpass',.7)]:
                with self.subTest(slot=slot,key=key),self.assertRaises(ValueError):
                    models.validate_export(self.changed(slot,lambda c:c[part].update({key:value})))
            for value in (None,True,.2,float('nan')):
                with self.subTest(slot=slot,ema=value),self.assertRaises(ValueError):
                    models.validate_export(self.changed(slot,lambda c:c.update(action_ema_old_weight=value)))
            for alpha in ('head_alpha','legs_alpha'):
                with self.subTest(slot=slot,trained_alpha=alpha),self.assertRaises(ValueError):
                    models.validate_export(self.changed(slot,lambda c:c['actions']['joint_pos'].update({alpha:True})))

    def test_pick_training_and_required_period_must_agree(self):
        for value in (None,True,0,2.8,float('inf')):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'周期'):
                models.validate_export(self.changed('ground_pick',lambda c:c['required_policy_settings'].update(ground_pick_period=value)))
        with self.assertRaisesRegex(ValueError,'周期'):
            models.validate_export(self.changed('ground_pick',lambda c:c['commands']['twist'].update(period=2.0)))

    def test_only_exact_supported_task_names_are_accepted(self):
        for slot,task in (('ground_pick','Mjlab-GroundPick-Rough-Backlash-MicroDuck'),
                          ('ground_pick',TASKS['ground_pick']+'-Other'),
                          ('roulade','Mjlab-Roulade-Flat-Backlash-MicroDuck')):
            files=self.changed(slot,lambda c:c.update(task=task))
            manifest=json.loads(files['manifest.json']);manifest['task']=task
            files['manifest.json']=json.dumps(manifest).encode()
            with self.subTest(task=task),self.assertRaises(ValueError):models.validate_export(files)


    def test_release_has_only_current_action_models_and_preserves_other_model_ids(self):
        rows=[models.verify_directory(ROOT/'packaging/models'/r['id'] if r['slot']=='kick_right' else ROOT/'policies'/r['slot']) for r in models.PROFILE['builtin_models']]
        self.assertEqual(len(rows),5)
        self.assertEqual({r['slot']:r['id'] for r in rows},
                         {**IDS,'walk':'1cbf8730eadd75a5704332c9f3c10f60',
                          'kick_right':'67ad09d82f4865d222a7ae06f250cf9f',
                          'sitstand':'1c94934c6421ec72ed48079cea749668'})

if __name__=='__main__':unittest.main()
