[Русский](armbian-boot-config.ru.md)

# 修复 Armbian 启动配置的重复写入

`scripts/repair-armbian-env.py` 是独立维护工具，用于修补已确认的 Armbian 26.2.1
硬件优化脚本。无需升级系统或重新安装机器人固件，不会运行硬件优化服务、重启系统、
重启机器人服务或发送运动命令。补丁在下次正常开机时使用。

这是源码提供的可选修复，已发布的 V167 下载包没有因此改变，安装旧发布包也不会自动获得它。

## 问题与范围

旧版 `add_usb_storage_quirks()` 每次开机先用多次 `sed -i` 整理
`/boot/armbianEnv.txt`，再删除并追加 `usbstoragequirks=`，最后后台 `sync &`。
即使没有 USB 存储设备、参数完全不变，也会重写整个启动配置。

在一次 Radxa ZERO 3W / Armbian 26.2.1 故障中，U-Boot 看到该文件为 0 字节，
随后使用错误的默认设备树路径而无法启动。手动启动 Linux 后，文件系统回放日志，
配置恢复完整。这与未完成的文件系统事务一致，但不足以证明具体哪次写入或供电事件是唯一原因。
Armbian 上游也已针对该写入流程加入保护，参见
[硬件优化脚本](https://github.com/armbian/build/blob/main/packages/bsp/common/usr/lib/armbian/armbian-hardware-optimization)。

此工具只识别已确认的旧 USB 函数以及本工具的补丁；其他系统版本、已由上游修改或用户定制的
函数会明确报错并保持原样。它不通过覆盖整个系统脚本来猜测兼容性。

## 使用

将源码中的 `microduck-hd1910/firmware/scripts/repair-armbian-env.py` 复制到板子，
例如 `/tmp/repair-armbian-env.py`。只需这一个文件；依赖系统已有的 Python 3.9+、
Bash、GNU coreutils。USB 枚举仍使用原系统脚本依赖的 `lsusb`。

先只读检查：

```bash
python3 /tmp/repair-armbian-env.py --check
```

- `needs-fix`：匹配已确认的旧写法，可执行下面的修复。
- `already-fixed`：已安装同样的补丁，无须重复修改。
- `not-applicable`：没有 Armbian 硬件优化脚本。
- 未识别的函数或调用方式：返回非零退出码，需核对系统脚本，勿强行替换。

修复：

```bash
sudo python3 /tmp/repair-armbian-env.py --apply
```

工具先检查 Bash 语法，把原脚本、当前启动配置及哈希记录保存并同步到
`/var/backups/microduck-armbian-env/<时间与随机后缀>/`，然后原子替换硬件优化脚本。
输出 JSON 中的 `backup` 是本次备份目录。启动配置本身不会被修改，原属主和权限会保留。
空启动配置必须先恢复，工具不会把空文件当作有效配置继续修补。

修复后，USB 参数先在 `/tmp` 计算；内容相同不触碰启动配置，变化时才在 `/boot`
创建临时文件、完整写入、同步、原子替换并同步文件系统。函数以前台方式执行，
同步未完成或发生错误时，服务不会提前报告成功。其他硬件优化函数保持原样。

安装本工具不会增加 systemd drop-in；已有的后置同步补丁可以保留。
这不是禁止断电的绝对保证，也不能修复介质或供电硬件故障。

## 回退

把下面示例目录替换成修复输出的 `backup` 路径：

```bash
sudo python3 /tmp/repair-armbian-env.py --restore /var/backups/microduck-armbian-env/<备份目录>
```

回退只恢复原硬件优化脚本，不恢复旧启动配置。工具验证备份哈希，并在系统脚本已被后续
软件包或用户修改时拒绝覆盖。软件包升级可能替换局部补丁；升级后重新执行 `--check`
并核对上游脚本即可，不要自动覆盖未知的新版本。

## 验证

在 `microduck-hd1910/firmware` 目录执行：

```bash
python3 -m unittest discover -s scripts/tests -p test_repair_armbian_env.py -v
```

Linux 运行全部测试；macOS 跳过依赖 GNU coreutils 的启动函数测试。可在仓库根目录使用
已有的 Linux Python 镜像隔离执行，无需连接机器人：

```bash
docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$PWD:/src:ro" -w /src/microduck-hd1910/firmware \
  python:3.12-slim-bookworm \
  python3 -m unittest discover -s scripts/tests -p test_repair_armbian_env.py -v
```

测试覆盖旧脚本的重复写入、补丁幂等性、USB 规则与其他启动字段保留、属主与权限、
部分写入/同步/替换失败、未知函数拒绝覆盖、备份及受保护的回退。使用的配置、USB 枚举和
内核参数文件均为临时副本；未做物理断电或补丁后的完整启动验证。

USB 函数及其测试摘录保留 Armbian 的 GPL-2.0-only 许可，见
[`scripts/licenses/GPL-2.0.txt`](../../scripts/licenses/GPL-2.0.txt)。
