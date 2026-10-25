**简体中文** | [English](official-roller-route.en.md) | [Русский](official-roller-route.ru.md)

# 官方滑轮起身路由核对

目标 0.15.1 / 1fa84386。本工程保留的 robotd-params/src/lib.rs 中 Roller 默认 stand=None；robotd/src/main.rs 的 set_standing_disabled 对 Roller 为 true。原始训练导出合同也声明 manual_skill、slot=null、required_skill_settings=null。

公开官方文档（核对日期 2026-10-11，main 内容可能比 0.15.1 更新）：
- https://github.com/pollen-robotics/microduck/blob/main/docs/policy-manifest.md：perpetual 持续型模型没有 duration_s 时要求 --hold，不自动成为定时动作。
- https://github.com/pollen-robotics/microduck/blob/main/duck-control/src/policy.rs：Roller 不按零速度选择 Stand。

当前结论：安装并验证原始起身权重，显示未绑定；不把训练 episode 长度或虚构秒数写成执行窗口，也不覆盖 LB 左踢。
