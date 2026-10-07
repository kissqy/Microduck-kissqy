"""Training Studio ZIP imports. Never load checkpoint pickle or execute package code."""
from __future__ import annotations
import hashlib, io, json, math, os, re, shlex, shutil, subprocess, tempfile, zipfile
from pathlib import Path
import tomllib
from configure import dumps
from model_commands import PARAM_FILES, RUNTIME_FILE, resolve as resolve_commands, encode as encode_commands

BASE=Path('/opt/robot/feetech-ft5-r5')
CONFIG=Path('/etc/robot/feetech-ft5/robotd.toml')
CALIBRATION=CONFIG.with_name('hd1910-calibration.toml')
NAMES=('left_hip_yaw','left_hip_roll','left_hip_pitch','left_knee','left_ankle','neck_pitch','head_pitch','head_yaw','head_roll','right_hip_yaw','right_hip_roll','right_hip_pitch','right_knee','right_ankle')
from management_profile import SLOTS, LABELS, ACTION_INFO
BAM='ef2d51adfb1cc0831b9b02ca19aa9176fceecdf725148d084378d7d9a64afceb'
ROUGH_TASK='Mjlab-Velocity-Rough-Backlash-MicroDuck'
ROUGH_STAND_TASK='Mjlab-StandUp-Rough-Backlash-MicroDuck'
ROUGH_JOINT_TASK='Mjlab-VelStand-Rough-Backlash-MicroDuck'
EXECUTION_FILE='deployment-execution.json'
MAX_SIZE=64*1024*1024
EXPORT_FILES=('policy.onnx','deployment-contract.json','manifest.json','training-request.json')
OPTIONAL_EXPORT_FILES=('training-config.json','export-audit.json','deployment-profile.toml','使用说明.md')
EXPORT_DATA='export-data.zip'
SOURCE_FILES=(*EXPORT_FILES[1:],*PARAM_FILES,*OPTIONAL_EXPORT_FILES)
def export_data(files):
    """Keep the original training metadata, separate from regenerated runtime data."""
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCE_FILES:
            if name in files:archive.writestr(name,files[name])
    return output.getvalue()
def restore_export_data(directory):
    source=directory/EXPORT_DATA
    if not source.exists():return
    try:
        with zipfile.ZipFile(source) as archive:
            names=archive.namelist()
            if len(names)!=len(set(names)) or any(n not in SOURCE_FILES for n in names) or sum(i.file_size for i in archive.infolist())>8*1024*1024:
                raise ValueError('原始导出数据结构无效')
            files={name:archive.read(name) for name in names}
        files['policy.onnx']=(directory/'policy.onnx').read_bytes()
        info=validate_export(files)
        resolve_commands(files,info)
        for name in SOURCE_FILES:
            if name in files:atomic(directory/name,files[name])
            else:(directory/name).unlink(missing_ok=True)
    except (OSError,ValueError,zipfile.BadZipFile,KeyError) as exc:
        raise ValueError(f'{source}: {exc}') from exc
def runtime_environment():
    env=os.environ.copy()
    result=subprocess.run(['systemctl','show','robotd.service','-p','Environment','--value'],capture_output=True,text=True,timeout=10)
    if result.returncode:raise ValueError('无法读取 robotd 的 ONNX Runtime 环境')
    for item in shlex.split(result.stdout):
        key,sep,value=item.partition('=')
        if sep and key in ('ORT_DYLIB_PATH','LD_LIBRARY_PATH'):env[key]=value
    return env
def slot_for(task):
    if task in ('Mjlab-VelStand-Flat-MicroDuck',ROUGH_JOINT_TASK):return 'walk'
    for row in ACTION_INFO.values():
        for prefix in row['task_prefixes']:
            if prefix=='VelStand':continue  # Only the exact combined-task contract is implemented.
            if isinstance(task,str) and task.startswith('Mjlab-'+prefix+'-') and 'MicroDuck' in task:return row['slot']
    raise ValueError('当前服务尚未实现该训练任务的动作适配：'+str(task))

def finite(v):
    if isinstance(v,bool) or not isinstance(v,(int,float)):return False
    try:return math.isfinite(v)
    except OverflowError:return False
