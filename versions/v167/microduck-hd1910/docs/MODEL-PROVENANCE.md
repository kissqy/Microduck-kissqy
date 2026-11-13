**简体中文** | [English](MODEL-PROVENANCE.en.md)

# HD1910 动作模型：来源与发布范围

本页按具体权重记录作者自训成果、发布副本和来源证据。使用边界见[软件与自训模型权利说明](SOFTWARE-MODEL-RIGHTS.md)，许可正文见[个人非商业许可](../LICENSES/Personal-NonCommercial.txt)。

作者确认本项目的飞特 HD1910 动作策略由作者自行训练和适配。这里的“自训”描述训练成果来源，不把官方训练框架、官方任务、机器人几何或他人的预训练权重变为作者原创。对作者依法享有、可以单独授权的权重成果及自有训练记录，项目声明的使用范围为个人非商业使用；第三方权利及既有有效授权保留。

核对基线：2026-10-27，仓库提交 `ad45dd78d9033ac575d5a92e46342ab0829bb274`，R17 V167 / control.43 发布清单。下表短 ID 是 `manifest.json` 所记 ONNX SHA-256 的前 12 位；完整值以相应 manifest 为准。本次核对未重新解包、重算现有二进制发布包的哈希，也未更改其内容。

## 1. 当前随包清单中的十个动作模型

依据：[随包说明](../firmware/packaging/README.zh-CN.md)、[安装文件清单](../firmware/packaging/install-files.json)、[V167 ARM64/QEMU 格式与首次推理记录](../firmware/console/verification/v167/arm64-models.json)。QEMU 记录是格式和执行检查，不等同于每种动作都完成真机验证。

| 动作／发布名称 | 短 ID | 权重在安装包中的相对位置／来源记录 | 记录的检查点 |
| --- | --- | --- | --- |
| 行走、零速保持与倒地恢复 `walk` | `1cbf8730eadd` | `models/1cbf8730eadd75a5704332c9f3c10f60/policy.onnx` · [manifest](../firmware/packaging/models/1cbf8730eadd75a5704332c9f3c10f60/manifest.json) | 9599 |
| 起坐 `sitstand` | `1c94934c6421` | `models/1c94934c6421ec72ed48079cea749668/policy.onnx` · [manifest](../firmware/packaging/models/1c94934c6421ec72ed48079cea749668/manifest.json) | 10000 |
| 地面捡取 `ground_pick` | `b14e3a8b56dd` | `models/b14e3a8b56ddbb8d2d831e727774a168/policy.onnx` · [manifest](../firmware/packaging/models/b14e3a8b56ddbb8d2d831e727774a168/manifest.json) | 9999 |
| 前滚翻 `roulade` | `59e15d7b04d0` | `models/59e15d7b04d0c40e9b11b8a70bdecae6/policy.onnx` · [manifest](../firmware/packaging/models/59e15d7b04d0c40e9b11b8a70bdecae6/manifest.json) | 9999 |
| 右脚踢球 `kick_right` | `67ad09d82f48` | `models/67ad09d82f4865d222a7ae06f250cf9f/policy.onnx` · [manifest](../firmware/packaging/models/67ad09d82f4865d222a7ae06f250cf9f/manifest.json) | 9999 |
| 左脚踢球 `kick_left` | `ee0376c92704` | `models/ee0376c927044cdece056ba1d3e6eac7/policy.onnx` · [manifest](../firmware/packaging/models/ee0376c927044cdece056ba1d3e6eac7/manifest.json) | 9999 |
| 滑轮对称滑 `roller_swizzle` | `14195135fcaa` | `roller/swizzle/policy.onnx` · [manifest](../firmware/packaging/roller/swizzle/manifest.json) | 9999 |
| 滑轮蹲下 `roller_crouch` | `82be20b115d9` | `roller/crouch/policy.onnx` · [manifest](../firmware/packaging/roller/crouch/manifest.json) | 7999 |
| 滑轮原地转 `roller_spin` | `621fe9f3ae34` | `roller/spin/policy.onnx` · [manifest](../firmware/packaging/roller/spin/manifest.json) | 7999 |
| 滑轮倒地起身 `roller_standup` | `2575b5894bcd` | `roller/standup/policy.onnx` · [manifest](../firmware/packaging/roller/standup/manifest.json) | 11000 |

这些是六个普通脚掌动作和四个滑轮动作。`packaging/models/` 与 `packaging/roller/` 当前 Git 树主要保存来源和部署元数据；安装清单中的权重随固件包分发。`packaging/LICENSE` 已有 Apache-2.0 声明，不能仅凭本页把该目录中已有明确许可的文件统一改为非商业许可；同样不能仅凭软件目录的许可证推断每份另行分发权重的权利链。具体权重须结合其随附声明、来源及此前有效授权判断。本页不撤回既有授权，也不声称已经逐项核实旧归档内部的许可文件。

## 2. 源码树直接保存的六个策略权重

`firmware/policies/` 中有以下六份 `policy.onnx`。其目录数量不等于当前发布包模型数量；其中 `stand` 是训练/评估用的起身老师，不是当前自动站立保持槽，也不在上述十个模型的安装清单中。

