"""One official training source, targeting the daemon-v0.15.1 model protocol."""
import copy
import json
import math
from pathlib import Path

ENGINE = 'official_0151'
RUNTIME_VERSION = '0.15.1'
RUNTIME_REVISION = '1fa84386f07884e27866411bc1ba166977bced95'
REVISION = '8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec'
TRAINING_ADAPTER_REVISION = 'R1.5.9-current-actions-backlash'
PIN = {
    'title': '官方训练 · 适配固件 0.15.1 / HD1910',
    'url': 'https://github.com/pollen-robotics/microduck_rl.git',
    'revision': REVISION, 'subdir': '',
    'repo': '~/microduck-training-studio/engines/official_0151',
    'task': 'Mjlab-Velocity-Flat-MicroDuck',
    'motor': 'HD1910 / BAM M6 · 官方骨架 820g',
    'target_runtime': RUNTIME_VERSION, 'runtime_revision': RUNTIME_REVISION,
}

# Public deployed action set, checked against the official policies manifest.
# Native task variants stay available internally for historical PT evaluation.
# Profiles keep the action picker short; terrain/gear play select a real task.
PROFILES = [
    ('joint', 'VelStand', '行走与倒地起身 / Walk + recovery', 6000, 'velstand',
     '当前官方 walk 槽：行走、零速度保持和倒地恢复；粗糙＋齿隙为官方发布配方。', 'Rough', True, '当前实机动作 / Current actions'),
    ('sitstand', 'SitStand', '坐下与站起 / Sit–stand', 15000, 'sitstand',
     '当前坐站配方含坐姿头部突变和后仰扰动训练；vx=1 坐下，vx=0 站起。', 'Flat', False, '当前实机动作 / Current actions'),
    ('ground_pick', 'GroundPick', '低头捡取 / Ground pick', 20000, 'ground_pick',
     '官方相位动作：周期4秒、运行窗口2.8秒。', 'Flat', False, '当前实机动作 / Current actions'),
    ('kick_left', 'BallKickLeft', '左脚踢球 / Left kick', 10000, 'ball_kick',
     '调用官方 BallKick 工厂的 kick_foot=left；独立训练左脚，不复用右脚权重。', 'Flat', False, '当前实机动作 / Current actions'),
    ('kick_right', 'BallKick', '右脚踢球 / Right kick', 10000, 'ball_kick',
     '官方右脚踢球配方；运行窗口0.5秒。', 'Flat', False, '当前实机动作 / Current actions'),
    ('roulade', 'Roulade', '前滚翻 / Forward roll', 10000, 'roulade',
     '官方前滚翻配方；运行窗口1秒。官方没有注册此动作的齿隙版本。', 'Flat', False, '当前实机动作 / Current actions'),
    ('walk', 'Velocity', '行走老师 / Walking teacher', 50000, 'velocity',
     '联合训练的行走热启动与行走老师；单独训练不含完整倒地恢复。', 'Rough', True, '联合训练老师 / Teachers'),
    ('stand', 'StandUp', '倒地起身老师 / Recovery teacher', 15000, 'standup',
     '联合训练的起身老师；不是旧版单独原地站立模型。两位老师的动作系数和滤波需一致。', 'Rough', True, '联合训练老师 / Teachers'),
    ('roller', 'Velocity', '轮滑行走 / Roller skating', 50000, 'velocity_rollers',
     '官方被动滑轮机器人配方；需要安装滑轮，不用于当前无滑轮硬件。', 'Flat', False, '滑轮硬件动作 / Requires rollers'),
    ('crouch', 'RollerCrouch', '轮滑蹲下 / Roller crouch', 8000, 'roller_crouch',
     '需要滑轮；官方相位动作周期5秒、运行窗口3.5秒。', 'Flat', False, '滑轮硬件动作 / Requires rollers'),
]
TASKS = {}
ACTION_PROFILES = []
for role, family, title, budget, source, description, default_terrain, default_backlash, group in PROFILES:
    variants = []
    terrains = ('Flat', 'Rough') if role in ('walk', 'stand', 'joint') else ('Flat',)
    for terrain in terrains:
        for backlash in ((False, True) if role != 'roulade' else (False,)):
            name = f'Mjlab-{family}-{terrain}'+('-Backlash' if backlash else '')+'-MicroDuck'+('-Rollers' if role == 'roller' else '')
            upstream = name.replace('BallKickLeft', 'BallKick')
            TASKS[name] = {
                'id': name, 'upstream': upstream, 'upstream_task': upstream,
                'role': role, 'name': title, 'description': description,
                'iterations': budget, 'enabled': True, 'engine': ENGINE,
                'source_revision': REVISION, 'source': f'microduck_{source}_env_cfg.py',
                'group': group, 'terrain': terrain, 'backlash': backlash,
                'backlash_total_deg': 2.0 if backlash else 0.0,
                'hardware': 'rollers' if role in ('roller', 'crouch') else 'feet',
                **({'kick_foot': 'left'} if role == 'kick_left' else {}),
            }
            variants.append(name)
    default = next(k for k in variants if TASKS[k]['terrain'] == default_terrain and TASKS[k]['backlash'] == default_backlash)
    ACTION_PROFILES.append({'role': role, 'name': title, 'group': group, 'default_task': default, 'variants': variants})
