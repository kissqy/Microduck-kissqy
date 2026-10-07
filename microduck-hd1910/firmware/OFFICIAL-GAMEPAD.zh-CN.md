R17 v1.0.97 / 官方 0.15.1 手柄

R7 GameSir Xbox 输入桥二进制与映射沿用 R17。官方 padd 原样编译。
网页是标准 Xbox evdev 输入，不是自写 robot.move 或自动保持/启停序列。

Start：首次 HOME；之后切换官方策略开关，关闭返回 HOME。
Select：短按松开卸力；按住 2 秒执行官方坐下/关机流程。
左摇杆 / 右摇杆：按官方模式与 [pad] 参数解释速度、转向、头部或身体姿态。
Y：头部模式；B：身体模式；LT / RT：官方叫声与嘴动作。
方向键下：原 10000 轮坐下/站起。
没有配套模型的技能按钮在网页灰显；[pad] 中 A、X、LB、RB 解绑。

真实手柄出现时，后台销毁网页 evdev 设备并丢弃待发帧；网页输入超时 600ms 也销毁设备。
首次网页按键等待只读 pad.input 报告接入，防止官方 500ms 手柄发现周期漏掉 Start。
接管不合成 Select 松开，也不另写 robot.stop/robot.enable；断开和释放后的行为仍由官方 padd 处理。
完整键值与轴描述见 packaging/webpad.py 和原 gamepad-r7/gamesir-xboxd.c。
