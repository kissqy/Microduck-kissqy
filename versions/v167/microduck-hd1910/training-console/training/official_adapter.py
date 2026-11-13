"""Glue only: pinned official VelStand, local HD1910 teachers, and checkpoint I/O.
The official reward, curriculum, PPO and expert-BC update implementations stay intact.
"""
import copy
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

if __package__:
    from .official_spec import TASKS, JOINT, JOINT_TASKS, WALK, STAND, REVISION, OBSERVATIONS, contract, compare_contracts
else:
    from official_spec import TASKS, JOINT, JOINT_TASKS, WALK, STAND, REVISION, OBSERVATIONS, contract, compare_contracts


def register_tasks():
    from mjlab.tasks.registry import list_tasks, register_mjlab_task
    # The public factory supports both feet, while upstream registers right only.
    # Give the left recipe its own truthful ID, environment and experiment root.
    from mjlab_microduck.tasks.microduck_ball_kick_env_cfg import make_microduck_ball_kick_env_cfg, MicroduckBallKickRlCfg
    from mjlab_microduck.tasks.backlash import make_backlash_variant
    from mjlab_microduck.tasks import MicroduckOnPolicyRunner
    from mjlab_microduck.robot.microduck_constants import MICRODUCK_BACKLASH_ROBOT_CFG
    for task, info in TASKS.items():
        if info['role'] != 'kick_left' or task in list_tasks():
            continue
        cfg = copy.deepcopy(MicroduckBallKickRlCfg)
        cfg.experiment_name = cfg.run_name = 'ball_kick_left'
        env = make_microduck_ball_kick_env_cfg(kick_foot='left')
        play = make_microduck_ball_kick_env_cfg(play=True, kick_foot='left')
        if info['backlash']:
            env = make_backlash_variant(env, MICRODUCK_BACKLASH_ROBOT_CFG)
            play = make_backlash_variant(play, MICRODUCK_BACKLASH_ROBOT_CFG)
        register_mjlab_task(task_id=task, env_cfg=env, play_env_cfg=play, rl_cfg=cfg, runner_cls=MicroduckOnPolicyRunner)
    missing = set(TASKS) - set(list_tasks())
    if missing:
        raise RuntimeError('官方冻结源码缺少任务：' + ', '.join(sorted(missing)))


def hardware_actuator(backlash=False):
    module = importlib.import_module((__package__+'.' if __package__ else '')+'hd1910_actuator')
    return module.hardware_actuator(backlash=backlash)


