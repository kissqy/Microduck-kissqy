# Microduck R17 V181 / control.54

以 V169-upload-fix 为基线，增加火烈鸟和装死。火烈鸟最多站立 6 秒、交替换脚、取消落脚后回 Walk，确认倒地直接回 Walk。装死使用独立模型，运行 5 秒后交回原 Walk。

本工程是 Microduck 的 R17 适配版本，面向 Radxa Zero、HD1910 舵机及配套 IMU。当前中控为 `1.0.181`，机器人固件为 `1fa8438-feetech-ft6-control.54`，配套官方系统为 `0.15.1`。

实体手柄通过 padd 与 robotd 的原生通道控制行走和滑轮。随包提供 swizzle、crouch、spin、standup 四个滑轮 ONNX，以及行走、起坐、地面捡取、前滚翻和左右踢球模型。滑轮航向由 IMU 反馈参与计算。各滑轮模型使用自己的合同运行系数；standup 使用实体 L3 手动测试：仅滑轮模式、运动已启用且 IMU 确认倒地时响应；测试窗口 5 秒，不自动触发、不连发。

13 个官方表情通过空闲背键映射 R3 逐次轮播，使用官方动作与原始声音；不含装死。仅行走策略已启用、直立静止且反馈有效时响应。背键设置和轮播顺序见当前使用说明。

## 使用与开发入口

| 目的 | 文档 |
| --- | --- |
| 安装中控、固件及操作实体手柄 | [当前使用说明](console/README.zh-CN.md) |
| 查看随包模型、标定与服务配置 | [当前固件说明](packaging/README.zh-CN.md) |
| 编译与打包 V181 | [构建说明](BUILDING-V181.md) |
| 阅读服务设计与接口 | [文档索引](docs/README.md) |
| 查看构建和验证结果 | `verification/v181/` |

当前参考配置包含用户确认的装配标定、SSH 密码保存逻辑及网页/CMD GitHub 入口。安装保留有效本机标定和设置；无有效标定时可使用随包数据恢复。

robotd 与 padd 为本版 ARM64 编译程序；新模型及调度软件验证记录见 `verification/v181/`。Zero 真机平衡和恢复尚未验证。

## 开源与许可

R17 仓库：[kissqy/Microduck-kissqy](https://github.com/kissqy/Microduck-kissqy)。上游工程：[pollen-robotics/microduck](https://github.com/pollen-robotics/microduck)。模型训练工程：[microduck_rl](https://github.com/pollen-robotics/microduck_rl)。

第三方许可与模型声明随对应目录提供，发布和再分发请遵循各自的 LICENSE 与 notices。

P 继续使用模型合同；显式上力时写入地址 51 单字节 D=0、地址 48 小端两字节 1000。卸力仅恢复 P，D 与限值保持。

装死模型为 V8 训练＋STS3215 M6 BAM，接入说明见 [装死机制](docs/design/robotd-design.md#r17-v181-playdead-named-skill)。