def execution_profile(data,info):
    """Validate uniform model-bound tuning without rewriting its training facts."""
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('执行配置字段重复：'+key)
            result[key]=value
        return result
    try:
        value=json.loads(data,object_pairs_hook=unique)
    except (ValueError,UnicodeError) as exc:
        raise ValueError(f'{EXECUTION_FILE}: {exc}') from exc
    def keys(row,expected):
        if not isinstance(row,dict) or set(row)!=set(expected):
            raise ValueError(f'{EXECUTION_FILE}: 执行配置字段缺失或尚未支持')
    keys(value,('schema','model_sha256','mode','action_scale','head_lowpass','legs_lowpass'))
    contract=info['contract']
    action=contract.get('actions',{}).get('joint_pos',{})
    filters=contract.get('action_filter',{})
    ema=contract.get('action_ema_old_weight',0.0)
    if (info['task']!=ROUGH_JOINT_TASK or info['slot']!='walk'
            or not finite(action.get('scale')) or action['scale']!=1.0
            or filters.get('enabled') is not False
            or any(not finite(filters.get(k)) or filters[k]!=1.0 for k in ('head_alpha','legs_alpha'))
            or not finite(ema) or ema!=0.0):
        raise ValueError(f'{EXECUTION_FILE}: 仅适用于无缩放和滤波的粗糙地面联合 Walk 模型')
    if (value['schema']!='microduck-runtime-execution/v1'
            or value['mode']!='uniform'
            or value['model_sha256']!=info['sha256']
            or not isinstance(value['model_sha256'],str)
            or not re.fullmatch('[a-f0-9]{64}',value['model_sha256'])):
        raise ValueError(f'{EXECUTION_FILE}: 执行配置类型或模型 SHA256 不匹配')
    # The same bounded settings apply in every posture; no phase switch is encoded.
    if not finite(value['action_scale']) or not .1<=value['action_scale']<=2.0:
        raise ValueError(f'{EXECUTION_FILE}: 统一动作系数须在 0.1 到 2.0 之间')
    for name in ('head_lowpass','legs_lowpass'):
        if not finite(value[name]) or not 0<value[name]<=1.0:
            raise ValueError(f'{EXECUTION_FILE}: {name} 须大于 0 且不超过 1')
    return value
def fields(data):
    def integer(i):
        value=shift=0
        while i<len(data):
            byte=data[i];i+=1;value|=(byte&127)<<shift
            if byte<128:return value,i
            shift+=7
            if shift>70:break
        raise ValueError('ONNX protobuf 无效')
    i=0
    while i<len(data):
        key,i=integer(i);kind=key&7
        if kind==0:value,i=integer(i)
        elif kind==2:
            size,i=integer(i);value=data[i:i+size];i+=size
            if len(value)!=size:raise ValueError('ONNX 数据截断')
        elif kind in (1,5):
            size=8 if kind==1 else 4;value=data[i:i+size];i+=size
        else:raise ValueError('ONNX protobuf wire type 无效')
        yield key>>3,value
def one(data,key):
    values=[v for k,v in fields(data) if k==key]
    if len(values)!=1:raise ValueError('ONNX 字段缺失或重复')
    return values[0]
def graph_interface(data):
    graph=one(data,7)
    def outlet(v):
        tensor=one(one(v,2),1)
        return one(v,1).decode(),one(tensor,1),[one(dim,1) for k,dim in fields(one(tensor,2)) if k==1]
    inputs=[outlet(v) for k,v in fields(graph) if k==11]
    outputs=[outlet(v) for k,v in fields(graph) if k==12]
    if inputs!=[('obs',1,[1,61])] or outputs!=[('actions',1,[1,14])]:raise ValueError('要求 float32 obs[1,61] → actions[1,14] 的完整部署模型')
    allowed={'Sub','Div','Gemm','Elu','Tanh','Relu','Add','Mul','Clip','Identity','Constant','MatMul','LeakyRelu','Sigmoid','Softplus'}
    for k,v in fields(graph):
        if k==5 and any(a in (13,14) for a,_ in fields(v)):raise ValueError('不支持引用外部权重文件的 ONNX')
        if k==1:
            node=dict(fields(v));op=node.get(4,b'').decode();domain=node.get(7,b'').decode()
            if domain not in ('','ai.onnx') or op not in allowed:raise ValueError('当前模型适配不支持 ONNX 运算：'+domain+':'+op)
    return {one(v,1).decode():one(v,2).decode() for k,v in fields(data) if k==14}
