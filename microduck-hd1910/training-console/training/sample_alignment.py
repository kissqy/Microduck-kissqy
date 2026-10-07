"""Align timed curricula by collected transitions, against 4096 x 24.

This changes schedule thresholds, not physics, rollout length, PPO or BC.
Performance-driven terrain promotion has no timed stages and is left intact.
"""
import copy
import math

REFERENCE_ENVS = 4096
REFERENCE_STEPS = 24
CLOCK_KEY = 'studio_sample_clock'
STRICT_FUNCTIONS = {
    'reward_weight', 'standing_envs_curriculum', 'velocity_tracking_std_curriculum',
    'push_curriculum', 'wheel_friction_curriculum', 'com_range_curriculum',
    'velocity_command_ranges_curriculum', 'face_down_prob_curriculum',
}


def budget_iterations(reference_iterations, num_envs, steps_per_iteration=REFERENCE_STEPS):
    return math.ceil(reference_iterations * REFERENCE_ENVS * REFERENCE_STEPS /
                     (num_envs * steps_per_iteration))


def threshold(step, num_envs, strict=False):
    # Retain the official > / >= boundary, including non-divisor env counts.
    numerator = step * REFERENCE_ENVS
    return numerator // num_envs if strict else (numerator + num_envs - 1) // num_envs


def align_curricula(env, agent):
    n = int(env.scene.num_envs)
    if n <= 0:
        raise ValueError('并行环境数必须大于零。')
    stages, untouched = [], []
    for name, term in env.curriculum.items():
        if term is None:
            continue
        # Registry configs and module constants may share lists. Never mutate
        # those lists, and do not scale an already-aligned config a second time.
        original = getattr(term, '_studio_reference_params', None)
        if original is None:
            original = copy.deepcopy(term.params)
            term._studio_reference_params = original
        term.params = copy.deepcopy(original)
        strict = getattr(term.func, '__name__', '') in STRICT_FUNCTIONS
        found = False
        for key, values in term.params.items():
            if not key.endswith('_stages') or not isinstance(values, (list, tuple)):
                continue
            for index, stage in enumerate(values):
                if not isinstance(stage, dict) or 'step' not in stage:
                    continue
                old = stage['step']
                if type(old) is not int or old < 0:
                    raise ValueError('课程阶段步数无效：'+name+'.'+key)
                stage['step'] = threshold(old, n, strict)
                stages.append({'term': name, 'key': key, 'index': index,
                               'reference_step': old, 'step': stage['step'], 'strict': strict})
                found = True
        if not found:
            untouched.append(name)
    steps = agent.num_steps_per_env
    return {'version': 1, 'reference_envs': REFERENCE_ENVS,
            'reference_steps_per_iteration': REFERENCE_STEPS,
            'num_envs': n, 'steps_per_iteration': steps,
            'factor': REFERENCE_ENVS / n,
            'iteration_factor': REFERENCE_ENVS * REFERENCE_STEPS / (n * steps),
            'stages': stages, 'untimed_terms': untouched}


def sample_count(env):
    return int(env.common_step_counter) * int(env.num_envs) + int(getattr(env, '_studio_sample_remainder', 0))


def progress(env):
    samples = sample_count(env)
    return {'sample_count': samples, 'num_envs': int(env.num_envs),
            'reference_envs': REFERENCE_ENVS,
            'reference_iterations': samples / (REFERENCE_ENVS * REFERENCE_STEPS)}


def install(official, request, report):
    """Carry an exact sample clock through saves/resumes, leaving PPO iter intact.

    mjlab already saves common_step_counter in infos.env_state. Additional infos
    retain the total transitions when the next run changes its parallel count.
    Warm starts from teachers deliberately start a NEW curriculum at zero.
    """
    original_loader = official.load_runner_cls
    original_default = official.MjlabOnPolicyRunner
    wrappers = {}

    def wrapped(base):
        if base in wrappers:
            return wrappers[base]

        class SampleAlignedRunner(base):
            def save(self, path, infos=None):
                env = self.env.unwrapped
                clock = {'version': 1, **progress(env)}
                return super().save(path, infos={**(infos or {}), CLOCK_KEY: clock})

            def load(self, path, *args, **kwargs):
                infos = super().load(path, *args, **kwargs)
                env = self.env.unwrapped
                if (request.get('joint') or {}).get('mode') == 'warm_start':
                    # The upstream warm-start patch also resets PPO's iteration.
                    env.common_step_counter = 0
                    env._studio_sample_remainder = 0
                    report('log', line='[采样对齐] 从老师热启动：联合课程从 0 开始。')
                    return infos
                clock = (infos or {}).get(CLOCK_KEY)
                if clock:
                    samples = clock.get('sample_count')
                    if clock.get('version') != 1 or type(samples) is not int or samples < 0:
                        raise ValueError('检查点中的累计采样记录无效。')
                    source = '检查点累计采样记录'
                else:
                    old_n = (request.get('resume_sample_source') or {}).get('num_envs', int(env.num_envs))
                    samples = int(env.common_step_counter) * int(old_n)
                    source = '旧检查点步数 × 原并行数；此前的课程过程不追溯修改'
                env.common_step_counter, env._studio_sample_remainder = divmod(samples, int(env.num_envs))
                report('log', line='[采样对齐] 续训累计 %d 个样本，折合 4096 基准 %.2f 轮；来源：%s。' %
                       (samples, samples / (REFERENCE_ENVS * REFERENCE_STEPS), source))
                report('sample_clock', data=progress(env))
                return infos

        wrappers[base] = SampleAlignedRunner
        return SampleAlignedRunner

    def loader(task):
        cls = original_loader(task)
        return wrapped(cls) if cls is not None else None

    official.load_runner_cls = loader
    official.MjlabOnPolicyRunner = wrapped(original_default)

    def restore():
        official.load_runner_cls = original_loader
        official.MjlabOnPolicyRunner = original_default
    return restore
