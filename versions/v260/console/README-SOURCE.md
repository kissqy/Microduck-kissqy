# V260 中控源码

配套中控 `1.0.260`、ZERO 固件 `control.102`。本目录只属于独立 V260 线，不替换仓库原 V167。

Python、JavaScript、CSS、启动脚本和验证代码均取自已经交付的 V260 运行包。大型运行资源没有在源码目录重复存放；下载同版本 `Microduck-Console-Studio-V260.zip` 后执行：

```bash
python3 prepare-resources.py /path/to/Microduck-Console-Studio-V260.zip
```

脚本核对整包及每个资源的 SHA256，恢复 3D 资源、随包固件和 IMU 载荷。然后 Windows 运行 `start.cmd`，macOS/Linux 运行 `bash start.command`。

源文件与运行包的对应关系见 `SOURCE-IDENTITY.json`。使用者的 KEY、SSH 密码、个人对话日志不在源码包中。本版本沿用实际交付的功能范围；火烈鸟模型及入口已撤下。

完整软件回归结果见 `verification/v260/`；本次整理没有进行新的实体运动或热点验收。原 V167 的文件、下载地址与 Known-Good 参考均保留。