def validate_export(files):
    if any(n not in files for n in EXPORT_FILES):raise ValueError('请导入训练台导出的完整 ZIP：缺少模型、部署合同、manifest 或训练记录')
    parsed={}
    for name in ('deployment-contract.json','manifest.json'):
        try:parsed[name]=json.loads(files[name])
        except (ValueError,UnicodeError) as exc:raise ValueError(f'{name}: {exc}') from exc
    c=parsed['deployment-contract.json'];m=parsed['manifest.json']
    official_adapter=c.get('task_adapter')=='hd1910-official0151' and c.get('task') in ('Mjlab-VelStand-Flat-MicroDuck','Mjlab-GroundPick-Flat-MicroDuck','Mjlab-Roulade-Flat-MicroDuck','Mjlab-StandUp-Flat-MicroDuck',ROUGH_TASK,ROUGH_STAND_TASK,ROUGH_JOINT_TASK) and c.get('target_firmware',{}).get('version')=='0.15.1' and c.get('control_hz')==50
    current_target_contract=official_adapter and c.get('task') in (ROUGH_TASK,ROUGH_STAND_TASK,ROUGH_JOINT_TASK)
    supported_adapter=official_adapter or c.get('task_adapter')=='hd1910-v1' or (c.get('task_adapter')=='hd1910-v2' and c.get('task') in ('Mjlab-StandUp-Flat-MicroDuck-V2-HD1910','Mjlab-Velocity-Flat-MicroDuck-V2-HD1910'))
    if c.get('schema')!='microduck-deployment-contract/v1' or not supported_adapter or (c.get('input_dim'),c.get('output_dim'))!=(61,14):raise ValueError('当前服务支持 HD1910 V1、已适配 V2，以及官方 0.15.1 联合行走、地面捡取与前滚翻合同，61 维观测、14 关节输出')
    if c.get('obs_normalizer')!='baked_in_onnx':raise ValueError('模型须内含训练观测归一化')
    slot=slot_for(c.get('task'))
    digest=hashlib.sha256(files['policy.onnx']).hexdigest()
    if digest!=m.get('onnx_sha256') or m.get('task')!=c.get('task'):raise ValueError('模型校验值或任务名称与导出记录不一致')
    metadata=graph_interface(files['policy.onnx'])
    if metadata!=c.get('onnx_metadata') or metadata.get('joint_names')!=','.join(NAMES):raise ValueError('ONNX 元数据、部署合同或关节顺序不一致')
    a=c.get('actions',{}).get('joint_pos',{});scale=c.get('inference_action_scale',{})
    if a.get('use_default_offset') is not True or a.get('offset')!=0 or a.get('clip') is not None or not finite(a.get('scale')) or not 0<a['scale']<=2:raise ValueError('当前服务不支持此动作偏置、缩放或裁剪方式')
    if not official_adapter and (scale.get('value')!=1.0 or scale.get('baked_into_onnx') is not False):raise ValueError('当前部署固定使用推理缩放 1.0，请按当前训练台重新导出')
    ema=c.get('action_ema_old_weight',0.0 if current_target_contract else None)
    if not finite(ema) or not 0<=ema<1:raise ValueError('动作 EMA 参数无效')
    settings=None
    if current_target_contract:
        f=c.get('action_filter',{});required=c.get('required_policy_settings',{})
        expected={'version':1,'control_hz':50.0,'stage':'joint_position_target_after_home_and_scale','reset':'first_target_passthrough_per_environment','update':'once_per_policy_step','previous_action_observation':'raw_policy_output','onnx':'external_filter_not_baked_into_graph'}
        if not isinstance(f.get('enabled'),bool) or any(f.get(k)!=v for k,v in expected.items()) or required.get('action_scale')!=a['scale'] or ema!=0:raise ValueError('新版目标滤波与动作缩放合同不一致')
        for name,alpha in (('head_lowpass','head_alpha'),('legs_lowpass','legs_alpha')):
            value=f.get(alpha)
            trained=a.get(alpha)
            if not finite(value) or not 0<value<=1 or required.get(name)!=value or (f['enabled'] and trained!=value) or (not f['enabled'] and (value!=1.0 or trained not in (None,1.0))):raise ValueError('目标滤波系数与训练记录不一致')
        settings={k:required[k] for k in ('action_scale','head_lowpass','legs_lowpass')}
    terms=c.get('observations',{}).get('terms',{})
    if set(terms)!=set(('base_ang_vel','projected_gravity','joint_pos','joint_vel','actions','command','head_command','body_command')):raise ValueError('当前服务不支持该观测布局')
    suffix='_backlash' if current_target_contract else ''
    if not terms['joint_pos'].get('func',{}).get('callable','').endswith('joint_pos_rel'+suffix) or not terms['joint_vel'].get('func',{}).get('callable','').endswith('joint_vel_rel'+suffix):raise ValueError('当前服务支持相对 HOME 的编码器关节位置与速度观测')
    for t in terms.values():
        if t.get('clip') is not None or t.get('scale') not in (None,1.0) or t.get('history_length') not in (None,0):raise ValueError('当前服务不支持此观测缩放、裁剪或历史长度')
    body=terms['body_command'].get('func',{}).get('callable','')
    if not body.endswith(('zero_command_padding','generated_commands')):raise ValueError('身体姿态观测函数尚未适配')
    head=terms['head_command'].get('func',{}).get('callable','')
    if not head.endswith(('zero_command_padding','generated_commands')):raise ValueError('头部姿态观测函数尚未适配')
    for key,dim in (('head_command',4),('body_command',6)):
        if terms[key].get('func',{}).get('callable','').endswith('zero_command_padding') and terms[key].get('params',{}).get('dim')!=dim:raise ValueError('指令零填充维度不匹配：'+key)
    if slot=='ground_pick':
        command=c.get('commands',{}).get('twist',{});period=command.get('period',command.get('period_s'))
        if not command.get('class_type',{}).get('callable','').endswith('GroundPickPhaseCommand') or not finite(period) or period<=0:raise ValueError('捡取模型须使用阶段指令及有效动作周期')
    actuators=c.get('model',{}).get('actuators',[])
    if len(actuators)!=1 or actuators[0].get('parameter_file',{}).get('sha256')!=BAM:raise ValueError('模型使用了尚未适配的 BAM 参数')
    p=actuators[0].get('kp_fw')
    if not finite(p) or p!=int(p) or not 1<=p<=32:raise ValueError('BAM 固件 P 参数无效')
    joints=c.get('model',{}).get('joints',[]);home={}
    for name in NAMES:
        found=[j for j in joints if j.get('name')==name]
        if len(found)!=1 or not finite(found[0].get('home_rad')):raise ValueError('缺少精确训练 HOME：'+name)
        home[name]=found[0]['home_rad']
    metadata_home=[float(v) for v in metadata.get('default_joint_pos','').split(',')]
    if len(metadata_home)!=14 or any(abs(home[n]-v)>0.000501 for n,v in zip(NAMES,metadata_home)):raise ValueError('训练 HOME 与 ONNX 元数据不一致')
    info={'id':digest[:32],'sha256':digest,'task':c['task'],'slot':slot,'label':LABELS[slot],'home':home,'firmware_p':int(p),'contract':c,'source_revision':m.get('source_revision'),'deployment_verified':False}
    if settings is not None:info['policy_settings']=settings
    if EXECUTION_FILE in files:info['execution_profile']=execution_profile(files[EXECUTION_FILE],info)
    if slot=='roulade':
        # This is an official episodic skill, not a fall-recovery trigger.
        # Carry its local manifest settings through the official [[policy.skill]] API.
        command=m.get('command',{})
        duration=m.get('duration_s');action_scale=m.get('action_scale')
        if m.get('kind')!='episodic' or command.get('encoding')!='constant' or command.get('idle')!=[0,0,0] or command.get('twist')!='zeros':raise ValueError('前滚翻须使用官方一次动作窗口和零速度指令')
        if not finite(duration) or not .02<=duration<=10 or type(m.get('chain')) is not bool or not finite(action_scale) or not .1<=action_scale<=2:raise ValueError('前滚翻动作窗口、连续执行或动作系数无效')
        info['skill']={'name':'roulade','duration':duration,'chain':m['chain'],'command':[0.0,0.0,0.0],'unwind':[0.0,0.0,0.0],'unwind_s':0.0,'params':{'action_scale':action_scale,'gain_ratio':1.0}}
    return info
