"""Small, dependency-free control state shared by the Linux simulation adapter.

No robot transport is present. Commands have a short lease, so a stopped browser
or delayed pipe cannot leave the simulated robot walking indefinitely.
"""
import math
import threading
import time
from collections import deque


class SimulationControls:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.Lock()
        self.deadline = 0.0
        self.velocity = (0.0, 0.0, 0.0)
        self.actions = deque(maxlen=16)
        self.closed = False
        self.last_control = {}
        self.sequences = {}

    def receive(self, message):
        action = message.get('action')
        with self.lock:
            if self.closed: return
            if action=='shutdown':
                self.closed=True;self.velocity=(0.0,0.0,0.0);self.deadline=0;self.actions.clear();return
            client, sequence = message.get('client'), message.get('sequence')
            if isinstance(client,str) and type(sequence) is int:
                if sequence <= self.sequences.get(client,-1): return
                self.sequences[client] = sequence
                if len(self.sequences)>128: self.sequences = {client:sequence}
            if action == 'move':
                values = message.get('velocity')
                expiry = message.get('expires_at')
                if not isinstance(values, list) or len(values) != 3: return
                if any(type(v) not in (float, int) or not math.isfinite(v) for v in values): return
                if type(expiry) not in (float, int) or not math.isfinite(expiry): return
                self.velocity = tuple(max(-limit, min(limit, v)) for v, limit in zip(values, (.4, .3, 1.0)))
                self.deadline = min(expiry, self.clock()+.8)
                self.last_control = {'client':message.get('client'), 'sequence':message.get('sequence'),
                                     'received_at':self.clock()}
            elif action in ('zero', 'pause', 'resume', 'reset'):
                self.velocity = (0.0, 0.0, 0.0)
                self.deadline = 0.0
                self.last_control = {'client':client, 'sequence':sequence, 'received_at':self.clock()}
                if action != 'zero': self.actions.append(action)

    def clear(self):
        with self.lock:
            self.velocity = (0.0, 0.0, 0.0)
            self.deadline = 0.0

    def close(self):
        with self.lock:
            self.closed = True
            self.velocity = (0.0, 0.0, 0.0)
            self.deadline = 0.0

    def sample(self):
        with self.lock:
            return self.velocity if not self.closed and self.clock() < self.deadline else (0.0, 0.0, 0.0)

    def drain(self):
        with self.lock:
            result = list(self.actions)
            self.actions.clear()
            return result

    def status(self):
        """Adapter receipt, independent of the desktop HTTP acknowledgement."""
        with self.lock:
            return {**self.last_control, 'expired':bool(self.last_control and self.clock() >= self.deadline),
                    'requested':list(self.velocity), 'closed':self.closed}


class OnnxPolicy:
    """Run a recorded official ONNX export, including its embedded normalizer.

    MLP, GRU and LSTM exports from RSL-RL are supported. Unknown observation or
    output contracts fail explicitly; they are never padded or guessed.
    """
    def __init__(self, path, observation_width, action_width, groups, device, session=None):
        import numpy as np
        self.np = np
        if session is None:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            session = ort.InferenceSession(str(path), sess_options=opts, providers=['CPUExecutionProvider'])
        self.session, self.groups, self.device = session, groups, device
        self.action_width = action_width
        inputs = {item.name: item for item in session.get_inputs()}
        outputs = {item.name: item for item in session.get_outputs()}
        if set(inputs) not in ({'obs'}, {'obs','h_in'}, {'obs','h_in','c_in'}):
            raise ValueError('ONNX 输入契约不受支持；请选择本台导出的 MLP / GRU / LSTM 策略。')
        if 'actions' not in outputs or inputs['obs'].type != 'tensor(float)':
            raise ValueError('ONNX 缺少官方 obs / actions 浮点接口。')
        if len(inputs['obs'].shape) != 2 or inputs['obs'].shape[-1] != observation_width:
            raise ValueError('ONNX 观测维度与所选任务不一致，已取消加载。')
        if inputs['obs'].shape[0] not in (1, None, 'batch', 'batch_size'):
            raise ValueError('ONNX 不支持单环境输入。')
        if len(outputs['actions'].shape) != 2 or outputs['actions'].shape[-1] != action_width:
            raise ValueError('ONNX 动作维度与所选机器人不一致，已取消加载。')
        self.states = {}
        self.output_names = ['actions']
        for name in ('h_in','c_in'):
            if name not in inputs: continue
            shape = inputs[name].shape
            output_name = name.replace('_in','_out')
            if (inputs[name].type != 'tensor(float)' or len(shape) != 3 or
                    any(type(x) is not int or x <= 0 for x in shape) or shape[1] != 1 or output_name not in outputs):
                raise ValueError('ONNX 循环网络状态接口不匹配。')
            self.states[name] = np.zeros(shape, dtype=np.float32)
            self.output_names.append(output_name)

    def infer_array(self, observation):
        np = self.np
        observation = np.asarray(observation, dtype=np.float32)
        if not np.isfinite(observation).all(): raise ValueError('仿真观测含无效值，已暂停。')
        result = self.session.run(self.output_names, {'obs':observation, **self.states})
        action = result[0]
        if action.shape != (1, self.action_width) or not np.isfinite(action).all():
            raise ValueError('ONNX 返回无效动作，已暂停仿真。')
        for name, value in zip(self.states, result[1:]):
            if value.shape != self.states[name].shape or not np.isfinite(value).all():
                raise ValueError('ONNX 返回无效循环状态，已暂停仿真。')
            self.states[name] = value
        return action

    def __call__(self, observation):
        import torch
        raw = torch.cat([observation[name] for name in self.groups], dim=-1)
        result = self.infer_array(raw.detach().cpu().numpy())
        return torch.as_tensor(result, device=self.device)

    def reset(self):
        for value in self.states.values(): value.fill(0)
