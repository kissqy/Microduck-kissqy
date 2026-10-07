"""Local glue for the installed official mjlab environment, never robotd.

This file is copied into a private Linux temporary directory by worker.py.
Official source files and dependency versions are not modified.
"""
import hashlib
import json
import math
import queue
import re
import sys
import threading
import time
from pathlib import Path

if __package__:
    from .sim_protocol import OnnxPolicy, SimulationControls
    from .recipe import apply_overrides, apply_robot, inspect_configs, validate_training_action_scale, validate_training_firmware_p
else:
    from sim_protocol import OnnxPolicy, SimulationControls
    from recipe import apply_overrides, apply_robot, inspect_configs, validate_training_action_scale, validate_training_firmware_p

if __package__:
    from .event_protocol import emit
    from . import action_filter
else:
    from event_protocol import emit
    import action_filter

if __package__:
    from .official_spec import TASKS, JOINT_TASKS, REVISION, RUNTIME_VERSION, RUNTIME_REVISION, new_training_action_scale
else:
    from official_spec import TASKS, JOINT_TASKS, REVISION, RUNTIME_VERSION, RUNTIME_REVISION, new_training_action_scale
WALK_TASKS = {name for name, info in TASKS.items() if info['role'] in ('walk', 'joint', 'roller')}



def curriculum_rewards(cfg):
    result = set()
    for term in cfg.curriculum.values():
        if term is None: continue
        params = getattr(term, 'params', {})
        for key, value in params.items():
            if 'reward' in key and isinstance(value, str): result.add(value)
    return result


def apply_agent(agent, req):
    for key, name in [('actor_dims','actor'), ('critic_dims','critic')]:
        if req.get(key): getattr(agent, name).hidden_dims = tuple(req[key])
    if req.get('activation'):
        agent.actor.activation = agent.critic.activation = req['activation']
    for key, name in [('learning_rate','learning_rate'),('gamma','gamma'),('entropy','entropy_coef'),('clip','clip_param')]:
        if req.get(key) is not None: setattr(agent.algorithm, name, req[key])
    if req.get('seed') is not None: agent.seed = req['seed']
    return agent


def apply_env(cfg, req):
    locked = curriculum_rewards(cfg)
    for name, value in req.get('reward_weights', {}).items():
        if name not in cfg.rewards or cfg.rewards[name] is None:
            raise ValueError('所选任务没有奖励项：'+name)
        if name in locked: raise ValueError('奖励 '+name+' 由官方课程调度，本版不覆盖其权重。')
        cfg.rewards[name].weight = value
    if req.get('pushes') == 'off': cfg.events.pop('push_robot', None)
    return cfg


def describe(task, req=None):
    from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
    cfg, agent = load_env_cfg(task), load_rl_cfg(task)
    if req: apply_recipe(cfg,agent,req)
    locked = curriculum_rewards(cfg)
    return {
        'inspection':inspect_configs(task,cfg,agent),
        'task':task, 'actor_dims':list(agent.actor.hidden_dims), 'critic_dims':list(agent.critic.hidden_dims),
        'activation':agent.actor.activation, 'learning_rate':agent.algorithm.learning_rate,
        'gamma':agent.algorithm.gamma, 'entropy':agent.algorithm.entropy_coef, 'clip':agent.algorithm.clip_param,
        'seed':agent.seed, 'steps_per_env':agent.num_steps_per_env,
        'terrain':getattr(cfg.scene.terrain, 'terrain_type', None),
        'pushes_available':'push_robot' in cfg.events,
        'rewards':[{'name':name,'weight':term.weight,'editable':name not in locked}
                   for name, term in cfg.rewards.items() if term is not None],
    }


