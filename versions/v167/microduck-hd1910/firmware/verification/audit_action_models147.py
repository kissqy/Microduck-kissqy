"""Audit ZIP/JSON/ONNX bytes without unpickling, importing or executing package code."""
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import stat
import struct
import tarfile
import tomllib
import zipfile

import numpy as np
try:
    import onnx
    import onnxruntime as ort
except ImportError:
    onnx=None
    ort=None

ROOT=Path(__file__).resolve().parent
WORKSPACE=ROOT.parent
UPLOAD=WORKSPACE/'upload'
BASELINE=WORKSPACE/'recovered-r17-146/宠物机器人/Microduck-Source-R17-v1.0.146.tar.gz'
INPUTS={'roulade':'前滚翻_10000_4096_无缩放滤波.zip',
        'ground_pick':'低头减取_10000_4096_无缩放滤波.zip'}
NAMES='left_hip_yaw left_hip_roll left_hip_pitch left_knee left_ankle neck_pitch head_pitch head_yaw head_roll right_hip_yaw right_hip_roll right_hip_pitch right_knee right_ankle'.split()
BAM='ef2d51adfb1cc0831b9b02ca19aa9176fceecdf725148d084378d7d9a64afceb'

def digest(data):return hashlib.sha256(data).hexdigest()
def unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('duplicate JSON field: '+k)
        result[k]=v
    return result
def read_json(data):return json.loads(data,object_pairs_hook=unique)
def varint(data,index):
    value=0
    for shift in range(0,70,7):
        if index>=len(data):raise ValueError('truncated varint')
        byte=data[index];index+=1;value|=(byte&127)<<shift
        if byte<128:return value,index
    raise ValueError('invalid varint')
def fields(data):
    index=0
    while index<len(data):
        tag,index=varint(data,index);field,wire=tag>>3,tag&7
        if wire==0:value,index=varint(data,index)
        elif wire==2:
            size,index=varint(data,index);value=data[index:index+size];index+=size
            if len(value)!=size:raise ValueError('truncated protobuf field')
        elif wire in (1,5):
            size=8 if wire==1 else 4;value=data[index:index+size];index+=size
            if len(value)!=size:raise ValueError('truncated protobuf fixed field')
        else:raise ValueError('unsupported protobuf wire '+str(wire))
        yield field,wire,value
def values(data,key):return [v for k,_,v in fields(data) if k==key]
def one(data,key):
    result=values(data,key)
    if len(result)!=1:raise ValueError('missing or duplicate protobuf field '+str(key))
    return result[0]

