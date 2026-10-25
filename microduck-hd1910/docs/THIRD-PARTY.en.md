[简体中文](THIRD-PARTY.md) | **English** | [Русский](THIRD-PARTY.ru.md)

# Third-party sources and licensing scope

This page is an attribution index. Complete licenses, copyright headers, and NOTICE files remain in the corresponding directories; this guide does not replace them.

| Component | Source / license | Bundled location |
| --- | --- | --- |
| Microduck Rust firmware workspace and upstream code | Pollen Robotics; Apache-2.0 | `firmware/LICENSE`, `firmware/Cargo.toml` |
| Official training engine | Pollen Robotics microduck_rl; software Apache-2.0; downloaded by commit during first preparation | `training-console/NOTICE.md`, `training-console/docs/licenses/microduck_rl-Apache-2.0.txt` |
| HD1910 parameters and corresponding actuator implementation | fanhao 375/microduck-replica; relevant code Apache-2.0 | `training-console/docs/licenses/`, `training/hd1910_m6.json`, `training/hd1910_actuator.py` (last two under training-console) |
| Three.js | Three.js authors; MIT | `firmware/console/licenses/THREE-MIT.txt` |
| ONNX Runtime 1.28.0 | Microsoft and dependency authors; MIT and listed third-party terms | `firmware/packaging/onnxruntime/LICENSE`, `ThirdPartyNotices.txt` |
| PyYAML | Original authors; MIT | `firmware/packaging/_model_yaml/LICENSE` |
| tomli | Taneli Hukkinen; MIT | `training-console/training/_vendor/tomli/LICENSE` |
| ST IMU and ToF drivers | STMicroelectronics; respective headers and bundled BSD terms | `firmware/firmware/imu-source/vendor/lsm6dsv16x/LICENSE`, `firmware/tof/vendor/LICENSE.txt` |
| Official geometry and display meshes | Pollen Robotics and model contributors; upstream README states Creative Commons BY-SA-NC without a version | `firmware/console/licenses/MODEL-NOTICE.md` |
| Official reference ONNX and detection models | Corresponding upstream model licenses; personal terms do not apply | `firmware/verification/official-reference/`, `firmware/pet-detect/` |
| The author's current five self-trained policies | Personal terms apply only to weights and records the author can license; upstream rights remain | `firmware/policies/`, `firmware/BUILD.json` |

Upstream firmware remains under Apache-2.0, including its existing grants. Third-party code, models, and geometry cannot all be relabeled “personal use only.” The root LICENSE defines personal noncommercial scope for the author's consoles and new publication materials.

The official geometry declaration does not specify a license version. This package preserves attribution, noncommercial, and share-alike requirements without inventing a 4.0 version or converting geometry to a software license.

Compiled firmware ZIPs use the same component licenses: Apache firmware programs, separately licensed libraries / assets, and the author's licensable self-trained models. Attached personal terms do not change the Apache programs' license.

## Upstream links

- [Microduck](https://github.com/pollen-robotics/microduck)
- [microduck_rl](https://github.com/pollen-robotics/microduck_rl)
- [microduck-replica](https://github.com/fanhao375/microduck-replica)
- [Apache-2.0 original text](https://www.apache.org/licenses/LICENSE-2.0)
- [OSI definition](https://opensource.org/osd)

Microduck, Pollen Robotics, and third-party trademarks remain with their respective owners. This project does not imply official endorsement.
