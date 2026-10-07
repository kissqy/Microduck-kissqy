R17 v1.0.137 / 官方0.15.1

在 v1.0.136 基础上，本次新增官方源码差异：
- duck-control/src/deployment.rs：接受粗糙地面合同明确关闭滤波的形式；要求头腿alpha为1。记录本模型直通标志，不更改全局参数。
- robotd/src/control.rs：当前模型明确要求直通时跳过原低通处理，退出模型后恢复原参数；提供当前实际滤波回读。
- robotd/src/main.rs：bus 增加 active_target_filters 回读，其他控制及遥测路径保持。
- robotd/src/feetech_commissioning.rs：编译标识更新为 control.21。

LB 使用既有官方命名技能接口，路径改为本次11000轮倒地老师，基础系数1.0。Python导入器同步接受相同合同；中控显示当前模型实际滤波，未增加滤波开关。原模型合同和 ONNX 不修改。

原有官方技能调度、UART/HAT、标定单位转换、HOME取消、声音、真实手柄输入桥均沿用v136。全局滤波算法与配置不更改；官方电压补偿仍参与实际倍率。本次仅重编译robotd，其余二进制沿用v136。已有R17改动与临时舵机测试机制见 R17-CHANGES.zh-CN.md、docs/design/r17-settings-design.md；完整文件差异见 R17-SOURCE-MANIFEST.json。
