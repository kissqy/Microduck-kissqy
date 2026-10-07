"""Evaluation-only push dependency regression tests; no GPU/physics/real PT run."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import Mock, patch

from training import runtime_adapter as adapter

ROOT = Path(__file__).resolve().parents[1]
TASK = 'Mjlab-Velocity-Flat-MicroDuck'


def config():
    return NS(
        events={name: NS(params={}) for name in
                ('push_robot', 'reset_base', 'randomize_com', 'random_prone_init')},
        curriculum={
            'push_range': NS(params={'event_name': 'push_robot'}),
            'com_range': NS(params={'event_name': 'randomize_com'}),
            'prone_init_prob': NS(params={'event_name': 'random_prone_init'}),
            'standing_envs': NS(params={'command_name': 'twist'}),
            'action_rate_weight': NS(params={'reward_name': 'action_rate'}),
            'disabled_placeholder': None,
        },
        rewards={'action_rate': NS(weight=-1.0)},
        scene=NS(num_envs=32),
    )


def compute_event_curricula(cfg):
    """Reproduce the reported manager lookup contract, without faking physics."""
    active = {name: term for name, term in cfg.events.items() if term is not None}
    for term in cfg.curriculum.values():
        if term is None:
            continue
        event_name = (getattr(term, 'params', None) or {}).get('event_name')
        if event_name is not None and event_name not in active:
            raise ValueError("Event term '%s' not found in active terms." % event_name)


def module_for(cfg):
    return NS(load_env_cfg=Mock(side_effect=lambda *a, **k: copy.deepcopy(cfg)),
              load_rl_cfg=Mock(side_effect=lambda name: NS()))


class EvaluationDependencyTests(unittest.TestCase):
    def setUp(self):
        self.logs = patch.object(adapter, 'emit').start()
        self.addCleanup(patch.stopall)

    def test_reproduces_original_crash_then_cleans_orphan(self):
        cfg = config()
        cfg.events.pop('push_robot')  # R1.4.0's original evaluation action.
        with self.assertRaisesRegex(ValueError, "Event term 'push_robot'"):
            compute_event_curricula(cfg)
        self.assertIs(adapter.configure_evaluation_events(cfg, {'op': 'play'}), cfg)
        compute_event_curricula(cfg)
        self.assertNotIn('push_range', cfg.curriculum)

    def test_turn_off_removes_event_and_dependent_term(self):
        cfg = config()
        adapter.configure_evaluation_events(cfg, {'op': 'play', 'eval_pushes': False})
        self.assertNotIn('push_robot', cfg.events)
        self.assertNotIn('push_range', cfg.curriculum)
        compute_event_curricula(cfg)

    def test_matches_dependency_not_curriculum_key(self):
        cfg = config()
        cfg.curriculum['custom_push_stage'] = cfg.curriculum.pop('push_range')
        cfg.curriculum['push_curriculum'] = NS(params={'reward_name': 'keep_me'})
        adapter.configure_evaluation_events(cfg, {'op': 'play'})
        self.assertNotIn('custom_push_stage', cfg.curriculum)
        self.assertIn('push_curriculum', cfg.curriculum)

    def test_all_dependent_terms_removed(self):
        cfg = config()
        cfg.curriculum['another_push_schedule'] = NS(params={'event_name': 'push_robot'})
        adapter.configure_evaluation_events(cfg, {'op': 'play'})
        self.assertNotIn('push_range', cfg.curriculum)
        self.assertNotIn('another_push_schedule', cfg.curriculum)

    def test_unrelated_events_rewards_and_curricula_unchanged(self):
        cfg = config()
        before = copy.deepcopy(cfg)
        keep_event = cfg.events['reset_base']
        keep_term = cfg.curriculum['standing_envs']
        adapter.configure_evaluation_events(cfg, {'op': 'play'})
        del before.events['push_robot']
        del before.curriculum['push_range']
        self.assertEqual(cfg, before)
        self.assertIs(cfg.events['reset_base'], keep_event)
        self.assertIs(cfg.curriculum['standing_envs'], keep_term)

    def test_push_enabled_keeps_event_and_curricula(self):
        cfg = config()
        before = copy.deepcopy(cfg)
        adapter.configure_evaluation_events(cfg, {'op': 'play', 'eval_pushes': True})
        self.assertEqual(cfg, before)
        self.logs.assert_not_called()
        compute_event_curricula(cfg)

    def test_already_absent_event_not_restored_when_push_flag_true(self):
        cfg = config()
        del cfg.events['push_robot']
        adapter.configure_evaluation_events(cfg, {'op': 'play', 'eval_pushes': True})
        self.assertNotIn('push_robot', cfg.events)
        self.assertNotIn('push_range', cfg.curriculum)
        compute_event_curricula(cfg)

    def test_none_event_is_inactive(self):
        cfg = config()
        cfg.events['push_robot'] = None
        adapter.configure_evaluation_events(cfg, {'op': 'play', 'eval_pushes': True})
        self.assertIsNone(cfg.events['push_robot'])
        self.assertNotIn('push_range', cfg.curriculum)
        compute_event_curricula(cfg)

    def test_v2_cleans_both_push_dependencies(self):
        cfg = config()
        cfg.events['topple_push'] = NS(params={})
        cfg.curriculum['topple_push_range'] = NS(params={'event_name': 'topple_push'})
        adapter.configure_evaluation_events(cfg, {'op': 'play', 'engine': 'official_0151'})
        for name in ('push_robot', 'topple_push'):
            self.assertNotIn(name, cfg.events)
        for name in ('push_range', 'topple_push_range'):
            self.assertNotIn(name, cfg.curriculum)
        self.assertIn('prone_init_prob', cfg.curriculum)
        compute_event_curricula(cfg)

    def test_v2_push_enabled_retains_both_events_and_courses(self):
        cfg = config()
        cfg.events['topple_push'] = NS(params={})
        cfg.curriculum['topple_push_range'] = NS(params={'event_name': 'topple_push'})
        before = copy.deepcopy(cfg)
        adapter.configure_evaluation_events(cfg, {'op': 'play', 'engine': 'official_0151', 'eval_pushes': True})
        self.assertEqual(cfg, before)
        compute_event_curricula(cfg)

    def test_training_preflight_describe_requests_do_nothing(self):
        for op in ('train', 'preflight', 'describe', 'probe', None):
            with self.subTest(op=op):
                cfg = config()
                before = copy.deepcopy(cfg)
                adapter.configure_evaluation_events(cfg, {'op': op, 'engine': 'official_0151'})
                self.assertEqual(cfg, before)
        self.logs.assert_not_called()

    def test_all_four_evaluation_operations_clean_dependencies(self):
        for op in ('preview', 'play', 'onnx', 'export'):
            with self.subTest(op=op):
                cfg = config()
                adapter.configure_evaluation_events(cfg, {'op': op})
                compute_event_curricula(cfg)
                self.assertNotIn('push_range', cfg.curriculum)

    def test_other_configuration_errors_are_not_hidden(self):
        cfg = config()
        del cfg.events['randomize_com']
        adapter.configure_evaluation_events(cfg, {'op': 'play'})
        self.assertIn('com_range', cfg.curriculum)
        with self.assertRaisesRegex(ValueError, "Event term 'randomize_com'"):
            compute_event_curricula(cfg)

    def test_idempotent_and_keeps_disabled_placeholders(self):
        cfg = config()
        adapter.configure_evaluation_events(cfg, {'op': 'play'})
        self.assertIn('disabled_placeholder', cfg.curriculum)
        before = copy.deepcopy(cfg)
        self.logs.reset_mock()
        adapter.configure_evaluation_events(cfg, {'op': 'play'})
        self.assertEqual(cfg, before)
        self.logs.assert_not_called()

    def test_real_bundled_baseline_dependency_tables(self):
        # Real serialized task tables supplied in the R1.4.0 package, not GPUs.
        for engine in ('official_0151',):
            with self.subTest(engine=engine):
                raw = json.loads((ROOT / 'data' / 'baseline_official0151.json').read_text(encoding='utf-8'))['full']['env']
                cfg = NS(events=copy.deepcopy(raw['events']),
                         curriculum={k: None if v is None else NS(params=copy.deepcopy(v.get('params', {})))
                                     for k, v in raw['curriculum'].items()})
                adapter.configure_evaluation_events(cfg, {'op': 'play', 'engine': engine})
                compute_event_curricula(cfg)
                self.assertNotIn('push_robot', cfg.events)

    def test_wrapper_forwards_play_mode_and_keeps_registry_snapshot(self):
        for op in ('preview', 'play', 'export'):
            with self.subTest(op=op):
                source = config()
                before = copy.deepcopy(source)
                mod = module_for(source)
                original_env = mod.load_env_cfg
                with patch.object(adapter, 'apply_recipe'):
                    adapter.wrap_official_config(mod, {}, {'op': op, 'task': TASK})
                    result = mod.load_env_cfg(TASK, play=True)
                original_env.assert_called_once_with(TASK, play=True)
                compute_event_curricula(result)
                self.assertNotIn('push_range', result.curriculum)
                self.assertEqual(source, before)

    def test_wrapper_cleanup_runs_after_recipe_overrides(self):
        source = config()
        source.curriculum.clear()
        source.events.pop('push_robot')
        mod = module_for(source)
        def recipe(cfg, agent, req):
            cfg.events['push_robot'] = NS(params={})
            cfg.curriculum['added_by_recipe'] = NS(params={'event_name': 'push_robot'})
        with patch.object(adapter, 'apply_recipe', side_effect=recipe):
            adapter.wrap_official_config(mod, {}, {'op': 'play', 'task': TASK})
            cfg = mod.load_env_cfg(TASK, play=True)
        self.assertNotIn('added_by_recipe', cfg.curriculum)
        compute_event_curricula(cfg)

    def test_saved_policy_pushes_off_is_reconciled_even_with_eval_pushes_true(self):
        mod = module_for(config())
        with patch.object(adapter, 'apply_recipe'):
            adapter.wrap_official_config(mod, {'pushes': 'off'},
                                         {'op': 'play', 'task': TASK, 'eval_pushes': True})
            cfg = mod.load_env_cfg(TASK, play=True)
        self.assertNotIn('push_robot', cfg.events)
        self.assertNotIn('push_range', cfg.curriculum)
        compute_event_curricula(cfg)

    def test_onnx_path_cleans_before_environment_construction(self):
        # Execute the real adapter.onnx control flow; only third-party/GPU/ONNX
        # execution is replaced. This is NOT real ONNX numerical verification.
        for engine in ('official_0151', 'official_0151'):
            with self.subTest(engine=engine), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'fixture.onnx'
                path.write_bytes(b'transport fixture, not a real model')
                cfg = config()
                if engine == 'official_0151':
                    cfg.events['topple_push'] = NS(params={})
                    cfg.curriculum['topple_push_range'] = NS(params={'event_name': 'topple_push'})
                env = NS(get_observations=Mock(return_value={'actor': NS(ndim=2, shape=(1, 61))}),
                         num_actions=14, device='cpu', close=Mock())
                def construct(*, cfg, device):
                    compute_event_curricula(cfg)
                    self.assertNotIn('push_robot', cfg.events)
                    self.assertEqual(cfg.scene.num_envs, 1)
                    if engine == 'official_0151':
                        self.assertNotIn('topple_push', cfg.events)
                    return env
                modules = {name: ModuleType(name) for name in
                           ('torch', 'mjlab', 'mjlab.envs', 'mjlab.rl', 'mjlab.tasks',
                            'mjlab.tasks.registry', 'mjlab.utils', 'mjlab.utils.torch')}
                modules['torch'].cuda = NS(is_available=lambda: False)
                modules['mjlab.envs'].ManagerBasedRlEnv = construct
                modules['mjlab.rl'].RslRlVecEnvWrapper = lambda raw, **kw: raw
                modules['mjlab.tasks.registry'].load_env_cfg = lambda *a, **kw: cfg
                modules['mjlab.tasks.registry'].load_rl_cfg = lambda *a: NS(clip_actions=1.0, obs_groups={'actor': ['actor']})
                modules['mjlab.utils.torch'].configure_torch_backends = Mock()
                policy, viewer = Mock(), Mock()
                req = {'op': 'onnx', 'task': TASK, 'engine': engine, 'onnx_path': str(path),
                       'onnx_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                with patch.dict(sys.modules, modules), patch.object(adapter, 'apply_recipe'), \
                        patch.object(adapter, 'OnnxPolicy', return_value=policy), \
                        patch.object(adapter, 'viewer_class', return_value=viewer):
                    adapter.onnx(req)
                viewer.assert_called_once_with(env, policy)
                viewer.return_value.run.assert_called_once()
                env.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
