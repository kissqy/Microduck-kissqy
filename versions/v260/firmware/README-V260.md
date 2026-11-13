# V260 / control.102 固件源码

这是独立 V260 线的 ZERO Linux 服务源码，基于官方 0.15.1。不是 STM32 IMU 固件，也不替换原 V167/control.43 源码。

原生工作区从冻结 V186 源码恢复，应用已验证的 AI IPC 补丁；手柄代码取自 V229 当前二进制对应的快照，摄像头曝光代码取自已验证 UI40 快照。核心源文件按原构建记录 SHA256 逐项核对。唯一部署版本常量同步为 control.102。

GameSir 桥接源码按已保存补丁恢复，B 键未分配。使用 Zig 0.13.0 重新交叉编译后，与 V260 已交付桥接程序逐字节一致，见 `BRIDGE-REBUILD.json`。其源码排版与历史摘要不同，未冒充原始源码字节一致。

`packaging/` 保存 V260 的安装、迁移、配网和模型管理源码，以及当前模型配置和说明。编译好的程序、动态库及模型权重通过配套固件资源恢复，源码目录不内嵌旧完整包或训练检查点。

## 准备和编译

下载同版本 `Microduck-Firmware-V260-control102.zip`：

```bash
python3 prepare-resources.py /path/to/Microduck-Firmware-V260-control102.zip
```

按 `CONTRIBUTING.md` 安装 Rust 1.99.0、原系统库；交叉编译使用 cargo-zigbuild 0.23.4 和 Zig 0.14.1，目标 `aarch64-unknown-linux-gnu.2.31`。摄像头构建还需要原 `scripts/cross-sysroot.sh` 所述 GStreamer 开发库与交叉环境。

```bash
bash BUILD-V260.sh /path/to/Microduck-Firmware-V260-control102.zip
```

构建产物写入 `target/`，不会安装到机器人或覆盖正式发布包。修改功能后应另增版本，不能覆盖同名 V260 归档。运行包沿用已交付 V260 的原字节；不声称本次完成了所有 Rust/ARM64 重编译。

## 验证边界

V260 的 109 项 Python 和 5 组前端回归结果随中控源码保存。本次另核对源码来源、资源恢复及桥接程序重编译一致性。工作区还保留上游/历史测试，部分旧动作测试依赖旧配置；不能将历史测试记录当成本次全工作区测试通过。没有执行本轮实体运动或热点验收。

Known-Good 保留此前实机参考。下一步唯一主任务是参考卡上的 V260 功能验收；原 V167 主线保持原样。