def training_config(req):
    """Validate and configure the actual official API used by both gates and training."""
    from mjlab.scripts.train import TrainConfig
    cfg = TrainConfig.from_task(req['task'])
    paths = ['env.scene.num_envs','agent.max_iterations','agent.run_name',
             'agent.save_interval','agent.logger','agent.seed',
             'agent.actor.hidden_dims','agent.critic.hidden_dims',
             'agent.actor.activation','agent.critic.activation',
             'agent.algorithm.learning_rate','agent.algorithm.gamma',
             'agent.algorithm.entropy_coef','agent.algorithm.clip_param']
    if req.get('checkpoint'): paths += ['agent.resume','agent.load_run','agent.load_checkpoint']
    for path in paths:
        value = cfg
        for name in path.split('.'):
            if not hasattr(value,name):
                raise RuntimeError('当前训练引擎缺少官方配置字段 '+path+'；请核对冻结源码和依赖版本。')
            value = getattr(value,name)
    apply_agent(cfg.agent, req)
    apply_env(cfg.env, req)
    apply_recipe(cfg.env,cfg.agent,req)
    cfg.env.scene.num_envs = req['num_envs']
    cfg.agent.max_iterations = req['iterations']
    if req.get('run_name'): cfg.agent.run_name = req['run_name']
    cfg.agent.save_interval = 1000
    cfg.agent.logger = 'tensorboard'
    if req.get('checkpoint'):
        cp = Path(req['checkpoint'])
        cfg.agent.resume = True
        cfg.agent.load_run = '^'+re.escape(cp.parent.name)+'$'
        cfg.agent.load_checkpoint = '^'+re.escape(cp.name)+'$'
    if req.get('engine')=='official_0151' and req['task'] in JOINT_TASKS:
        from importlib import import_module
        configure_training=import_module((__package__+'.' if __package__ else '')+'official_adapter').configure_training
        req['_joint_receipt']=configure_training(cfg,req,inspect_configs(req['task'],cfg.env,cfg.agent))
    if req.get('engine') == 'official_0151':
        from importlib import import_module
        alignment = import_module((__package__+'.' if __package__ else '')+'sample_alignment')
        req['_curriculum_alignment'] = alignment.align_curricula(cfg.env, cfg.agent)
    return cfg


def train(req):
    from mjlab.scripts.train import launch_training
    emit('log',line='正在加载并校验官方训练配置。')
    cfg = training_config(req)
    aligned = req.get('_curriculum_alignment')
    if aligned:
        emit('log', line='[采样对齐] 4096 环境 × 24 步为基准；本次 %d 环境 × %d 步；课程轮数倍率 %.6g。%d 实际轮约合 %.2f 基准轮。' %
             (aligned['num_envs'], aligned['steps_per_iteration'], aligned['iteration_factor'],
              cfg.agent.max_iterations, cfg.agent.max_iterations / aligned['iteration_factor']))
        emit('log', line='[采样对齐] 已换算倒地复位、奖励、推扰等时间课程；地形表现晋级保持官方逻辑；每1000实际轮保存。')
    emit('log',line='训练动作系数 / Action scale = %s；目标角 = 默认姿态 + 系数 × 策略输出；折扣系数 γ = %s。' %
         (cfg.env.actions['joint_pos'].scale,cfg.agent.algorithm.gamma))
    firmware_p = cfg.env.scene.entities['robot'].articulation.actuators[0].kp_fw
    emit('log', line='[训练舵机P / Servo P] 实际执行器P=%g；仿真与导出沿用此值；实机启用运动时由模型合同写入运行P。' % firmware_p)
    if TASKS[req['task']].get('backlash'):
        emit('log', line='[训练舵机齿隙] 官方14关节±1°（总间隙2°）；HD1910输出侧编码器反馈＝电机角＋齿隙角；动作仍为14维。')
    emit('log',line='官方配置已确认：env.scene.num_envs=%s，agent.max_iterations=%s，agent.save_interval=%s。' %
         (cfg.env.scene.num_envs,cfg.agent.max_iterations,cfg.agent.save_interval))
    filter_state = action_filter.describe(cfg.env.actions['joint_pos'], 1.0 / (cfg.env.sim.mujoco.timestep * cfg.env.decimation))
    emit('log', line='[训练动作滤波] ' + action_filter.note(filter_state) + ' 上一帧动作观测仍为原始策略输出；不改变Home和动作系数。')
    emit('effective_config', data={
        'action_filter': filter_state,
        'curriculum_alignment': aligned,
        'joint':req.get('_joint_receipt'),
        'resolved':inspect_configs(req['task'],cfg.env,cfg.agent),
        'num_envs':cfg.env.scene.num_envs,'iterations':cfg.agent.max_iterations,
        'training_action_scale':cfg.env.actions['joint_pos'].scale,
        'training_firmware_p':firmware_p,
        'save_interval':cfg.agent.save_interval,'run_name':cfg.agent.run_name,
        'actor_dims':list(cfg.agent.actor.hidden_dims), 'critic_dims':list(cfg.agent.critic.hidden_dims),
        'activation':cfg.agent.actor.activation, 'learning_rate':cfg.agent.algorithm.learning_rate,
        'gamma':cfg.agent.algorithm.gamma, 'entropy':cfg.agent.algorithm.entropy_coef,
        'clip':cfg.agent.algorithm.clip_param, 'seed':cfg.agent.seed,
        'pushes':'default' if 'push_robot' in cfg.env.events else 'off',
        'reward_weights':req.get('reward_weights',{}),
    })
    from importlib import import_module
    official=import_module('mjlab.scripts.train')
    restore_alignment = (import_module((__package__+'.' if __package__ else '')+'sample_alignment').install(official,req,emit)
                         if aligned else lambda:None)
    checkpoint_policy=import_module((__package__+'.' if __package__ else '')+'checkpoint_policy')
    restore_checkpoints=checkpoint_policy.install(official,emit)
    install=import_module((__package__+'.' if __package__ else '')+'live_view').install_training_view
    first_step = None
    if req.get('engine') == 'official_0151':
        first_step = import_module((__package__+'.' if __package__ else '')+'official_adapter').report_friction_state
    restore=install(official,emit,on_first_step=first_step)
    try:launch_training(req['task'],cfg)
    finally:
        restore()
        restore_checkpoints()
        restore_alignment()