def package_files(path):
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)>200 or len(set(names))!=len(names) or sum(i.file_size for i in z.infolist())>128*1024*1024:raise ValueError('模型包大小或文件结构无效')
        if any(Path(n).is_absolute() or '..' in Path(n).parts or '\\' in n for n in names):raise ValueError('模型包包含无效路径')
        files={n:z.read(n) for n in ('policy.onnx',*SOURCE_FILES,EXECUTION_FILE) if n in names}
    info=validate_export(files)
    runtime=resolve_commands(files,info)
    if runtime is not None:files[RUNTIME_FILE]=encode_commands(runtime)
    return files,info
def verify_directory(directory):
    directory=Path(directory)
    files={n:(directory/n).read_bytes() for n in ('policy.onnx',*SOURCE_FILES,EXECUTION_FILE) if (directory/n).is_file()}
    try:
        info=validate_export(files)
        runtime=resolve_commands(files,info)
    except (ValueError,KeyError) as exc:
        raise ValueError(f'{directory}: {exc}') from exc
    if runtime is not None:
        try:saved=json.loads((directory/RUNTIME_FILE).read_bytes())
        except (FileNotFoundError,ValueError,UnicodeError):saved=None
        # A valid matching cache is reused without writing it again.
        if saved!=runtime:atomic(directory/RUNTIME_FILE,encode_commands(runtime))
    else:(directory/RUNTIME_FILE).unlink(missing_ok=True)
    return info

