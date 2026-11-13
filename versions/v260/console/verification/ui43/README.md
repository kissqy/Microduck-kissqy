# UI43 固定步行平移速度验证

在中控目录执行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest verification.test_fixed_speed_ui43 verification.test_input157 verification.test_pad_recorder_status_ui42 verification.test_ai_input_ui41 verification.test_gamepad_repair -v
PYTHONDONTWRITEBYTECODE=1 python3 verification/ui43/test_installer_fixed_ui43.py --embedded
node verification/test_pad_recorder_ui42.mjs
node verification/test_ai_ui40.mjs
node verification/test_gamepad_repair_ui.mjs
```

78项Python行为测试与5项实际安装脚本/状态测试通过；三套前端测试通过。安装脚本测试只写临时目录，系统命令使用记录替身，不接触真实机器人。`--embedded`强制使用随包固件，验证旧0.1/0.2/损坏速度文件不会影响新启动配置，并保留上次录制和头嘴幅度。

实体PADD原生前后与侧移默认0.3，网页映射固定0.3；摇杆继续按比例，转向上限1.5。滑轮专用模式、AI显式参数、旧记录中的实际速度沿用原行为。无原生代码重编；所有原生二进制、110个模型/滑轮资源、运动配置与标定保持UI42字节不变。本次未连接实体机器人。

具体范围见scope-check.json，改动见product.patch。旧UI42/41/40证据保持原目录。初次历史测试依赖缺失与版本标题断言记录于harness-notes.json，不计入通过数。
