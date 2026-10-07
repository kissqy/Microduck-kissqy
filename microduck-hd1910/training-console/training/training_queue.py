"""Persisted sequential training; scheduling belongs to the desktop backend."""
import copy
import json
import secrets
import threading
import time

from training.official_spec import TASKS, TEACHER_TASKS, JOINT_TASKS, model_task
from training.recipe import digest

ACTIVE = ('starting', 'running', 'stopping')
TERMINAL = ('completed', 'failed', 'stopped', 'cancelled')


class TrainingQueueMixin:
    def initialize_queue(self, save_json):
        self._save_queue_json = save_json
        self._queue_wake = threading.Event()
        self._queue_thread = None
        self._launching_queue_entry = None
        self.training_queue = {'version': 1, 'enabled': False, 'failure_policy': 'pause',
                               'message': '选择参数 → 加入队列 → 开始训练。', 'entries': []}
        path = self.directory/'training-queue.json'
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            if (saved.get('version') != 1 or type(saved.get('enabled')) is not bool
                    or saved.get('failure_policy') not in ('pause', 'continue')
                    or not isinstance(saved.get('entries'), list) or len(saved['entries']) > 100):
                raise ValueError('队列格式无效')
            ids = set()
            for e in saved['entries']:
                if (not isinstance(e, dict) or not isinstance(e.get('request'), dict)
                        or not isinstance(e.get('recipe'), dict) or e.get('status') not in (*ACTIVE, 'waiting', *TERMINAL)
                        or not isinstance(e.get('id'), str) or e['id'] in ids):
                    raise ValueError('队列条目无效')
                ids.add(e['id'])
            self.training_queue = saved
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, AttributeError) as error:
            self.training_queue['message'] = '原队列读取失败，未自动启动：'+str(error)

    def _queue_save(self):
        self.training_queue['updated'] = time.time()
        self._save_queue_json(self.directory/'training-queue.json', self.training_queue)

    def queue_snapshot(self):
        with self.lock:
            q = copy.deepcopy(self.training_queue)
            q['stop_supported'] = True
            for e in q['entries']:
                e.pop('recipe', None)
                job = self.jobs.get(e.get('job_id'), {})
                e['progress'] = None
                if job:
                    from training_console import progress_for
                    e['progress'] = progress_for(job)
            return q

    def _queue_dependencies(self, entry):
        return [v['queue_entry'] for k in ('walk_teacher', 'stand_teacher')
                if isinstance((v := entry['request'].get(k)), dict) and v.get('queue_entry')]

    def _queue_validate_order(self, entries):
        preceding = set()
        for e in entries:
            if e['status'] not in ('cancelled', 'completed', 'failed', 'stopped'):
                if any(d not in preceding for d in self._queue_dependencies(e)):
                    raise ValueError('联合任务必须排在它引用的两位老师后面。')
            preceding.add(e['id'])

    def queue_add(self, value):
        from training_console import validate_parameters, validate_profile
        from training.official_spec import physical_recipe
        with self.lock:
            if self.closed:
                raise ValueError('训练中控正在关闭。')
            key = value.get('client_id')
            if not isinstance(key, str) or not 1 <= len(key) <= 100:
                raise ValueError('添加请求编号无效。')
            old = next((e for e in self.training_queue['entries'] if e.get('client_id') == key), None)
            if old:
                return {'entry_id': old['id']}
            if len(self.training_queue['entries']) >= 100:
                raise ValueError('队列最多100项，请清理已结束记录后再添加。')
            task = value.get('task')
            if not TASKS.get(task, {}).get('enabled'):
                raise ValueError('请选择当前官方动作。')
            ref = json.loads((self.directory_source/'data/task-configs'/(task+'.json')).read_text(encoding='utf-8'))
            req = validate_parameters(value, {'tasks': [task], 'configs': {task: ref}})
            req['execution_profile'] = validate_profile(value.get('execution_profile') or self.profile)
            if TASKS[task]['role'] == 'sitstand' and not value.get('source_job') and req['training_action_scale'] != 1:
                raise ValueError('官方坐站动作系数固定1.0。')
            if value.get('source_job'):
                owner = self.jobs.get(value['source_job'], {})
                if owner.get('resume_import_supported') is False:
                    raise ValueError('旧上传包缺少原训练并行数，可用作老师；续训需要含原训练快照的完整ZIP。')
                if owner.get('op') != 'train' or owner.get('request', {}).get('task') != task:
                    raise ValueError('续训来源与所选动作不一致。')
                if not any(c['path'] == value.get('checkpoint') for c in owner.get('checkpoints', [])):
                    raise ValueError('请选择实际存在的续训PT。')
                req.update(source_job=value['source_job'], checkpoint=value['checkpoint'])
            elif task in JOINT_TASKS:
                for role in ('walk', 'stand'):
                    selection = copy.deepcopy(value.get(role+'_teacher'))
                    if not isinstance(selection, dict):
                        raise ValueError('联合训练需要选择行走老师和起身老师。')
                    if selection.get('queue_entry'):
                        prior = next((e for e in self.training_queue['entries'] if e['id'] == selection['queue_entry']), None)
                        if not prior or prior['status'] == 'cancelled' or prior['request']['task'] not in TEACHER_TASKS[role]:
                            raise ValueError('队列老师类型不正确或已移除。')
                        if physical_recipe(prior['recipe']) != physical_recipe(self.recipe):
                            raise ValueError('队列老师与联合任务的机器人物理参数不同。')
                        for k in ('training_action_scale', 'action_filter', 'actor_dims', 'training_firmware_p'):
                            if prior['request'].get(k) != req.get(k):
                                raise ValueError('队列老师与联合任务的动作系数、滤波、舵机P或策略网络不同。')
                        if any(prior['request']['execution_profile'].get(k) != req['execution_profile'].get(k) for k in ('mode', 'distro')):
                            raise ValueError('队列老师与联合任务必须在同一训练机。')
                        selection = {'queue_entry': prior['id']}
                    else:
                        teacher = self.jobs.get(selection.get('source_job'), {})
                        if (teacher.get('op') != 'train' or model_task(teacher.get('request', {})) not in TEACHER_TASKS[role]
                                or not any(c['path'] == selection.get('checkpoint') for c in teacher.get('checkpoints', []))):
                            raise ValueError('请选择实际老师PT，或排在前面的队列老师。')
                        selection = {k: selection[k] for k in ('source_job', 'checkpoint')}
                    req[role+'_teacher'] = selection
            entry = {'id': secrets.token_hex(8), 'client_id': key, 'created': time.time(),
                     'status': 'waiting', 'attempt': 1, 'request': copy.deepcopy(req),
                     'recipe': copy.deepcopy(self.recipe), 'recipe_sha256': digest(self.recipe),
                     'calibration_source': (self.recipe.get('calibration') or {}).get('source', '随包标定'),
                     'message': '等待训练。'}
            self.training_queue['entries'].append(entry)
            self._queue_save()
            self._queue_wake.set()
            return {'entry_id': entry['id']}

    def queue_command(self, value):
        with self.lock:
            q = self.training_queue
            action = value.get('action')
            e = next((e for e in q['entries'] if e['id'] == value.get('entry_id')), None)
            if action == 'start':
                if not any(e['status'] in (*ACTIVE, 'waiting') for e in q['entries']):
                    raise ValueError('没有等待训练的任务。')
                q.update(enabled=True, message='队列已启动，依次训练。')
            elif action == 'pause':
                q.update(enabled=False, message='队列已暂停；当前训练继续，后续任务不启动。')
            elif action == 'stop':
                # Persist the scheduling barrier under the same lock as dispatch.
                # Stop only managed training jobs, never viewers or the WSL host.
                jobs = [j for j in self.jobs.values() if j['op'] == 'train' and j['status'] in ACTIVE]
                q.update(enabled=False, message='正在停止训练；后续任务不再启动，等待任务保留。'
                         if jobs else '已停止后续执行，等待任务保留。')
                self._queue_save()
                for job in jobs:
                    if job['status'] != 'stopping':
                        self.stop(job['id'])
            elif action == 'policy':
                if value.get('failure_policy') not in ('pause', 'continue'):
                    raise ValueError('失败处理选项无效。')
                q['failure_policy'] = value['failure_policy']
            elif action == 'clear':
                needed = {d for item in q['entries'] if item['status'] not in TERMINAL for d in self._queue_dependencies(item)}
                q['entries'] = [item for item in q['entries'] if item['status'] not in TERMINAL or item['id'] in needed]
            elif action in ('remove', 'move', 'retry'):
                if not e:
                    raise ValueError('找不到该队列任务。')
                if e['status'] in ACTIVE:
                        raise ValueError('当前任务正在运行，请先停止训练。')
                if action == 'remove':
                    if any(e['id'] in self._queue_dependencies(item) for item in q['entries'] if item['status'] not in TERMINAL):
                        raise ValueError('后面的联合任务正在引用此老师，请先移除联合任务。')
                    q['entries'].remove(e)
                elif action == 'move':
                    if e['status'] != 'waiting' or value.get('direction') not in (-1, 1):
                        raise ValueError('只能调整等待任务的顺序。')
                    ordered = list(q['entries'])
                    i = ordered.index(e)
                    j = i+value['direction']
                    if not 0 <= j < len(ordered) or ordered[j]['status'] != 'waiting':
                        raise ValueError('只能在等待任务之间调整顺序。')
                    ordered[i], ordered[j] = ordered[j], ordered[i]
                    self._queue_validate_order(ordered)
                    q['entries'] = ordered
                else:
                    if e['status'] not in ('failed', 'stopped'):
                        raise ValueError('只有失败或停止的任务需要重试。')
                    job = self.jobs.get(e.get('job_id'), {})
                    if job.get('id') in self.processes or job.get('_monitor_thread') or job.get('status') in ACTIVE:
                        raise ValueError('原训练进程仍在收尾，请稍后重试。')
                    e.update(status='waiting', attempt=e.get('attempt', 1)+1, message='等待重试。')
                    for k in ('job_id', 'started', 'ended'): e.pop(k, None)
                    q.update(enabled=False, message='已放回队列；点击开始训练重试，沿用添加时参数。')
            else:
                raise ValueError('未知队列操作。')
            self._queue_save()
            self._queue_wake.set()
            return {'okay': True}

    def _queue_resolve_teachers(self, entry):
        req = copy.deepcopy(entry['request'])
        for role in ('walk', 'stand'):
            selection = req.get(role+'_teacher', {})
            if not selection.get('queue_entry'):
                continue
            teacher = next((e for e in self.training_queue['entries'] if e['id'] == selection['queue_entry']), None)
            if not teacher or teacher['status'] != 'completed':
                raise ValueError('队列中的'+('行走' if role == 'walk' else '起身')+'老师没有成功完成。')
            job = self.jobs.get(teacher.get('job_id'), {})
            checkpoints = job.get('checkpoints', [])
            if not checkpoints:
                raise ValueError('队列老师没有保存PT；请设置足够轮数（1000轮起保存）。')
            cp = max(checkpoints, key=lambda c: c.get('iteration', -1))
            req[role+'_teacher'] = {'source_job': job['id'], 'checkpoint': cp['path']}
        return req

    def queue_tick(self):
        """One atomic scheduling pass; no remote inspection or training in HTTP threads."""
        with self.lock:
            if self.closed:
                return
            q = self.training_queue
            for entry in q['entries']:
                if entry['status'] not in ACTIVE:
                    continue
                # The job is persisted before launch returns. Recover its link after
                # an interrupted desktop process, without launching a second copy.
                matches = [j for j in self.jobs.values() if j.get('request', {}).get('queue_entry_id') == entry['id']
                           and j['request'].get('queue_attempt') == entry.get('attempt', 1)]
                job = self.jobs.get(entry.get('job_id')) or (matches[-1] if matches else None)
                if not job:
                    entry.update(status='waiting', message='尚未创建训练进程，等待启动。')
                    self._queue_save()
                    continue
                entry['job_id'] = job['id']
                # A complete event precedes owner exit/GPU cleanup. Never launch
                # the next training while the durable owner is still alive.
                if not job.get('ended') or job['id'] in self.processes or job.get('_monitor_thread'):
                    entry['status'] = job['status'] if job['status'] in ACTIVE else 'running'
                    return
                okay = job['status'] == 'completed' and job.get('worker_exit_code') == 0
                entry.update(status='completed' if okay else 'stopped' if job['status'] == 'stopped' else 'failed',
                             ended=job['ended'], message=job.get('message', '训练结束。'))
                if not okay and (q['failure_policy'] == 'pause' or entry['status'] == 'stopped'):
                    q.update(enabled=False, message='队列已暂停：'+entry['message'])
                self._queue_save()
            if not q['enabled']:
                return
            if any(j['status'] in ACTIVE or (j['op'] == 'train' and (j['id'] in self.processes or j.get('_monitor_thread')))
                   for j in self.jobs.values() if j['op'] not in ('preview', 'play', 'onnx')):
                return
            entry = next((e for e in q['entries'] if e['status'] == 'waiting'), None)
            if not entry:
                q.update(enabled=False, message='队列已全部执行完。')
                self._queue_save()
                return
            recipe = self.recipe
            try:
                req = self._queue_resolve_teachers(entry)
                entry.update(status='starting', started=time.time(), message='正在按添加时的参数启动…')
                self._queue_save()
                self.recipe = copy.deepcopy(entry['recipe'])
                self._launching_queue_entry = entry
                result = self.launch('train', req)
                entry.update(job_id=result['job_id'], status='running', message='正在训练。')
                q['message'] = '正在训练：'+(entry['request']['label'] or TASKS[entry['request']['task']]['name'])
            except Exception as error:
                # If launch created a durable record before a local write failed,
                # reconnect that record rather than claiming it never started.
                job = next((j for j in self.jobs.values() if j.get('request', {}).get('queue_entry_id') == entry['id']
                            and j['request'].get('queue_attempt') == entry.get('attempt', 1)), None)
                if job:
                    entry.update(job_id=job['id'], status='running', message='已创建训练，等待状态回读。')
                else:
                    entry.update(status='failed', ended=time.time(), message=str(error))
                    q['message'] = '队列任务启动失败：'+str(error)
                    if q['failure_policy'] == 'pause': q['enabled'] = False
            finally:
                self.recipe = recipe
                self._launching_queue_entry = None
                self._queue_save()

    def start_queue_scheduler(self):
        with self.lock:
            if self._queue_thread and self._queue_thread.is_alive():
                return
            def run():
                while not self.closed:
                    try:
                        self.queue_tick()
                    except Exception as error:
                        with self.lock:
                            self.training_queue.update(enabled=False, message='队列调度暂停，当前WSL训练不受影响：'+str(error))
                    self._queue_wake.wait(1)
                    self._queue_wake.clear()
            self._queue_thread = threading.Thread(target=run, name='training-queue', daemon=True)
            self._queue_thread.start()

    def close(self):
        with self.lock:
            self.closed = True
            self._queue_wake.set()
        super().close()
