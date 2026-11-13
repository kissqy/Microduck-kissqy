# V238：B 未分配

当前 GameSir Nova 2 Lite 的 R7 输入桥保留原 Xbox 描述符、轴和其它键，只在 `xbox_key` 中过滤 BTN_EAST 的按下与松开事件。网页端同样忽略 B，界面保留灰色未分配占位。官方 PADD、动作模型和无线驱动保持原程序。

源码基线为 V237 包内 `verification/ui42/native-source/gamepad-r7/gamesir-xboxd.c`。本目录附修改后的完整 C 源码与 `tests/test_b_unmapped.c`。测试编译生产事件处理函数，通过匿名管道验证 B 被过滤，Start/Select/A/X/Y/LB/RB/HOME、摇杆与扳机仍可传递；相同测试对修改前基线失败，对本版通过。

构建工具：Zig 0.13.0。目标与 ABI：AArch64 Linux、glibc 2.17，沿用原 EXEC 类型。

```sh
zig cc -target aarch64-linux-gnu.2.17 -O2 -s gamesir-xboxd.c -o gamesir-xboxd
zig cc -O0 -UNDEBUG -Wall -Wextra tests/test_b_unmapped.c -o test_b_unmapped
./test_b_unmapped
```

该变更覆盖本项目当前的 GameSir R7 实体输入路径及网页输入。新二进制已经打包，实体 B 取消映射需要安装本版随包固件。目标板上的实际按键验收待完成。
