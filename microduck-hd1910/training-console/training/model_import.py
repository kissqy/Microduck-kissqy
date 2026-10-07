"""Move exported teacher/checkpoint ZIPs between training machines."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import secrets
import time
import zipfile

MAX_ZIP = 30 * 1024 * 1024
MAX_EXPANDED = 120 * 1024 * 1024


def import_model(manager, value, root):
    from training.official_spec import PIN, TASKS, current_request, contract, model_task
    if __import__('sys').platform != 'linux':
        raise ValueError('请连接SSH训练服务器后上传模型。')
    from training.action_filter import validate as validate_filter
    from training.recipe import validate_training_action_scale, validate_training_firmware_p
    if not isinstance(value.get('data'), str) or len(value['data']) > 4 * ((MAX_ZIP + 2) // 3):
        raise ValueError('请上传不超过30MB的老师/续训模型 ZIP。')
    try:
        packed = base64.b64decode(value['data'], validate=True)
    except ValueError:
        raise ValueError('模型上传编码无效。') from None
    if len(packed) > MAX_ZIP:
        raise ValueError('模型包超过30MB。')
    try:
        with zipfile.ZipFile(io.BytesIO(packed)) as archive:
            names = archive.namelist()
            if len(names) > 200 or len(names) != len(set(names)) or sum(i.file_size for i in archive.infolist()) > MAX_EXPANDED:
                raise ValueError('模型包解压大小或文件列表无效。')
            for required in ('checkpoint.pt', 'deployment-contract.json', 'training-request.json', 'manifest.json'):
                if required not in names:
                    raise ValueError('模型包缺少 ' + required + '；请用原训练中控导出完整 ZIP。')
            request = json.loads(archive.read('training-request.json'))
            deployment = json.loads(archive.read('deployment-contract.json'))
            manifest = json.loads(archive.read('manifest.json'))
            checkpoint = archive.read('checkpoint.pt')
            if not checkpoint:
                raise ValueError('检查点为空。')
            if not current_request(request):
                raise ValueError('上传支持当前官方0.15.1训练源的完整模型包；此包来源不符，未改写模型来源。')
            task = model_task(request)
            if not isinstance(deployment.get('model'), dict) or deployment.get('task') != task or manifest.get('task') != task:
                raise ValueError('模型包内任务和合同不一致。')
            if deployment.get('input_dim') != 61 or deployment.get('output_dim') != 14:
                raise ValueError('模型接口不是61观测/14动作。')
            original_request = copy.deepcopy(request)
            parameters = request.get('policy_parameters') or {}
            # Older ZIPs store the export request, with the actual trained
            # action mapping under policy_parameters rather than top-level.
            from training_console import PARAMETER_KEYS
            for key in PARAMETER_KEYS:
                if request.get(key) is None and key in parameters:
                    request[key] = copy.deepcopy(parameters[key])
            request['op'] = 'train'
            scale = validate_training_action_scale(request.get('training_action_scale', 1.0))
            action = deployment.get('actions', {}).get('joint_pos', {})
            if action.get('scale') != scale or manifest.get('action_scale') != scale:
                raise ValueError('训练记录、模型合同和 manifest 的动作系数不一致。')
            filtering = validate_filter(request.get('action_filter'))
            expected_head = filtering['head_alpha'] if filtering['enabled'] else 1.0
            expected_legs = filtering['legs_alpha'] if filtering['enabled'] else 1.0
            if action.get('head_alpha', 1.0) != expected_head or action.get('legs_alpha', 1.0) != expected_legs:
                raise ValueError('模型合同与训练记录的头腿滤波不一致。')
            p = request.get('training_firmware_p')
            if p is None:
                gains = {a.get('kp_fw') for a in deployment['model'].get('actuators', [])}
                if len(gains) == 1 and None not in gains:
                    p = validate_training_firmware_p(next(iter(gains)))
                    request['training_firmware_p'] = p
            if p is not None:
                p = validate_training_firmware_p(p)
                actuators = deployment['model'].get('actuators', [])
                if not actuators or any(a.get('kp_fw') != p for a in actuators):
                    raise ValueError('模型合同与训练记录的舵机P不一致。')
            if 'policy.onnx' in names and manifest.get('onnx_sha256'):
                if hashlib.sha256(archive.read('policy.onnx')).hexdigest() != manifest['onnx_sha256']:
                    raise ValueError('模型包的ONNX校验失败。')
            snapshot = json.loads(archive.read('training-config.json')) if 'training-config.json' in names else deployment.get('training_snapshot')
            if isinstance(snapshot, dict) and snapshot.get('full') and snapshot.get('model'):
                inspection = copy.deepcopy(snapshot)
                # Inspect both records; never override saved scale/filter/P.
                compact = contract(inspection, request)
                if compact['actions'] != deployment['actions']:
                    raise ValueError('原训练快照与部署动作合同不一致。')
            else:
                # Older exports contain actual physics/actions/observations, but
                # not full PPO readback. Keep this limitation explicit.
                reference = json.loads((root / 'data/task-configs' / (task + '.json')).read_text())['inspection']
                actor = copy.deepcopy(reference['full']['agent']['actor'])
                actor['hidden_dims'] = parameters.get('actor_dims') or request.get('actor_dims') or actor['hidden_dims']
                actor['activation'] = parameters.get('activation') or request.get('activation') or actor['activation']
                env = {'actions': deployment['actions'], 'observations': {'actor': deployment['observations']},
                       'sim': {'mujoco': {'timestep': 1.0 / deployment.get('control_hz', 50.0)}}, 'decimation': 1}
                compact = contract({'model': deployment['model'], 'full': {'env': env, 'agent': {'actor': actor}}}, request)
                inspection = {'model': deployment['model'], 'portable_contract': compact,
                              'provenance': 'exported_physics_and_action_contract; actor_from_pinned_task_and_saved_parameters'}
            iteration = manifest.get('training', {}).get('checkpoint')
            if type(iteration) is not int or iteration < 0:
                raise ValueError('模型包缺少有效的检查点轮数。')
            if TASKS[task]['role'] == 'joint':
                raise ValueError('联合模型续训还依赖原来的两位老师；请在原训练服务器续训。此入口支持独立老师与其他独立动作。')
            original_envs = request.get('num_envs')
            if original_envs is None and isinstance(snapshot, dict):
                original_envs = snapshot.get('full', {}).get('env', {}).get('scene', {}).get('num_envs')
            resume_supported = type(original_envs) is int and 1 <= original_envs <= 8192
            if resume_supported:
                request['num_envs'] = original_envs
            recipe = request.get('studio_recipe')
            if not isinstance(recipe, dict):
                raise ValueError('模型包缺少原机器人物理配方。')
    except (zipfile.BadZipFile, KeyError, TypeError, json.JSONDecodeError, ZeroDivisionError, RuntimeError) as error:
        raise ValueError('模型包内容不完整或格式无效：' + str(error)) from error
    sha = hashlib.sha256(packed).hexdigest()
    with manager.lock:
        existing = next((job for job in manager.jobs.values() if job.get('import_sha256') == sha), None)
        if existing:
            path = existing['checkpoints'][0]['path'] if existing.get('checkpoints') else ''
            if path and Path(path).is_file():
                return {'job_id': existing['id'], 'reused': True}
        jid = secrets.token_hex(8)
        destination = manager.directory / 'imports' / jid
        destination.mkdir(parents=True, exist_ok=False)
        path = destination / ('model_%d.pt' % iteration)
        path.write_bytes(checkpoint)
        (destination / 'source-package.zip').write_bytes(packed)
        (destination / 'training-request.original.json').write_text(json.dumps(original_request, ensure_ascii=False, indent=2), encoding='utf-8')
        (destination / 'deployment-contract.json').write_text(json.dumps(deployment, ensure_ascii=False, indent=2), encoding='utf-8')
        with zipfile.ZipFile(io.BytesIO(packed)) as archive:
            for name in ('agent.yaml', 'env.yaml'):
                member = 'upstream-params/' + name
                if member in archive.namelist():
                    (destination / 'params').mkdir(exist_ok=True)
                    (destination / 'params' / name).write_bytes(archive.read(member))
        profile = {'mode': 'local', 'distro': 'Ubuntu', 'repo': PIN['repo']}
        now = time.time()
        job = {'id': jid, 'op': 'train', 'status': 'completed', 'created': now, 'ended': now,
               'profile': profile, 'revision': PIN['revision'], 'request': copy.deepcopy(request),
               'logs': ['已上传完整模型包；保留原训练倍率、滤波、P和来源，未运行训练。'],
               'metrics': [], 'checkpoints': [{'path': str(path), 'iteration': iteration}],
               'effective_config': {'resolved': inspection}, 'import_sha256': sha, 'resume_import_supported': resume_supported,
               'message': '已上传模型，可选择为老师或续训来源。' if resume_supported else '已上传模型，可用作老师；旧包缺少原并行数，未开放续训。'}
        job['request']['label'] = '上传 · ' + str(value.get('name', '模型.zip'))[:50]
        manager.jobs[jid] = job
        manager.persist(job)
        return {'job_id': jid, 'sha256': sha, 'checkpoint_sha256': hashlib.sha256(checkpoint).hexdigest(),
                'resume_supported': resume_supported, 'task': task, 'training_action_scale': scale, 'action_filter': filtering, 'training_firmware_p': p}