def apply_recipe(cfg, agent, req):
    recipe=req.get('studio_recipe') or {}
    if req.get('ignored_legacy_bam_overrides'):
        emit('log', line='[历史模型] 原中控记录过BAM修改，但旧执行器实际未加载；本次沿用原来真正生效的BAM参数，原PT不变。')
    if req.get('engine')=='official_0151':
        from importlib import import_module
        adapt_robot=import_module((__package__+'.' if __package__ else '')+'official_adapter').adapt_robot
        adapt_robot(cfg,agent,req)
    overrides=recipe.get('task_overrides',{}).get(req['task'],[])
    apply_overrides(cfg,agent,overrides)
    # Set the environment's position mapping, not the policy output tensor. This
    # preserves raw previous-action observations/rewards and scales exactly once.
    # Evaluation/export use the training job's immutable parameters, never the page.
    parameters = (req.get('policy_parameters') or {}) if req.get('op') in ('play','onnx','export') else req
    scale = parameters.get('training_action_scale')
    if req.get('op') in ('train','preflight'):
        scale = req.get('training_action_scale', 1.0 if req.get('source_job') else new_training_action_scale(req['task']))
    elif req.get('op') == 'preview':
        scale = req.get('training_action_scale', new_training_action_scale(req['task']))
    elif req.get('op') == 'describe':
        scale = 1.0  # Source inspection still reports the unmodified official defaults.
    if scale is not None:
        scale = validate_training_action_scale(scale)
        if 'joint_pos' not in cfg.actions or not cfg.actions['joint_pos'].use_default_offset:
            raise ValueError('当前任务不支持默认姿态偏移的关节位置动作系数。')
        cfg.actions['joint_pos'].scale = scale
    apply_robot(cfg,recipe.get('robot',{}),recipe.get('baseline'))
    # A saved source's absent key keeps its original recipe/baseline P. Do not
    # apply the new page's trial value to old PT evaluation, resume or export.
    firmware_p = parameters.get('training_firmware_p')
    if firmware_p is not None:
        firmware_p = validate_training_firmware_p(firmware_p)
        for actuator in cfg.scene.entities['robot'].articulation.actuators:
            actuator.kp_fw = float(firmware_p)
    action_filter.configure(cfg, parameters)
    agent.save_interval=1000
    if req.get('model_source') and req.get('op') in ('play','onnx','export'):
        from importlib import import_module
        spec=import_module((__package__+'.' if __package__ else '')+'official_spec')
        # Validate the rebuilt model, not merely the checkpoint's tensor shapes.
        spec.compare_contracts(req['model_source']['contract'],spec.contract(inspect_configs(req['task'],cfg,agent)))
    return cfg,agent


def preflight(req):
    cfg=training_config(req)
    group=cfg.env.observations['actor']
    required=['base_ang_vel','projected_gravity','joint_pos','joint_vel','actions','command','head_command','body_command']
    if list(group.terms)!=required or group.history_length not in (None,0) or any(t.history_length for t in group.terms.values()):
        raise ValueError('本训练台要求既有61维观测顺序且不堆叠历史；改变观测结构需要单独适配。')
    robot=cfg.env.scene.entities['robot'].build()
    model=robot.spec.compile()
    if model.nu!=14:raise ValueError('当前策略要求14个驱动关节，实际为'+str(model.nu))
    result=inspect_configs(req['task'],cfg.env,cfg.agent)
    result['checks']={'entity_compiled':True,'action_count':model.nu,'control_hz':1/(cfg.env.sim.mujoco.timestep*cfg.env.decimation),'cuda_training_tested':False}
    if req.get('_joint_receipt'):result['joint']=req['_joint_receipt']
    emit('validation',data=result)


