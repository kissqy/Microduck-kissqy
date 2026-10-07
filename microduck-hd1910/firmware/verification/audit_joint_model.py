"""Read-only model audit; reads JSON and ONNX, never unpickles checkpoint.pt."""
from pathlib import Path
from collections import Counter
import copy
import hashlib
import json
import math
import sys

import numpy as np
import onnxruntime as ort

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'model-input'
SOURCE = ROOT / 'source' / 'Microduck-Source-R17-v1.0.146'
BASELINES = {'walk':SOURCE / 'test-data' / 'walk-teacher14000',
             'stand':SOURCE / 'policies' / 'stand'}

def read(p):
    return json.loads(p.read_text())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def varint(b, i):
    out = 0
    for j in range(10):
        if i >= len(b):
            raise ValueError('truncated varint')
        v = b[i]
        i += 1
        out |= (v & 127) << (7 * j)
        if v < 128:
            return out, i
    raise ValueError('excessive varint')

def fields(b):
    i = 0
    while i < len(b):
        tag, i = varint(b, i)
        f, w = tag >> 3, tag & 7
        if w == 0:
            v, i = varint(b, i)
        elif w in (1, 5):
            n = 8 if w == 1 else 4
            v = b[i:i+n]
            i += n
        elif w == 2:
            n, i = varint(b, i)
            v = b[i:i+n]
            i += n
        else:
            raise ValueError('unsupported protobuf wire type ' + str(w))
        if i > len(b):
            raise ValueError('truncated protobuf')
        yield f, w, v

contract = read(INPUT / 'deployment-contract.json')
manifest = read(INPUT / 'manifest.json')
snapshot = read(INPUT / 'training-config.json')
model_path = INPUT / 'policy.onnx'
model = dict((f,v) for f,w,v in fields(model_path.read_bytes()))
graph = list(fields(model[7]))
nodes = []
initializers = []
for f,w,b in graph:
    if f == 1:
        node = {'inputs': [], 'outputs': []}
        for nf,nw,v in fields(b):
            if nf == 1:
                node['inputs'].append(v.decode())
            elif nf == 2:
                node['outputs'].append(v.decode())
            elif nf in (3,4,7):
                node[{3:'name',4:'op',7:'domain'}[nf]] = v.decode()
        nodes.append(node)
    elif f == 5:
        init = {'shape': []}
        raw = None
        for nf,nw,v in fields(b):
            if nf == 1 and nw == 0:
                init['shape'].append(v)
            elif nf == 2:
                init['data_type'] = v
            elif nf == 8:
                init['name'] = v.decode()
            elif nf == 9:
                raw = v
        if raw is not None and init.get('data_type') == 1:
            values = np.frombuffer(raw, dtype='<f4')
            init['all_finite'] = bool(np.isfinite(values).all())
            init['elements'] = int(values.size)
            if init.get('name') in ('obs_normalizer._mean', 'onnx::Div_24'):
                init['minimum'] = float(values.min())
                init['maximum'] = float(values.max())
                init['all_positive'] = bool((values > 0).all())
        initializers.append(init)

options = ort.SessionOptions()
options.intra_op_num_threads = 1
options.inter_op_num_threads = 1
session = ort.InferenceSession(str(model_path), options, providers=['CPUExecutionProvider'])
probes = []
for deg in [0,20,24,25,26,34,35,36,45,60,90,120,180]:
    for axis in [0,1]:
        radians = math.radians(deg)
        obs = np.zeros((1,61), np.float32)
        obs[0,3+axis] = math.sin(radians)
        obs[0,5] = -math.cos(radians)
        actions = session.run(None, {'obs': obs})[0]
        probes.append({'tilt_deg':deg, 'axis':axis, 'finite':bool(np.isfinite(actions).all()),
                       'shape':list(actions.shape), 'min':float(actions.min()), 'max':float(actions.max())})