def report_friction_state(env, report):
    """One readback after the first real step; never reset or sample the env."""
    import torch
    import mujoco
    from mjlab_microduck.actuator.friction_dr_bam import FrictionDRBamActuator
    plain = importlib.import_module((__package__+'.' if __package__ else '')+'recipe').plain

    def stats(values, item_limit=None):
        # Indexing the mjlab bridge yields a real Tensor; do not interpret the
        # wrapper repr or compile-time mj_model values as per-world DR values.
        values = values.detach()
        finite = bool(torch.isfinite(values).all())
        items = values if item_limit is None else values[:, :item_limit]
        result = {'shape': list(values.shape), 'finite': finite,
                'min': float(values.min().item()) if values.numel() and finite else None,
                'max': float(values.max().item()) if values.numel() and finite else None,
                'per_item_min': items.amin(dim=0).cpu().tolist() if items.numel() and finite else [],
                'per_item_max': items.amax(dim=0).cpu().tolist() if items.numel() and finite else []}
        if item_limit is not None:
            result.update(total_count=int(values.shape[1]), sample_count=int(items.shape[1]),
                          truncated=items.shape[1] < values.shape[1])
        return result

    def unavailable(exc):
        return {'available': False, 'reason': type(exc).__name__+': '+str(exc)[:240]}

    def value_range(item):
        return ('%.6g～%.6g' % (item['min'], item['max'])
                if item['min'] is not None and item['max'] is not None else '非有限或为空')

    data = {'schema': 'microduck-friction-readback-v1', 'num_envs': int(env.num_envs),
            'step': int(env.common_step_counter), 'motor': [],
            'scope': 'one post-step snapshot; not long-run randomization coverage',
            'configured_events': {}}
    for name in ('randomize_joint_friction', 'foot_friction', 'randomize_wheel_friction'):
        if name in env.cfg.events and env.cfg.events[name] is not None:
            data['configured_events'][name] = plain(env.event_manager.get_term_cfg(name))
        else:
            data['configured_events'][name] = None
    event = (env.event_manager.get_term_cfg('randomize_joint_friction')
             if data['configured_events']['randomize_joint_friction'] is not None else None)
    asset_name = getattr(event.params.get('asset_cfg'), 'name', 'robot') if event else 'robot'
    robot = env.scene[asset_name]
    actuators = robot.actuators
    for index, actuator in enumerate(actuators):
        if not isinstance(actuator, FrictionDRBamActuator):
            report('log', line='[摩擦随机化读回] 执行器 %d 未被官方事件识别。' % index)
            data['motor'].append({'actuator_index': index, 'available': False,
                                  'reason': '执行器不是FrictionDRBamActuator'})
            continue
        try:
            scale = stats(actuator.friction_scale)
            dof_ids = robot.indexing.joint_v_adr[actuator.target_ids]
            friction = stats(env.sim.model.dof_frictionloss[:, dof_ids])
            item = {'actuator_index': index, 'available': True,
                    'joint_names': list(actuator.target_names),
                    'configured_scale_range': list(event.params['scale_range']) if event else None,
                    'friction_scale': scale, 'actual_dof_frictionloss_nm': friction}
            data['motor'].append(item)
            if event and scale['finite'] and scale['min'] is not None:
                lo, hi = event.params['scale_range']
                report('log', line='[摩擦随机化读回] 官方事件已识别飞特执行器 %d；%d 个环境；任务范围 %.4f～%.4f；实际倍率 %.4f～%.4f。' %
                       (index, int(scale['shape'][0]), lo, hi, scale['min'], scale['max']))
            report('log', line='[电机摩擦读回] %s；实际摩擦预算 %s N·m；这是本步预算，不是随机化倍率。' %
                   (friction['shape'], value_range(friction)))
        except Exception as exc:
            data['motor'].append({'actuator_index': index, **unavailable(exc)})
            report('log', line='[电机摩擦读回] 不可用：'+data['motor'][-1]['reason'])

    def geom_readback(ids, detail_limit=None):
        if not ids:
            raise ValueError('配置范围内没有碰撞面')
        model = env.sim.mj_model
        ids = sorted(set(ids))
        values = env.sim.model.geom_friction[:, ids, :]
        detail_ids = ids if detail_limit is None else ids[:detail_limit]
        return {'available': True, 'geom_count': len(ids), 'total_count': len(ids),
                'sample_count': len(detail_ids), 'truncated': len(detail_ids) < len(ids),
                'scope': 'geom_coefficients_after_DR; not mixed contact coefficients or contact forces',
                'statistics_scope': 'shape and min/max cover all geoms; per_item and metadata may be truncated',
                'coefficients': stats(values, detail_limit), 'sliding': stats(values[:, :, 0], detail_limit),
                'geoms': [{'name': mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i),
                           'body': mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, int(model.geom_bodyid[i])),
                           'condim': int(model.geom_condim[i]), 'priority': int(model.geom_priority[i])}
                          for i in detail_ids]}

    try:
        sensor = env.scene['feet_ground_contact']
        primary = sensor.cfg.primary
        entity = env.scene[primary.entity or 'robot']
        # Follow the actual contact sensor's name selector, including excludes.
        names = sensor._resolve_primary_names(env.scene.entities, primary)
        if primary.mode == 'geom':
            local_ids, _ = entity.find_geoms([re.escape(name) for name in names])
            ids = entity.indexing.geom_ids[local_ids].cpu().tolist()
        else:
            local_ids, _ = entity.find_bodies([re.escape(name) for name in names])
            bodies = set(entity.indexing.body_ids[local_ids].cpu().tolist())
            model = env.sim.mj_model
            ids = []
            for geom in entity.indexing.geom_ids.cpu().tolist():
                body = int(model.geom_bodyid[geom])
                if primary.mode == 'subtree':
                    while body and body not in bodies:
                        body = int(model.body_parentid[body])
                if body in bodies:
                    ids.append(geom)
        model = env.sim.mj_model
        ids = [i for i in ids if model.geom_contype[i] or model.geom_conaffinity[i]]
        data['foot_or_wheel_contact'] = geom_readback(ids)
        sliding = data['foot_or_wheel_contact']['sliding']
        report('log', line='[脚/轮接触面读回] %d个碰撞面；滑动摩擦系数 %s；实际%s，配置事件另记。' %
               (len(ids), value_range(sliding), sliding['shape']))
    except Exception as exc:
        data['foot_or_wheel_contact'] = unavailable(exc)
        report('log', line='[脚/轮接触面读回] 不可用：'+data['foot_or_wheel_contact']['reason'])

    try:
        terrain = env.scene.terrain
        data['terrain_contact'] = geom_readback(terrain.indexing.geom_ids.cpu().tolist(), detail_limit=32)
    except Exception as exc:
        data['terrain_contact'] = unavailable(exc)

    try:
        wheel_names = [name for name in robot.joint_names
                       if name.startswith('passive_') and name.endswith('wheel')]
        if wheel_names:
            local_ids, names = robot.find_joints([re.escape(name) for name in wheel_names])
            dof_ids = robot.indexing.joint_v_adr[local_ids]
            actual = stats(env.sim.model.dof_frictionloss[:, dof_ids])
            data['wheel_bearings'] = {'available': True, 'joint_names': list(names),
                                      'actual_frictionloss_nm': actual}
            report('log', line='[轮轴阻力读回] %d个被动轮；实际 %s N·m，%s；与地面摩擦系数分开记录。' %
                   (len(names), value_range(actual), actual['shape']))
        else:
            data['wheel_bearings'] = {'available': True, 'joint_names': [],
                                      'actual_frictionloss_nm': None, 'reason': '该模型没有被动轮'}
    except Exception as exc:
        data['wheel_bearings'] = unavailable(exc)
    report('friction_readback', data=data)