def configure_evaluation_events(cfg, req):
    """Keep disabled evaluation pushes and their curricula consistent.

    Run after the task recipe/overrides and before ManagerBasedRlEnv constructs
    its managers. A curriculum term is matched by params.event_name, NOT by its
    dictionary key (e.g. push_range vs push_curriculum). Do not clear unrelated
    curricula or patch official files, training settings, or checkpoint data.
    """
    if req.get('op') not in ('preview', 'play', 'onnx', 'export'):
        return cfg

    managed_events = {'push_robot'}
    if req.get('engine') == 'official_0151':
        managed_events.add('topple_push')

    removed_events = []
    if not req.get('eval_pushes'):
        for name in sorted(managed_events):
            if name in cfg.events:
                cfg.events.pop(name)
                removed_events.append(name)

    # Also handle a play config (or saved recipe) that already removed the event
    # or set it to None. None is inactive in the official EventManager.
    inactive = {name for name in managed_events if cfg.events.get(name) is None}
    removed_curricula = []
    for name, term in tuple(cfg.curriculum.items()):
        if term is None:
            continue
        event_name = (getattr(term, 'params', None) or {}).get('event_name')
        if isinstance(event_name, str) and event_name in inactive:
            cfg.curriculum.pop(name)
            removed_curricula.append(name)

    if removed_events or removed_curricula:
        emit('log', line='EvalFix1：评估推扰依赖已对齐；关闭事件：%s；停用依赖课程：%s。仅作用于本次评估配置。' %
             ('、'.join(removed_events) or '无新增', '、'.join(removed_curricula) or '无'))
    return cfg


def wrap_official_config(module, parameters, req):
    old_agent,old_env=module.load_rl_cfg,module.load_env_cfg
    def agent_config(name):
        cfg=old_env(name,play=True);agent=apply_agent(old_agent(name),parameters)
        apply_recipe(cfg,agent,req)
        return agent
    def env_config(name,*args,**kwargs):
        cfg=apply_env(old_env(name,*args,**kwargs),parameters);agent=apply_agent(old_agent(name),parameters)
        apply_recipe(cfg,agent,req)
        configure_evaluation_events(cfg, req)
        from importlib import import_module
        recovery = import_module((__package__+'.' if __package__ else '')+'recovery_evaluation')
        return recovery.prepare_config(cfg, req)
    module.load_rl_cfg=agent_config;module.load_env_cfg=env_config


