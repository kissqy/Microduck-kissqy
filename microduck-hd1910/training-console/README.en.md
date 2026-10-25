[简体中文](README.md) | **English** | [Русский](README.ru.md)

# 🧠 Microduck Training Studio · R1.5.27

An independent Chinese-language console for organizing training tasks, managing queues, viewing reward curves and logs, evaluating physics simulations, and exporting ONNX and complete model packages.

**Current pairing: Official Microduck 0.15.1 · Official chassis + Feetech HD1910 · 14 action categories and 35 task recipes.**

[⬇️ Download complete Training Studio R1.5.27](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Training-Studio-R1.5.27.zip) · [Detailed training rules](USER-GUIDE.en.md) · [Project homepage](../../README.en.md)

## Features

| Feature | Purpose |
| --- | --- |
| Actions and task recipes | Walking, recovery, sit / stand, joint training, picking, kicking, forward rolls, and roller tasks. |
| Training queue | Save parameters for each task, execute tasks sequentially, and inspect progress / state. |
| Monitoring | Reward curves, progress, sampling speed, logs, and saved checkpoints. |
| Physics simulation | Inspect the initial robot model; run selected PT / ONNX policies with simulation controls and pose reset. |
| Export | ONNX and complete packages preserving training and deployment information. |
| Local calibration | Import calibration files or console recordings, or retrieve current calibration from ZERO over SSH. |
| SSH training server | Operate the page on your computer while training, evaluating, and saving results on a Linux GPU server. |

## Download and start

Extract the complete runtime ZIP. The computer opening the console needs **Python 3.10 or newer**. On Windows, make `py` or `python` available after installation.

| Computer | Launcher |
| --- | --- |
| Windows | Double-click `start-training.cmd`. |
| macOS / Linux | Run `bash start-training.command` in this directory. |
| Direct Python launch | Run `python3 training_console.py --open` here. |

Open **http://127.0.0.1:8092** and keep the launch terminal running. Source uses the same entry points.

The page operates independently; training and simulation run on the selected execution host. Actual training uses **Linux / WSL2 + NVIDIA GPU**, with the pinned engine and dependencies prepared through the page. ZERO is needed only when retrieving physical calibration, not for training itself.

## First training run

1. **Choose the execution host.** Under **训练位置** (Training Location), select **本机 / WSL** (Local / WSL) or **SSH 服务器** (SSH Server). Local uses your existing Linux / WSL environment. For remote use, fill in host, username, SSH port, authentication, and workspace; click **部署并准备环境** (Deploy and Prepare Environment) on first use.
2. **Prepare the environment once.** Initial preparation downloads the fixed engine and dependencies. Later sessions reuse the environment and detection cache.
3. **Prepare calibration.** Import a file or console recording, or use **从 ZERO 获取** (Fetch from ZERO). Check the robot and assembly data used by this training run.
4. **Choose a task.** Select action, terrain, and backlash recipe; set parallel environments, actual training iterations, and run name. Select a checkpoint or teacher when resuming or doing joint training.
5. **Queue it.** Click **＋ 加入队列** (Add to Queue). Each entry saves its parameters and calibration at insertion. Later page changes do not rewrite queued tasks.
6. **Start.** Click **开始训练 ▶** (Start Training). Follow curves, logs, and task states; use **停止训练** (Stop Training) to stop.
7. **Evaluate.** After a checkpoint is saved, select it under **模型与验证** (Models and Validation), then click **查看所选策略** (View Selected Policy).
8. **Export.** Use **导出 ONNX** (Export ONNX) to produce the deployment model and full package. Import only model types supported by the Robot Console.

First establish the task's default recipe, then change one variable at a time. New tasks default to P=5 and action scale=1.0; see [detailed rules](USER-GUIDE.en.md#current-training-and-model-rules).

## Simulation and model files

| File or operation | Purpose |
| --- | --- |
| PT checkpoint | Resume training, choose a teacher, or evaluate the saved policy. |
| ONNX | Inference, corresponding simulation evaluation, and robot deployment. |
| Complete model ZIP | Model plus training / deployment information for transfer and import; keep the complete export. |
| 查看初始模型 (View Initial Model) | Inspect the robot model and initial state for this task. |
| 查看所选策略 (View Selected Policy) | Run the chosen checkpoint or ONNX. |
| 自动查看新检查点（周期评估） (Automatically View New Checkpoints / Periodic Evaluation) | Update the evaluation preview as checkpoints are saved. |

Monitoring displays the active training run; simulation evaluates a selected saved model. Compare training stages using periodic evaluation or manually selected checkpoints.

## Local and server tasks

- **Local / WSL:** records and models are saved in the selected local training directory; the page displays the output path. Closing the page does not stop training. Use Stop Training.
- **SSH server:** queues, training, evaluation, and results live in the server workspace. Upload / download models through the page. Disconnecting SSH or closing the desktop console leaves server training and queues running.
- **After server reboot:** reconnect and resume from a saved checkpoint.

## Related guides

- [Detailed user guide and training rules](USER-GUIDE.en.md)
- [Official task parameter audit](docs/audit-0151/official-task-parameter-audit.en.md)
- [Roller task audit](docs/audit-0151/roller-audit/official-roller-audit.en.md)
- [Testing](tests/README.md)
- [Robot Console](../firmware/console/README.en.md)
- [Licenses and third-party sources](NOTICE.md)
