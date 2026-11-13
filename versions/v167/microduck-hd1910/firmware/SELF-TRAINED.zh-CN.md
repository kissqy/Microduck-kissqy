**简体中文** | [English](SELF-TRAINED.en.md)

> 以下为历史版本记录，不能用其中的模型数量代表当前发布。当前 V167 / control.43 的十模型清单、六份源码策略及作者训练来源见 [模型来源表](../docs/MODEL-PROVENANCE.md)；原创归属与商用边界见 [权利说明](../docs/SOFTWARE-MODEL-RIGHTS.md)。

R17 v1.0.137 / 官方0.15.1

运行与安装见 console/README.zh-CN.md 和 packaging/README.zh-CN.md。随包模型：粗糙行走老师14000轮、起坐10000轮、低头捡物5000轮、前滚翻10000轮，以及 LB 倒地起身老师11000轮。自动 Stand 为空；LB 使用官方命名技能 stand_test，原地保持使用 Walk。

本次只更换 LB 模型并适配其无滤波合同；原始合同与权重逐字保留。参数来源与逐模型直通机制见 docs/design/r17-settings-design.md。训练标定作为来源记录保留，安装继续使用本机装配标定。