def atomic(path,data):
    from configure import atomic_write
    atomic_write(Path(path),data)
def describe_directory(directory):
    """Read installed metadata; import/startup own model validation and derivation."""
    directory=Path(directory)
    contract=json.loads((directory/'deployment-contract.json').read_text())
    manifest=json.loads((directory/'manifest.json').read_text())
    if not (directory/'policy.onnx').is_file():raise ValueError('模型文件不存在')
    slot=slot_for(contract.get('task'))
    info={'slot':slot,'label':LABELS[slot],'task':contract['task'],'sha256':manifest['onnx_sha256']}
    if (directory/EXECUTION_FILE).exists():
        info['execution_profile']=execution_profile((directory/EXECUTION_FILE).read_bytes(),{**info,'contract':contract})
    return info
def catalog(base=BASE,config_path=CONFIG):
    cfg=tomllib.loads(Path(config_path).read_text()) if Path(config_path).exists() else {};rows=[]
    for directory in sorted((Path(base)/'models').glob('*')):
        if not directory.is_dir() or not re.fullmatch('[a-f0-9]{32}',directory.name):continue
        try:
            info=describe_directory(directory);meta=json.loads((directory/'model-info.json').read_text()) if (directory/'model-info.json').exists() else {}
            active=str(directory/'policy.onnx')==cfg.get('policy',{}).get(info['slot'])
            rows.append({'id':directory.name,'name':meta.get('name',info['label']),'slot':info['slot'],'label':info['label'],'task':info['task'],'path':str(directory/'policy.onnx'),'active':active,'available':True,'official':False,'managed':True,'deletable':True,'sha256':info['sha256'],**({'execution_profile':info['execution_profile']} if 'execution_profile' in info else {})})
        except (OSError,ValueError,KeyError) as e:rows.append({'id':directory.name,'name':directory.name,'available':False,'active':False,'official':False,'error':str(e)})
    # Official action slots and a named skill bound to LB are separate routes.
    skills=cfg.get('policy',{}).get('skill',[]);pad=cfg.get('pad',{})
    for row in rows:
        path=str(Path(base)/'models'/row['id']/'policy.onnx')
        row['skill_bindings']=[{'name':skill['name'],'buttons':[button for button,value in pad.items() if value==skill['name']],'action_scale':skill.get('params',{}).get('action_scale',1.0)} for skill in skills if skill.get('path')==path]
    lb=next((skill for skill in skills if skill.get('name')==pad.get('lb')),None)
    manual_recovery=None
    if lb:
        model=next((row for row in rows if str(Path(base)/'models'/row['id']/'policy.onnx')==lb.get('path')),None)
        manual_recovery={'button':'lb','skill':lb['name'],'path':lb.get('path'),'model':model,'action_scale':lb.get('params',{}).get('action_scale',1.0)}
    current=next((x['id'] for x in rows if x.get('active') and x.get('slot')=='walk'),None)
    slots=[{'slot':slot,'label':LABELS[slot],'import_supported':ACTION_INFO[slot]['import_supported'],'support_message':ACTION_INFO[slot]['support_message'],'model':next((row for row in rows if row.get('active') and row.get('slot')==slot),None)} for slot in SLOTS]
    return {'models':rows,'slots':slots,'manual_recovery':manual_recovery,'configured_model':current,'fixed_profile':False,'model_source':'deployment_contract_disk'}
