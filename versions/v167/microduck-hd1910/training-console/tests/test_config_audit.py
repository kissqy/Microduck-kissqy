"""Exercise the audit against real serialized Entity compilations, offline."""
import copy
import json
import math
from pathlib import Path
import unittest

from training.config_audit import audit_configuration
from training.official_spec import TASKS

ROOT = Path(__file__).resolve().parents[1]
WALK = 'Mjlab-Velocity-Flat-MicroDuck'
BACKLASH = 'Mjlab-Velocity-Flat-Backlash-MicroDuck'
ROLLER = 'Mjlab-Velocity-Flat-MicroDuck-Rollers'


def fixture(task=WALK):
    return json.loads((ROOT/'data/task-configs'/(task+'.json')).read_text())['inspection']


class ConfigurationAuditTests(unittest.TestCase):
    def assert_error(self, task, data, code):
        report = audit_configuration(task, data, strict=False)
        json.dumps(report, allow_nan=False)
        self.assertIn(code, [e['code'] for e in report['errors']])
        with self.assertRaises(ValueError) as error:
            audit_configuration(task, data)
        self.assertEqual(error.exception.report, report)

    def test_compiled_fixture_is_audited_without_mutation_or_engine_import(self):
        data = fixture();before = copy.deepcopy(data)
        report = audit_configuration(WALK, data)
        self.assertEqual(data, before)
        self.assertTrue(report['passed'])
        self.assertEqual(report['joint_mapping']['compiled_nu'], 14)
        self.assertEqual(report['timing']['control_hz'], 50)
        self.assertIn('no reset/step', report['validation_scope'])
        json.dumps(report, allow_nan=False)

    def test_all_catalog_entries_have_actual_compiled_configuration_evidence(self):
        for task in TASKS:
            with self.subTest(task=task):
                report = audit_configuration(task, fixture(task))
                self.assertTrue(report['passed'])
                self.assertEqual(report['timing']['control_hz'], 50)
                self.assertGreater(report['body_physics']['total_mass_kg'], 0)
                self.assertTrue(report['body_physics']['bodies'])
                json.dumps(report, allow_nan=False)

    def test_structural_mapping_failures_are_not_hidden_by_matching_shapes(self):
        for case in ('nu', 'order', 'frequency', 'last_action', 'head_padding', 'selection', 'selection_slice', 'clip'):
            with self.subTest(case=case):
                data=fixture();env=data['full']['env'];terms=env['observations']['actor']['terms']
                if case=='nu':data['model']['entity_compiled']['nu']=15;code='compiled_action_count'
                elif case=='order':
                    active=[j for j in data['model']['joints'] if j['type']==3 and not j['name'].startswith('passive_')]
                    active[0]['name'],active[1]['name']=active[1]['name'],active[0]['name'];code='joint_order'
                elif case=='frequency':env['decimation']=2;code='control_frequency'
                elif case=='last_action':terms['actions']['func']={'callable':'custom.filtered_action'};code='actor_semantics'
                elif case=='head_padding':terms['head_command']={'func':{'callable':'mdp.zero_command_padding'},'params':{'dim':3}};code='command_mapping'
                elif case=='selection':terms['joint_pos']['params']['asset_cfg']['joint_names']=['left_.*'];code='actor_joint_mapping'
                elif case=='selection_slice':terms['joint_pos']['params']['asset_cfg']['joint_ids']={'slice':[0,5,None]};code='actor_joint_mapping'
                else:env['actions']['joint_pos']['clip']=[-1,1];code='action_clipping_or_offset'
                self.assert_error(WALK,data,code)

    def test_backlash_requires_geometry_encoder_and_actuator_feedback_together(self):
        data=fixture(BACKLASH)
        self.assertTrue(audit_configuration(BACKLASH,data)['passed'])
        row=next(j for j in data['model']['joints'] if j['name'].endswith('_backlash'))
        row['range']=[-math.pi/90,math.pi/90]
        self.assert_error(BACKLASH,data,'backlash_range')
        data=fixture(BACKLASH)
        data['full']['env']['observations']['actor']['terms']['joint_pos']['func']={'callable':'mdp.joint_pos_rel'}
        self.assert_error(BACKLASH,data,'backlash_encoder')
        data=fixture(BACKLASH);data['model']['actuators'][0]['implementation']='Hd1910BamActuatorCfg'
        self.assert_error(BACKLASH,data,'backlash_actuator_feedback')

    def test_roller_name_cannot_hide_a_wheelless_model(self):
        data=fixture(ROLLER)
        self.assertTrue(audit_configuration(ROLLER,data)['rollers']['passive_wheels'])
        data['model']['joints']=[j for j in data['model']['joints'] if 'wheel' not in j['name']]
        self.assert_error(ROLLER,data,'missing_wheels')

    def test_tuning_remains_editable_and_motor_friction_is_not_contact_friction(self):
        data=fixture();data['full']['env']['actions']['joint_pos']['scale']=.76
        data['model']['actuators'][0]['kp_fw']=6.
        report=audit_configuration(WALK,data)
        self.assertEqual(report['actions']['joint_pos']['scale'],.76)
        self.assertEqual(report['bam_motor_friction']['actuators'][0]['kp_fw'],6.)
        foot=report['contact_friction']['configured_randomization']['foot_friction']
        self.assertEqual(foot['params']['ranges'],[.7,1.3])
        self.assertEqual(foot['effective_axes'],[0])
        self.assertEqual(foot['mode'],'startup')
        self.assertFalse(foot['sampled_values_available'])
        self.assertIn('randomize_joint_friction',report['bam_motor_friction']['configured_randomization'])
        self.assertNotIn('randomize_joint_friction',report['contact_friction']['configured_randomization'])

    def test_numerically_invalid_physics_fails_before_training(self):
        for case in ('p', 'delay', 'contact', 'random_range', 'mass', 'inertia'):
            with self.subTest(case=case):
                data=fixture()
                if case=='p':data['model']['actuators'][0]['kp_fw']=float('nan');code='invalid_actuator_value'
                elif case=='delay':data['model']['actuators'][0]['delay_max_lag']=-1;code='invalid_delay'
                elif case=='contact':data['model']['entity_compiled']['geoms'][0]['friction']=[1,-.01,.001];code='invalid_contact_friction'
                elif case=='random_range':data['full']['env']['events']['foot_friction']['params']['ranges']=[1.3,.7];code='invalid_friction_randomization'
                elif case=='mass':data['model']['total_mass_kg']=0;code='invalid_robot_mass'
                else:data['model']['bodies'][0]['inertia'][0]=float('inf');code='invalid_body_inertia'
                self.assert_error(WALK,data,code)

    def test_home_edit_is_preserved_but_not_claimed_runtime_compatible(self):
        data=fixture();joint=next(j for j in data['model']['joints'] if j['name']=='left_hip_yaw')
        joint['home_rad']=.1
        report=audit_configuration(WALK,data)
        self.assertTrue(report['passed'])
        self.assertFalse(report['runtime_structure_compatible'])
        self.assertEqual(report['joint_mapping']['home_rad'][0],.1)

    def test_override_receipt_records_actual_value_and_mismatch(self):
        data=fixture();request={'studio_recipe':{'task_overrides':{WALK:[
            {'path':['env','actions','joint_pos','scale'],'value':.9},
            {'path':['env','decimation'],'value':4}]}}}
        report=audit_configuration(WALK,data,request)
        self.assertEqual(report['requested_overrides'][0]['resolved'],1.)
        self.assertFalse(report['requested_overrides'][0]['matches'])
        self.assertTrue(report['requested_overrides'][1]['matches'])

    def test_servo_space_rewards_reject_interleaved_wheel_indices(self):
        data=fixture(ROLLER)
        data['full']['env']['rewards']['bad_pose']={'func':{'callable':'mjlab_microduck.tasks.mdp.pose_target_match'},
            'weight':1.,'params':{'joint_indices':[0,1,2,3,4,11,12,13,14,15]}}
        self.assert_error(ROLLER,data,'servo_reward_index')
        data['full']['env']['rewards']['bad_pose']['params']['joint_indices']=[0,1,2,3,4,9,10,11,12,13]
        self.assertTrue(audit_configuration(ROLLER,data)['passed'])


if __name__=='__main__':
    unittest.main()