# These former choices were not the currently published one-shot recipes.
# Their original records can still be evaluated/exported without relabelling.
for family, role, source, budget in [('SitStand', 'sitstand', 'sitstand', 15000), ('GroundPick', 'ground_pick', 'ground_pick', 20000)]:
    name = f'Mjlab-{family}-Rough-MicroDuck'
    TASKS[name] = {**TASKS[f'Mjlab-{family}-Flat-MicroDuck'], 'id': name, 'upstream': name, 'upstream_task': name,
                   'terrain': 'Rough', 'enabled': False, 'reason': '历史配方，仅评估、导出或原配置续训。'}
WALK = 'Mjlab-Velocity-Flat-MicroDuck'
STAND = 'Mjlab-StandUp-Flat-MicroDuck'
JOINT = 'Mjlab-VelStand-Flat-MicroDuck'
DEFAULT_TASK = 'Mjlab-VelStand-Rough-Backlash-MicroDuck'
PIN['task'] = DEFAULT_TASK
JOINT_TASKS = tuple(k for k, v in TASKS.items() if v['role'] == 'joint')

def new_training_action_scale(task):
    return 0.9 if TASKS[task]['role'] in ('walk', 'stand', 'joint') else 1.0

TEACHER_TASKS = {role: tuple(k for k, v in TASKS.items() if v['role'] == role) for role in ('walk', 'stand')}
OBSERVATIONS = ['base_ang_vel', 'projected_gravity', 'joint_pos', 'joint_vel', 'actions', 'command', 'head_command', 'body_command']
# duck-control/src/model.rs DEFAULT_POSITION, with mouth excluded by obs::joint_of.
RUNTIME_JOINTS = ['left_hip_yaw','left_hip_roll','left_hip_pitch','left_knee','left_ankle',
                  'neck_pitch','head_pitch','head_yaw','head_roll',
                  'right_hip_yaw','right_hip_roll','right_hip_pitch','right_knee','right_ankle']
RUNTIME_HOME = [0.,-.0873,-.4579,-.0049,.4530,.3491,.3491,0.,0.,0.,.0873,.4579,.0049,-.4530]
for _task, _info in TASKS.items():
    _info['training_action_scale'] = new_training_action_scale(_task)