comparisons = {}
for role in ['walk', 'stand']:
    baseline_path = BASELINES[role] / 'deployment-contract.json'
    previous = read(baseline_path)
    current_actuator = copy.deepcopy(contract['model']['actuators'])
    old_actuator = copy.deepcopy(previous['model']['actuators'])
    for value in current_actuator + old_actuator:
        value.pop('json_path', None)
    old_bodies = {b['name']: b for b in previous['model']['bodies']}
    new_bodies = {b['name']: b for b in contract['model']['bodies']}
    body_diff = {name:{k:{'new':new_bodies[name][k], 'previous':old_bodies[name][k]}
                      for k in new_bodies[name] if new_bodies[name][k] != old_bodies[name][k]}
                 for name in new_bodies if new_bodies[name] != old_bodies[name]}
    comparisons[role] = {
        'baseline_contract':str(baseline_path),
        'baseline_contract_sha256':sha(baseline_path),
        'equal_fields':{k:contract.get(k) == previous.get(k) for k in
                        ['runtime_joint_order','runtime_home_rad','observations','commands','hardware_command',
                         'previous_action_observation','normalization','gear_backlash','robot_mode']},
        'hardware_calibration_data_equal':contract['hardware_calibration']['data'] == previous['hardware_calibration']['data'],
        'joint_definitions_including_limits_equal':contract['model']['joints'] == previous['model']['joints'],
        'bam_and_runtime_actuator_properties_equal_ignoring_temporary_path':current_actuator == old_actuator,
        'body_differences':body_diff,
        'total_mass_equal':contract['model']['total_mass_kg'] == previous['model']['total_mass_kg'],
        'collision_geom_count':{'new':len(contract['model']['collision_geoms']), 'previous':len(previous['model']['collision_geoms'])}
    }