def export(req):
    import mjlab_microduck.export as official
    wrap_official_config(official,req.get('policy_parameters',{}),req)
    official.run_export(req['task'],official.ExportConfig(checkpoint_file=req['checkpoint'],num_envs=1,onnx_file=req['export_path']))
    path=Path(req['export_path'])
    if not path.is_file():raise RuntimeError('官方导出没有生成ONNX。')
    import onnx as onnxlib
    import onnxruntime as ort
    import numpy as np
    model=onnxlib.load(path);onnxlib.checker.check_model(model)
    session=ort.InferenceSession(str(path),providers=['CPUExecutionProvider'])
    inputs=session.get_inputs();outputs=session.get_outputs()
    if len(inputs)!=1 or len(outputs)!=1 or inputs[0].name!='obs' or len(inputs[0].shape)!=2 or len(outputs[0].shape)!=2 or inputs[0].shape[-1]!=61 or outputs[0].shape[-1]!=14:raise RuntimeError('导出模型不符合 0.15.1 的 obs [1,61] → actions [1,14] 接口。')
    if not np.isfinite(session.run(None,{inputs[0].name:np.zeros((1,61),np.float32)})[0]).all():raise RuntimeError('导出模型输出无效。')
    from mjlab.tasks.registry import load_env_cfg,load_rl_cfg
    cfg=load_env_cfg(req['task']);agent=apply_agent(load_rl_cfg(req['task']),req.get('policy_parameters',{}));apply_recipe(cfg,agent,req)
    resolved=inspect_configs(req['task'],cfg,agent)
    contract={'schema':'microduck-deployment-contract/v1','task':req['task'],'input_dim':61,'output_dim':14,'obs_normalizer':'baked_in_onnx','action_filter':action_filter.describe(cfg.actions['joint_pos']),'model':resolved['model'],'observations':resolved['full']['env']['observations']['actor'],'actions':resolved['full']['env']['actions'],'onnx_metadata':{x.key:x.value for x in model.metadata_props},'hardware_calibration':(req.get('studio_recipe') or {}).get('calibration'),'deployment_verified':False,'note':'目标固件0.15.1；按导出包的动作、观测和硬件约定部署。接口验证不等于实机步态验证。'}
    contract['task_adapter']=req.get('task_adapter')
    contract['training_adapter_revision']=req.get('training_adapter_revision')
    contract['training_hardware_calibration']=req.get('training_calibration',contract['hardware_calibration'])
    contract['commands']=resolved['full']['env']['commands']
    contract['command_note']='不同动作可能将指令槽用于阶段/姿态标志；部署按本任务观测函数和commands重建，不能统一当作行走速度。'
    contract['action_mapping']='q_target = home + training_action_scale * raw_policy_output'
    from importlib import import_module
    deployment=import_module((__package__+'.' if __package__ else '')+'deployment')
    contract.update(deployment.deployment_contract(req, resolved))
    snapshot = contract['training_snapshot']
    contract['model'] = snapshot['model']
    contract['observations'] = snapshot['full']['env']['observations']['actor']
    contract['actions'] = snapshot['full']['env']['actions']
    contract['commands'] = snapshot['full']['env']['commands']
    contract['obs_normalizer'] = ('baked_in_onnx' if contract['normalization'] == 'embedded_in_onnx_once'
                                  else 'not_used_in_training')
    contract['action_mapping'] += '; ' + ('q_filtered = alpha * q_target + (1-alpha) * previous_filtered; first tick = q_target' if contract['action_filter']['enabled'] else 'target passthrough')
    metadata={x.key:x.value for x in model.metadata_props}
    metadata['microduck.action_filter']=json.dumps(contract['action_filter'],sort_keys=True)
    metadata['microduck.deployment'] = json.dumps({
        'export_contract_revision': contract['export_contract_revision'],
        'required_policy_settings': contract['required_policy_settings'],
        'runtime_only_settings': contract['runtime_only_settings'],
        'normalization': contract['normalization'],
        'training_snapshot_sha256': snapshot['sha256'],
    }, ensure_ascii=False, sort_keys=True)
    onnxlib.helper.set_model_props(model,metadata)
    onnxlib.save(model,path)
    contract['onnx_metadata']=metadata
    deployment.write_sidecars(path, req, contract)
    path.with_suffix('.contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')


def fix_velocity_gui_sliders(server):
    """Fix only this viewer's small/zero velocity-limit GUI controls.

    mjlab creates `Max lin_vel_x/y` and `Max ang_vel_z` with min=0.1,
    even when a non-walking task configures maxima of 0.01/0.05/0.
    Preserve the actual initial value and all command/training configuration.
    """
    original = server.gui.add_slider
    labels = {'Max lin_vel_x', 'Max lin_vel_y', 'Max ang_vel_z'}

    def add_slider(label, *args, **kwargs):
        if label in labels:
            value, low, high = (kwargs.get(k) for k in ('initial_value', 'min', 'max'))
            if (all(isinstance(v, (int, float)) and math.isfinite(v) for v in (value, low, high))
                    and 0 <= value < low <= high):
                kwargs['min'] = 0.0
                kwargs['step'] = min(kwargs.get('step', 0.1), max(value, 0.001))
                emit('log', line=f'仿真滑块兼容修复：{label} 保留任务值 {value:g}，界面下限调整为 0。')
        return original(label, *args, **kwargs)

    server.gui.add_slider = add_slider
    def restore():
        server.gui.add_slider = original
    return restore