CATALOG = {'revision': REVISION, 'version': '1.5.13', 'runtime_version': RUNTIME_VERSION,
           'runtime_revision': RUNTIME_REVISION, 'aliases': {},
           'reference_envs': 4096, 'reference_steps_per_iteration': 24,
           'budget_note': '以4096环境×24步为采样基准，课程和默认预算按并行数换算；官方轮数是默认上限，不是收敛保证。',
           'default_task': DEFAULT_TASK, 'profiles': ACTION_PROFILES, 'tasks': list(TASKS.values())}


def current_request(request):
    return (request.get('engine') == ENGINE and request.get('task') in TASKS
            and (request.get('baseline_pin') or {}).get('revision') == REVISION)


LEGACY_V2_REVISION = 'cb70b792312d559a4da09064d92009079671815f'
LEGACY_V2_TASKS = {task+'-V2-HD1910': task for task in (WALK, STAND, JOINT)}


def legacy_v2_request(request):
    """Known V2 sources only; an engine name or a 61x14 shape alone is insufficient."""
    return (request.get('engine') == 'velstand_v2' and request.get('task') in LEGACY_V2_TASKS
            and (request.get('baseline_pin') or {}).get('revision') == LEGACY_V2_REVISION)


def model_task(request):
    if current_request(request):
        return request['task']
    if legacy_v2_request(request):
        return LEGACY_V2_TASKS[request['task']]
    return None


def training_origin(request):
    """Keep weight provenance across re-export; never relabel cb70 weights as 8d0."""
    if request.get('model_source'):
        return copy.deepcopy(request['model_source']['origin'])
    legacy = legacy_v2_request(request)
    adapter = request.get('training_adapter_revision')
    return {'engine': request.get('engine'), 'task': request.get('task'),
            'baseline_pin': {'revision': (request.get('baseline_pin') or {}).get('revision', REVISION)},
            'training_adapter_revision': adapter,
            'friction_randomization': ('fixed' if legacy and adapter != 'R1.4.23-friction-dr-base' else 'official')}


def compatibility_label(request):
    origin = training_origin(request)
    if not legacy_v2_request(origin):
        return ''
    return '既有 V2 · '+('固定摩擦' if origin['friction_randomization'] == 'fixed' else '摩擦随机化已修复')


def ignored_legacy_bam_overrides(request):
    """Known 1.5.0–1.5.2 path-cache bug: those JSON edits were never loaded."""
    revision = request.get('training_adapter_revision') or ''
    if current_request(request) and revision.startswith(('R1.5.0-', 'R1.5.1-', 'R1.5.2-')):
        return copy.deepcopy((request.get('studio_recipe') or {}).get('robot', {}).get('actuator_parameters') or {})
    return {}


def normalize_model_recipe(request):
    """Map the known V2 recipe namespace, without changing its physical edits."""
    recipe = copy.deepcopy(request.get('studio_recipe') or {})
    if ignored_legacy_bam_overrides(request):
        # Preserve the actual historical physics, not the edits that the old UI
        # recorded but failed to apply. Never rewrite the original run or PT.
        recipe['robot'].pop('actuator_parameters', None)
    if legacy_v2_request(request):
        if recipe.get('baseline') != 'hd1910':
            raise ValueError('既有 V2 模型缺少 HD1910 机器人配置。')
        recipe['baseline'] = ENGINE
        old_task, task = request['task'], model_task(request)
        overrides = recipe.setdefault('task_overrides', {})
        if old_task in overrides:
            overrides[task] = copy.deepcopy(overrides[old_task])
    return recipe


def physical_recipe(recipe):
    return {'baseline': recipe.get('baseline'), 'robot': recipe.get('robot')}