bc = snapshot['full']['agent']['algorithm']['bc_cfg']
execution_path = SOURCE / 'policies' / 'walk' / 'deployment-execution.json'
execution = read(execution_path)
audit = {
    'schema':'microduck-joint-model-audit/v1',
    'scope':'Read-only uploaded JSON/ONNX analysis; checkpoint.pt was never unpickled; no real robot or closed-loop simulator test.',
    'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in INPUT.iterdir() if p.is_file() and p.name != 'checkpoint.pt'},
    'identity':{'task':manifest['task'],'slot':manifest['slot'],'role':contract['role'],
                'onnx_sha256':sha(model_path),'model_id':sha(model_path)[:32],
                'manifest_sha_matches':sha(model_path) == manifest['onnx_sha256'],
                'checkpoint_iteration':manifest['training']['checkpoint'], 'training_max_iterations':snapshot['full']['agent']['max_iterations'],
                'num_envs':snapshot['full']['env']['scene']['num_envs'], 'control_hz':contract['control_hz'],
                'training_source_revision':manifest['training']['commit'], 'snapshot_provenance':snapshot['provenance'],
                'origin':'Uploaded locally trained HD1910 joint student using the pinned official training recipe; not a claim that these weights are an official published velstand model.',
                'training_source_file':manifest['training']['source_file'],
                'training_adapter_revision':manifest['model_origin']['training_adapter_revision'],
                'deployment_verified_in_original_manifest':manifest['deployment_verified']},
    'training_action':{'source_keys':['deployment-contract.json/action_mapping','deployment-contract.json/actions/joint_pos',
                                      'manifest.json/required_policy_settings'],
                       'mapping':contract['action_mapping'], 'action_term':contract['actions']['joint_pos'],
                       'filter':contract['action_filter'], 'required_policy_settings':contract['required_policy_settings'],
                       'previous_action_observation':contract['previous_action_observation'],
                       'runtime_only_settings':contract['runtime_only_settings']},
    'training_expert_bc':{'source_key':'training-config.json/full/agent/algorithm/bc_cfg',
                          'gate_tilt_deg':bc['gate_tilt_deg'],'anchor_tilt_deg':bc['anchor_tilt_deg'],
                          'gravity_slice':bc['gravity_slice'], 'twist_slice':bc['twist_slice'],
                          'coef':bc['coef'], 'anchor_coef':bc['anchor_coef'],
                          'checkpoint_path':bc['checkpoint_path'], 'anchor_checkpoint_path':bc['anchor_checkpoint_path'],
                          'limits':'The package records config and cached checkpoint paths, not the CheckpointedExpertPpo implementation or teacher weights. Do not infer teacher iterations from checkpoint_name defaults, and do not claim a runtime teacher label exists.'},
    'training_recovery_reward':{'source_key':'training-config.json/full/env/rewards/recovery_success/params',
                                'parameters':{k:v for k,v in snapshot['full']['env']['rewards']['recovery_success']['params'].items() if k != 'asset_cfg'},
                                'limits':'up_z is simulator world height. Existing robot odometry assumes a foot contact anchor and is not a direct world-height sensor.'},
    'onnx':{'runtime_version':ort.__version__, 'inputs':[{'name':v.name,'shape':v.shape,'type':v.type} for v in session.get_inputs()],
            'outputs':[{'name':v.name,'shape':v.shape,'type':v.type} for v in session.get_outputs()],
            'ops':dict(Counter(v['op'] for v in nodes)), 'nodes':nodes, 'initializers':initializers,
            'all_initializers_finite':all(v.get('all_finite',False) for v in initializers),
            'normalization':'One Sub/Div normalizer before the MLP. No external re-normalization is needed.',
            'mode_output_present':False, 'recurrent_state_present':False, 'output_postprocessing_in_graph':False,
            'finite_probe_count':len(probes), 'finite_probe_passes':sum(p['finite'] and p['shape']==[1,14] for p in probes),
            'finite_probes':probes,
            'probe_limits':'Synthetic snapshots with zero gyro, HOME-relative joint positions, velocities, previous actions and commands. Checks format/finite inference only, not recovery success, stability, or sim-to-real equivalence.'},
    'baseline_comparison':comparisons,
    'final_deployment_selection':{
        'status':'User-authorized uniform runtime tuning in every posture; no teacher phase detector or posture-based parameter switch.',
        'execution_file':str(execution_path), 'execution_sha256':sha(execution_path), 'profile':execution,
        'binding_matches_model':execution['model_sha256']==sha(model_path),
        'storage':'Separate model-SHA256-bound deployment-execution.json; original ONNX, manifest, deployment contract and training-profile TOML remain byte-for-byte training records.',
        'schema_limits':{'supported_task':'Mjlab-VelStand-Rough-Backlash-MicroDuck','supported_slot':'walk',
                         'mode':'uniform','action_scale_inclusive_range':[0.1,2.0],
                         'head_and_legs_lowpass':'finite number >0 and <=1; reject booleans, unknown and duplicate fields'},
        'missing_execution_profile':'Use the recorded training base scale1/head1/legs1, without inheriting an unrelated saved global0.7.',
        'training_gate_boundary':'The recorded 35/25-degree masks select teacher losses during training. They do not configure deployed scale/filter switching.',
        'observations':'previous_action remains the previous raw ONNX action, before target scale/filter.',
        'loop':'Existing 50 Hz policy loop; one ONNX inference per policy step. No second inference, new telemetry loop, network task or posture switch required by this uniform profile.',
        'hardware':'Preserve current robot calibration, independent LB recovery skill and existing motor/input protections.',
        'catalog':'Exactly one shipped Walk at policies/walk; the old teacher is only test-data/walk-teacher14000, excluded from the firmware model catalog.',
        'voltage_adaptation':'Existing voltage compensation remains active according to the saved setting. The profile specifies a base action scale, not a promise that the final effective scale is identical.',
        'limitation':'The entire joint student was trained at1/1/1. Uniform0.9/0.5/0.7 is the requested runtime experiment, not a recovered teacher-specific or officially trained setting. No real Zero, closed-loop simulation or real Chromium validation is claimed.'}
}
reference = ROOT / 'official-reference' / 'microduck_rl-src_mjlab_microduck_tasks_distill.py'
if reference.exists():
    audit['upstream_gate_verification'] = {
        'source_file':str(reference), 'sha256':sha(reference),
        'revision':manifest['training']['commit'],
        'predicate':'g=gravity/norm(gravity); fallen=(-g.z < cos(gate)); therefore stand expert is used above 35 degrees, walk anchor at or below 25 degrees, no BC teacher between 25 and 35 degrees.',
        'functions':['fallen_mask_from_obs','PpoWithExpertBc._bc_update','expert_input'],
        'student_twist':'Only the stand teacher input is twist-zeroed for the training loss; this is not a runtime instruction to zero the deployed student command.',
        'limits':'Training-only BC masks, not a deployment switch. This is the pinned upstream implementation; the recorded local CheckpointedExpertPpo adapter implementation is not present in the uploaded package.'
    }