def _repair_roller_standup_servo_indices(cfg, req):
    """Translate this pinned recipe's raw roller indices into its reward view.

    Upstream's three pose rewards now call ``_servo_joint_pos`` (14 values),
    but RollerStandUp still supplies indices from the 18-joint wheel model.
    Only those reward functions consume servo indices. Reset/event indices
    still address the complete articulation and must remain untouched.
    """
    if req.get('task') != 'Mjlab-RollerStandUp-Flat-MicroDuck':
        return
    previous = getattr(cfg, '_studio_adapter_corrections', None)
    if previous:
        req['_adapter_corrections'] = copy.deepcopy(previous)
        return

    import mujoco
    spec = cfg.scene.entities['robot'].spec_fn()
    raw_names = [joint.name for joint in spec.joints
                 if joint.type != mujoco.mjtJoint.mjJNT_FREE]
    servo_names = [name for name in raw_names if not name.startswith('passive_')]
    if len(raw_names) != 18 or len(servo_names) != 14 or len(set(raw_names)) != 18:
        raise ValueError('RollerStandUp索引校正要求官方14关节加4被动轮模型；当前关节布局已改变。')
    servo_index = {name: index for index, name in enumerate(servo_names)}

    def remap(index):
        if type(index) is not int or not 0 <= index < len(raw_names):
            raise ValueError('RollerStandUp奖励包含无效原模型关节索引：'+str(index))
        name = raw_names[index]
        if name not in servo_index:
            raise ValueError('RollerStandUp伺服奖励不能引用被动轮：'+name)
        return servo_index[name]

    consumers = {'pose_target_match', 'pose_l1_penalty', 'standing_composite_score'}
    changes = []
    # Prepare every change before committing, so an unexpected passive target
    # cannot leave half of the recipe corrected.
    updates = []
    for name, term in cfg.rewards.items():
        if term is None or getattr(term.func, '__name__', '') not in consumers:
            continue
        if getattr(term.func, '__module__', '') != 'mjlab_microduck.tasks.mdp':
            continue
        params = copy.deepcopy(term.params)
        before = {key: copy.deepcopy(params[key]) for key in ('joint_indices', 'target_overrides')
                  if key in params}
        if params.get('joint_indices') is not None:
            params['joint_indices'] = [remap(index) for index in params['joint_indices']]
        if params.get('target_overrides') is not None:
            params['target_overrides'] = {remap(index): value
                                          for index, value in params['target_overrides'].items()}
        after = {key: copy.deepcopy(params[key]) for key in before}
        if before != after:
            changes.append({'reward': name, 'function': term.func.__name__,
                            'before': before, 'after': after})
            updates.append((term, params))
    if not changes:
        return
    for term, params in updates:
        term.params = params
    receipt = {'schema': 'microduck-roller-servo-index-correction-v1',
               'task': req['task'], 'source_revision': REVISION,
               'source_joint_names': raw_names, 'servo_joint_names': servo_names,
               'changes': changes,
               'scope': 'reward_indices_only; weights, reset/events and upstream files unchanged'}
    cfg._studio_adapter_corrections = [receipt]
    req['_adapter_corrections'] = copy.deepcopy(cfg._studio_adapter_corrections)
    module = importlib.import_module((__package__+'.' if __package__ else '')+'event_protocol')
    module.emit('log', line='[官方索引适配] RollerStandUp的3个姿态奖励按关节名转换为14维伺服序；右腿9～13，颈头5～8。奖励权重与倒地复位不变。')
    module.emit('adapter_correction', data=receipt)


