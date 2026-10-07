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
    from mjlab_microduck.actuator.friction_dr_bam import FrictionDRBamActuator
    event = env.event_manager.get_term_cfg('randomize_joint_friction')
    lo, hi = event.params['scale_range']
    asset_name = getattr(event.params.get('asset_cfg'), 'name', 'robot')
    actuators = env.scene[asset_name].actuators
    for index, actuator in enumerate(actuators):
        if not isinstance(actuator, FrictionDRBamActuator):
            report('log', line='[摩擦随机化读回] 执行器 %d 未被官方事件识别。' % index)
            continue
        values = actuator.friction_scale.detach()
        minimum, maximum = float(values.min().item()), float(values.max().item())
        report('log', line='[摩擦随机化读回] 官方事件已识别飞特执行器 %d；%d 个环境；任务范围 %.4f～%.4f；实际倍率 %.4f～%.4f。' %
               (index, int(values.shape[0]), lo, hi, minimum, maximum))


def adapt_robot(cfg, agent, req):
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