def selected_config(base=BASE,config_path=CONFIG):return tomllib.loads(Path(config_path).read_text())
def save_config(config_path,data):
    data.setdefault('policy',{}).pop('r17_inference_scale',None)
    path=Path(config_path);text=dumps(data)
    atomic(path,text)
    atomic(path.with_name(path.stem+'.saved'+path.suffix),text)
def check_calibration(info,calibration_path=CALIBRATION):
    if not Path(calibration_path).exists():return []
    actual=tomllib.loads(Path(calibration_path).read_text());warnings=[]
    joints={j['name']:j for j in actual.get('joints',[])}
    for name,home in info['home'].items():
        j=joints.get(name,{})
        if not j or not j.get('min_rad',-math.inf)<=home<=j.get('max_rad',math.inf):raise ValueError('模型 HOME 超出本机机械限位：'+name)
    trained=info['contract'].get('hardware_calibration',{}).get('data',{})
    if trained.get('joints')!=actual.get('joints') or trained.get('imu_mount_quat')!=actual.get('imu_mount_quat'):warnings.append('本机标定与训练记录有差异；保留本机标定，请核对变化。')
    return warnings
def import_package(path,name,base=BASE,config_path=CONFIG,calibration_path=CALIBRATION,validator=True,target_slot=None):
    if Path(name).name!=name or not name.lower().endswith('.zip') or len(name)>180:raise ValueError('请导入完整模型 ZIP')
    if not 0<Path(path).stat().st_size<=MAX_SIZE:raise ValueError('模型包上限 64 MiB')
    files,info=package_files(path)
    if target_slot not in SLOTS or info['slot']!=target_slot:raise ValueError('所选动作 '+LABELS.get(target_slot,str(target_slot))+' 与模型合同动作 '+info['label']+' 不一致；请选择对应动作。')
    warnings=check_calibration(info,calibration_path)
    directory=Path(base)/'models'/info['id'];directory.parent.mkdir(parents=True,exist_ok=True)
    if directory.exists() and EXECUTION_FILE not in files and (directory/EXECUTION_FILE).exists():
        # Reimporting the original training ZIP must not silently erase the
        # operator's matching deployment experiment. Validate it before staging.
        files[EXECUTION_FILE]=(directory/EXECUTION_FILE).read_bytes()
        info['execution_profile']=execution_profile(files[EXECUTION_FILE],info)
    with tempfile.TemporaryDirectory(prefix='.import-',dir=directory.parent) as temp:
        stage=Path(temp)
        for n,data in files.items():
            atomic(stage/n,data)
        if validator:
            result=subprocess.run([str(Path(base)/'robotd'),'validate-policy',str(stage/'policy.onnx')],env=runtime_environment(),capture_output=True,text=True,timeout=45)
            if result.returncode:raise ValueError('Zero 模型加载检查失败：'+(result.stderr or result.stdout)[-1200:])
        (stage/'model-info.json').write_text(json.dumps({'name':info['label']+' · '+name.removesuffix('.zip'),'source_filename':name},ensure_ascii=False,indent=2))
        atomic(stage/EXPORT_DATA,export_data(files))
        if directory.exists():
            if hashlib.sha256((directory/'policy.onnx').read_bytes()).hexdigest()!=info['sha256']:raise ValueError('模型标识发生冲突')
            if not any(n in files for n in PARAM_FILES) and (directory/EXPORT_DATA).exists():
                try:
                    with zipfile.ZipFile(directory/EXPORT_DATA) as archive:
                        # A ZIP without YAML does not downgrade the same unchanged export.
                        if all(n in archive.namelist() and archive.read(n)==files[n] for n in EXPORT_FILES[1:]):
                            for n in PARAM_FILES:
                                if n in archive.namelist():files[n]=archive.read(n)
                except (ValueError,zipfile.BadZipFile,KeyError):pass
            atomic(directory/EXPORT_DATA,export_data(files))
            restore_export_data(directory)
            if EXECUTION_FILE in files:atomic(directory/EXECUTION_FILE,files[EXECUTION_FILE])
            verify_directory(directory)
            return {'id':info['id'],'name':info['label'],'slot':info['slot'],'duplicate':True,'warnings':warnings,'message':'已重新写入原始导出数据并重建运行配置；当前模型选择保留',**({'execution_profile':info['execution_profile']} if 'execution_profile' in info else {})}
        stage.chmod(0o755)
        for f in stage.rglob('*'):f.chmod(0o755 if f.is_dir() else 0o644)
        os.rename(stage,directory)
    return {'id':info['id'],'name':info['label'],'slot':info['slot'],'warnings':warnings,'message':'已导入并通过接口检查；等待绑定所选动作并确认实际加载',**({'execution_profile':info['execution_profile']} if 'execution_profile' in info else {})}