def adapt_robot(cfg, agent, req):
    _repair_roller_standup_servo_indices(cfg, req)
    robot = copy.deepcopy(cfg.scene.entities['robot'])
    from mjlab_microduck.actuator.friction_dr_bam import BacklashEncoderBamActuatorCfg
    backlash = any(isinstance(a, BacklashEncoderBamActuatorCfg) for a in robot.articulation.actuators)
    robot.articulation.actuators = (hardware_actuator(backlash=backlash),)
    cfg.scene.entities['robot'] = robot
    origin = (req.get('model_source') or {}).get('origin', {})
    if req['op'] in ('play','onnx','export') and origin.get('friction_randomization') == 'fixed':
        # Preserve the old model's actual evaluation dynamics. This does NOT
        # disable DR in a new student trained with that model as a teacher.
        cfg.events.pop('randomize_joint_friction', None)
    # Evaluation/export load only the student. No hidden W&B fetch or teacher GPU copies.
    # Describe only reads dataclasses; it must expose BC rather than pretending
    # the training task has none. It does not instantiate/download experts.
    if req['task'] in JOINT_TASKS and req['op'] in ('preview','play','onnx','export'):
        agent.algorithm.bc_cfg = None
    # Clear an inherited shell variable for ALL non-warm-start executions, including play.
    os.environ['MICRODUCK_WARM_START'] = '0'


def assert_joint_recipe(cfg):
    from mjlab_microduck.tasks import microduck_velstand_env_cfg as upstream
    if not upstream.WARM_START or not upstream.ENABLE_EXPERT_BC:
        raise RuntimeError('官方 0.15.1 对应联合任务未启用官方warm-start或专家BC。')
    if cfg.agent.algorithm.class_name != 'mjlab_microduck.tasks.distill.PpoWithExpertBc':
        raise RuntimeError('联合任务算法被覆盖，不是官方双教师版本。')
    if list(cfg.env.observations['actor'].terms) != OBSERVATIONS:
        raise ValueError('官方 0.15.1 对应联合任务必须保持61维观测顺序；不能只按维数相同强行加载。')
    for name in ('action_rate_l2','joint_torque_rate_l2'):
        if cfg.env.rewards[name].params.get('fallen_scale') != 0.1:
            raise ValueError('官方 0.15.1 对应倒地平滑减罚被覆盖，请恢复官方0.1设置。')
    if 'topple_push' not in cfg.env.events or 'servo_ground_contact' not in [s.name for s in cfg.env.scene.sensors]:
        raise ValueError('官方 0.15.1 对应保护摔倒事件/传感器缺失。')
    if list(cfg.agent.actor.hidden_dims) != [512,256,128] or cfg.agent.actor.activation != 'elu':
        raise ValueError('双教师入口沿用512/256/128、ELU网络；修改网络需另行迁移老师。')


