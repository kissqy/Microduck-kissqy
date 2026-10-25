**简体中文** | [English](README.en.md) | [Русский](README.ru.md)

# R147 验证记录

`3d-audit147.json` 记录本次范围、数值测试、原文件哈希与验收限制。`r146_*` 是对 R146 原视图的独立对照结果。所有模型方向检查都使用生产 Three.js 与 DuckView，没有连接舵机。

在本中控目录打开终端，安装 Node.js 后可以重复数值检查：

```bash
node verification/test_calibration_reference.mjs
node verification/test_calibration_reference.mjs verification/reference_training_8d0db749.xml
node verification/test_pose_state.mjs
```

第一项使用内置运行模型，第二项使用固定提交 8d0db749 的训练 XML，第三项检查反馈顺序、缺失值、旧目标和 IMU 状态。XML 仅供独立变换计算，不用此目录启动 MuJoCo 仿真。

这三项不启动浏览器、不发送舵机命令。浏览器实际画面和用户真机尚未验收，数值检查不代表已经解决实机翻身。
