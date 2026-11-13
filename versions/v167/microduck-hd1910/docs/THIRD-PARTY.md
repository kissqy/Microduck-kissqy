**简体中文** | [English](THIRD-PARTY.en.md)

# 第三方来源与授权范围

本页是归属索引；完整许可、版权头和 NOTICE 保留在对应目录。它不替代原许可证。作者原创软件与自训模型的具体范围、使用方式和来源核验见 [软件与自训模型权利说明](SOFTWARE-MODEL-RIGHTS.md)。

## 软件、依赖与素材

| 内容 | 来源 / 许可 | 仓库位置 |
| --- | --- | --- |
| Microduck 固件 Rust 工作区及上游代码 | Pollen Robotics；Apache-2.0。当前飞特适配所在工作区保留此许可，不因网页或模型采用个人条款而改变 | `firmware/LICENSE`、`firmware/Cargo.toml` |
| 官方训练引擎 | Pollen Robotics microduck_rl；软件 Apache-2.0；首次准备环境时按固定提交下载，不包含在训练中控源码包内 | `training-console/NOTICE.md`、`training-console/docs/licenses/microduck_rl-Apache-2.0.txt` |
| HD1910 参数与相应执行器实现 | fanhao375/microduck-replica；相关训练代码、配置和参数 Apache-2.0；不归本项目独占 | `training-console/docs/licenses/`、`training-console/training/hd1910_m6.json`、`training-console/training/hd1910_actuator.py` |
| Three.js 与 OrbitControls | Three.js authors；MIT。网页演示、装配页和机器人中控中的复制件保留相同来源与许可；OrbitControls 的本地模块路径适配不改变许可 | `firmware/console/static/vendor/`、`firmware/console/licenses/THREE-MIT.txt`；仓库根目录 `docs/vendor/` 的网页副本 |
| ONNX Runtime 1.28.0 | Microsoft 与依赖作者；MIT 及列出的第三方条款 | `firmware/packaging/onnxruntime/LICENSE`、同目录 `ThirdPartyNotices.txt` |
| PyYAML | 原作者；MIT | `firmware/packaging/_model_yaml/LICENSE` |
| tomli | Taneli Hukkinen；MIT | `training-console/training/_vendor/tomli/LICENSE` |
| ST IMU 与 ToF 驱动 | STMicroelectronics；依各版权头及随包 BSD 许可 | `firmware/firmware/imu-source/vendor/lsm6dsv16x/LICENSE`、`firmware/tof/vendor/LICENSE.txt` |
| 官方几何与显示网格 | Pollen Robotics 与模型贡献者；几何许可与软件许可分开，历史快照和当前上游声明分别核对 | `firmware/console/licenses/MODEL-NOTICE.md`、`firmware/console/static/assets/duck-visual.json` 及根目录 `docs/assets/` 的相应来源记录 |
| 官方参考 ONNX 与检测模型 | 对应上游模型许可；不是本项目作者自训权重，不适用作者个人非商业条款 | `firmware/verification/official-reference/`、`firmware/pet-detect/`；具体文件按来源记录确认 |

Rust crates、Python 包及训练环境中的其他依赖，仍按各自固定版本的许可证处理。以上是仓库已记录的主要来源，不宣称是全部传递依赖的完整 SBOM。部分依赖在安装、构建或首次训练环境准备时下载，不能因未直接保存在本仓库就忽略其分发要求。

## 自训权重、训练软件与三维模型是三类内容

作者针对飞特 HD1910 组织训练、调参、筛选和验证所得的策略，应按具体权重、检查点、训练记录及其来源单独判断。使用官方训练引擎或官方动作任务，不等于使用官方成品权重；反过来，文件位于本项目或改成了新文件名，也不能证明从零自训或获得全部权利。

本项目仅对作者实际拥有、能够单独许可且未受既有许可约束的原创贡献主张相应权利。自训成果的许可范围及已确认/待确认的来源，见 [软件与自训模型权利说明](SOFTWARE-MODEL-RIGHTS.md)。上游代码、执行器参数、任务实现、几何、教师或初始检查点等权利仍各自保留。训练投入本身也不等于每一份权重当然取得著作权。

`firmware/policies/` 中的现有许可不能仅凭目录关系自动覆盖所有 `firmware/packaging/models/`、`firmware/packaging/roller/`、测试样本或官方参考文件。`firmware/packaging/LICENSE` 的 Apache 声明同样不能用来把所有随包权重和几何一概视为 Apache 软件。具体文件应结合权重哈希、原始许可、来源及既有有效授权确认。

## 官方几何：区分历史快照与当前上游声明

显示网格来自记录在 `MODEL-NOTICE.md` 和资产来源文件中的冻结官方提交。原有快照引用的 README 写作 Creative Commons BY-SA-NC，未明确版本；这些历史归属记录保留，不在没有来源依据时追溯改写。

当前官方 microduck_rl 的 [LICENSE-MODELS.md](https://github.com/pollen-robotics/microduck_rl/blob/develop/LICENSE-MODELS.md) 明确将其指定目录中的 STL 以 **CC BY-NC-SA 4.0** 发布；具体范围按该文件列明的路径与对应版本确认。这不表示所有历史模型、社区改件、本仓库全部三维文件或训练权重都统一适用该许可，也不将几何改成软件的 Apache-2.0 许可。

## 源码、运行包和镜像中的许可

上游固件保留 Apache-2.0 授予的权利。作者原创中控、工具和资料的适用范围见 [分项许可](../LICENSE)；不得用个人条款取消他人已经享有的 Apache、MIT 或其他有效授权。

编译后的中控 ZIP、固件载荷及系统镜像是多种内容的组合：程序、运行库、模型、三维资源及系统软件分别遵循对应许可。随包个人条款不改变 Apache 程序的许可，仓库新增说明也不自动改写既有归档内的许可证、哈希或此前有效授予的权利。重新分发时应保留适用许可证、版权声明、NOTICE 和修改说明，并履行所含组件的其他要求。

FT6 IMU 源码及成品二进制也应结合 `firmware/firmware/imu-source/` 的实际来源、父目录许可和 ST 驱动许可分别处理；HAT/IMU 电路设计资料的个人非商业说明不会自动改变其中软件的既有许可。

## 上游链接

- [Microduck](https://github.com/pollen-robotics/microduck)
- [microduck_rl](https://github.com/pollen-robotics/microduck_rl)
- [microduck-replica](https://github.com/fanhao375/microduck-replica)
- [Apache-2.0 原文](https://www.apache.org/licenses/LICENSE-2.0)
- [OSI 定义](https://opensource.org/osd)

Microduck、Pollen Robotics 及第三方商标仍属于其相应权利人；本项目不表示官方背书。
