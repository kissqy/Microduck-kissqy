# UI45 手柄同入口关机与热点按钮位置

在中控目录运行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest verification.test_shutdown_ui45 verification.test_hotspot_helper_ui44 verification.test_hotspot_service_ui44 verification.test_fixed_speed_ui43 verification.test_input157 verification.test_pad_recorder_status_ui42 verification.test_ai_input_ui41 verification.test_gamepad_repair -v
node verification/test_power_ui45.mjs
node verification/test_hotspot_ui44.mjs
node verification/test_pad_recorder_ui42.mjs
node verification/test_ai_ui40.mjs
node verification/test_gamepad_repair_ui.mjs
node verification/test_center185.mjs
node verification/test_install_progress157.mjs
```

关机测试使用真实AF_UNIX socketpair，将中控请求穿过实际service_rpc，确认只出现一条robot.shutdown {}，没有sudo/OS关机/外部播放声音或额外运动命令。验证拒绝、坏回执、断线不回退不重发，AI租约不能调用关机，重启仍保留系统重启路径。

热点位置与醒目样式、确认取消、手动关机提交及断线状态由前端行为测试覆盖。官方流程源码审查见official-shutdown-audit.json和shutdown-source-excerpts.txt；客户端只接同一个入口，原生服务依自己的当前状态决定音效、卸力与关机过程。

固件tar与UI44逐字节相同，PADD/robotd/mediad/模型/标定不变。本次未连接实体Zero，未执行真实关机、音效或热点切换。完整测试结果见results.json。