def onnx_audit(raw,slot):
    graph=one(raw,7)
    metadata={one(v,1).decode():one(v,2).decode() for v in values(raw,14)}
    def outlet(v):
        tensor=one(one(v,2),1)
        return {'name':one(v,1).decode(),'dtype':one(tensor,1),
                'shape':[one(dim,1) for dim in values(one(tensor,2),1)]}
    inputs=[outlet(v) for v in values(graph,11)]
    outputs=[outlet(v) for v in values(graph,12)]
    arrays={};initializers=[]
    for tensor in values(graph,5):
        dims=[]
        for k,w,v in fields(tensor):
            if k==1 and w==0:dims.append(v)
            elif k==1 and w==2:
                i=0
                while i<len(v):n,i=varint(v,i);dims.append(n)
        dtype=one(tensor,2);name=one(tensor,8).decode()
        if dtype!=1:raise ValueError('non-float initializer '+name)
        if values(tensor,13) or values(tensor,14):raise ValueError('external ONNX tensor')
        array=np.frombuffer(one(tensor,9),dtype='<f4').reshape(dims)
        arrays[name]=array
        initializers.append({'name':name,'shape':dims,'all_finite':bool(np.isfinite(array).all())})
    nodes=[]
    for n in values(graph,1):
        attrs={}
        for a in values(n,5):
            name=one(a,1).decode();f=values(a,2);i=values(a,3)
            if f:attrs[name]=struct.unpack('<f',f[0])[0]
            elif i:attrs[name]=i[0]
            else:raise ValueError('unsupported ONNX attribute '+name)
        node={'op':one(n,4).decode(),'inputs':[v.decode() for v in values(n,1)],
              'outputs':[v.decode() for v in values(n,2)],'attributes':attrs}
        domain=values(n,7)
        if domain and domain[0] not in (b'',b'ai.onnx'):raise ValueError('custom ONNX op domain')
        nodes.append(node)
    def infer(obs):
        env={**arrays,'obs':obs}
        for n in nodes:
            x=[env[k] for k in n['inputs']];a=n['attributes'];op=n['op']
            if op=='Sub':result=x[0]-x[1]
            elif op=='Div':result=x[0]/x[1]
            elif op=='Gemm':
                left=x[0].T if a.get('transA',0) else x[0]
                right=x[1].T if a.get('transB',0) else x[1]
                result=a.get('alpha',1.0)*(left@right)+a.get('beta',1.0)*x[2]
            elif op=='Elu':
                result=x[0].copy();negative=result<0
                result[negative]=a.get('alpha',1.0)*np.expm1(result[negative])
            else:raise ValueError('unsupported reference inference operation '+op)
            if len(n['outputs'])!=1:raise ValueError('multiple node outputs')
            env[n['outputs'][0]]=result
        return env[outputs[0]['name']]
    session=None
    runtime_check={'available':ort is not None and onnx is not None}
    if runtime_check['available']:
        onnx.checker.check_model(raw,full_check=True)
        options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
        session=ort.InferenceSession(raw,options,providers=['CPUExecutionProvider'])
        runtime_check.update({'onnx_checker_version':onnx.__version__,'onnx_checker_passed':True,
                              'onnxruntime_version':ort.__version__,'provider':'CPUExecutionProvider'})
    probes=[]
    for tilt in (0,45,90,180):
        for phase in ((0,.25,.5,.7) if slot=='ground_pick' else (0,)):
            obs=np.zeros((1,61),np.float32);r=math.radians(tilt)
            obs[0,3]=math.sin(r);obs[0,5]=-math.cos(r)
            if slot=='ground_pick':obs[0,48:51]=(math.cos(2*math.pi*phase),math.sin(2*math.pi*phase),0)
            result=infer(obs)
            probe={'tilt_deg':tilt,'phase':phase,'finite':bool(np.isfinite(result).all()),
                   'shape':list(result.shape),'minimum':float(result.min()),'maximum':float(result.max())}
            if session is not None:
                actual=session.run(None,{'obs':obs})[0]
                probe.update({'ort_finite':bool(np.isfinite(actual).all()),'ort_shape':list(actual.shape),
                              'ort_reference_max_abs_delta':float(np.max(np.abs(actual-result))),
                              'ort_matches_reference':bool(np.allclose(actual,result,rtol=1e-4,atol=1e-5))})
            probes.append(probe)
    if session is not None:
        runtime_check.update({'finite_probe_count':sum(p['ort_finite'] and p['ort_shape']==[1,14] for p in probes),
                              'all_match_reference':all(p['ort_matches_reference'] for p in probes),
                              'maximum_reference_delta':max(p['ort_reference_max_abs_delta'] for p in probes)})
    return {'inputs':inputs,'outputs':outputs,'metadata':metadata,'ops':dict(Counter(n['op'] for n in nodes)),
            'nodes':nodes,'initializers':initializers,'all_initializers_finite':all(i['all_finite'] for i in initializers),
            'normalization':'Sub and Div before MLP; normalization is embedded once.',
            'reference_inference':'NumPy float32 evaluation of parsed ONNX Sub/Div/Gemm/Elu; independently compared with host ONNX Runtime when the optional library is available.',
            'host_runtime_check':runtime_check,
            'probes':probes,'finite_probe_count':sum(p['finite'] and p['shape']==[1,14] for p in probes),
            'probe_limits':'Synthetic snapshots only; no temporal rollout, closed-loop dynamics, recovery success or physical safety assertion.'}

def actuator_without_temp_path(value):
    value=copy.deepcopy(value)
    for row in value:row.pop('json_path',None)
    return value

baseline_files={}
if BASELINE.is_file():
    with tarfile.open(BASELINE) as archive:
        for member in archive.getmembers():
            for role in ('walk','stand','ground_pick','roulade'):
                suffix=f'/policies/{role}/deployment-contract.json'
                if member.isfile() and member.name.endswith(suffix):baseline_files[role]=archive.extractfile(member).read()