def _safe_checkpoint(spec, cache_root):
    """Read a managed checkpoint; content-addressed copy does not overwrite an old run."""
    source = Path(spec['checkpoint']).expanduser().resolve()
    allowed = Path(spec['repo']).expanduser().resolve()/'logs/rsl_rl'
    if source.suffix != '.pt' or not source.is_file() or not source.is_relative_to(allowed):
        raise ValueError('老师PT不存在或不属于来源训练目录：'+str(source))
    if source.stat().st_size > 256*1024*1024: raise ValueError('老师PT超过256MB，不符合当前MLP模型大小。')
    raw = source.read_bytes(); sha = hashlib.sha256(raw).hexdigest()
    if spec.get('sha256') and sha != spec['sha256']: raise ValueError('老师PT内容与本次保存的身份不一致，请重新选择对应检查点。')
    target = cache_root/sha/'model.pt'; target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != sha:
        temp = target.with_suffix('.tmp'); temp.write_bytes(raw); temp.replace(target)
    return target, sha


def validate_state_dicts(agent, walk_path, stand_path, need_walk_critic=True):
    """Real PyTorch strict loads, on CPU, before allocating a large GPU simulation."""
    import torch
    from tensordict import TensorDict
    from rsl_rl.models import MLPModel
    groups = {'actor':['actor'],'critic':['critic']}
    obs = TensorDict({'actor':torch.zeros(1,61),'critic':torch.zeros(1,76)}, batch_size=[1])
    def model(which, width):
        c = getattr(agent,which)
        return MLPModel(obs,groups,which,width,hidden_dims=tuple(c.hidden_dims),activation=c.activation,
                        obs_normalization=c.obs_normalization,distribution_cfg=copy.deepcopy(getattr(c,'distribution_cfg',None)))
    actor = model('actor',14)
    # No arbitrary pickle execution during validation; only local self-trained weights are accepted.
    loaded = [torch.load(p,map_location='cpu',weights_only=True) for p in (walk_path,stand_path)]
    for state in loaded:
        if not isinstance(state,dict) or 'actor_state_dict' not in state: raise ValueError('请选择训练PT，而不是ONNX或仅推理权重。')
        actor.load_state_dict(state['actor_state_dict'],strict=True)
        for tensor in state['actor_state_dict'].values():
            if torch.is_tensor(tensor) and not torch.isfinite(tensor).all(): raise ValueError('老师权重或归一化含NaN/Inf。')
        actor.eval()
        with torch.no_grad():
            if not torch.isfinite(actor(obs)).all(): raise ValueError('老师CPU试推理输出无效。')
    if need_walk_critic:
        model('critic',1).load_state_dict(loaded[0]['critic_state_dict'],strict=True)
        if 'optimizer_state_dict' not in loaded[0]: raise ValueError('行走热启动需要包含优化器状态的完整训练PT。')
    return loaded[0]


def install_checkpoint_extension(teacher_hashes, resume):
    """Only persists BC Adam state. Official update() / rewards are not overridden."""
    from mjlab_microduck.tasks.distill import PpoWithExpertBc
    class CheckpointedExpertPpo(PpoWithExpertBc):
        def save(self):
            saved = super().save()
            saved['studio_joint_0151'] = {'revision':REVISION,'teachers':dict(teacher_hashes),
                'bc_optimizer':self.bc_optimizer.state_dict()}
            return saved
        def load(self, loaded_dict, load_cfg, strict):
            meta = loaded_dict.get('studio_joint_0151')
            if resume:
                if not meta or meta.get('revision') != REVISION or meta.get('teachers') != teacher_hashes:
                    raise ValueError('续训模型不是此官方 0.15.1 对应联合任务或老师已变更；不静默重置课程/老师。')
            result = super().load(loaded_dict,load_cfg,strict)
            if meta and (load_cfg is None or load_cfg.get('optimizer')):
                self.bc_optimizer.load_state_dict(meta['bc_optimizer'])
            return result
    globals()['CheckpointedExpertPpo'] = CheckpointedExpertPpo
    return __name__+'.CheckpointedExpertPpo'


