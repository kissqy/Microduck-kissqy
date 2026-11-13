# UI44 R5 热点入口验证

在中控目录执行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest verification.test_hotspot_helper_ui44 verification.test_hotspot_service_ui44 verification.test_fixed_speed_ui43 verification.test_input157 verification.test_pad_recorder_status_ui42 verification.test_ai_input_ui41 verification.test_gamepad_repair -v
node verification/test_hotspot_ui44.mjs
node verification/test_pad_recorder_ui42.mjs
node verification/test_ai_ui40.mjs
node verification/test_gamepad_repair_ui.mjs
node verification/test_center185.mjs
node verification/test_install_progress157.mjs
```

93项Python测试与6套前端验证通过。新增15项Python测试覆盖原脚本压缩校验、R5组件/依赖/账户预检、真实Bash worker使用临时网络命令替身、清理范围、5秒后台调度、并发重复请求、确认/密码/队列回执和暂停旧连接。

实际Bash测试只操作临时文件；nmcli/systemctl/chown均为临时命令替身。为避免查看测试机真实网络配置，执行worker时仅将legacy检测函数替换为空，其余R5清理函数保持原字节；另有独立legacy存在时拒绝的预检测试。没有执行真实网络切换或实体机器人动作。

确认弹窗/取消、无IMU但已认证SSH、断线提示、结果未知、不自动重试、连接恢复后再次人工提交、旧job竞争由前端行为测试覆盖。原R5配网页要求设置radxa登录密码，按钮提示保留此语义；不调用seal、不改SSH密钥/机器ID、不关机。

原固件tar与UI43逐字节相同，保持203个payload文件、原生程序、模型与标定。本次无需重新编译原生代码。具体范围见scope-check.json，改动见product.patch。