report={'schema':'microduck-action-model-audit/v1','scope':'Read-only uploaded ZIP/JSON/ONNX audit. checkpoint.pt is CRC checked as opaque bytes only; never unpickled or executed.',
        'baseline_archive':str(BASELINE),'models':{},'unchanged_requirements':{'joint_walk':'Keep uniform .9/.5/.7 and existing SHA-bound profile','lb':'Keep independent LB11000','calibration':'Retain installed calibration; archived calibration is comparison data only.'}}
for role,filename in INPUTS.items():
    path=UPLOAD/filename
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist();names=[e.filename for e in entries]
        safe=all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts and '\\' not in n for n in names)
        symlinks=[e.filename for e in entries if stat.S_ISLNK(e.external_attr>>16)]
        duplicate_names=len(names)!=len(set(names))
        if not safe or symlinks or duplicate_names:raise ValueError('unsafe ZIP structure')
        crc_failure=archive.testzip()
        if crc_failure:raise ValueError('ZIP CRC failure: '+crc_failure)
        files={n:archive.read(n) for n in names if n!='checkpoint.pt'}
    m=read_json(files['manifest.json']);c=read_json(files['deployment-contract.json'])
    r=read_json(files['training-request.json']);s=read_json(files['training-config.json'])
    profile=tomllib.loads(files['deployment-profile.toml'].decode())['policy']
    graph=onnx_audit(files['policy.onnx'],role);onnx_sha=digest(files['policy.onnx'])
    joints={j['name']:j for j in c['model']['joints']};active={n:joints[n] for n in NAMES}
    actuator=c['model']['actuators'][0]
    command=c['commands']['twist'];metadata=graph['metadata']
    deployment=read_json(metadata['microduck.deployment'])
    checks={
        'zip_safe_unique_names':safe and not duplicate_names and not symlinks,'all_zip_crcs_valid':crc_failure is None,
        'required_files_present':all(n in files for n in ('policy.onnx','manifest.json','deployment-contract.json','training-request.json','training-config.json','deployment-profile.toml','upstream-params/agent.yaml','upstream-params/env.yaml')),
        'onnx_sha_matches_manifest':onnx_sha==m['onnx_sha256'],
        'task_matches_contract_manifest_request_snapshot':len({m['task'],c['task'],r['task'],s['task']})==1,
        'slot_matches_manifest_contract':m['slot']==c['slot']==role,
        'onnx_metadata_matches_original_contract':metadata==c['onnx_metadata'],
        'single_float32_61_to_14_interface':graph['inputs']==[{'name':'obs','dtype':1,'shape':[1,61]}] and graph['outputs']==[{'name':'actions','dtype':1,'shape':[1,14]}],
        'training_action_matches_full_snapshot':c['actions']==s['full']['env']['actions'],
        'training_commands_match_full_snapshot':c['commands']==s['full']['env']['commands'],
        'scale_one_all_actual_task_records':all(v==1.0 for v in (c['trained_action_scale'],c['actions']['joint_pos']['scale'],m['action_scale'],r['policy_parameters']['training_action_scale'],float(metadata['action_scale']))),
        'filter_records_match':c['action_filter']==m['action_filter']==r['policy_parameters']['action_filter']==read_json(metadata['microduck.action_filter']),
        'filter_disabled_and_alphas_one':c['action_filter']['enabled'] is False and c['action_filter']['head_alpha']==c['action_filter']['legs_alpha']==1,
        'required_settings_match_all_deployment_records':c['required_policy_settings']==m['required_policy_settings']==profile==deployment['required_policy_settings'],
        'training_snapshot_declared_hash_consistent':s['sha256']==m['training_snapshot_sha256']==deployment['training_snapshot_sha256'],
        'joint_order_matches_onnx':c['runtime_joint_order']==metadata['joint_names'].split(',')==NAMES,
        'runtime_home_matches_exact_model_joints':c['runtime_home_rad']==[active[n]['home_rad'] for n in NAMES],
        'rounded_onnx_home_matches_contract':all(abs(a-b)<=.000501 for a,b in zip(c['runtime_home_rad'],map(float,metadata['default_joint_pos'].split(',')))),
        'home_within_training_joint_limits':all(not j['limited'] or j['range'][0]<=j['home_rad']<=j['range'][1] for j in active.values()),
        'bam_expected_sha':len(c['model']['actuators'])==1 and actuator['parameter_file']['sha256']==BAM,
        'p_five_matches_contract_request_actuator':c['hardware_command']['firmware_kp_raw']==r['policy_parameters']['training_firmware_p']==actuator['kp_fw']==actuator['runtime_properties']['kp_fw']==5,
        'all_onnx_weights_finite':graph['all_initializers_finite'],
        'all_reference_probes_finite':graph['finite_probe_count']==len(graph['probes'])}
    if role=='ground_pick':checks['phase_duration_consistent']=m['duration_s']==m['command']['period_s']*m['command']['end_phase'] and m['command']['period_s']==command['period']==4.0
    if graph['host_runtime_check']['available']:
        checks['host_onnx_checker_passed']=graph['host_runtime_check']['onnx_checker_passed']
        checks['host_ort_all_probes_finite']=graph['host_runtime_check']['finite_probe_count']==len(graph['probes'])
        checks['host_ort_matches_numpy_reference']=graph['host_runtime_check']['all_match_reference']
    if not all(checks.values()):raise ValueError(filename+' failed checks: '+str([k for k,v in checks.items() if not v]))
    comparisons={}
    for baseline_role,raw in baseline_files.items():
        old=read_json(raw);old_joints={j['name']:j for j in old['model']['joints']}
        comparisons[baseline_role]={
            'contract_sha256':digest(raw),'same_runtime_joint_order':c['runtime_joint_order']==old['runtime_joint_order'],
            'same_exact_home':c['runtime_home_rad']==old['runtime_home_rad'],
            'same_active_joint_definitions':all(active[n]==old_joints[n] for n in NAMES),
            'same_active_joint_ranges':all(active[n]['range']==old_joints[n]['range'] for n in NAMES),
            'same_calibration_data':c['hardware_calibration']['data']==old['hardware_calibration']['data'],
            'same_bam_data':actuator['parameter_file']['data']==old['model']['actuators'][0]['parameter_file']['data'],
            'same_actuator_except_temp_path':actuator_without_temp_path(c['model']['actuators'])==actuator_without_temp_path(old['model']['actuators']),
            'actuator_field_differences_except_temp_path':{k:{'previous':old['model']['actuators'][0].get(k),'new':actuator.get(k)}
                for k in sorted(set(actuator)|set(old['model']['actuators'][0])) if k!='json_path' and actuator.get(k)!=old['model']['actuators'][0].get(k)},
            'same_hardware_command':c['hardware_command']==old['hardware_command'],
            'same_total_mass':c['model']['total_mass_kg']==old['model']['total_mass_kg'],
            'baseline_training_scale':old['actions']['joint_pos']['scale'],'baseline_filter':old.get('action_filter'),
            'baseline_action_ema_old_weight':old.get('action_ema_old_weight'),'baseline_task':old['task']}
    report['models'][role]={
        'archive':str(path),'archive_sha256':digest(path.read_bytes()),'archive_bytes':path.stat().st_size,
        'entries':[{'name':e.filename,'bytes':e.file_size,'crc32':f'{e.CRC:08x}'} for e in entries],
        'source_files':{n:{'bytes':len(v),'sha256':digest(v)} for n,v in files.items()},
        'onnx_sha256':onnx_sha,'model_id':onnx_sha[:32],'task':c['task'],'slot':role,
        'num_envs':s['full']['env']['scene']['num_envs'],'training_max_iterations':s['full']['agent']['max_iterations'],
        'source_iteration':r['source_iteration'],'training_commit':m['training']['commit'],'control_hz':c['control_hz'],
        'original_action_scale':c['actions']['joint_pos']['scale'],'filter':c['action_filter'],
        'action_ema_old_weight_field_present':'action_ema_old_weight' in c,
        'ema_interpretation':'No legacy EMA field is supplied. Explicit current action_filter disabled / head1 / legs1 records target passthrough; do not insert a fictional legacy field into the contract.',
        'previous_action_observation':c['previous_action_observation'],'required_policy_settings':c['required_policy_settings'],
        'manifest_command':m['command'],'contract_command':command,'duration_s':m['duration_s'],'chain':m['chain'],
        'joint_order':NAMES,'home_rad':c['runtime_home_rad'],
        'active_joint_limits':{n:active[n]['range'] for n in NAMES},'gear_backlash':c['gear_backlash'],
        'hardware_command':c['hardware_command'],'actuator_parameter_sha256':actuator['parameter_file']['sha256'],
        'actuator_properties':actuator['runtime_properties'],'total_mass_kg':c['model']['total_mass_kg'],
        'joint_count':len(c['model']['joints']),'checks':checks,'onnx':graph,'baseline_comparison':comparisons,
        'archived_global_studio_recipe':{'task':r.get('studio_recipe',{}).get('task'),'training_action_scale':r.get('studio_recipe',{}).get('training_action_scale'),
                                         'interpretation':'Archived studio defaults may refer to another task. Actual task scale is confirmed by full environment snapshot, ONNX metadata, contract and task-specific policy_parameters.'},
        'deployment_limits':'Original manifest deployment_verified remains false. ZIP/schema and host inference probes are not an aarch64 deployment or real Zero motion test.'}