def configure_training(cfg, req, inspection):
    assert_joint_recipe(cfg)
    joint = req.get('joint') or {}
    mode = joint.get('mode')
    if mode not in ('warm_start','resume'): raise ValueError('官方 0.15.1 对应联合训练必须选择行走和起身老师；不允许无老师随机开训。')
    target_contract = contract(inspection)
    repo = Path(req['repo']).expanduser().resolve()
    cache_root = repo/'logs/rsl_rl/expert_cache/studio_0151'
    teachers = {}; receipts = {}
    for role in ('walk','stand'):
        spec = joint.get(role)
        if not isinstance(spec,dict): raise ValueError('缺少'+role+'老师。')
        compare_contracts(spec.get('contract',{}), target_contract)
        path, sha = _safe_checkpoint(spec,cache_root)
        teachers[role] = path
        receipts[role] = {'sha256':sha,'path':str(path),'source_job':spec['source_job'],
                          'source_checkpoint':spec['checkpoint'],'origin':copy.deepcopy(spec.get('origin',{})),
                          'source_gear_backlash':copy.deepcopy(spec.get('gear_backlash', {'enabled':False})),
                          'student_gear_backlash':copy.deepcopy(inspection['model'].get('gear_backlash', {'enabled':False}))}
        if receipts[role]['source_gear_backlash']['enabled'] != receipts[role]['student_gear_backlash']['enabled']:
            print('[老师迁移] %s：老师齿隙=%s，本次学生齿隙=%s；保留老师原权重和来源，学生使用页面所选物理模型。输出侧编码器观测和动作合同一致。' %
                  (role, receipts[role]['source_gear_backlash']['enabled'], receipts[role]['student_gear_backlash']['enabled']), flush=True)
        if spec.get('origin',{}).get('engine') == 'velstand_v2':
            friction = '固定摩擦，未启用随机化' if spec['origin'].get('friction_randomization') == 'fixed' else '已修复摩擦随机化'
            print('[老师兼容] %s：既有 V2（%s）；原权重不变，本次联合训练使用当前官方摩擦随机化。' % (role, friction), flush=True)
    validate_state_dicts(cfg.agent,teachers['walk'],teachers['stand'],mode=='warm_start')
    bc = copy.deepcopy(cfg.agent.algorithm.bc_cfg)
    if not bc: raise ValueError('官方BC配置缺失，不能当普通PPO开训。')
    bc.update(checkpoint_path=str(teachers['stand']),anchor_checkpoint_path=str(teachers['walk']),
              wandb_run_path=None,anchor_wandb_run_path=None)
    cfg.agent.algorithm.bc_cfg = bc
    hashes = {role:r['sha256'] for role,r in receipts.items()}
    if mode=='resume':
        import torch
        cp=Path(req.get('checkpoint','')).expanduser().resolve()
        if not cp.is_file() or not cp.is_relative_to(repo/'logs/rsl_rl'):
            raise ValueError('官方 0.15.1 对应联合续训PT不存在或不属于本引擎。')
        saved=torch.load(cp,map_location='cpu',weights_only=True)
        meta=saved.get('studio_joint_0151') if isinstance(saved,dict) else None
        if not meta or meta.get('revision')!=REVISION or meta.get('teachers')!=hashes or not meta.get('bc_optimizer'):
            raise ValueError('续训PT缺少匹配的双教师身份/BC优化器；不能把旧联合模型冒充官方 0.15.1 对应续训。')
    cfg.agent.algorithm.class_name = install_checkpoint_extension(hashes,mode=='resume')
    if mode == 'warm_start':
        # Keep lookup inside the new experiment root; no monkey-patching the official load path.
        run = '_studio_warm_'+hashes['walk'][:16]
        destination = repo/'logs/rsl_rl'/cfg.agent.experiment_name/run/'model.pt'
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest()!=hashes['walk']:
            shutil.copyfile(teachers['walk'], destination)
        cfg.agent.resume = True; cfg.agent.load_run = '^'+re.escape(run)+'$'; cfg.agent.load_checkpoint = r'^model\.pt$'
        os.environ['MICRODUCK_WARM_START'] = '1'
    else:
        if not req.get('checkpoint'): raise ValueError('官方 0.15.1 对应续训缺少联合任务检查点。')
        os.environ['MICRODUCK_WARM_START'] = '0'
    return {'mode':mode,'upstream_revision':REVISION,'teachers':receipts,
            'curriculum_restart':mode=='warm_start','bc_optimizer_checkpointed':True,
            'actor_input_dim':61,'actor_output_dim':14,'cuda_training_tested_here':False}
