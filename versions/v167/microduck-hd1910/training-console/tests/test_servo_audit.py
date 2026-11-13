"""Reference completeness, historical BAM honesty and real loaded parameters."""
import copy
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from training.official_spec import (ENGINE, REVISION, WALK, contract,
    normalize_model_recipe, ignored_legacy_bam_overrides)
from studio import fresh_recipe


class ServoAuditTests(unittest.TestCase):
    def test_every_reference_field_has_bilingual_help_and_usage(self):
        ref=json.loads((ROOT/'data/servo_references.json').read_text())
        base=json.loads((ROOT/'data/baseline_official0151.json').read_text())
        bam=json.loads((ROOT/'training/hd1910_m6.json').read_text())
        self.assertEqual(set(bam),set(ref['bam_fields']))
        cfg_fields=set(base['model']['actuators'][0])-{'parameter_file','runtime_properties'}
        self.assertEqual(cfg_fields,set(ref['actuator_fields']))
        for group in ('actuator_fields','bam_fields','runtime_fields'):
            for key,help_ in ref[group].items():
                self.assertTrue(any('\u4e00'<=c<='\u9fff' for c in help_['title']),key)
                for field in ('english','unit','explanation'):self.assertTrue(help_[field],(key,field))
        regs=ref['registers'];self.assertEqual(len(regs),110)
        self.assertEqual(len({r['address'] for r in regs}),len(regs))
        self.assertEqual(next(r for r in regs if r['address']==84)['default'],400)
        for r in regs:self.assertTrue(r['title'] and r['english'] and r['usage'])
        self.assertIn('未使用',ref['bam_fields']['command_delay']['usage'])
        self.assertIn('未使用',ref['bam_fields']['q_offset']['usage'])
        xl=ref['official_training']['actuators'][0]['runtime_properties']
        hd=base['model']['actuators'][0]['runtime_properties']
        self.assertEqual(xl['max_current'],1.75)
        self.assertIsNone(hd['max_current'])
        self.assertAlmostEqual(hd['duty_slope_per_rad'],5*.166*bam['error_gain_ratio'])

    def request(self,version):
        req={'engine':ENGINE,'baseline_pin':{'revision':REVISION},'task':WALK,
             'training_adapter_revision':version,'studio_recipe':fresh_recipe()}
        req['studio_recipe']['robot']['actuator_parameters']={'0':{'kt':.7}}
        return req

    def test_old_recorded_bam_edits_do_not_change_historical_physics(self):
        req=self.request('R1.5.2-sample-alignment-4096');before=copy.deepcopy(req)
        normalized=normalize_model_recipe(req)
        self.assertNotIn('actuator_parameters',normalized['robot'])
        self.assertEqual(req,before)
        self.assertTrue(ignored_legacy_bam_overrides(req))
        inspection=json.loads((ROOT/'data/task-configs'/(WALK+'.json')).read_text())['inspection']
        inspection['model']['actuators'][0]['parameter_file']['data']['kt']=.7
        old=contract(inspection,req)
        default=json.loads((ROOT/'training/hd1910_m6.json').read_text())
        self.assertEqual(old['actuators'][0]['parameters'],default)
        self.assertEqual(inspection['model']['actuators'][0]['parameter_file']['data']['kt'],.7)

    def test_new_edits_are_preserved_and_other_revisions_not_guessed(self):
        for revision in ('R1.5.3-servo-audit-0151-hd1910','unknown','R1.4.23-friction-dr-base'):
            req=self.request(revision)
            self.assertFalse(ignored_legacy_bam_overrides(req))
            self.assertEqual(normalize_model_recipe(req),req['studio_recipe'])


@unittest.skipUnless(os.environ.get('MICRODUCK_OFFICIAL_SOURCE'),'Pinned upstream not supplied')
class RealBamLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0,str(Path(os.environ['MICRODUCK_OFFICIAL_SOURCE'])/'src'))
        import mjlab.tasks, mjlab_microduck.tasks

    def test_describe_retains_all_teacher_fields_but_evaluation_loads_only_student(self):
        from mjlab.tasks.registry import load_env_cfg,load_rl_cfg
        from training.runtime_adapter import apply_recipe
        from training.official_spec import JOINT
        from training.recipe import plain,flatten
        from training.explanations import annotate_rows
        for op in ('describe','train','play','export'):
            cfg,agent=load_env_cfg(JOINT),load_rl_cfg(JOINT)
            apply_recipe(cfg,agent,{'engine':ENGINE,'op':op,'task':JOINT,'studio_recipe':fresh_recipe()})
            if op in ('describe','train'):
                self.assertEqual(agent.algorithm.bc_cfg['gate_tilt_deg'],35)
                self.assertEqual(agent.algorithm.bc_cfg['anchor_tilt_deg'],25)
                rows=annotate_rows(list(flatten({'agent':plain(agent)})))
                self.assertFalse([r['path'] for r in rows if r['help'].get('documentation_missing')])
            else:self.assertIsNone(agent.algorithm.bc_cfg)

    def test_loaded_model_and_compiled_inertia_follow_edits(self):
        from mjlab.tasks.registry import load_env_cfg,load_rl_cfg
        from training.runtime_adapter import apply_recipe
        from training.recipe import model_details
        from bam.model import load_model
        cfg,agent=load_env_cfg(WALK),load_rl_cfg(WALK)
        recipe=fresh_recipe();recipe['robot']['actuator_parameters']={'0':{'kt':.7,'armature':.0022}}
        apply_recipe(cfg,agent,{'engine':ENGINE,'op':'describe','task':WALK,'studio_recipe':recipe})
        act=cfg.scene.entities['robot'].articulation.actuators[0]
        self.assertEqual(Path(act.json_path),Path(act._resolved_json_path))
        loaded=load_model(act._resolved_json_path)
        self.assertEqual(loaded.kt.value,.7)
        details=model_details(cfg);runtime=details['actuators'][0]['runtime_properties']
        self.assertEqual(runtime['kt'],.7)
        self.assertEqual(runtime['armature'],.0022)
        self.assertAlmostEqual(runtime['compiled_force_limit_nm'],8*.7/loaded.R.value)
        active=[j for j in details['entity_compiled']['joints'] if j['joint']=='left_knee']
        self.assertEqual(active[0]['armature'],.0022)


if __name__=='__main__':unittest.main()