| 源码权重路径 | 对应 ID | 此次基线中的 Git blob SHA-1 |
| --- | --- | --- |
| [walk/policy.onnx](../firmware/policies/walk/policy.onnx) | `1cbf8730eadd75a5704332c9f3c10f60` | `cadea39ee4a5253660cf08eced75e473f75a20a4` |
| [sitstand/policy.onnx](../firmware/policies/sitstand/policy.onnx) | `1c94934c6421ec72ed48079cea749668` | `ce482e6dca89d3b53bf54fc4461b14ce20e6c97f` |
| [ground_pick/policy.onnx](../firmware/policies/ground_pick/policy.onnx) | `b14e3a8b56ddbb8d2d831e727774a168` | `dff6e83ce5fcd080113a71d3c55bd56e0ee8d7b0` |
| [roulade/policy.onnx](../firmware/policies/roulade/policy.onnx) | `59e15d7b04d0c40e9b11b8a70bdecae6` | `2cdf8fdb6362a06c344a5bd6e70e9474b93eeef9` |
| [kick_left/policy.onnx](../firmware/policies/kick_left/policy.onnx) | `ee0376c927044cdece056ba1d3e6eac7` | `2b6703c2f6b15326a59180c7e16d8fb3d6da6bc0` |
| [stand/policy.onnx](../firmware/policies/stand/policy.onnx) | `a481d9f211f31d9476ab1a319fe362a2` | `a2adfc893d1125e1fd08836799a6a5bffdfe3020` |

Git blob SHA-1 用于定位本次审查的仓库文件，不是 ONNX 文件的 SHA-256。`a481…` 的[来源记录](../firmware/packaging/models/a481d9f211f31d9476ab1a319fe362a2/manifest.json)标记 `teacher_only: true`，实际检查点为 11000。

## 3. 现有来源记录能说明什么

多数当前动作记录了官方训练框架 `pollen-robotics/microduck_rl` 的提交 `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`，以及 HD1910 适配、训练任务、检查点、导出哈希和本地训练运行标识。起坐的较早记录为提交 `25791f0bd260fd869ed841578785fa8d7e14396d`。这些源码来源字段不等于“权重由官方提供”，也不等于“全部来源权利均已核验”。

`walk` 的[训练请求快照](../firmware/packaging/models/1cbf8730eadd75a5704332c9f3c10f60/training-request.json)记录了续训、热启动及两份专家/锚定检查点。仅凭本地缓存路径，无法确定所有老师权重的最初作者、下载来源及许可。部分其他模型快照记录 `resume: false`，但这一个字段仍不足以证明完整的从零初始化及权利链。公开介绍可以写“作者自训、适配 HD1910”，不要据此统一写成“所有模型完全从零原创、无第三方权重”。

后续每份新模型应随附：作者、任务与版本、ONNX SHA-256、训练框架提交、是否从零训练/续训/微调/蒸馏、初始权重及每份老师权重的作者和许可、自有配置或代码的改动、数据/几何来源、导出记录、适用许可及实机验证范围。未知项如实注明，不用导出时间或模型文件名替代来源证据。

## 4. 历史模型、参考权重与测试样本

| 范围 | 身份与处理方式 |
| --- | --- |
| `firmware/test-data/walk-teacher14000/` | 历史行走老师／数值回归样本，SHA-256 前缀 `9e3ff8bde021`，检查点 13999；不等于当前 `walk` |
| `firmware/test-data/walk-teacher10000/` | 历史 HD1910 行走样本，SHA-256 前缀 `0b8f04476cab`；不在当前十模型安装清单 |
| `firmware/test-data/ground-pick-legacy/`、`roulade-legacy/` | 历史自训记录与回归模型，分别为 `2b69fa681ed0`、`8fdaf12c7478`；使用时仍须按自身来源确认许可 |
| `firmware/robotd/test-data/joint-audit/` | 联合模型检查样本，SHA-256 前缀 `5c019c3d3d2c`；不能因位于测试目录就认定为官方或无许可限制 |
| `firmware/verification/official-reference/hf-policies-*.onnx` | 标明为官方参考的权重；不纳入作者自训原创声明，许可须按具体上游权重确认 |
| `firmware/duck-control/tests/fixtures/*.onnx` | 格式、状态、异常输入等测试夹具，不是可部署动作模型 |
| `firmware/pet-detect/models/pet_detect.onnx` | 抚摸声音分类器，组件说明记载移植自 `apirrone/microduck_pet_detect`；不是 HD1910 自训运动策略，不作作者原创权重声明 |

“模型”也可能指三维几何，勿将本页的神经网络权重与 `duck.bin`、`duck-visual.bin`、STL 等几何资产混为一类。几何来源见[第三方说明](THIRD-PARTY.md)与[几何声明](../firmware/console/licenses/MODEL-NOTICE.md)。

## 5. 单脚独立演示

首页的单脚独立是作者展示的自训实机成果。此次已核对的 Git 树、十模型安装清单和 V167 模型检查记录中，尚未识别到能与该演示一一对应、单独列明哈希和来源的单脚独立权重。因此，演示视频不表示上述发布包已经包含该模型；它也不能替代具体模型的许可和训练来源记录。

公开分发该权重时，应为它建立独立模型目录和来源记录，并确认有无使用第三方初始/老师权重。官方文档里 `RemiFabre/microduck-flamingo-cycle` 等示例属于其他来源，不能仅因动作相似而认定为本项目模型，或替其更改权利归属。