def viewer_class(req):
    import torch
    import viser
    from mjlab.viewer import ViserPlayViewer
    from importlib import import_module
    recovery = import_module((__package__+'.' if __package__ else '')+'recovery_evaluation')
    controls = SimulationControls()
    def read_controls():
        try:
            for line in sys.stdin:
                try: controls.receive(json.loads(line))
                except (ValueError, AttributeError): continue
        finally: controls.close()
    threading.Thread(target=read_controls, daemon=True).start()

    class ConsoleViewer(ViserPlayViewer):
        def __init__(self, env, policy, **kwargs):
            # Use the official PT / ONNX callable unchanged. Action mapping is
            # restored from the training recipe on the environment; policies do
            # not expose a separate inference-scale attribute.
            # Explicit loopback binding; the only control input is our owned pipe.
            server = viser.ViserServer(host='127.0.0.1', port=8080, label='Microduck · 仿真')
            restore_gui = fix_velocity_gui_sliders(server)
            if req.get('recovery_evaluation') and recovery.eligible(req):
                # A trial table belongs to one selected checkpoint. Start a new
                # viewer to compare another model instead of mixing its counts.
                kwargs['checkpoint_manager'] = None
            try: super().__init__(env, policy, viser_server=server, **kwargs)
            except BaseException:
                restore_gui()
                server.stop()
                raise
            self._console_closed=False
            self._restore_console_gui=restore_gui
            self._console_controls = controls
            self._telemetry_time = 0.0
            self._terminations = 0
            self._upright = 0.0
            self._upright_best = 0.0
            self._command = None
            self._velocity = (0.0,0.0,0.0)
            self._command_hooks = []
            self._recovery = None
            self._recovery_actions = queue.SimpleQueue()
            self._recovery_status = None
            self._pose_snapshot_requests = queue.SimpleQueue()
            self._pose_snapshot_status = None
            if req.get('recovery_evaluation') and recovery.eligible(req):
                raw = env.unwrapped
                if not getattr(raw, '_studio_recovery_evaluation', {}).get('specialist'):
                    raise RuntimeError('翻身检查配置未加载；请使用配套完整中控后端。')
                self._recovery = recovery.TrialRecorder(recovery.stand_height(raw))
            self._walk = req['task'] in WALK_TASKS and req['op'] != 'preview'
            if self._walk:
                self._command = env.unwrapped.command_manager.get_term('twist')
            if self._walk or self._recovery is not None:
                # Preserve the official command update, then apply the explicit
                # browser command. This runs on the simulation thread only.
                for name in ('twist','head_pose','body_pose'):
                    if name not in env.unwrapped.command_manager.active_terms: continue
                    term = env.unwrapped.command_manager.get_term(name)
                    original = term.compute
                    def update(dt, _term=term, _original=original, _name=name):
                        _original(dt)
                        if self._recovery is not None: _term.command.zero_()
                        elif _name == 'twist': self.apply_velocity()
                        else: _term.command.zero_()
                    term.compute = update
                    self._command_hooks.append((term, original))

        def apply_velocity(self):
            if self._recovery is not None:
                recovery.zero_commands(self.env.unwrapped)
                return
            if not getattr(self, '_walk', False): return
            velocity = controls.sample() if not self._is_paused else (0.0,0.0,0.0)
            ranges = self._command.cfg.ranges
            bounds = (ranges.lin_vel_x, ranges.lin_vel_y, ranges.ang_vel_z)
            self._velocity = tuple(max(lo, min(hi, value)) for value, (lo,hi) in zip(velocity, bounds))
            self._command.command[0,:3] = torch.tensor(self._velocity, device=self.env.device)

        def setup(self):
            super().setup()
            receipt = getattr(self.env.unwrapped, '_studio_recovery_evaluation', None)
            if receipt:
                emit('log', line='[起身评估] PT与ONNX统一使用成熟课程；姿态混合：'+
                     json.dumps(receipt['final_mix'], ensure_ascii=False)+
                     '；评估期间课程固定。仅本次仿真使用这些设置，模型权重和原训练配置未改。')
            if recovery.eligible(req):
                with self._server.gui.add_folder('姿态记录'):
                    capture = self._server.gui.add_button('记录当前姿态')
                    self._pose_snapshot_status = self._server.gui.add_html(
                        '卡住时可先暂停再记录，姿态记录写入完整日志。记录不改变当前仿真。')
                capture.on_click(lambda _: self._pose_snapshot_requests.put(True))
            if self._recovery is not None:
                with self._server.gui.add_folder('翻身检查'):
                    self._server.gui.add_markdown(
                        '平地专项检查，指令归零。固定姿态从地面上方1毫米、零速度开始。'
                        '切换姿态或点击重新放置，开始一次检查；结束后暂停。')
                    labels = list(recovery.POSES.values())
                    selected = self._server.gui.add_dropdown(
                        '起始姿态', options=labels, initial_value=recovery.POSES['back_flat'])
                    again = self._server.gui.add_button('重新放置并检查')
                    self._recovery_status = self._server.gui.add_html('准备翻身检查…')
                def select_recovery(_):
                    # Viser callbacks run outside the physics thread. Only queue
                    # the choice here; live manager writes happen in tick().
                    self._recovery_actions.put(next(key for key, label in recovery.POSES.items()
                                                    if label == selected.value))
                selected.on_update(select_recovery)
                again.on_click(select_recovery)
                self.reset_environment()
            self.apply_velocity()
            ranges=self._command.cfg.ranges if self._walk else None
            emit('viewer_ready', url='http://127.0.0.1:'+str(self._server.get_port()),
                 controls={'movement':self._walk,'pause':True,'reset':True,
                           'recovery_evaluation': self._recovery is not None,
                           'velocity_ranges':[list(ranges.lin_vel_x),list(ranges.lin_vel_y),list(ranges.ang_vel_z)] if ranges else None},
                 model=Path(req.get('onnx_path') or req.get('checkpoint') or 'zero').name)

        def tick(self):
            if controls.closed:
                self._interrupted = True
                return False
            for action in controls.drain():
                if action == 'pause': self.pause()
                elif action == 'resume': self.resume()
                elif action == 'reset': self.reset_environment()
            selected_pose = None
            while True:
                try: selected_pose = self._recovery_actions.get_nowait()
                except queue.Empty: break
            if selected_pose is not None and self._recovery is not None:
                self._recovery.mode = selected_pose
                self.reset_environment()
                self.resume()
            self._drain_pose_snapshots()
            result = super().tick()
            if time.monotonic()-self._telemetry_time >= .2:
                self._telemetry_time = time.monotonic()
                self.telemetry()
            return result

        def _drain_pose_snapshots(self):
            # Native GUI callbacks only enqueue. All live tensor reads happen
            # here on the physics thread, including while the viewer is paused.
            while True:
                try: self._pose_snapshot_requests.get_nowait()
                except queue.Empty: break
                try:
                    manager = getattr(self, '_ckpt_mgr', None)
                    state = recovery.capture_pose(self.env.unwrapped, req, self._recovery,
                                                  getattr(manager, 'current_name', None))
                    emit('log', line='MICRODUCK_POSE_RECORD '+json.dumps(state, ensure_ascii=False, allow_nan=False))
                    if self._pose_snapshot_status is not None:
                        self._pose_snapshot_status.content = '已记录当前姿态。请在运行日志中查找 MICRODUCK_POSE_RECORD。'
                except Exception as error:
                    emit('log', line='[姿态记录] 未完成：'+str(error))

        def pause(self):
            controls.clear()
            super().pause()
            self.apply_velocity()

        def resume(self):
            if self._recovery is not None and self._recovery.current and self._recovery.current['result'] in ('passed', 'failed', 'cancelled'):
                self.reset_environment()
            super().resume()

        def _handle_gui_reset(self, all_envs):
            if self._recovery is not None:
                self.reset_environment()
            else:
                super()._handle_gui_reset(all_envs)

        def reset_environment(self):
            controls.clear()
            if self._recovery is not None:
                self._recovery.finish('cancelled', '重新放置')
                # get_term_cfg returns the LIVE term in mjlab 1.3.0; env.cfg is
                # a separate copy and cannot switch an already-built manager.
                term = self.env.unwrapped.event_manager.get_term_cfg(recovery.GROUND_EVENT)
                term.params['pose'] = self._recovery.mode
            super().reset_environment()
            self._terminations = 0
            self._upright = self._upright_best = 0.0
            self.apply_velocity()
            if self._recovery is not None:
                self._recovery.start(self._recovery.mode)
                self._update_recovery_status()

        def _update_recovery_status(self):
            if self._recovery_status is not None:
                self._recovery_status.content = self._recovery.html()

        def _execute_step(self):
            self.apply_velocity()
            ok = super()._execute_step()
            if ok:
                raw = self.env.unwrapped
                done = bool(raw.reset_terminated[0].item())
                truncated = bool(raw.reset_time_outs[0].item())
                self._terminations += int(done)
                if done or truncated:
                    reset = getattr(self.policy, 'reset', None)
                    if reset: reset()
                    self._upright = 0.0
                else:
                    upright = float(raw.scene['robot'].data.projected_gravity_b[0,2].item()) < -math.sqrt(.5)
                    self._upright = self._upright+raw.step_dt if upright else 0.0
                    self._upright_best = max(self._upright_best,self._upright)
                if self._recovery is not None:
                    data = raw.scene['robot'].data
                    origin_z = float(raw.scene.env_origins[0,2].item())
                    finished = self._recovery.observe(
                        raw.step_dt,
                        height=float(data.root_link_pos_w[0,2].item()) - origin_z,
                        gravity_z=float(data.projected_gravity_b[0,2].item()),
                        terminated=done, timed_out=truncated)
                    if finished:
                        self.pause()
                        self._sim_budget = 0.0
                        self._update_recovery_status()
                        result = self._recovery.current
                        emit('log', line='[翻身检查] '+recovery.POSES[result['pose']]+'：'+
                             result['reason']+'；'+format(result['elapsed_s'], '.2f')+'秒。')
            elif self._recovery is not None:
                self._recovery.finish('cancelled', '仿真计算错误，本次不计入成功率')
                self._update_recovery_status()
            return ok

        def telemetry(self):
            raw = self.env.unwrapped
            data = raw.scene['robot'].data
            actual = [float(v) for v in data.root_link_lin_vel_b[0,:2].tolist()]
            actual.append(float(data.root_link_ang_vel_b[0,2].item()))
            q = data.root_link_quat_w[0].tolist()
            w,x,y,z = q
            roll = math.degrees(math.atan2(2*(w*x+y*z),1-2*(x*x+y*y)))
            pitch = math.degrees(math.asin(max(-1,min(1,2*(w*y-z*x)))))
            status = self.get_status()
            self._update_recovery_status()
            emit('sim_state', data={
                'command':self._command.command[0,:3].tolist() if self._walk else None,
                'control':controls.status(),
                'actual':actual,'roll':roll,'pitch':pitch, 'paused':status.paused,
                'steps':status.step_count,'sim_seconds':status.step_count*raw.step_dt,
                'loop_fps':status.smoothed_fps,'realtime':status.actual_realtime,
                'episode_seconds':float(raw.episode_length_buf[0].item())*raw.step_dt,
                'terminations':self._terminations,'upright_seconds':self._upright,'upright_best':self._upright_best,
                'recovery_evaluation': self._recovery.state() if self._recovery is not None else None,
                'error':'物理仿真已暂停：计算出错，请查看运行日志。' if status.last_error else None,
            })

        def close(self):
            if self._console_closed:return
            self._console_closed=True
            controls.close()
            for term, original in self._command_hooks: term.compute = original
            # Upstream GUI cleanup still sends remove messages. Keep the server
            # alive until those resources and the scene pool are released.
            # The parent viewer watchdog bounds a hung physics/scene shutdown.
            self._restore_console_gui()
            try:super().close()
            finally:self._server.stop()

    return ConsoleViewer