def contract(inspection, source_request=None):
    if isinstance(inspection, dict) and inspection.get('portable_contract'):
        return copy.deepcopy(inspection['portable_contract'])
    if not isinstance(inspection, dict) or not inspection.get('model') or not inspection.get('full'):
        raise ValueError('老师缺少实际生效的机器人和策略配置。')
    model = inspection['model']; env = inspection['full']['env']; agent = inspection['full']['agent']
    acts = []
    for a in model['actuators']:
        acts.append({k: a.get(k) for k in ('target_names_expr', 'kp_fw', 'vin', 'vin_range', 'vin_min', 'vin_drop_gain_range', 'delay_min_lag', 'delay_max_lag', 'delay_hold_prob', 'stiff_frictionloss')})
        acts[-1]['parameters'] = a.get('parameter_file', {}).get('data')
    ignored = ignored_legacy_bam_overrides(source_request or {})
    if ignored:
        original = json.loads(Path(__file__).with_name('hd1910_m6.json').read_text())
        for index in ignored:
            acts[int(index)]['parameters'] = copy.deepcopy(original)
    joints = [j for j in model['joints'] if j.get('type') == 3 and not j['name'].startswith('passive_')]
    obs = env['observations']['actor']
    return {
        'joints': [{k: j.get(k) for k in ('name', 'axis', 'range', 'home_rad')} for j in joints],
        'bodies': [{k: b.get(k) for k in ('name', 'mass_kg', 'pos', 'quat', 'ipos', 'iquat', 'inertia')} for b in model['bodies']],
        'actuators': acts, 'actions': env['actions'],
        'observations': [{'name': k, 'scale': v.get('scale'), 'clip': v.get('clip'), 'history_length': v.get('history_length', 0)} for k, v in obs['terms'].items()],
        'history_length': obs.get('history_length'),
        'step_dt': env['sim']['mujoco']['timestep'] * env['decimation'],
        'actor': {k: agent['actor'].get(k) for k in ('class_name', 'hidden_dims', 'activation', 'obs_normalization')},
    }


def compare_contracts(source, target):
    """Compare physics and policy semantics; quaternion sign is not a rotation change."""
    def normalize(value):
        value = copy.deepcopy(value)
        names = [j.get('name') for j in value.get('joints', [])]
        # V2 used exactly this selector. Both forms resolve to the SAME ordered
        # active joints; do not erase arbitrary selector/action-order differences.
        if names == RUNTIME_JOINTS and len(value.get('actuators', [])) == 1:
            a = value['actuators'][0]
            if a.get('target_names_expr') == ['^(?!passive_).*']:
                a['target_names_expr'] = names
        return value
    source, target = normalize(source), normalize(target)
    def same(a, b, field=''):
        if isinstance(a, (int, float)) and not isinstance(a, bool) and isinstance(b, (int, float)) and not isinstance(b, bool):
            return math.isfinite(a) and math.isfinite(b) and abs(a-b) <= 1e-7 + 1e-6*max(abs(a), abs(b))
        if isinstance(a, dict) and isinstance(b, dict):
            return a.keys() == b.keys() and all(same(a[k], b[k], k) for k in a)
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b): return False
            if field in ('quat', 'iquat') and len(a) == 4:
                return min(sum((x-y)**2 for x, y in zip(a, b)), sum((x+y)**2 for x, y in zip(a, b))) <= 1e-10
            return all(same(x, y) for x, y in zip(a, b))
        return a == b
    differences = [k for k in target if not same(source.get(k), target[k])]
    if differences:
        if 'actions' in differences:
            a=(source.get('actions') or {}).get('joint_pos') or {}
            b=(target.get('actions') or {}).get('joint_pos') or {}
            if a.get('scale') != b.get('scale'):
                raise ValueError('老师与本次训练的动作系数不同；请用相同动作系数训练的两位老师。其他差异：'+', '.join(differences))
            if any(a.get(k)!=b.get(k) for k in ('head_alpha','legs_alpha','filter_version')):
                raise ValueError('老师与本次训练的头腿动作滤波不同；联合训练请使用同一组滤波参数训练的行走和起身老师。其他差异：'+', '.join(differences))
        raise ValueError('老师与本次机器人/策略配置不匹配：' + ', '.join(differences) + '。未转换动作映射。')
    return []