(ROOT / 'joint-model-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
text = '''联合模型审计（仅输入文件及源码读取；未执行 checkpoint.pt）

模型：Mjlab-VelStand-Rough-Backlash-MicroDuck，2560 并行，9600 次训练上限，导出 model_9599，50 Hz。
ONNX SHA256：%s
接口：obs[1,61] -> actions[1,14]，单一无状态 MLP。图结构为一次 Sub/Div 观测归一化、4 个 Gemm、3 个 Elu。无老师身份、模式或起身完成标签，也没有图内动作缩放/滤波。26 个合成倾角探针均输出有限值，仅验证接口和推理可执行。

训练动作：q_target = HOME + 1.0 * raw_action；头腿 EMA 禁用。下一帧 previous_action 是原始 ONNX 输出，不能用缩放/滤波后的目标替换。
训练专家配置：bc_cfg.gate_tilt_deg=35.0；anchor_tilt_deg=25.0；gravity_slice=[3,6]。包内没有该专家适配类实现和两个老师权重，老师缓存路径不等于可验证的老师版本。恢复成功奖励还要求 up_z=0.09 m；这是仿真真实高度，实机脚支撑里程计不能冒充该测量。

兼容性：新模型与 v145 当前 Walk 及 LB 老师的实际 HOME、14 动作关节顺序、29 关节定义/限位、观测定义、硬件标定来源数据、BAM 参数、P=5 和电气参数一致；BAM 只有临时路径不同。总质量仍0.82 kg。jaw_soft 惯量约1e-9量级数值差，其他身体定义相同；新包比旧包额外记录15个舵机碰撞几何。Walk 命令定义也完全相同。

本版最终部署选择：按用户最终授权，联合模型在所有姿态下统一使用基础动作缩放0.9、头滤波0.5、腿滤波0.7。没有运行期老师身份判断，也没有35°/25°或其他倒地切档。参数放到与 ONNX SHA256 绑定的独立 deployment-execution.json（mode=uniform），原 ONNX、manifest、deployment-contract.json、deployment-profile.toml 等训练记录仍逐字节保留全1事实。若没有独立执行配置，联合模型用原训练1/1/1，不受旧全局0.7干扰。保留 raw previous_action，既有50 Hz内一次推理，无新增采集或网络任务。电压补偿沿用保存设置，因此这里的0.9是基础缩放，不保证最终有效倍率永远等于0.9。

发布模型：新联合模型在 policies/walk 替换唯一 Walk，ID 为 %s。旧14000轮 Walk 移到 test-data/walk-teacher14000 仅作数值回归资料，不在固件模型列表；独立 LB11000 和其他动作保留。Python 导入适配已接受精确任务 Mjlab-VelStand-Rough-Backlash-MicroDuck 与 Walk 槽，执行配置拒绝错 SHA、错任务、错槽、未知或重复字段、非有限及越界数字。原训练 ZIP 重导入时保留已安装的独立执行参数。

来源和边界：包中记录本地训练台 model_9599.pt 与 HD1910 适配版本R1.5.9；这是按固定官方训练配方自训的联合学生，不能把这份权重称为官方发布 velstand 原模型。上传包的 required_policy_settings 及 deployment-profile.toml 均为1/1/1；没有官方部署阶段切换记录。训练35°/25°仅决定BC损失的老师掩码，不能据此推导运行输出档位。本版统一0.9/0.5/0.7是明确的用户运行试验，不能保证实机步态不变。本审计没有真实Zero、真实Chromium或闭环物理仿真测试。

详细证据、原文件哈希和字段位置见 joint-model-audit.json。
''' % (sha(model_path),sha(model_path)[:32])
if reference.exists():
    text += '\n补充：已读取与训练提交一致的官方 distill.py。其函数 fallen_mask_from_obs 先归一化重力，再以 -g.z < cos(门限) 判断；训练中起身专家作用于大于35°、行走老师作用于不大于25°、中间区域无BC老师约束。仅老师输入的twist被置零，联合学生部署指令不因此改写。本包的本地CheckpointedExpertPpo适配实现未附带，不能额外断言其实现细节。\n'
(ROOT / 'joint-model-audit.txt').write_text(text)
print(json.dumps({'audit_json':str(ROOT / 'joint-model-audit.json'),'audit_txt':str(ROOT / 'joint-model-audit.txt'),
                  'sha256':sha(model_path),'finite_probe_passes':audit['onnx']['finite_probe_passes'],
                  'initializers_finite':audit['onnx']['all_initializers_finite'],'ops':audit['onnx']['ops']},ensure_ascii=False))
