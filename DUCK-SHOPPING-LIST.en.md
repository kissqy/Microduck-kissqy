[简体中文](DUCK-SHOPPING-LIST.md) | **English** | [Русский](DUCK-SHOPPING-LIST.ru.md)

# 🦆 Microduck shopping guide

[🏠 Project homepage](README.en.md)

**Start here to buy parts for one complete duck.** This guide has three sections: **duck body, PCB boards, and build tools**. Product links, exact variants and costs can be viewed directly on GitHub.

> [!IMPORTANT]
> **🛒 Bought by the author, selected after price comparisons, and tested on the real robot**
>
> The author compared prices when buying the listed products, prioritizing **free shipping and good prices** while meeting the project’s requirements.
>
> The listed products have been used and verified over time; **communication, functions and operating stability meet the project’s requirements**. Choose the exact model and variant shown in each row. Prices below are historical order prices.

| Category | Contents | Entry |
| --- | --- | --- |
| **🦆 Duck body** | Controller, servos, NP-F batteries, camera, ToF, speaker, bearings, screws and wiring | [Body list below](#duck-body) |
| **🔧 PCB** | HAT and IMU complete-board costs; detailed BOMs and fabrication records | [PCB summary below](#pcb) · [Detailed board procurement](hardware/README.en.md#shopping-list) |
| **🧰 Tools** | Solder paste, tweezers, hotplate, soldering stations and debugging tools | [Separate tools list](docs/BUILD-TOOLS.en.md) |

## Total cost

**Configuration: one duck with 15 HD-1910-C001 servos, ZERO 3W, an NP-F550 two-battery/dual-charger kit, camera, ToF and speaker, plus one HAT and one IMU.**

| Item | Free PCB coupons | No PCB coupons |
| --- | ---: | ---: |
| 🦆 Duck body, including reference spare stock | ¥2139.79 | ¥2139.79 |
| 🔧 HAT complete board | ¥16.72 | ¥20.72 |
| 🔧 IMU complete board | ¥12.33 | ¥16.33 |
| **🦆 Whole duck total** | **¥2168.85** | **¥2176.85** |

Totals use unrounded board costs and are then rounded to two decimal places.

**Scope:** the listed hardware and reference spare stock only. **3D printers, printed parts, printing materials, build tools, soldering and cleaning consumables are excluded.** Bearings, wires, screws and connectors use the purchase quantities below, which include spare stock. TF/microSD cards and other items without recorded prices are outside this priced subtotal.

The board lines above allocate component costs by actual use, including their historical shipping share. Without coupons, PCBs cost **¥20 for five boards per design (¥4 per board)**. Buying board components in whole packages for the first time brings the initial product budget to **¥2225.96 with free PCBs**, or **¥2265.96 without coupons**, including one five-board batch of each design. New-order shipping is separate.

## Duck body

**🔌 The original tables on this page describe EH2.5 HAT / IMU boards; Feetech servos use AMP2.0 cables. An AMP2.0 project variant is also available, with AMP2.0 bus sockets, HP1.25 audio sockets, and an added LED plus 1kΩ resistor. See its [separate parts guide](hardware/AMP2.0-VERSION.en.md).** Choose the version for your wiring.

### 🦆 Controller, servos and external modules

| Item / exact variant | Unit | Reference quantity | Historical unit price | Subtotal | Shop / link |
| --- | --- | ---: | ---: | ---: | --- |
| **飞特 HD1910 串口总线舵机**<br>HD-1910-C001；HD-1910-C001 | 只 | 15 | ¥99.00 | ¥1485.00 | 深圳飞特舵机工厂店<br>[Product](https://item.taobao.com/item.htm?id=1078248851201) |
| **Radxa ZERO 3W**<br>2GB RAM 无 eMMC 带排针[【Microduck 原版主板】]；2GB RAM / 无eMMC / 带排针 | 个 | 1 | ¥309.00 | ¥309.00 | 瑞莎计算机(深圳)有限公司<br>[Product](https://item.taobao.com/item.htm?id=763812025816) |
| **NP-F550 电池与双充套装**<br>【NP-F550补光灯专用▲2200mAh】2电+标准双充套裝；沣标 NP-F550 / 2200mAh / 2块电池＋标准双充 | 套 | 1 | ¥84.59 | ¥84.59 | fb数码旗舰店<br>[Product](https://item.taobao.com/item.htm?id=585415365001) |
| **IMX219 160° camera**<br>SKU: **IMX219 160度摄像头** | 个 | 1 | ¥64.35 | ¥64.35 | 树莓派零售商<br>[Product](https://item.taobao.com/item.htm?id=1083291197130&skuId=6300750750661) |
| **8×8 ToF 测距模块**<br>VL53L5X V2模块配盖片；VL53L5X V2模块配盖片（商品标题 VL53L5CX） | 个 | 1 | ¥49.50 | ¥49.50 | 都会明武电子<br>[Product](https://item.taobao.com/item.htm?id=737603917521) |
| **扬声器**<br>3525腔体-4Ω3W/喇叭；3525 腔体 / 4Ω 3W | 个 | 1 | ¥3.08 | ¥3.08 | 深圳市优信电子科技有限公司<br>[Product](https://item.taobao.com/item.htm?id=683920556900) |

### ⚙️ Bearings

| Item / exact variant | Unit | Reference quantity | Historical unit price | Subtotal | Shop / link |
| --- | --- | ---: | ---: | ---: | --- |
| **6700 开式薄壁轴承**<br>6700开式【轴承钢·精品级】10\*15\*3MM；6700开式 / 10×15×3mm / 轴承钢精品级 | 只 | 5 | ¥1.94 | ¥9.70 | 优可吉轴承销售店<br>[Product](https://item.taobao.com/item.htm?id=625390659071) |
| **ET2216 薄壁轴承**<br>ET2216【精品级】16\*22\*4MM[轴承钢]；ET2216 / 16×22×4mm / 轴承钢精品级 | 只 | 12 | ¥2.91 | ¥34.92 | 优可吉轴承销售店<br>[Product](https://item.taobao.com/item.htm?id=733598659967) |

### Optional roller bearings

**The FrankenDuck rollers use 623ZZ bearings (3 mm bore × 10 mm outer diameter × 4 mm width).** This optional roller item is priced separately and excluded from the base duck totals above.

| Product / exact variant | Reference purchase quantity | Order unit price | Goods subtotal | Seller / product |
| --- | ---: | ---: | ---: | --- |
| **623ZZ miniature bearing**<br>Exact order variant: **623 内3外10厚4**; for FrankenDuck rollers | 8 pcs | ¥1.50 | ¥12.00 | EVT进口轴承<br>[Product](https://item.taobao.com/item.htm?id=618009195719) |

From the author's **October 14, 2026** order. This is a reference purchase quantity; assembly quantities depend on the roller setup. Shipping was ¥0.50 and the paid total was ¥12.50. [Matching printing set and plate project](hardware/3d-print-frankenduck/README.en.md).

### 🔩 Screws

| Item / exact variant | Unit | Reference quantity | Historical unit price | Subtotal | Shop / link |
| --- | --- | ---: | ---: | ---: | --- |
| **M2×4 十字盘头平尾自攻螺丝**<br>M2\*4[200只]镀镍；铁镀镍 / 十字圆头 / 平尾自攻 / M2×4 | 包（200个） | 1 | ¥3.03 | ¥3.03 | 固万基官方旗舰店<br>[Product](https://item.taobao.com/item.htm?id=534923831046) |
| **M2×5 十字盘头平尾自攻螺丝**<br>M2\*5[200只]镀镍；铁镀镍 / 十字圆头 / 平尾自攻 / M2×5 | 包（200个） | 1 | ¥0.00 | ¥0.00 | 固万基官方旗舰店<br>[Product](https://item.taobao.com/item.htm?id=534923831046) |
| **M2×6 十字盘头平尾自攻螺丝**<br>M2\*6[200只]镀镍；铁镀镍 / 十字圆头 / 平尾自攻 / M2×6 | 包（200个） | 1 | ¥3.31 | ¥3.31 | 固万基官方旗舰店<br>[Product](https://item.taobao.com/item.htm?id=534923831046) |
| **M2×8 十字盘头平尾自攻螺丝**<br>M2\*8[200只]镀镍；铁镀镍 / 十字圆头 / 平尾自攻 / M2×8 | 包（200个） | 1 | ¥3.59 | ¥3.59 | 固万基官方旗舰店<br>[Product](https://item.taobao.com/item.htm?id=534923831046) |
| **M2×12 十字盘头平尾自攻螺丝**<br>M2\*12[200只]镀镍；铁镀镍 / 十字圆头 / 平尾自攻 / M2×12 | 包（200个） | 1 | ¥3.88 | ¥3.88 | 固万基官方旗舰店<br>[Product](https://item.taobao.com/item.htm?id=534923831046) |
| **M2.6×8 十字盘头平尾自攻螺丝**<br>M2.6\*8[200只]镀镍；铁镀镍 / 十字圆头 / 平尾自攻 / M2.6×8 | 包（200个） | 1 | ¥3.59 | ¥3.59 | 固万基官方旗舰店<br>[Product](https://item.taobao.com/item.htm?id=534923831046) |

### 🔌 Wiring and connectors

| Item / exact variant | Unit | Reference quantity | Historical unit price | Subtotal | Shop / link |
| --- | --- | ---: | ---: | ---: | --- |
| **EH 2P 母壳**<br>EH2.5MM 2P胶壳（50个）；EH 2P，配 HAT J1/J2/J9 | 包（50个） | 1 | ¥2.20 | ¥2.20 | 启色数码旗舰店<br>[Product](https://item.taobao.com/item.htm?id=832569969546) |
| **EH 3P 母壳**<br>EH2.5MM 3P胶壳（50个）；EH 3P，配 HAT J13/J14、IMU J1 | 包（50个） | 1 | ¥2.80 | ¥2.80 | 启色数码旗舰店<br>[Product](https://item.taobao.com/item.htm?id=832569969546) |
| **EH 压接端子**<br>EH2.5MM 端子（100个）；EH2.5MM 端子 | 包（100个） | 1 | ¥3.50 | ¥3.50 | 启色数码旗舰店<br>[Product](https://item.taobao.com/item.htm?id=832569969546) |
| **SH1.0 4P 转杜邦母线**<br>0.2m;1.0-4P转杜邦母（5条）；SH1.0 4P / 20cm / 杜邦母 | 包（5个） | 1 | ¥4.56 | ¥4.56 | 信容芯旗舰店<br>[Product](https://item.taobao.com/item.htm?id=895049863252) |
| **AMP2.0 3P 舵机线 20cm**<br>200mm;1007/24#;3P;AMP2.0；200mm / 1007 / 24AWG / 3P / AMP2.0 | 条 | 30 | ¥0.90 | ¥27.00 | 永茂电子<br>[Product](https://item.taobao.com/item.htm?id=825340808235) |
| **AMP2.0 3P 舵机线 10cm**<br>100mm;1007/24#;3P;AMP2.0；100mm / 1007 / 24AWG / 3P / AMP2.0 | 条 | 30 | ¥0.90 | ¥27.00 | 永茂电子<br>[Product](https://item.taobao.com/item.htm?id=825340808235) |
| **22AWG 三芯硅胶排线**<br>黑色;3芯;22AWG;1m；黑色 / 3芯 / 22AWG / 1m | 米 | 3 | ¥3.5933 | ¥10.78 | 萨牛旗舰店<br>[Product](https://item.taobao.com/item.htm?id=781764816472) |
| **22AWG 单芯硅胶线**<br>22AWG(0.33平方)黑色 2米；黑色 / 22AWG / 0.33mm² / 2m | 个 | 1 | ¥3.42 | ¥3.42 | 渡竹旗舰店<br>[Product](https://item.taobao.com/item.htm?id=736162720327) |
| **彩色热缩管套装**<br>袋装 164片 彩色 【2倍收缩】；164片 / 彩色 / 2倍收缩 | 个 | 1 | ¥0.99 | ¥0.99 | 圣佰路旗舰店<br>[Product](https://item.taobao.com/item.htm?id=945215173380) |

NP-F550 is the original 2200mAh kit with two batteries and a standard dual charger. The M2×5 screws had a historical ¥0 promotional amount; this is not a regular selling price.

<details>
<summary>Reference purchase quantities and assembly notes</summary>

- **飞特 HD1910 串口总线舵机**：作者两次订单分别购入13只和2只，共15只；选择 HD-1910-C001 款式。
- **Radxa ZERO 3W**：已完成订单的主板款式；属于配套主控，不计入 HAT 84 个器件。
- **NP-F550 电池与双充套装**：按“NP-F550补光灯专用▲2200mAh，2电+标准双充套裝”原款式购买。
- **IMX219 160° camera**: buy from **树莓派零售商**, selecting the exact SKU **IMX219 160度摄像头** (SKU ID `6300750750661`). Reference unit price: **¥64.35**, included in the totals above; check the product page at checkout for the final price.
- **8×8 ToF 测距模块**：外接模块，不是 PCB 上的裸芯片；模块接线和供电按已验证方案。
- **扬声器**：订单自带1.25端子；HAT板座是 EH 2P，需改接或转接，不能直接认为插头相同。
- **6700 开式薄壁轴承**：按订单参考采购数量计入，包含备料；尺寸顺序为内径×外径×宽度；两次订单为3只和2只。
- **ET2216 薄壁轴承**：按订单参考采购数量计入，包含备料；尺寸顺序为内径×外径×宽度；两次订单为10只和2只。
- **M2×4 十字盘头平尾自攻螺丝**：每种买1包（200只），包含备料；按打印模型及对应安装位置选择长度；每包数量是备料数量。
- **M2×5 十字盘头平尾自攻螺丝**：每种买1包（200只），包含备料；按打印模型及对应安装位置选择长度；每包数量是备料数量。原订单商品金额为0元（订单优惠），不代表常规售价。
- **M2×6 十字盘头平尾自攻螺丝**：每种买1包（200只），包含备料；按打印模型及对应安装位置选择长度；每包数量是备料数量。
- **M2×8 十字盘头平尾自攻螺丝**：每种买1包（200只），包含备料；按打印模型及对应安装位置选择长度；每包数量是备料数量。
- **M2×12 十字盘头平尾自攻螺丝**：每种买1包（200只），包含备料；按打印模型及对应安装位置选择长度；每包数量是备料数量。
- **M2.6×8 十字盘头平尾自攻螺丝**：每种买1包（200只），包含备料；按打印模型及对应安装位置选择长度；每包数量是备料数量。
- **EH 2P 母壳**：每只母壳配2个EH压接端子；按EH2.5款式购买，与板上的EH接口配套。
- **EH 3P 母壳**：每只母壳还需3个压接端子。
- **EH 压接端子**：与EH母壳成套使用，按EH2.5MM端子款式购买。
- **SH1.0 4P 转杜邦母线**：用于外部接口转接；每根线的脚序按 HAT J5 与模块核对，不按线色猜。
- **AMP2.0 3P 舵机线 20cm**：按订单参考采购数量计入，包含备料；用于飞特舵机线束；10cm和20cm按实际走线位置选择。
- **AMP2.0 3P 舵机线 10cm**：按订单参考采购数量计入，包含备料；与20cm线是不同长度选项，数量按实际线束方案准备。
- **22AWG 三芯硅胶排线**：原订单2米×3.63元＋1米×3.52元，合计3米10.78元；单价按两次订单均价。
- **22AWG 单芯硅胶线**：用于自制接线，按22AWG黑色2米款式购买。
- **彩色热缩管套装**：用于接线处绝缘及整理。

</details>

## PCB

**🔧 HAT and IMU are the PCB branch of the duck build.** Each complete board is counted once in the duck total. Their detailed component and reference-designator lists stay in the original hardware directory.

| Board | Original detailed list | Fabrication record |
| --- | --- | --- |
| **HAT** · HAT-V5 | [84 components](hardware/README.en.md#full-reference-designator-boms) | [HAT](hardware/HAT-TIMELINE.en.md) |
| **IMU** · IMU-TO-DLX-V2 | [25 components](hardware/README.en.md#full-reference-designator-boms) | [IMU](hardware/IMU-TIMELINE.en.md) |

**[🔧 Open PCB procurement and board costs](hardware/README.en.md#shopping-list)**

## Tools

**🧰 Keep build tools and consumables in their own list.** It includes solder paste, tweezers, stencils, hotplate, soldering stations, solder wick, cleaning supplies and programming/debugging tools. Reuse tools you already have; these purchases are outside the duck hardware total.

**[🧰 Open the tools and consumables list](docs/BUILD-TOOLS.en.md)**

[📊 Optional Excel download (Chinese)](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/hardware/Microduck-HAT-IMU-Shopping-List-20261013.xlsx)
