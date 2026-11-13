# 中控与固件源码清理审计 · 2026-11-12

范围为公开仓库的 R17 V167 / control.43，清理基于提交 `c1a53b2c28ecbb6f890296fb668156987871ba76`。这是源码维护修订 1，不是新的中控或固件安装包。私有 V257 / control.99 不在本次范围内。

## 清理结果

| 项目 | 处理与依据 |
| --- | --- |
| 41 个旧版工具，300,699 字节 | 移除 V146–V163 一次性构建、打包、恢复、运行和验包工具。当前构建入口、代码与工作流没有组外调用；旧复现说明改为指向清理前 Git 版本。 |
| 59 份重复模型资料，3,879,136 字节 | 与 `policies/` 的指定文件字节完全相同，改由现有 `prepare-V167.py` 按 `SOURCE-LAYOUT.json` 恢复，逐项校验 SHA256、长度与文件模式。不能整目录删除：同一模型中的其他合同文件并不一定相同。 |
| 1 个未接入编译的试验模块，3,823 字节 | 删除 `duck-control/src/hd1910_test.rs`。Cargo target、Rust `mod` / `path` / `include` 均未引用，且不在 V164 native 快照中。 |
| 重复依赖声明 | 删除一个重复 workspace default-member、`duck-control` 一个重复测试依赖、`updater` 八个与普通依赖完全相同的测试依赖；保留额外特性不同的测试依赖。 |
| 中控未使用代码 | 删除未使用的导入、`displayRootQuaternion` 转发别名，以及未使用的 `modeBuilds` / `managementBuilds` 导出；同步生成器，避免下次生成时重新引入。 |

共从受控源码树移除 101 个文件、4,183,658 字节，约 3.99 MiB。59 份资料仍会在构建/测试准备时生成。这不是已发布运行包的体积变化，也不清除 Git 历史。

精确文件清单、原 SHA256 和恢复映射见 [机器可读记录](../firmware/verification/source-cleanup-20261112.json)。

## 保留范围

- 已发布 V167 中控 ZIP、control.43 固件载荷与固定 V164 构建基线；其版本与原始字节不变。
- 生产 Rust 源码、模型权重、标定、运动参数、安全保护与手柄逻辑。
- 四个仍被当前测试引用的 `test-data` 模型目录；不按 `legacy` 或旧版本文件名判断是否无用。
- V167 原始编译/模型验证记录、官方来源快照与许可证。
- GitHub Pages 独立演示所需资源，以及有运行引用的 JS / CSS / 3D 资源。

## 验证

- 固定固件载荷与 V164 ZIP 的 SHA256 通过。
- `prepare-V167.py` 恢复 91 个资源；新增 59 个资料副本与清理前的长度、SHA256、0644 模式完全一致，且全部来源仍受 Git 管理。
- V164 native 快照比较通过；仅对三份 Cargo 清单中的精确重复声明归一化，其余文件仍按字节比较。负向检查确认生产 Rust、版本或其他依赖改动仍被拒绝。
- V167 指定的模型执行合同与原子安装测试：18/18 通过。
- 当前控制 socket、原始遥测、采集转发、版本兼容测试：39/39 通过。
- 中控 Python 验证：141/141 通过。
- 前端验证：10/11 个脚本通过；姿态状态脚本包含 6 个通过的检查。
- 启动中控 dashboard 服务，配置、HTML、JS 与 snapshot HTTP 端点返回正常，并正常退出。没有连接或操作机器人。
- `service-builds.js` 与修改后的生成器输出一致；Python 编译和差异空白检查通过。

环境没有 Rust / Cargo，因此没有重新编译 Rust、执行 Rust 测试、ARM64/QEMU 模型推理或实机验证。`verification/v167/` 内的历史 Rust / ARM64 记录保留原文，不冒充本次结果。

## 原有测试问题

以下问题在清理前即已存在，本次未删除测试或修改断言以隐藏失败：

- 旧输入测试组 22 项中有 10 个错误、1 个失败：测试仍修改已移除的 `controls.open_remote_socket` 或旧 `peer/reader` 字段，未使用现行 InputChannel。
- 较宽的 57 项组合测试原有 2 个失败：BallKickLeft descriptor 不匹配，以及 `refresh_after_service` 的旧测试替身。
- `console/verification/test_controls154.mjs:54` 对未修改的 HTML 使用 `LB.*起身` 宽泛正则，命中了后续踢球/滑轮文字。

## 构建边界与 Known-Good

现有 `package-V167.py` 从固定 V164 ZIP 复现 V167 发布，只覆盖其定义的文件。它不会自动将所有当前中控源码改动打入 ZIP，因此本次不运行它生成同版本新包，不改变下载区，也不将源码清理声称为新的固件发布。

Known-Good 公开运行参考仍为官方 0.15.1 + R17 V167 / control.43 + Training R1.5.27，系统镜像仍为 Public Image R1。

下一步唯一主任务：在既有 Linux / WSL 构建环境完成清理后源码的 Rust 与 ARM64 构建验收，再决定是否按新版本发布中控和配套固件。