report['v146_compatibility_review']={
    'source':'Recovered v146 packaging/model_packages.py read directly from source tar.',
    'roulade':'Exact task is known, but v146 does not recognize its current target-filter contract and requires a legacy action_ema_old_weight field that this genuine export does not contain.',
    'ground_pick':'New exact task GroundPick-Flat-Backlash is absent from the official_adapter allowlist. Needs task-specific ground_pick_action_scale mapping, current target-filter validation and backlash observation functions.',
    'scope':'Adapt firmware/import parsing to the genuine new contracts; preserve original exported bytes. Native path review and native validation remain separate release work.'}
(ROOT/'action-model-audit147.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
lines=['R17 v1.0.147 两个替换模型只读审计','',
       '未执行或反序列化 checkpoint.pt；仅把它作为不透明字节进行 ZIP CRC 校验。上传原件未改。']
for role,row in report['models'].items():
    lines.extend(['',f'{role}：{row["task"]}',f'模型 SHA256：{row["onnx_sha256"]}',f'32位模型ID：{row["model_id"]}',
                  f'4096环境，训练上限10000，导出9999；50Hz，单一 float32 obs[1,61] → actions[1,14]。',
                  '原训练动作缩放1.0、头1.0、腿1.0、滤波disabled；previous_action保留原始输出。新合同不含旧 action_ema_old_weight，不能为适配修改原件补字段。',
                  f'动作时长{row["duration_s"]}秒，chain={row["chain"]}；命令：'+json.dumps(row['manifest_command'],ensure_ascii=False),
                  f'BAM ef2d51…afceb，固件P=5，质量0.82kg，backlash={row["gear_backlash"]["enabled"]}。',
                  f'ZIP结构、全部CRC、ONNX哈希、元数据、实际训练记录、HOME/限位等{len(row["checks"])}项检查全部通过。NumPy按ONNX图运算得到{row["onnx"]["finite_probe_count"]}个有限值探针。',
                  '主机ONNX检查及ORT探针对照：'+json.dumps(row['onnx']['host_runtime_check'],ensure_ascii=False),
                  '主动14关节定义/HOME/限位、BAM参数文件及数值、硬件P和装配标定与v146四个模型都一致；新包多记录actuator implementation字段，捡取明确为Backlash。以上不代表实机运动或aarch64部署验证。'])
lines.extend(['','与 v146 的兼容工作：',report['v146_compatibility_review']['roulade'],report['v146_compatibility_review']['ground_pick'],
              '必须保留新联合Walk的独立uniform 0.9/0.5/0.7配置、LB11000以及本机标定；替换仅针对ground_pick和roulade。',
              '两份原包的studio_recipe全局快照仍可含另一任务旧默认0.9，实际本任务训练全1由完整环境、ONNX元数据、合同及policy_parameters共同确认。',
              '详细原文件哈希、动作相位、主动关节限位、v146比较和每项检查见 action-model-audit147.json。'])
(ROOT/'action-model-audit147.txt').write_text('\n'.join(lines)+'\n')
print(json.dumps({role:{'id':row['model_id'],'checks':len(row['checks']),'checks_pass':all(row['checks'].values()),'finite_probes':row['onnx']['finite_probe_count']} for role,row in report['models'].items()},ensure_ascii=False))
