"""Resolve command curricula from exported text configuration, without loading checkpoints."""
import hashlib
import json
import math

PARAM_FILES = ('upstream-params/env.yaml', 'upstream-params/agent.yaml')
RUNTIME_FILE = 'deployment-runtime.json'

def resolve(files, info):
    if not any(name in files for name in PARAM_FILES):
        return None
    if not all(name in files for name in PARAM_FILES):
        raise ValueError('训练参数不完整：需要 env.yaml 和 agent.yaml')
    from _model_yaml import load, BaseLoader
    for name in PARAM_FILES:
        if len(files[name]) > 2 * 1024 * 1024:
            raise ValueError('训练参数文件过大')
    try:
        env = load(files[PARAM_FILES[0]], Loader=BaseLoader)
        agent = load(files[PARAM_FILES[1]], Loader=BaseLoader)
        request = json.loads(files['training-request.json'])
        iteration = request['source_iteration']
        steps = int(agent['num_steps_per_env'])
        if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 0 or not 1 <= steps <= 10000:
            raise ValueError('训练轮次或每轮步数无效')
        counter = iteration * steps
        commands = {}
        curriculum = env.get('curriculum') or {}
        for name, dimension, observation in [('head_pose', 4, 'head_command'), ('body_pose', 6, 'body_command')]:
            if info['contract']['observations']['terms'][observation]['func']['callable'].endswith('zero_command_padding'):
                continue
            entry = curriculum.get(name + '_range')
            if entry is None:
                continue
            params = entry['params']
            if params['command_name'] != name:
                raise ValueError('课程指令名称不匹配')
            stages = params['range_stages']
            if not isinstance(stages, list) or not stages or len(stages) > 1000:
                raise ValueError('指令范围课程无效')
            previous = -1
            selected = None
            for stage in stages:
                step = int(stage['step'])
                rows = stage['ranges']
                if step < 0 or step <= previous or not isinstance(rows, list) or len(rows) != dimension:
                    raise ValueError('指令课程阶段或维度无效')
                previous = step
                ranges = []
                for row in rows:
                    if not isinstance(row, list) or len(row) != 2:
                        raise ValueError('指令范围维度无效')
                    lo, hi = map(float, row)
                    if not all(math.isfinite(x) for x in (lo, hi)) or lo > hi:
                        raise ValueError('指令范围无效')
                    ranges.append([lo, hi])
                if selected is None or counter >= step:
                    selected = ranges
            commands[name] = selected
        return {'schema': 'microduck-runtime-commands/v1', 'model_sha256': info['sha256'],
                'source_iteration': iteration, 'num_steps_per_env': steps, 'training_step': counter,
                'source_parameters_sha256': {name: hashlib.sha256(files[name]).hexdigest() for name in PARAM_FILES},
                'commands': commands}
    except (KeyError, TypeError, OverflowError) as e:
        raise ValueError('无法恢复训练指令课程：' + str(e)) from e

def encode(runtime):
    return (json.dumps(runtime, ensure_ascii=False, indent=2) + '\n').encode()