def play(req):
    import mjlab.scripts.play as official
    wrap_official_config(official, req.get('policy_parameters',{}), req)
    official.ViserPlayViewer = viewer_class(req)
    official.run_play(req['task'], official.PlayConfig(
        agent='zero' if req['op'] == 'preview' else 'trained',
        checkpoint_file=req.get('checkpoint'),num_envs=1,viewer='viser'))


def onnx(req):
    import torch
    from mjlab.envs import ManagerBasedRlEnv
    from mjlab.rl import RslRlVecEnvWrapper
    from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
    from mjlab.utils.torch import configure_torch_backends
    configure_torch_backends()
    path = Path(req['onnx_path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != req['onnx_sha256']:
        raise ValueError('ONNX 文件已变化，请重新从本台导出后再验证。')
    parameters = req.get('policy_parameters',{})
    cfg = apply_env(load_env_cfg(req['task'], play=True), parameters)
    agent = apply_agent(load_rl_cfg(req['task']), parameters)
    apply_recipe(cfg,agent,req)
    cfg.scene.num_envs = 1
    configure_evaluation_events(cfg, req)
    from importlib import import_module
    recovery = import_module((__package__+'.' if __package__ else '')+'recovery_evaluation')
    recovery.prepare_config(cfg, req)
    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    env = RslRlVecEnvWrapper(ManagerBasedRlEnv(cfg=cfg,device=device),clip_actions=agent.clip_actions)
    try:
        obs = env.get_observations()
        groups = agent.obs_groups['actor']
        if any(obs[key].ndim != 2 for key in groups): raise ValueError('本版 ONNX 评估只支持向量观测。')
        width = sum(obs[key].shape[-1] for key in groups)
        policy = OnnxPolicy(path,width,env.num_actions,groups,env.device)
        policy(obs)  # A real inference must succeed before the viewer is exposed.
        policy.reset()
        viewer_class(req)(env,policy).run()
    finally: env.close()


def main(req):
    import mjlab.tasks  # Registers the installed official task package.
    if req.get('engine')=='official_0151':
        from importlib import import_module
        register_tasks=import_module((__package__+'.' if __package__ else '')+'official_adapter').register_tasks
        register_tasks()
    if req['op'] == 'describe': emit('task_config', data=describe(req['task'],req))
    elif req['op'] == 'preflight': preflight(req)
    elif req['op'] == 'train': train(req)
    elif req['op'] == 'export': export(req)
    elif req['op'] in ('preview','play'): play(req)
    elif req['op'] == 'onnx': onnx(req)
    else: raise ValueError('不支持的训练操作。')


if __name__ == '__main__':
    main(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
