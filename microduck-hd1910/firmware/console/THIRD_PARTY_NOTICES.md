R17 v1.0.97：运行程序基线为 Pollen Robotics microduck 0.15.1 / 1fa84386f07884e27866411bc1ba166977bced95，Apache-2.0。源码修改清单见完整源码包 OFFICIAL-CHANGES.zh-CN.md；许可见 licenses/MICRODUCK-APACHE-2.0.txt。
旧 R17 三维鸭子、Three.js、STLLoader 和训练模型素材的原始许可记录继续保留如下。用户训练权重不因本软件许可而重新授权。
ONNX Runtime 1.28.0 许可证及 ThirdPartyNotices 随服务包 onnxruntime 目录保留。

# 本次音源与手柄来源

`audio/generator/{rng,personality,synth,voices}.rs` 来自 Pollen Robotics microduck 固定提交 590b986bd8c0d50ae02cb3ea2f59c463b6828168，保持原文件，Apache-2.0；许可见 `licenses/MICRODUCK-APACHE-2.0.txt`。新增 WAV 由这些模块生成；本包 main.rs 为写入 WAV 的包装。手柄映射同一官方提交 padd/src/main.rs。

# 第三方来源、版本与许可

本项目是独立的观测与手动控制工具，不是 Pollen Robotics 官方发布，也不代表官方或社区项目背书。以下第三方软件与素材保留各自许可；模型的许可不能被软件的 Apache/MIT 许可替代。

## 官方运行时、协议和模型

- 来源：[pollen-robotics/microduck · 固定提交 590b986](https://github.com/pollen-robotics/microduck/tree/590b986bd8c0d50ae02cb3ea2f59c463b6828168)。
- 完整提交：`590b986bd8c0d50ae02cb3ea2f59c463b6828168`；工作区软件版本 `0.10.0`。
- 协议核对：`duck-ipc-proto/src/lib.rs`、`robotd/src/main.rs`、`tof/src/main.rs`、`mediad/webclient/`。
- 运动学/模型核对：`robotctl/src/duck.rs`、`scripts/bake-duck-mesh.py`、`duck-control/src/model.rs`。
- IMU/舵机单位核对：`duck-control/src/imu.rs`、`duck-control/src/bus.rs` 及 ROBOTIS 官方资料。
- 上游软件许可：Apache-2.0，全文位于 `licenses/MICRODUCK-APACHE-2.0.txt`。

### 鸭子几何模型（单独许可）

模型及设计归 Pollen Robotics / 其上游贡献者。

网页显示的 `static/assets/duck-visual.bin` 从 [官方 microduck_rl 固定提交 e8a2de5](https://github.com/pollen-robotics/microduck_rl/tree/e8a2de510b6cb5062e9ccab8b41f2d47f2186504/src/mjlab_microduck/robot/microduck) 的原始 STL/MJCF 转换，未做几何减面；显示法线采用 35°硬边阈值，保留上游隐藏内部电子零件的规则。使用冻结运行时的关节树，右踝视觉零件转换到冻结坐标系；嘴部仍固定。生成方法见配套源码中的 `tools/bake_visual.py`，输入/输出哈希见 `static/assets/duck-visual.json`。该派生模型沿用上游模型的非商业、署名、相同方式共享要求。

`static/assets/duck.bin` 原样复制自冻结提交的 `robotctl/assets/duck.bin`；仅用于运动学基线核对。该原文件没有修改。

SHA-256：

```text
1e1200053e2326706632306bc80831d5e0dfa5462d792a677fc05a43f145651e
```

冻结仓库的烘焙脚本说明几何来自 Microduck MJCF/STL 模型。相关官方训练/模型仓库的 [README 许可段](https://github.com/pollen-robotics/microduck_rl#license) 明确单列：

> 3D model files are licensed under Creative Commons BY-SA-NC.

按上游表述保留署名、非商业、相同方式共享要求；这段来源说明未指定 CC 版本，因此本包不擅自补成某个版本，也不宣称几何属于 Apache-2.0。另见 `licenses/MODEL-NOTICE.md`。本包面向个人机器人调试，不赋予额外商业使用权。

## three.js 0.180.0

- 上游：[mrdoob/three.js · r180](https://github.com/mrdoob/three.js/tree/r180)。
- 文件：`static/vendor/three.module.min.js`、`three.core.min.js`、`OrbitControls.js`。
- Copyright © 2010–2025 three.js authors；MIT 全文：`licenses/THREE-MIT.txt`。
- 来源为官方 npm `three@0.180.0` 包。唯一适配：OrbitControls 的裸模块导入改为同目录 `./three.module.min.js`，以便离线运行。

## 参考但不捆绑的社区项目

- [microai-lab/microduck-studio](https://github.com/microai-lab/microduck-studio)，查看的提交为 `4ad606d58b44d1708296a3b9d699e458388b9c7f`。参考 3D、传感器和执行器集中呈现的思路；本包不包含其实现、不依赖其 MuJoCo 数据。
- [7757/fanduck](https://github.com/7757/fanduck)，查看社区镜像工作台及其公开的模型许可依据；不包含其应用实现或派生模型文件。完整视觉曲面直接取自上述固定官方 RL 提交。

## 开发测试依赖

DOM 测试使用 jsdom 26.1.0；浏览器回归脚本面向 Playwright。它们未捆绑在交付包中，运行中控不需要它们。安装开发依赖时，请保留各自上游许可。

ONNX CPU 测试依赖 ONNX / ONNX Runtime / NumPy，测试时在临时目录生成极小的数学模型，结束后删除；这些不是机器人训练权重。浏览器测试使用明确的仿真状态夹具，只验证页面与控制请求，不代表 GPU 物理仿真验收。

本包不包含机器人密钥、SSH known_hosts、私人配置或来自用户摄像头的图像。

## 官方鸭叫变体

`audio/chirp/chirp_a.wav` 至 `chirp_l.wav` 由固定官方 Microduck 提交 590b986 的 sounds 0.10.0 合成器生成，seed=590986、variant=0…11；48 kHz、16 bit、单声道。用于 Zero 缺少声音库时的手动 chirp 回退，现有声音库优先。源代码和声音配方依官方 Apache-2.0 许可，见 `licenses/MICRODUCK-APACHE-2.0.txt`。

## Official pad-expressions (v1.0.62)

Source: https://github.com/pollen-robotics/microduck/tree/5492ea602e3aef59b2a19d702977aab2da2cd88e


## PyYAML 6.0.3

仅纯 Python 文本解析代码，位于 R17 服务安装包的 `_model_yaml/`。MIT 许可全文随 `_model_yaml/LICENSE` 附带；使用 BaseLoader 读取导出的训练参数，不加载 Python 对象或 checkpoint。
