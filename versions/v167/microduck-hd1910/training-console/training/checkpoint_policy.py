"""Suppress early checkpoints without changing the official learning loop."""
import re
from pathlib import Path

MIN_ITERATION = 1000


def install(official, report):
    original_loader = official.load_runner_cls
    original_default = official.MjlabOnPolicyRunner
    wrappers = {}

    def wrapped(base):
        if base in wrappers:return wrappers[base]
        class ManagedCheckpoints(base):
            def save(self, path, *args, **kwargs):
                match = re.fullmatch(r'model_(\d+)\.pt', Path(path).name)
                iteration = int(match[1]) if match else self.current_learning_iteration
                # RSL-RL numbers iterations from zero. A final save at index 999
                # has completed 1000 updates; give it a retained filename while
                # preserving the official checkpoint's internal resume counter.
                if iteration < MIN_ITERATION - 1:return None
                if match and iteration == MIN_ITERATION - 1:
                    path = str(Path(path).with_name('model_1000.pt'))
                return super().save(path, *args, **kwargs)
        wrappers[base] = ManagedCheckpoints
        return ManagedCheckpoints

    def load_runner(task):
        runner = original_loader(task)
        return wrapped(runner) if runner is not None else None

    official.load_runner_cls = load_runner
    official.MjlabOnPolicyRunner = wrapped(original_default)
    report('log', line='模型保存：每1000轮及结束时保存；不足1000轮不写PT，跳过初始第0/1轮存档。')
    def restore():
        official.load_runner_cls = original_loader
        official.MjlabOnPolicyRunner = original_default
    return restore
