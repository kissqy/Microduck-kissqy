[简体中文](DUCK-SHOPPING-LIST.md) | **English**

# 🦆 Microduck shopping guide

> [!WARNING]
> **Hardware compatibility and commercial authorization**
>
> **HAT, IMU and HUB versions outside the designs published in this repository are incompatible with this repository’s system and may prevent it from operating normally.**
>
> **This repository has not authorized any commercial organization.** If you find pirated copies, impersonation or unauthorized commercial use, please contact the author. Sharing this work takes effort; please do not misappropriate it.
>
> **Scam warning: Do not trust private sales messages from anyone other than the group owner. Group members have already been scammed.**
>
> [Contact the author](https://github.com/kissqy/Microduck-kissqy/blob/main/docs/assets/purchase-wechat-qr.jpg) · [License scope](https://github.com/kissqy/Microduck-kissqy/blob/main/LICENSE). The repository’s existing licenses determine the scope of this notice.

[🏠 Project homepage](README.en.md)

**Assembled-board reference subtotal: CNY 2823.80**, including the 32GB microSD card and card reader, before printing. The complete FrankenDuck printing service is listed at CNY 199, making the assembled-board plus printing reference subtotal **CNY 3022.80**. Unpriced HUB / battery-connection parts and shipping are extra.

**[Open the shopping checklist (Chinese) →](https://kissqy.github.io/Microduck-kissqy/build/shopping.html)** · [Compare budget totals (Chinese)](https://kissqy.github.io/Microduck-kissqy/build/budget.html)

The online pages show totals first, then specifications, quantities and purchase links. The tables below use the author's purchase references, filtered for the default assembled-board route. Normal use uses the released models and Robot Console.

**The assembled IMU is preflashed with FT6 and needs no initial flashing; calibrate it for your robot after installation.** The author's assembled HAT / IMU boards are SMT assembled by JLCPCB and validated through extended real-robot use. See the [board guide](hardware/README.en.md) for original-design noncommercial use and commercial-permission terms.

## Total cost comparison

| Item | Buy assembled boards | DIY boards, including tools |
| --- | ---: | ---: |
| Duck body, including gamepad and reference spare stock | ¥2605.80 | ¥2605.80 |
| HAT + IMU | [HAT ¥119 + IMU ¥99](https://item.taobao.com/item.htm?id=1095121548583) | ¥94.22–134.22 · first component purchase |
| Soldering / programming tools and consumables | No board-soldering tools; assembled IMU has FT6 preflashed | ¥800–1000 |
| **Total without a printer** | **¥2823.80** | **¥3500.02–3740.02** |
| 3D printer allowance | +¥3500 | +¥3500 |
| **Total including a printer** | **¥6323.80** | **¥7000.02–7240.02** |

**For the FrankenDuck printing service, add CNY 199: assembled boards CNY 3022.80; DIY boards with existing tools CNY 2899.02–2939.02; DIY boards with new tools CNY 3699.02–3939.02.** No printer purchase is needed. [Edition features and printing instructions](hardware/3d-print-frankenduck/README.en.md).

- **The base table excludes printed parts or filament; the printing-service subtotals include CNY 199. Robot-assembly labor, a computer, unpriced HUB / battery-connection parts, new-order shipping and losses are extra.** The body includes 15 HD1910 servos at ¥119 each; the microSD card and card reader are priced and included.
- The HUB includes the main-power buffer capacitor. Do not buy or budget for a separate capacitor.
- DIY board materials use full component packs; the range covers free PCB coupons / no coupons. [Board cost breakdown](hardware/README.en.md#build-cost) · [Tool budget](docs/BUILD-TOOLS.en.md#budgeting-for-tools-from-scratch). Reuse existing tools; the assembled-board option assumes you have normal assembly hand tools.

The author supplied reference prices for the EAGET 32GB monitoring / dashcam microSD card (CNY 39.90) and one SAMZHE dual-head high-speed card reader, supporting simultaneous SD / TF card reading (CNY 22.90). Both are included in the body and whole-duck subtotals; 32GB is sufficient, and an existing card reader may be reused.

## Duck body

**Choose ready-made cables matching the assembled HAT / IMU connectors. Feetech HD1910 servos use AMP2.0 3P double-ended cables with reversed connector orientation (双头反向), at CNY 1.50 each; select matching ready-made adapter cables for peripheral modules.** See the [board connector guide](hardware/AMP2.0-VERSION.en.md) for details.

### 🦆 Controller, servos and external modules

| Item / exact variant | Unit | Reference quantity | Historical unit price | Subtotal | Shop / link |
| --- | --- | ---: | ---: | ---: | --- |
| **飞特 HD1910 串口总线舵机**<br>HD-1910-C001；HD-1910-C001 | 只 | 15 | ¥119.00 | ¥1785.00 | 深圳飞特舵机工厂店<br>[Product](https://item.taobao.com/item.htm?id=1078248851201) |
| **Radxa ZERO 3W**<br>2GB RAM 无 eMMC 带排针[【Microduck 原版主板】]；2GB RAM / 无eMMC / 带排针 | 个 | 1 | ¥309.00 | ¥309.00 | 瑞莎计算机(深圳)有限公司<br>[Product](https://item.taobao.com/item.htm?id=763812025816) |
| **EAGET 32GB microSD / TF card**<br>Monitoring / dashcam variant; 32GB is sufficient; reference price supplied by the author | card | 1 | ¥39.90 | ¥39.90 | JD.com<br>[Product](https://3.cn/392wR-H7?jkl=@D1sNrEalQdG@) |
| **SAMZHE dual-head high-speed card reader**<br>Simultaneous SD / TF card reading; reference price supplied by the author; reuse one you already have | unit | 1 | ¥22.90 | ¥22.90 | JD.com<br>[Product](https://3.cn/393kj-8k?jkl=@I2cIJ7xKJzv@) |
| **NP-F550 电池与双充套装**<br>【NP-F550补光灯专用▲2200mAh】2电+标准双充套裝；沣标 NP-F550 / 2200mAh / 2块电池＋标准双充 | 套 | 1 | ¥84.59 | ¥84.59 | fb数码旗舰店<br>[Product](https://item.taobao.com/item.htm?id=585415365001) |
| **IMX219 160° camera**<br>SKU: **IMX219 160度摄像头** | 个 | 1 | ¥64.35 | ¥64.35 | 树莓派零售商<br>[Product](https://item.taobao.com/item.htm?id=1083291197130&skuId=6300750750661) |
| **8×8 ToF 测距模块**<br>VL53L5X V2模块配盖片；VL53L5X V2模块配盖片（商品标题 VL53L5CX） | 个 | 1 | ¥49.50 | ¥49.50 | 都会明武电子<br>[Product](https://item.taobao.com/item.htm?id=737603917521) |
| **扬声器**<br>3525腔体-4Ω3W/喇叭；3525 腔体 / 4Ω 3W | 个 | 1 | ¥3.08 | ¥3.08 | 深圳市优信电子科技有限公司<br>[Product](https://item.taobao.com/item.htm?id=683920556900) |
| **GameSir 启明星2 wireless gamepad**<br>盖世小鸡启明星2；Bluetooth / Xbox mode | 个 | 1 | ¥89.91 | ¥89.91 | Taobao<br>[Product](https://e.tb.cn/h.j3ZcczhbdezbYBk?tk=1u6dTxTGFkS) |

### ⚙️ Bearings

| Item / exact variant | Unit | Reference quantity | Historical unit price | Subtotal | Shop / link |
| --- | --- | ---: | ---: | ---: | --- |
| **6700 开式薄壁轴承**<br>6700开式【轴承钢·精品级】10\*15\*3MM；6700开式 / 10×15×3mm / 轴承钢精品级 | 只 | 5 | ¥1.94 | ¥9.70 | 优可吉轴承销售店<br>[Product](https://item.taobao.com/item.htm?id=625390659071) |
| **ET2216 薄壁轴承**<br>ET2216【精品级】16\*22\*4MM[轴承钢]；ET2216 / 16×22×4mm / 轴承钢精品级 | 只 | 12 | ¥2.91 | ¥34.92 | 优可吉轴承销售店<br>[Product](https://item.taobao.com/item.htm?id=733598659967) |
| **623ZZ miniature bearing**<br>Exact variant: **623 内3外10厚4**; optional for FrankenDuck rollers; **excluded from the base total** | pcs | 8 | ¥1.50 | ¥12.00 | EVT进口轴承<br>[Product](https://item.taobao.com/item.htm?id=618009195719) |

623ZZ reference: author's October 14, 2026 order; shipping ¥0.50, paid total ¥12.50. Assembly quantities depend on the roller setup. [Matching printing set](hardware/3d-print-frankenduck/README.en.md).

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
| **SH1.0 4P 转杜邦母线**<br>0.2m;1.0-4P转杜邦母（5条）；SH1.0 4P / 20cm / 杜邦母 | 包（5个） | 1 | ¥4.56 | ¥4.56 | 信容芯旗舰店<br>[Product](https://item.taobao.com/item.htm?id=895049863252) |
| **AMP2.0 3P 舵机线 20cm（双头反向）**<br>200mm;1007/24#;3P;AMP2.0；200mm / 1007 / 24AWG / 3P / AMP2.0 | 条 | 30 | ¥1.50 | ¥45.00 | 永茂电子<br>[Product](https://item.taobao.com/item.htm?id=825340808235) |
| **AMP2.0 3P 舵机线 10cm（双头反向）**<br>100mm;1007/24#;3P;AMP2.0；100mm / 1007 / 24AWG / 3P / AMP2.0 | 条 | 30 | ¥1.50 | ¥45.00 | 永茂电子<br>[Product](https://item.taobao.com/item.htm?id=825340808235) |
| **彩色热缩管套装**<br>袋装 164片 彩色 【2倍收缩】；164片 / 彩色 / 2倍收缩 | 个 | 1 | ¥0.99 | ¥0.99 | 圣佰路旗舰店<br>[Product](https://item.taobao.com/item.htm?id=945215173380) |

NP-F550 is the original 2200mAh kit with two batteries and a standard dual charger. The M2×5 screws had a historical ¥0 promotional amount; this is not a regular selling price.

<details>
<summary>Reference purchase quantities and assembly notes</summary>

- **飞特 HD1910 串口总线舵机**：作者两次订单分别购入13只和2只，共15只；选择 HD-1910-C001 款式。
- **Radxa ZERO 3W**：已完成订单的主板款式；属于配套主控，不计入 HAT 84 个器件。
- **NP-F550 电池与双充套装**：按“NP-F550补光灯专用▲2200mAh，2电+标准双充套裝”原款式购买。
- **IMX219 160° camera**: buy from **树莓派零售商**, selecting the exact SKU **IMX219 160度摄像头** (SKU ID `6300750750661`). Reference unit price: **¥64.35**, included in the totals above; check the product page at checkout for the final price.
- **8×8 ToF 测距模块**：外接模块，不是 PCB 上的裸芯片；模块接线和供电按已验证方案。
- **Speaker / 扬声器**: choose the 3525 enclosure / 4Ω 3W variant. Match its connector to the assembled HAT and use a matching ready-made cable or adapter cable.
- **GameSir 启明星2 wireless gamepad**: one unit at the author's reference price of **¥89.91**, included in the duck body subtotal and whole-duck totals. Select the listed model; color and bundle are subject to the product page.
- **6700 开式薄壁轴承**：按订单参考采购数量计入，包含备料；尺寸顺序为内径×外径×宽度；两次订单为3只和2只。
- **ET2216 薄壁轴承**：按订单参考采购数量计入，包含备料；尺寸顺序为内径×外径×宽度；两次订单为10只和2只。
- **M2×4 十字盘头平尾自攻螺丝**：每种买1包（200只），包含备料；按打印模型及对应安装位置选择长度；每包数量是备料数量。
- **M2×5 十字盘头平尾自攻螺丝**：每种买1包（200只），包含备料；按打印模型及对应安装位置选择长度；每包数量是备料数量。原订单商品金额为0元（订单优惠），不代表常规售价。
- **M2×6 十字盘头平尾自攻螺丝**：每种买1包（200只），包含备料；按打印模型及对应安装位置选择长度；每包数量是备料数量。
- **M2×8 十字盘头平尾自攻螺丝**：每种买1包（200只），包含备料；按打印模型及对应安装位置选择长度；每包数量是备料数量。
- **M2×12 十字盘头平尾自攻螺丝**：每种买1包（200只），包含备料；按打印模型及对应安装位置选择长度；每包数量是备料数量。
- **M2.6×8 十字盘头平尾自攻螺丝**：每种买1包（200只），包含备料；按打印模型及对应安装位置选择长度；每包数量是备料数量。
- **SH1.0 4P 转杜邦母线**：用于外部接口转接；每根线的脚序按 HAT J5 与模块核对，不按线色猜。
- **AMP2.0 3P 舵机线 20cm（双头反向）**：按订单参考采购数量计入，包含备料；用于飞特舵机线束；10cm和20cm按实际走线位置选择。
- **AMP2.0 3P 舵机线 10cm（双头反向）**：按订单参考采购数量计入，包含备料；与20cm线是不同长度选项，数量按实际线束方案准备。
- **彩色热缩管套装**：用于接线处绝缘及整理。

</details>

## PCB

Component lists and reference designators:

| Board | Original detailed list | Fabrication record |
| --- | --- | --- |
| **HAT** · HAT-V5 | [84 components](hardware/README.en.md#full-reference-designator-boms) | [HAT](hardware/HAT-TIMELINE.en.md) |
| **IMU** · IMU-TO-DLX-V2 | [25 components](hardware/README.en.md#full-reference-designator-boms) | [IMU](hardware/IMU-TIMELINE.en.md) |

**[🔧 Open PCB procurement and board costs](hardware/README.en.md#shopping-list)**

## Tools

**🧰 Keep build tools and consumables in their own list.** It includes solder paste, tweezers, stencils, hotplate, soldering stations, solder wick, cleaning supplies and programming/debugging tools. Reuse tools you already have; these purchases are outside the duck hardware total.

**[🧰 Open the tools and consumables list](docs/BUILD-TOOLS.en.md)**

[📊 Excel snapshot (2026-10-13, Chinese; use the online lists for current purchases)](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/hardware/Microduck-HAT-IMU-Shopping-List-20261013.xlsx)
