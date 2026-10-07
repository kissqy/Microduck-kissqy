# 第三方来源与授权范围

本页是归属索引；完整许可、版权头和 NOTICE 保留在对应目录。它不替代原许可证。

| 内容 | 来源 / 许可 | 随包位置 |
| --- | --- | --- |
| Microduck 固件 Rust 工作区及上游代码 | Pollen Robotics；Apache-2.0 | `firmware/LICENSE`、`firmware/Cargo.toml` |
| 官方训练引擎 | Pollen Robotics microduck_rl；软件 Apache-2.0；首次准备时按提交下载 | `training-console/NOTICE.md`、`training-console/docs/licenses/microduck_rl-Apache-2.0.txt` |
| HD1910 参数与相应执行器实现 | fanhao375/microduck-replica；相关代码 Apache-2.0 | `training-console/docs/licenses/`、`training/hd1910_m6.json`、`training/hd1910_actuator.py`（后两者在 training-console 下） |
| Three.js | Three.js authors；MIT | `firmware/console/licenses/THREE-MIT.txt` |
| ONNX Runtime 1.28.0 | Microsoft 与依赖作者；MIT 及列出的第三方条款 | `firmware/packaging/onnxruntime/LICENSE`、`ThirdPartyNotices.txt` |
| PyYAML | 原作者；MIT | `firmware/packaging/_model_yaml/LICENSE` |
| tomli | Taneli Hukkinen；MIT | `training-console/training/_vendor/tomli/LICENSE` |
| ST IMU 与 ToF 驱动 | STMicroelectronics；依各版权头及随包 BSD 许可 | `firmware/firmware/imu-source/vendor/lsm6dsv16x/LICENSE`、`firmware/tof/vendor/LICENSE.txt` |
| 官方几何与显示网格 | Pollen Robotics 与模型贡献者；上游 README 声明 Creative Commons BY-SA-NC，未明确版本 | `firmware/console/licenses/MODEL-NOTICE.md` |
| 官方参考 ONNX 与检测模型 | 对应上游模型许可；不适用个人条款 | `firmware/verification/official-reference/`、`firmware/pet-detect/` |
| 作者自训的当前五个策略 | 仅作者有权授权的权重与记录适用个人条款；不覆盖上游权利 | `firmware/policies/`、`firmware/BUILD.json` |

上游固件继续遵守 Apache-2.0，包括其原本授予的使用权。不能把第三方代码、模型或几何整体改写成“只限个人”。作者自有中控和新增发布资料的个人非商业授权范围由根目录 LICENSE 列明。

官方几何声明中的许可版本不明确，本包沿用原有归属、非商业及相同方式共享说明，不擅自补写 4.0，也不把几何资产改成软件许可证。

编译后的固件 ZIP 内为同一套分项许可：Apache 固件程序、各自许可的运行库和资源、作者可授权的自训练模型。附带个人条款不改变 Apache 程序的许可。

## 上游链接

- [Microduck](https://github.com/pollen-robotics/microduck)
- [microduck_rl](https://github.com/pollen-robotics/microduck_rl)
- [microduck-replica](https://github.com/fanhao375/microduck-replica)
- [Apache-2.0 原文](https://www.apache.org/licenses/LICENSE-2.0)
- [OSI 定义](https://opensource.org/osd)

Microduck、Pollen Robotics 及第三方商标仍属于其相应权利人；本项目不表示官方背书。
