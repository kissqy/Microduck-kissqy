"""Pure request guard for evaluation-only comparison inputs.

Called before cached probes, job creation, or loading the simulation runtime.
The profile itself is validated against the selected ONNX separately.
"""


def validate_request(value, op=None, *, profile=None):
    operation = op if op is not None else value.get('op')
    comparison = 'target_limit_comparison' in value
    explicit_mode = 'target_limit_start_mode' in value
    if (comparison or explicit_mode) and operation != 'onnx':
        raise ValueError('限幅 / 真机起点对照仅用于所选倒地起身老师的 ONNX 仿真。')
    if explicit_mode and not comparison:
        raise ValueError('真机起点参数必须与限幅对照录制资料一起提交。')
    mode = value.get('target_limit_start_mode', 'standard')
    if type(mode) is not str or mode not in ('standard', 'recorded'):
        raise ValueError('起点对照模式无效：只允许 standard 或 recorded。')
    if mode == 'recorded' and profile is not None and not profile.get('recorded_start'):
        reason = profile.get('recorded_start_unavailable_reason') or '录制缺少有效的启用前静止姿态。'
        raise ValueError('无法运行真机起点对照：' + reason)
    return mode