def assign_model(ident,slot,base=BASE,config_path=CONFIG,calibration_path=CALIBRATION):
    if not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('模型标识无效')
    directory=Path(base)/'models'/ident;info=verify_directory(directory)
    if slot not in SLOTS or info['slot']!=slot:raise ValueError('所选动作与模型部署合同不一致，未修改绑定')
    check_calibration(info,calibration_path)
    cfg=selected_config(base,config_path);policy=cfg.setdefault('policy',{})
    for slot in SLOTS:
        path=policy.get(slot)
        if slot!=info['slot'] and path and path!='none':
            other=verify_directory(Path(path).parent)
            if other['firmware_p']!=info['firmware_p']:raise ValueError('各动作模型使用的 BAM 固件 P 不一致')
    policy[info['slot']]=str(directory/'policy.onnx')
    if info.get('skill'):
        policy['skill']=[s for s in policy.get('skill',[]) if s.get('name')!=info['skill']['name']]+[info['skill']]
        cfg.setdefault('pad',{})['x']='roulade'
    save_config(config_path,cfg)
    return {'id':ident,'name':info['label'],'slot':info['slot'],'message':'已更新 '+info['label']+'；服务重启后重新 HOME'}
def delete_model(ident,base=BASE,config_path=CONFIG):
    listing=catalog(base,config_path);row=next((r for r in listing['models'] if r['id']==ident),None)
    if not row or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('模型不存在')
    cfg=selected_config(base,config_path)
    if row.get('active'):
        if row['slot']=='walk':
            replacement=next((r for r in listing['models'] if r.get('slot')=='walk' and r.get('available') and r['id']!=ident),None)
            if replacement is None:raise ValueError('至少保留一个可用行走模型；请先导入另一份行走模型')
            assign_model(replacement['id'],'walk',base,config_path)
        else:
            cfg['policy'][row['slot']]='none';save_config(config_path,cfg)
    shutil.rmtree(Path(base)/'models'/ident)
    return {'id':ident,'active_deleted':bool(row.get('active')),'message':'模型已删除'}
