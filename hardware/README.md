**简体中文** | [English](README.en.md)

# HAT 与 IMU 自制硬件

> [!WARNING]
> **硬件兼容性与商业授权提示**
>
> **非本仓库开源版本的 HAT、IMU、HUB 无法适配本仓库系统，可能导致系统无法正常运行。**
>
> **本仓库未授权任何商业组织。** 如发现盗版、冒用或未经授权的商业使用，请联系作者。开源不易，请勿盗用。
>
> **防骗提醒：不要相信除群主以外任何人的私聊推销，已有群友被骗。**
>
> [联系作者](https://github.com/kissqy/Microduck-kissqy/blob/main/docs/assets/purchase-wechat-qr.jpg) · [查看分项许可](https://github.com/kissqy/Microduck-kissqy/blob/main/LICENSE)。授权范围以本仓库现有分项许可为准。

> 🛒 **[购买 HAT 主板 / IMU 板（作者提供）](https://item.taobao.com/item.htm?id=1095121548583)**
>
> **作者成品 HAT／IMU：自行设计绘制，经长期真机使用与迭代验证，由嘉立创 SMT 贴片生产，注重稳定性与易复刻。**
>
> 将供电、通信、音频与姿态反馈等复刻需求整合，减少分散采购与自行制作的成本。
>
> **成品 IMU 已预烧录 FT6 固件，到手无需另行烧录。** 安装后仍需完成本机舵机与 IMU 标定。
>
> 作者享有权利的原创设计及工程资料仅供个人学习与非商业复刻；商业使用、批量生产或复制销售须事先取得作者书面授权。第三方内容遵循原许可，见[板卡设计许可](LICENSE) · [分项许可](../LICENSE)。

**[🔧 装机提醒：ZERO 使用 5 GHz Wi-Fi；HUB 已带 1000 µF 总电源缓冲电容，无需另购。接线与注意事项](../docs/ASSEMBLY-NOTES.md)**

**原版 HAT 和独立躯干 IMU 均已在实机上经过长时间使用验证，运行正常。现另提供 AMP2.0 接口版。**

**自己焊制、换芯片或维护升级时再看 [IMU FT6 下载与烧录指南](IMU-FIRMWARE.md)。作者提供的成品 IMU 已烧录 FT6，无需为首次装机重复烧录。** STM32 IMU 固件与 ZERO 的 control.43 服务分别安装。

🖨️ 鸭子本体的 [全套打印件与摆盘 · 缝合怪版](3d-print-frankenduck/) 已单独发布，含两种电池仓和不用拆舵机即可装滑轮的脚部套件。

**两种接口版本均保留，按线束选择。** [AMP2.0 版接口、LED 与用料说明](AMP2.0-VERSION.md)。

| 硬件 | 原版 EH2.5 · 2026-10-07 | AMP2.0 版 · 2026-10-15 | 制作记录 |
| --- | --- | --- | --- |
| HAT 主板 | [EH2.5 工程](ProPrj_HAT_REVA_SCH_2026-10-07.epro2) | [AMP2.0 工程](ProPrj_HAT_REVA_SCH_2026-10-15.epro2)，音频 HP1.25，新增 LED + 1kΩ | [制作时间线](HAT-TIMELINE.md) |
| 独立躯干 IMU | [EH2.5 工程](ProPrj_imu_to_dxl_RevA_V1_2026-10-07.epro2) | [AMP2.0 工程](ProPrj_imu_to_dxl_RevA_V1_2026-10-15.epro2) | [制作视频](https://www.bilibili.com/video/BV1qapz6PERs/) · [时间线](IMU-TIMELINE.md) |

HAT 的思路是先分析官方器件及外围，按实际需要精简，再用两层板和家庭回流完成实物。IMU 先跑通独立硬件及原版协议，再复用硬件接入飞特和 15 个舵机。

时间线依据 2026-10-12《整理HAT时间线》中已经整理的制作过程。原版工程为 2026-10-07 快照，另提供 2026-10-15 的 AMP2.0 版；实板调试改动与工程 BOM 的差异见 HAT 文档。

**当前记录基线（2026-10-12 确认）：** HAT 与 IMU 已完成制作、整机接入及长期实机验证；IMU 制作及飞特适配的测试记录见时间线。

> [!NOTE]
> **🌙 题外话 · 给自己留一个做板子的夜晚**
>
> 找一个老婆和孩子都睡了、明天不用上班的夜晚。刚吃完饭，家里收拾得干干净净，也洗好了澡。
>
> 拆开今天刚到的 PCB 和一堆电子器件，拿起你的镊子，放一首喜欢的音乐。🎵
>
> 一颗颗器件慢慢落到它们的位置上，时间也这样悄悄流走。等你回过神来，一张完美的电路板已经做好了。✨

## 采购清单

**版本对应：以下采购表、历史价格和 Excel 对应原版 EH2.5。AMP2.0 版的接口及新增器件按 [单独用料说明](AMP2.0-VERSION.md) 选择。**

> [!IMPORTANT]
> **作者实购、比价挑选，已通过实机验证**
>
> 本清单中的所有商品都由作者在实际采购时经过比价挑选，尽量选择**包邮且价格有优势**的商品，在满足项目需求的同时控制制作成本。
>
> 所列商品均经过一段时间的实际使用验证，**HAT 与 IMU 的通信、功能和运行稳定性均符合项目要求**。大家可以按表中的商品链接及指定型号、款式采购。

**当前采购：TH1可使用原村田PRG18BB101MB1RB（100Ω PTC，0603）；R33使用0Ω／0603。**

本页是鸭子制作的 **🔧 PCB采购分支**，可直接在线查看HAT／IMU详细采购表，无需下载表格。

**用量基准：** 1块 HAT + 1块 IMU，共 **84 + 25 = 109个板上器件**，按46项工程用料整理。鸭子本体和工具作为总清单中的独立分类。购买时按表中**指定购买款式**选择；工程型号链接用于对照工程记录。

最少拍数按每行单套用量计算；同商品、同款式的用料可以合并数量后，再按每拍含量向上取整。

[🦆 返回鸭子采购总清单](../DUCK-SHOPPING-LIST.md) · [制作成本](#制作成本) · [板上器件](#板上器件) · [裸板与打样](#裸板与打样) · [完整位号BOM](#完整位号bom) · [🧰 工具清单](../docs/BUILD-TOOLS.md) · [Excel历史快照（2026-10-13，最新采购以本页为准）](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/hardware/Microduck-HAT-IMU-Shopping-List-20261013.xlsx)

### 制作成本

| 电路板 | 手焊材料 · PCB有券 | 手焊材料 · PCB无券 | 到手即用成品板 |
| --- | ---: | ---: | ---: |
| HAT | ¥16.72 | ¥20.72 | [¥119](https://item.taobao.com/item.htm?id=1095121548583) |
| IMU（成品已烧录 FT6） | ¥20.38 | ¥24.38 | [¥99](https://item.taobao.com/item.htm?id=1095121548583) |
| **两块合计** | **¥37.11** | **¥45.11** | **¥218** |

手焊价格仅为板上实际用料，**不含工具与人工**。第一次采购按下表整包预算，并另加 **¥800～1000** [工具与耗材](../docs/BUILD-TOOLS.md#从零配工具预算)；成品板已贴片、到手即用。

| 首批材料采购 | 仅HAT | 仅IMU | 两板合并采购（共用器件不重复买） |
| --- | ---: | ---: | ---: |
| PCB有券 | ¥66.88 | ¥35.20 | ¥94.22 |
| PCB无券，每种5张 | ¥86.88 | ¥55.20 | ¥134.22 |

PCB无券按每种 ¥20/5张；U2 LSM6DSV16XTR 按 ¥13.80/个，其余器件沿用历史分摊成本。钢网已列入工具预算，运费另计。

<details>
<summary>元器件成本明细（46项，点击展开）</summary>

订单“商品金额”按一拍记录；单个分摊成本已按商品金额占比分配订单实付金额，包含原订单运费及实付差额。合计使用未舍入金额计算。

| 型号 / 指定购买款式 | 每拍含量 | 订单商品金额 / 拍 | 单个实付分摊成本 | HAT：数量 / 成本 | IMU：数量 / 成本 |
| --- | --- | --- | --- | --- | --- |
| CC0603KRX5R9BB105<br>0603 1uF ±10% X7R;50V | 1 | ¥0.03 | ¥0.035843 | 15 / ¥0.537651 | 0 / ¥0.000000 |
| C1608X5R1A106KT000E<br>0603 10uF ±10% X5R;10V | 1 | ¥0.06 | ¥0.066019 | 5 / ¥0.330095 | 0 / ¥0.000000 |
| 0603CG221J500NT<br>0603 220pF ±5% NPO/COG;50V;100个 | 100 | ¥1.49 | ¥0.014900 | 2 / ¥0.029800 | 0 / ¥0.000000 |
| CC0603KRX7R9BB104<br>0603 100nF ±10% X7R;50V;100个 | 100 | ¥1.98 | ¥0.023657 | 13 / ¥0.307536 | 0 / ¥0.000000 |
| C3216X7R1V106KT000E<br>1206 10UF ±10% X7R;35V | 1 | ¥0.12 | ¥0.119223 | 1 / ¥0.119223 | 0 / ¥0.000000 |
| GRM188R61A226ME15D<br>22UF 226K 10% X5R;10V;0603=100个 | 100 | ¥3.50 | ¥0.035000 | 2 / ¥0.070000 | 0 / ¥0.000000 |
| CC0603KRX7R9BB103<br>0603 10NF 50V 10% 100个 | 100 | ¥2.00 | ¥0.020000 | 1 / ¥0.020000 | 0 / ¥0.000000 |
| BAT54SW,115<br>BAT54SW 印字44t（20只） | 20 | ¥4.50 | ¥0.225000 | 1 / ¥0.225000 | 0 / ¥0.000000 |
| BZT52C5V1S-7-F<br>BZT52C5V1S W8 SOD-323 (50个) | 50 | ¥1.53 | ¥0.030600 | 1 / ¥0.030600 | 0 / ¥0.000000 |
| BLM18KG601SN1D<br>0603_600R_1.3A_±25%【100只】 | 100 | ¥5.60 | ¥0.056000 | 1 / ¥0.056000 | 0 / ¥0.000000 |
| PE-0603PFB121ST<br>0603_120R_2A_±25%【100只】 | 100 | ¥4.00 | ¥0.040000 | 2 / ¥0.080000 | 0 / ¥0.000000 |
| B2B-EH-A(LF)(SN)<br>EH2.5MM 2P直针座（50个） | 50 | ¥2.50 | ¥0.050000 | 3 / ¥0.150000 | 0 / ¥0.000000 |
| FH-00339<br>2*20P 贴片排母【2个】 | 2 | ¥4.07 | ¥2.035000 | 1 / ¥2.035000 | 0 / ¥0.000000 |
| BM04B-SRSS-TB(LF)(SN)<br>4P立贴（15个） | 15 | ¥2.22 | ¥0.148000 | 1 / ¥0.148000 | 0 / ¥0.000000 |
| B3B-EH-A(LF)(SN)<br>EH2.5MM 3P直针座（50个） | 50 | ¥3.00 | ¥0.060000 | 2 / ¥0.120000 | 1 / ¥0.060000 |
| SWPA6045S6R8MT<br>合金0630 6.8UH 印6R8 10个 6A 一体 | 10 | ¥2.00 | ¥0.200000 | 1 / ¥0.200000 | 0 / ¥0.000000 |
| LMA2718T421-OA5-2<br>2718 上进音 硅麦克风【2个】 | 2 | ¥1.98 | ¥0.990000 | 1 / ¥0.990000 | 0 / ¥0.000000 |
| MMBT3906<br>MMBT3906 丝印2A SOT-23(50个) | 50 | ¥1.77 | ¥0.035400 | 1 / ¥0.035400 | 0 / ¥0.000000 |
| SI2312CDS-T1-GE3<br>SI2312DS（AE9T）N沟道（20只） | 20 | ¥3.00 | ¥0.150000 | 1 / ¥0.150000 | 0 / ¥0.000000 |
| RC0603FR-0710KL<br>10K;0603 1%（100个） | 100 | ¥1.42 | ¥0.014200 | 12 / ¥0.170400 | 3 / ¥0.042600 |
| 0603WAF0000T5E<br>0R/0欧;0603 1%（100个） | 100 | ¥1.46 | ¥0.014600 | 5 / ¥0.073000 | 1 / ¥0.014600 |
| 0603WAF1000T5E<br>100R/100欧;0603 1%（100个） | 100 | ¥1.46 | ¥0.014600 | 1 / ¥0.014600 | 0 / ¥0.000000 |
| 0603WAF2002T5E<br>20K;0603 1%（100个） | 100 | ¥1.46 | ¥0.014600 | 1 / ¥0.014600 | 0 / ¥0.000000 |
| PRG18BB101MB1RB<br>100R  PRG18BB101MB1RB | 1 | ¥0.70 | ¥1.200000 | 1 / ¥1.200000 | 0 / ¥0.000000 |
| PAM8406DR<br>PAM8406DR | 1 | ¥1.18 | ¥1.178000 | 1 / ¥1.178000 | 0 / ¥0.000000 |
| TLV320AIC3104IRHBR<br>商品无选项，按商品标题完整型号购买 | 1 | ¥1.90 | ¥2.304000 | 1 / ¥2.304000 | 0 / ¥0.000000 |
| XC6206P182MR<br>XC6206P182MR 65K5 SOT-23 (20个) | 20 | ¥1.80 | ¥0.090000 | 1 / ¥0.090000 | 0 / ¥0.000000 |
| SN74LVC1G08DBVR<br>SN74LVC1G08DBVR;5个全国包邮 | 5 | ¥1.20 | ¥0.240000 | 1 / ¥0.240000 | 0 / ¥0.000000 |
| SN74LVC1G125DBVR-TP<br>SN74LVC1G125DBVR;5个全国包邮 | 5 | ¥1.30 | ¥0.260000 | 1 / ¥0.260000 | 0 / ¥0.000000 |
| SN74LVC1G126DBVR<br>SN74LVC1G126DBVR;5个全国包邮 | 5 | ¥1.80 | ¥0.360000 | 1 / ¥0.360000 | 0 / ¥0.000000 |
| AP63205WU-7<br>AP63205WU-7 | 1 | ¥1.28 | ¥1.278000 | 1 / ¥1.278000 | 0 / ¥0.000000 |
| LM5050MKX-1/NOPB<br>SOT-23;LM5050MKX-1/NOPB  原装正品 | 1 | ¥2.46 | ¥2.456000 | 1 / ¥2.456000 | 0 / ¥0.000000 |
| OT3EL89CJI-111YLC-12M<br>12MHZ 1.2V~3.36V宽压[高精度10PPM];SMD2520-4P CMOS输出 | 1 | ¥1.45 | ¥1.452000 | 1 / ¥1.452000 | 0 / ¥0.000000 |
| CL21A475KAQNNNE<br>0805 4.7UF ±10% X7R;25V | 1 | ¥0.06 | ¥0.069400 | 0 / ¥0.000000 | 2 / ¥0.138800 |
| CL10B104JB8NNNC<br>0603 100nF ±10% X7R;50V;100个 | 100 | ¥1.98 | ¥0.023657 | 0 / ¥0.000000 | 6 / ¥0.141940 |
| CL10A105KB8NNNC<br>0603 1uF ±10% X7R;50V | 1 | ¥0.03 | ¥0.035843 | 0 / ¥0.000000 | 2 / ¥0.071687 |
| PESD5V0S1BA<br>商品无选项，按商品标题完整型号购买 | 1 | ¥0.06 | ¥0.090000 | 0 / ¥0.000000 | 1 / ¥0.090000 |
| 19-217/GHC-YR1S2/3T<br>0603 蓝色=100个 | 100 | ¥1.80 | ¥0.018000 | 0 / ¥0.000000 | 1 / ¥0.018000 |
| PZ254V-11-05P<br>1*5P直针 铜（30条） | 30 | ¥1.41 | ¥0.047000 | 0 / ¥0.000000 | 1 / ¥0.047000 |
| RC0603FR-07100KL<br>100K;0603 1%（100个） | 100 | ¥1.46 | ¥0.014600 | 0 / ¥0.000000 | 1 / ¥0.014600 |
| 0603WAF330JT5E<br>33R/33欧;0603 1%（100个） | 100 | ¥1.46 | ¥0.014600 | 0 / ¥0.000000 | 1 / ¥0.014600 |
| 0603WAF1001T5E<br>1K;0603 1%（100个） | 100 | ¥1.44 | ¥0.014400 | 0 / ¥0.000000 | 1 / ¥0.014400 |
| STM32G031F8P6<br>全新原装 | 1 | ¥4.83 | ¥4.967405 | 0 / ¥0.000000 | 1 / ¥4.967405 |
| LSM6DSV16XTR<br>LSM6DSV16XTR | 1 | ¥13.80 | ¥13.800000 | 0 / ¥0.000000 | 1 / ¥13.800000 |
| TLV70433DBVR<br>TLV70433DBVR | 1 | ¥0.47 | ¥0.470000 | 0 / ¥0.000000 | 1 / ¥0.470000 |
| SN74LVC2G125DCUR<br>商品无选项，按商品标题完整型号购买 | 1 | ¥0.43 | ¥0.478000 | 0 / ¥0.000000 | 1 / ¥0.478000 |

</details>

### 板上器件

#### HAT 与 IMU 板上器件

##### 电容

| 工程型号 / 当前用料 | 指定购买款式与说明 | HAT单板：数量 / 位号 | IMU单板：数量 / 位号 | 每拍含量 / 单套最少拍数 | 店铺 / 商品链接 |
| --- | --- | --- | --- | --- | --- |
| [CC0603KRX5R9BB105](https://www.lcsc.com/product-detail/C128624.html)<br>0603；1uF / ±10% / 50V / X5R | **0603 1uF ±10% X7R;50V**<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | **15**<br>C1, C2, C3, C4, C6, C10, C27, C29, C31, C33, C35, C40, C41, C42, C43 | — | 1个 / 拍<br>最少 **15拍** | 深圳市宏宸电子<br>[购买商品](https://item.taobao.com/item.htm?id=630712731066) |
| [C1608X5R1A106KT000E](https://item.szlcsc.com/77735.html)<br>0603；10uF / ±10% / 10V / X5R | **0603 10uF ±10% X5R;10V**<br>实际采购：0603 / 10uF / ±10% / 10V / X5R。 | **5**<br>C5, C7, C12, C13, C37 | — | 1个 / 拍<br>最少 **5拍** | 深圳市宏宸电子<br>[购买商品](https://item.taobao.com/item.htm?id=630712731066) |
| [0603CG221J500NT](https://item.szlcsc.com/167743.html)<br>0603；220pF / ±5% / 50V / C0G | **0603 220pF ±5% NPO/COG;50V;100个**<br>选 220pF、50V、C0G(NPO)、±5%、0603；同页其他容量分别选购。 | **2**<br>C8, C9 | — | 100个 / 拍<br>最少 **1拍** | 深圳市宏宸电子<br>[购买商品](https://item.taobao.com/item.htm?id=1005108810412) |
| [CC0603KRX7R9BB104](https://item.szlcsc.com/15331.html)<br>0603；100nF / ±10% / 50V / X7R | **0603 100nF ±10% X7R;50V;100个**<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | **13**<br>C11, C14, C16, C17, C18, C20, C26, C28, C30, C32, C36, C38, C39 | — | 100个 / 拍<br>最少 **1拍** | 深圳市宏宸电子<br>[购买商品](https://item.taobao.com/item.htm?id=731471380840) |
| [C3216X7R1V106KT000E](https://item.szlcsc.com/77793.html)<br>1206；10uF / ±10% / 35V / X7R | **1206 10UF ±10% X7R;35V**<br>C15 使用 1206、10uF、35V、X7R 款式。 | **1**<br>C15 | — | 1个 / 拍<br>最少 **1拍** | 深圳市宏宸电子<br>[购买商品](https://item.taobao.com/item.htm?id=730407108775) |
| [GRM188R61A226ME15D](https://item.szlcsc.com/85589.html)<br>0603；22uF / ±20% / 10V / X5R | **22UF 226K 10% X5R;10V;0603=100个**<br>实际采购：0603 / 22uF / ±10% / 10V / X5R。 | **2**<br>C21, C22 | — | 100个 / 拍<br>最少 **1拍** | 优好电子<br>[购买商品](https://item.taobao.com/item.htm?id=993202872551) |
| [CC0603KRX7R9BB103](https://item.szlcsc.com/101256.html)<br>0603；10nF / ±10% / 50V / X7R | **0603 10NF 50V 10% 100个**<br>实际采购：0603 / 10nF / ±10% / 50V / X7R。 | **1**<br>C34 | — | 100个 / 拍<br>最少 **1拍** | 欧贝顿旗舰店<br>[购买商品](https://item.taobao.com/item.htm?id=610558214623) |
| [CL21A475KAQNNNE](https://www.lcsc.com/product-detail/C1779.html)<br>0805；4.7uF / ±10% / 25V / X5R | **0805 4.7UF ±10% X7R;25V**<br>实际采购：0805 / 4.7uF / ±10% / 25V / X7R。 | — | **2**<br>C1, C3 | 1个 / 拍<br>最少 **2拍** | 深圳市宏宸电子<br>[购买商品](https://item.taobao.com/item.htm?id=977236759812) |
| [CL10B104JB8NNNC](https://item.szlcsc.com/25192.html)<br>0603；100nF / ±5% / 50V / X7R | **0603 100nF ±10% X7R;50V;100个**<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | — | **6**<br>C2, C4, C5, C7, C8, C10 | 100个 / 拍<br>最少 **1拍** | 深圳市宏宸电子<br>[购买商品](https://item.taobao.com/item.htm?id=731471380840) |
| [CL10A105KB8NNNC](https://item.szlcsc.com/16531.html)<br>0603；1uF / ±10% / 50V / X5R | **0603 1uF ±10% X7R;50V**<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | — | **2**<br>C6, C9 | 1个 / 拍<br>最少 **2拍** | 深圳市宏宸电子<br>[购买商品](https://item.taobao.com/item.htm?id=630712731066) |

##### 电阻与PTC热敏电阻

| 工程型号 / 当前用料 | 指定购买款式与说明 | HAT单板：数量 / 位号 | IMU单板：数量 / 位号 | 每拍含量 / 单套最少拍数 | 店铺 / 商品链接 |
| --- | --- | --- | --- | --- | --- |
| [RC0603FR-0710KL](https://item.szlcsc.com/99429.html)<br>0603；10kΩ / ±1% / ±100ppm/℃ / 100mW | **10K;0603 1%（100个）**<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | **12**<br>R1, R2, R6, R12, R13, R22, R23, R26, R27, R29, R31, R32 | **3**<br>R2, R4, R5 | 100个 / 拍<br>最少 **1拍** | 深圳市永芯泰电子企业店<br>[购买商品](https://item.taobao.com/item.htm?id=947267344247) |
| [0603WAF0000T5E](https://item.szlcsc.com/21903.html)<br>0603；0Ω / ±1% / 0603 | **0R/0欧;0603 1%（100个）**<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | **5**<br>R3, R4, R5, R7, R33 | **1**<br>R1 | 100个 / 拍<br>最少 **1拍** | 深圳市永芯泰电子企业店<br>[购买商品](https://item.taobao.com/item.htm?id=947267344247) |
| [0603WAF1000T5E](https://www.lcsc.com/product-detail/C22775.html)<br>0603；100Ω / ±1% / ±200ppm/℃ / 100mW | **100R/100欧;0603 1%（100个）**<br>100Ω / ±1% / 0603，用于 HAT R8。 | **1**<br>R8 | — | 100个 / 拍<br>最少 **1拍** | 深圳市永芯泰电子企业店<br>[购买商品](https://item.taobao.com/item.htm?id=947267344247) |
| [0603WAF2002T5E](https://item.szlcsc.com/4591.html)<br>0603；20kΩ / ±1% / ±100ppm/℃ / 100mW | **20K;0603 1%（100个）**<br>20kΩ / ±1% / 0603。 | **1**<br>R28 | — | 100个 / 拍<br>最少 **1拍** | 深圳市永芯泰电子企业店<br>[购买商品](https://item.taobao.com/item.htm?id=947267344247) |
| [PRG18BB101MB1RB](https://item.szlcsc.com/984022.html)<br>0603；100Ω / PTC / 村田 | **100R  PRG18BB101MB1RB**<br>TH1可使用原村田PRG18BB101MB1RB（100Ω PTC，0603），按原订单100R款式采购；R33使用0Ω。 | **1**<br>TH1 | — | 1个 / 拍<br>最少 **1拍** | 贤辉亿芯<br>[购买商品](https://item.taobao.com/item.htm?id=582129955778) |
| [RC0603FR-07100KL](https://item.szlcsc.com/15343.html)<br>0603；100kΩ / ±1% / ±100ppm/℃ / 100mW | **100K;0603 1%（100个）**<br>100kΩ / ±1% / 0603。 | — | **1**<br>R3 | 100个 / 拍<br>最少 **1拍** | 深圳市永芯泰电子企业店<br>[购买商品](https://item.taobao.com/item.htm?id=947267344247) |
| [0603WAF330JT5E](https://item.szlcsc.com/23867.html)<br>0603；33Ω / ±1% / ±100ppm/℃ / 100mW | **33R/33欧;0603 1%（100个）**<br>33Ω / ±1% / 0603，用于IMU R6。 | — | **1**<br>R6 | 100个 / 拍<br>最少 **1拍** | 深圳市永芯泰电子企业店<br>[购买商品](https://item.taobao.com/item.htm?id=947267344247) |
| [0603WAF1001T5E](https://item.szlcsc.com/21904.html)<br>0603；1kΩ / ±1% / ±100ppm/℃ / 100mW | **1K;0603 1%（100个）**<br>1kΩ / ±1% / 0603，八月备料订单。 | — | **1**<br>R7 | 100个 / 拍<br>最少 **1拍** | 深圳市永芯泰电子企业店<br>[购买商品](https://item.taobao.com/item.htm?id=947267344247) |

##### 磁珠、电感、晶振与麦克风

| 工程型号 / 当前用料 | 指定购买款式与说明 | HAT单板：数量 / 位号 | IMU单板：数量 / 位号 | 每拍含量 / 单套最少拍数 | 店铺 / 商品链接 |
| --- | --- | --- | --- | --- | --- |
| [BLM18KG601SN1D](https://item.szlcsc.com/87009.html)<br>0603；±25% / 600Ω@100MHz / 1.3A | **0603_600R_1.3A_±25%【100只】**<br>实际采购：0603 / 600Ω@100MHz / 1.3A / ±25%。 | **1**<br>FB1 | — | 100个 / 拍<br>最少 **1拍** | 科芯奇旗舰店<br>[购买商品](https://item.taobao.com/item.htm?id=931081429973) |
| [PE-0603PFB121ST](https://item.szlcsc.com/2753383.html)<br>0603；±25% / 120Ω@100MHz / 2A | **0603_120R_2A_±25%【100只】**<br>实际采购：0603 / 120Ω@100MHz / 2A / ±25%。 | **2**<br>FB2, FB3 | — | 100个 / 拍<br>最少 **1拍** | 科芯奇旗舰店<br>[购买商品](https://item.taobao.com/item.htm?id=931081429973) |
| [SWPA6045S6R8MT](https://item.szlcsc.com/58286.html)<br>SMD,6x6mm；6.8uH / ±20% / 3A | **合金0630 6.8UH 印6R8 10个 6A 一体**<br>实际使用：合金0630、6.8uH、6A一体成型电感（订单标称）。 | **1**<br>L4 | — | 10个 / 拍<br>最少 **1拍** | 迪林旗舰店<br>[购买商品](https://item.taobao.com/item.htm?id=598174251748) |
| [LMA2718T421-OA5-2](https://item.szlcsc.com/8705873.html)<br>SMD-4P,2.8x1.9mm；指向性:全指向；信噪比:55dB；灵敏度:-42dB；阻抗:300Ω | **2718 上进音 硅麦克风【2个】**<br>实际使用：2718 上进音模拟 MEMS 麦克风，按“2718 上进音 硅麦克风【2个】”购买。 | **1**<br>MK1 | — | 2个 / 拍<br>最少 **1拍** | 深圳市华源芯电子有限公司 电子元器件配单<br>[购买商品](https://item.taobao.com/item.htm?id=996702312391) |
| [OT3EL89CJI-111YLC-12M](https://item.szlcsc.com/8414369.html)<br>SMD2520-4P；12MHz | **12MHZ 1.2V~3.36V宽压[高精度10PPM];SMD2520-4P CMOS输出**<br>实际使用：12MHz、2520-4P、CMOS输出有源晶振，宽压1.2V~3.36V（订单标称）。 | **1**<br>Y1 | — | 1个 / 拍<br>最少 **1拍** | 深圳市晶诺源电子<br>[购买商品](https://item.taobao.com/item.htm?id=944053669860) |

##### 板上连接器

| 工程型号 / 当前用料 | 指定购买款式与说明 | HAT单板：数量 / 位号 | IMU单板：数量 / 位号 | 每拍含量 / 单套最少拍数 | 店铺 / 商品链接 |
| --- | --- | --- | --- | --- | --- |
| [B2B-EH-A(LF)(SN)](https://item.szlcsc.com/171642.html)<br>插件,P=2.5mm；250V / 3A | **EH2.5MM 2P直针座（50个）**<br>EH 2P 直针座；按 EH2.5MM 2P 直针座选项购买。 | **3**<br>J1, J2, J9 | — | 50个 / 拍<br>最少 **1拍** | 启色数码旗舰店<br>[购买商品](https://item.taobao.com/item.htm?id=832569969546) |
| [FH-00339](https://item.szlcsc.com/2784386.html)<br>SMD,P=2.54mm；3A | **2*20P 贴片排母【2个】**<br>双排 2×20P、2.54mm、贴片排母，安装在 HAT 底面。 | **1**<br>J4 | — | 2个 / 拍<br>最少 **1拍** | 海雀数码专营店<br>[购买商品](https://item.taobao.com/item.htm?id=533725557959) |
| [BM04B-SRSS-TB(LF)(SN)](https://item.szlcsc.com/171770.html)<br>SMD,P=1mm；50V / 1A | **4P立贴（15个）**<br>SH1.0 / 4P / 立贴，按“4P立贴（15个）”选项购买。 | **1**<br>J5 | — | 15个 / 拍<br>最少 **1拍** | 信容芯旗舰店<br>[购买商品](https://item.taobao.com/item.htm?id=920058690376) |
| [B3B-EH-A(LF)(SN)](https://item.szlcsc.com/171639.html)<br>插件,P=2.5mm；250V / 3A | **EH2.5MM 3P直针座（50个）**<br>EH 3P 直针座，HAT 两只、IMU 一只。 | **2**<br>J13, J14 | **1**<br>J1 | 50个 / 拍<br>最少 **1拍** | 启色数码旗舰店<br>[购买商品](https://item.taobao.com/item.htm?id=832569969546) |
| [PZ254V-11-05P](https://item.szlcsc.com/502960.html)<br>插件,P=2.54mm；3A | **1*5P直针 铜（30条）**<br>1×5P / 2.54mm 直排针，用于SWD烧录口。 | — | **1**<br>J2 | 30个 / 拍<br>最少 **1拍** | zxin旗舰店<br>[购买商品](https://item.taobao.com/item.htm?id=606816197525) |

##### 芯片、二极管与晶体管

| 工程型号 / 当前用料 | 指定购买款式与说明 | HAT单板：数量 / 位号 | IMU单板：数量 / 位号 | 每拍含量 / 单套最少拍数 | 店铺 / 商品链接 |
| --- | --- | --- | --- | --- | --- |
| [BAT54SW,115](https://item.szlcsc.com/79742.html)<br>SOT-323；二极管配置:1对串联式；正向压降(Vf):800mV@100mA；直流反向耐压(Vr):30V；整流电流:200mA | **BAT54SW 印字44t（20只）**<br>选择 BAT54SW / SOT-323 款式。 | **1**<br>D1 | — | 20个 / 拍<br>最少 **1拍** | 深圳市乐桥微科技<br>[购买商品](https://item.taobao.com/item.htm?id=793455311175) |
| [BZT52C5V1S-7-F](https://item.szlcsc.com/162688.html)<br>SOD-323；二极管配置:1个独立式；稳压值(标称值):5.1V；稳压值(范围值):4.8V~5.4V；耗散功率(Pd):200mW | **BZT52C5V1S W8 SOD-323 (50个)**<br>选择 BZT52C5V1S / 5.1V / SOD-323 款式。 | **1**<br>D4 | — | 50个 / 拍<br>最少 **1拍** | 稳泊仕旗舰店<br>[购买商品](https://item.taobao.com/item.htm?id=943185002457) |
| [MMBT3906](https://item.szlcsc.com/774233.html)<br>SOT-23；晶体管类型:PNP；集电极电流(Ic):200mA；集射极击穿电压(Vceo):40V；耗散功率(Pd):200mW；直流电流增益(hFE):100@10mA,1V | **MMBT3906 丝印2A SOT-23(50个)**<br>选择 MMBT3906 / PNP / SOT-23 款式。 | **1**<br>Q1 | — | 50个 / 拍<br>最少 **1拍** | 稳泊仕旗舰店<br>[购买商品](https://item.taobao.com/item.htm?id=944306254140) |
| [SI2312CDS-T1-GE3](https://item.szlcsc.com/153849.html)<br>SOT-23；数量:1个N沟道；漏源电压(Vdss):20V；连续漏极电流(Id):6A；导通电阻(RDS(on)):41.4mΩ@1.8V,5.6A；耗散功率(Pd):2.1W；阈值电压(Vgs(th)):1V@250uA | **SI2312DS（AE9T）N沟道（20只）**<br>实际使用：SI2312DS（AE9T）N沟道，20只包装。 | **1**<br>Q2 | — | 20个 / 拍<br>最少 **1拍** | 一芯向上电子<br>[购买商品](https://item.taobao.com/item.htm?id=909264246006) |
| [PAM8406DR](https://item.szlcsc.com/87446.html)<br>SOIC-16；功放类型:AB类功放；D类功放；扬声器通道数:双声道；输出功率:5Wx2@2Ω；静态电流(Iq):10mA | **PAM8406DR**<br>实际使用：PAM8406DR，订单标注 SOP16。 | **1**<br>U1 | — | 1个 / 拍<br>最少 **1拍** | 深圳市远大芯程科技<br>[购买商品](https://item.taobao.com/item.htm?id=808484505787) |
| [TLV320AIC3104IRHBR](https://www.lcsc.com/product-detail/C181753.html)<br>HVQFN-32-EP(5x5)；类型:编解码器；接口类型:I2S；I2C；采样率:8kHz~96kHz | **商品无选项，按商品标题完整型号购买**<br>TLV320AIC3104IRHBR，按商品完整型号购买。 | **1**<br>U2 | — | 1个 / 拍<br>最少 **1拍** | 淼鑫电子科技<br>[购买商品](https://item.taobao.com/item.htm?id=908248360601) |
| [XC6206P182MR](https://item.szlcsc.com/324033.html)<br>SOT-23；输出极性:正极；工作电压:8V；输出电压:1.8V；输出电流:250mA；电源纹波抑制比(PSRR):40dB@(1kHz)；输出类型:固定 | **XC6206P182MR 65K5 SOT-23 (20个)**<br>XC6206P182MR / 1.8V / SOT-23，20个包装。 | **1**<br>U3 | — | 20个 / 拍<br>最少 **1拍** | 启色数码旗舰店<br>[购买商品](https://item.taobao.com/item.htm?id=762173333947) |
| [SN74LVC1G08DBVR](https://www.lcsc.com/product-detail/C7666.html)<br>SOT-23-5；逻辑类型:与门；通道数:1；工作电压:1.65V~5.5V；静态电流(Iq):10uA；传播延迟(tpd):4ns@5V,50pF | **SN74LVC1G08DBVR;5个全国包邮**<br>SN74LVC1G08DBVR / SOT-23-5 与门，按同页对应型号选项购买。 | **1**<br>U5 | — | 5个 / 拍<br>最少 **1拍** | 深圳市德明电子贸易商城<br>[购买商品](https://item.taobao.com/item.htm?id=902117985110) |
| [SN74LVC1G125DBVR-TP](https://item.szlcsc.com/3597950.html)<br>SOT-23-5；输入类型:-；工作电压:1.65V~5.5V；元件数:1；每个元件位数:-；灌电流(IOL):24mA；拉电流(IOH):24mA | **SN74LVC1G125DBVR;5个全国包邮**<br>实际使用：SN74LVC1G125DBVR / SOT-23-5，5个包装。 | **1**<br>U6 | — | 5个 / 拍<br>最少 **1拍** | 深圳市德明电子贸易商城<br>[购买商品](https://item.taobao.com/item.htm?id=902117985110) |
| [SN74LVC1G126DBVR](https://www.lcsc.com/product-detail/C7834.html)<br>SOT-23-5；输入类型:-；工作电压:1.65V~5.5V；元件数:1；每个元件位数:1；灌电流(IOL):32mA；拉电流(IOH):32mA | **SN74LVC1G126DBVR;5个全国包邮**<br>实际使用：SN74LVC1G126DBVR / SOT-23-5，5个包装。 | **1**<br>U7 | — | 5个 / 拍<br>最少 **1拍** | 深圳市德明电子贸易商城<br>[购买商品](https://item.taobao.com/item.htm?id=902117985110) |
| [AP63205WU-7](https://item.szlcsc.com/2162639.html)<br>TSOT-23-6；功能类型:降压型；工作电压:3.8V~32V；输出电压:5V；输出电流:2A；输出类型:固定 | **AP63205WU-7**<br>AP63205WU-7，固定5V降压芯片，按对应完整型号购买。 | **1**<br>U9 | — | 1个 / 拍<br>最少 **1拍** | 深圳市远大芯程科技<br>[购买商品](https://item.taobao.com/item.htm?id=969642590399) |
| [LM5050MKX-1/NOPB](https://www.lcsc.com/product-detail/C473393.html)<br>TSOT-23-6；LM5050-1 5V 至 75V、400uA IQ ORing FET 控制器 | **SOT-23;LM5050MKX-1/NOPB  原装正品**<br>LM5050MKX-1/NOPB，按完整型号购买。 | **1**<br>U10 | — | 1个 / 拍<br>最少 **1拍** | 深圳市安芯选电子<br>[购买商品](https://item.taobao.com/item.htm?id=1013388982214) |
| [PESD5V0S1BA](https://www.lcsc.com/product-detail/C330094.html)<br>SOD-323；反向截止电压(Vrwm):5V@Max；最大钳位电压:10V；峰值脉冲电流(Ipp)@10/1000us:5A@8/20us；击穿电压:5.8V | **商品无选项，按商品标题完整型号购买**<br>PESD5V0S1BA / SOD-323 双向TVS，按商品完整型号购买。 | — | **1**<br>D1 | 1个 / 拍<br>最少 **1拍** | 深圳市优信电子科技有限公司<br>[购买商品](https://item.taobao.com/item.htm?id=891785167202) |
| [19-217/GHC-YR1S2/3T](https://www.lcsc.com/product-detail/Light-Emitting-Diodes-LED_Everlight-Elec-19-217-GHC-YR1S2-3T_C72043.html)<br>0603；110mW | **0603 蓝色=100个**<br>实际采购：0603 蓝色LED，100个包装。 | — | **1**<br>D2 | 100个 / 拍<br>最少 **1拍** | 泰辰电子<br>[购买商品](https://item.taobao.com/item.htm?id=1025817117811) |
| [STM32G031F8P6](https://item.szlcsc.com/549612.html)<br>TSSOP-20；CPU内核:ARM Cortex-M0+；CPU最大主频:64MHz；CPU位数:32 Bit | **全新原装**<br>STM32G031F8P6 / TSSOP-20，按商品完整型号购买。 | — | **1**<br>U1 | 1个 / 拍<br>最少 **1拍** | 深圳市新纶电子<br>[购买商品](https://item.taobao.com/item.htm?id=726808419708) |
| [LSM6DSV16XTR](https://item.szlcsc.com/5993815.html)<br>LGA-14(2.5x3)；传感器类型:IMU(加速度计+陀螺仪)；接口类型:I2C；SPI | **LSM6DSV16XTR**<br>LSM6DSV16XTR / LGA-14；指定购买 LSM6DSV16XTR，参考单价 ¥13.80/个。 | — | **1**<br>U2 | 1个 / 拍<br>最少 **1拍** | 淘宝<br>[购买商品](https://e.tb.cn/h.j3ZZ8HNmUBbhzqy?tk=jMe5TxTIPLE) |
| [TLV70433DBVR](https://www.lcsc.com/product-detail/C94917.html)<br>SOT-23-5；输出极性:正极；工作电压:24V；输出电压:3.3V；输出电流:150mA；电源纹波抑制比(PSRR):60dB@(100kHz)；输出类型:固定 | **TLV70433DBVR**<br>TLV70433DBVR / 3.3V / SOT-23-5。 | — | **1**<br>U3 | 1个 / 拍<br>最少 **1拍** | 深圳市恒芯科创电子<br>[购买商品](https://item.taobao.com/item.htm?id=747094785928) |
| [SN74LVC2G125DCUR](https://www.lcsc.com/product-detail/C21404.html)<br>VSSOP-8；输入类型:-；工作电压:1.65V~5.5V；元件数:2；每个元件位数:1；灌电流(IOL):32mA；拉电流(IOH):32mA | **商品无选项，按商品标题完整型号购买**<br>SN74LVC2G125DCUR / VSSOP-8，按商品完整型号购买。 | — | **1**<br>U4 | 1个 / 拍<br>最少 **1拍** | 深圳市垚鑫电子科技<br>[购买商品](https://item.taobao.com/item.htm?id=705642638300) |

#### 裸板与打样

| 商品 / 用品 | 指定购买款式 / 具体规格 | 用量 / 购买说明 | 订单商品金额 / 拍 | 店铺 / 商品链接 |
| --- | --- | --- | --- | --- |
| HAT 裸板 | **定制打样入口，不是现成商品**<br>HAT-V5，65×30.9mm，两层板；按对应工程生成生产资料 | 有券免费；无券20元5张（4元/张）<br>裸板需定制；R33按0Ω采购，TH1可用原村田PRG18BB101MB1RB；使用本项目对应工程。 | — | PCB打样平台<br>[购买商品](https://www.jlc.com/) |
| IMU 裸板 | **定制打样入口，不是现成商品**<br>IMU-TO-DLX-V2；按对应工程生成生产资料 | 有券免费；无券20元5张（4元/张）<br>使用对应 IMU 工程，裸板不是可直接购买的标准模块。 | — | PCB打样平台<br>[购买商品](https://www.jlc.com/) |

### 完整位号BOM

展开下表可逐个查看器件。工程原始属性与实际采购款式分别列出。HAT R33使用0Ω，TH1可用原村田PRG18BB101MB1RB（100Ω PTC，0603）；原工程值保留在位号表中。

<details>
<summary>HAT 完整位号 BOM（84个器件，点击展开）</summary>

| 位号 / 用途 | 工程型号 / 立创料号 | 工程封装 / 参数 | 实际购买款式 / 用料说明 | 链接 |
| --- | --- | --- | --- | --- |
| **C1**<br>1uF / left AC coupling | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C2**<br>1uF / right AC coupling | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C3**<br>1uF / VREF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C4**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C5**<br>10uF | C1608X5R1A106KT000E<br>C76608 | 0603<br>10uF / ±10% / 10V / X5R | 0603 10uF ±10% X5R;10V<br>实际采购：0603 / 10uF / ±10% / 10V / X5R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://item.szlcsc.com/77735.html) |
| **C6**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C7**<br>10uF | C1608X5R1A106KT000E<br>C76608 | 0603<br>10uF / ±10% / 10V / X5R | 0603 10uF ±10% X5R;10V<br>实际采购：0603 / 10uF / ±10% / 10V / X5R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://item.szlcsc.com/77735.html) |
| **C8**<br>0603CG221J500NT | 0603CG221J500NT<br>C156398 | 0603<br>220pF / ±5% / 50V / C0G | 0603 220pF ±5% NPO/COG;50V;100个<br>选 220pF、50V、C0G(NPO)、±5%、0603；同页其他容量分别选购。 | [商品](https://item.taobao.com/item.htm?id=1005108810412) · [工程型号](https://item.szlcsc.com/167743.html) |
| **C9**<br>0603CG221J500NT | 0603CG221J500NT<br>C156398 | 0603<br>220pF / ±5% / 50V / C0G | 0603 220pF ±5% NPO/COG;50V;100个<br>选 220pF、50V、C0G(NPO)、±5%、0603；同页其他容量分别选购。 | [商品](https://item.taobao.com/item.htm?id=1005108810412) · [工程型号](https://item.szlcsc.com/167743.html) |
| **C10**<br>1uF / onboard MIC coupling | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C11**<br>100nF / onboard MIC | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/15331.html) |
| **C12**<br>10uF / 1V8 | C1608X5R1A106KT000E<br>C76608 | 0603<br>10uF / ±10% / 10V / X5R | 0603 10uF ±10% X5R;10V<br>实际采购：0603 / 10uF / ±10% / 10V / X5R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://item.szlcsc.com/77735.html) |
| **C13**<br>10uF / 3V3 | C1608X5R1A106KT000E<br>C76608 | 0603<br>10uF / ±10% / 10V / X5R | 0603 10uF ±10% X5R;10V<br>实际采购：0603 / 10uF / ±10% / 10V / X5R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://item.szlcsc.com/77735.html) |
| **C14**<br>100nF / oscillator | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/15331.html) |
| **C15**<br>C3216X7R1V106KT000E | C3216X7R1V106KT000E<br>C76666 | 1206<br>10uF / ±10% / 35V / X7R | 1206 10UF ±10% X7R;35V<br>C15 使用 1206、10uF、35V、X7R 款式。 | [商品](https://item.taobao.com/item.htm?id=730407108775) · [工程型号](https://item.szlcsc.com/77793.html) |
| **C16**<br>100nF / U5 | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/15331.html) |
| **C17**<br>100nF / U6 | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/15331.html) |
| **C18**<br>100nF / U7 | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/15331.html) |
| **C20**<br>100nF 50V / bootstrap | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/15331.html) |
| **C21**<br>22uF 10V X5R | GRM188R61A226ME15D<br>C84419 | 0603<br>22uF / ±20% / 10V / X5R | 22UF 226K 10% X5R;10V;0603=100个<br>实际采购：0603 / 22uF / ±10% / 10V / X5R。 | [商品](https://item.taobao.com/item.htm?id=993202872551) · [工程型号](https://item.szlcsc.com/85589.html) |
| **C22**<br>22uF 10V X5R | GRM188R61A226ME15D<br>C84419 | 0603<br>22uF / ±20% / 10V / X5R | 22UF 226K 10% X5R;10V;0603=100个<br>实际采购：0603 / 22uF / ±10% / 10V / X5R。 | [商品](https://item.taobao.com/item.htm?id=993202872551) · [工程型号](https://item.szlcsc.com/85589.html) |
| **C26**<br>100nF / 1V8 | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/15331.html) |
| **C27**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C28**<br>100nF | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/15331.html) |
| **C29**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C30**<br>100nF | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/15331.html) |
| **C31**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C32**<br>100nF | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/15331.html) |
| **C33**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C34**<br>10nF | CC0603KRX7R9BB103<br>C100042 | 0603<br>10nF / ±10% / 50V / X7R | 0603 10NF 50V 10% 100个<br>实际采购：0603 / 10nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=610558214623) · [工程型号](https://item.szlcsc.com/101256.html) |
| **C35**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C36**<br>100nF | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/15331.html) |
| **C37**<br>10uF / 3V3 | C1608X5R1A106KT000E<br>C76608 | 0603<br>10uF / ±10% / 10V / X5R | 0603 10uF ±10% X5R;10V<br>实际采购：0603 / 10uF / ±10% / 10V / X5R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://item.szlcsc.com/77735.html) |
| **C38**<br>100nF / codec reset | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/15331.html) |
| **C39**<br>100nF 50V | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/15331.html) |
| **C40**<br>1uF / MIC R coupling | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C41**<br>1uF / MIC L coupling | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C42**<br>1uF / MIC supply | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **C43**<br>1uF / MIC supply | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://www.lcsc.com/product-detail/C128624.html) |
| **D1**<br>BAT54SW / diode 1 used | BAT54SW,115<br>C78606 | SOT-323<br>二极管配置:1对串联式；正向压降(Vf):800mV@100mA；直流反向耐压(Vr):30V；整流电流:200mA | BAT54SW 印字44t（20只）<br>选择 BAT54SW / SOT-323 款式。 | [商品](https://item.taobao.com/item.htm?id=793455311175) · [工程型号](https://item.szlcsc.com/79742.html) |
| **D4**<br>5V1 / bus clamp | BZT52C5V1S-7-F<br>C151348 | SOD-323<br>二极管配置:1个独立式；稳压值(标称值):5.1V；稳压值(范围值):4.8V~5.4V；耗散功率(Pd):200mW | BZT52C5V1S W8 SOD-323 (50个)<br>选择 BZT52C5V1S / 5.1V / SOD-323 款式。 | [商品](https://item.taobao.com/item.htm?id=943185002457) · [工程型号](https://item.szlcsc.com/162688.html) |
| **FB1**<br>600R@100MHz 1.3A | BLM18KG601SN1D<br>C85833 | 0603<br>±25% / 600Ω@100MHz / 1.3A | 0603_600R_1.3A_±25%【100只】<br>实际采购：0603 / 600Ω@100MHz / 1.3A / ±25%。 | [商品](https://item.taobao.com/item.htm?id=931081429973) · [工程型号](https://item.szlcsc.com/87009.html) |
| **FB2**<br>120R@100MHz 2A | PE-0603PFB121ST<br>C2661472 | 0603<br>±25% / 120Ω@100MHz / 2A | 0603_120R_2A_±25%【100只】<br>实际采购：0603 / 120Ω@100MHz / 2A / ±25%。 | [商品](https://item.taobao.com/item.htm?id=931081429973) · [工程型号](https://item.szlcsc.com/2753383.html) |
| **FB3**<br>120R@100MHz 2A | PE-0603PFB121ST<br>C2661472 | 0603<br>±25% / 120Ω@100MHz / 2A | 0603_120R_2A_±25%【100只】<br>实际采购：0603 / 120Ω@100MHz / 2A / ±25%。 | [商品](https://item.taobao.com/item.htm?id=931081429973) · [工程型号](https://item.szlcsc.com/2753383.html) |
| **J1**<br>SPK R / JST-EH 2P | B2B-EH-A(LF)(SN)<br>C160262 | 插件,P=2.5mm<br>250V / 3A | EH2.5MM 2P直针座（50个）<br>EH 2P 直针座；按 EH2.5MM 2P 直针座选项购买。 | [商品](https://item.taobao.com/item.htm?id=832569969546) · [工程型号](https://item.szlcsc.com/171642.html) |
| **J2**<br>MIC L / JST-EH 2P | B2B-EH-A(LF)(SN)<br>C160262 | 插件,P=2.5mm<br>250V / 3A | EH2.5MM 2P直针座（50个）<br>EH 2P 直针座；按 EH2.5MM 2P 直针座选项购买。 | [商品](https://item.taobao.com/item.htm?id=832569969546) · [工程型号](https://item.szlcsc.com/171642.html) |
| **J4**<br>FH-00339 stock pins / Zero pair-map / bottom | FH-00339<br>C2685112 | SMD,P=2.54mm<br>3A | 2*20P 贴片排母【2个】<br>双排 2×20P、2.54mm、贴片排母，安装在 HAT 底面。 | [商品](https://item.taobao.com/item.htm?id=533725557959) · [工程型号](https://item.szlcsc.com/2784386.html) |
| **J5**<br>ToF / Qwiic / pad 0 GND | BM04B-SRSS-TB(LF)(SN)<br>C160390 | SMD,P=1mm<br>50V / 1A | 4P立贴（15个）<br>SH1.0 / 4P / 立贴，按“4P立贴（15个）”选项购买。 | [商品](https://item.taobao.com/item.htm?id=920058690376) · [工程型号](https://item.szlcsc.com/171770.html) |
| **J9**<br>MIC R / JST-EH 2P | B2B-EH-A(LF)(SN)<br>C160262 | 插件,P=2.5mm<br>250V / 3A | EH2.5MM 2P直针座（50个）<br>EH 2P 直针座；按 EH2.5MM 2P 直针座选项购买。 | [商品](https://item.taobao.com/item.htm?id=832569969546) · [工程型号](https://item.szlcsc.com/171642.html) |
| **J13**<br>Dynamixel TTL 3P | B3B-EH-A(LF)(SN)<br>C160259 | 插件,P=2.5mm<br>250V / 3A | EH2.5MM 3P直针座（50个）<br>EH 3P 直针座，HAT 两只、IMU 一只。 | [商品](https://item.taobao.com/item.htm?id=832569969546) · [工程型号](https://item.szlcsc.com/171639.html) |
| **J14**<br>Dynamixel TTL 3P | B3B-EH-A(LF)(SN)<br>C160259 | 插件,P=2.5mm<br>250V / 3A | EH2.5MM 3P直针座（50个）<br>EH 3P 直针座，HAT 两只、IMU 一只。 | [商品](https://item.taobao.com/item.htm?id=832569969546) · [工程型号](https://item.szlcsc.com/171639.html) |
| **L4**<br>6.8uH / 3A / Isat 4.3A | SWPA6045S6R8MT<br>C57254 | SMD,6x6mm<br>6.8uH / ±20% / 3A | 合金0630 6.8UH 印6R8 10个 6A 一体<br>实际使用：合金0630、6.8uH、6A一体成型电感（订单标称）。 | [商品](https://item.taobao.com/item.htm?id=598174251748) · [工程型号](https://item.szlcsc.com/58286.html) |
| **MK1**<br>Onboard analog MEMS MIC | LMA2718T421-OA5-2<br>C7587901 | SMD-4P,2.8x1.9mm<br>指向性:全指向；信噪比:55dB；灵敏度:-42dB；阻抗:300Ω | 2718 上进音 硅麦克风【2个】<br>实际使用：2718 上进音模拟 MEMS 麦克风，按“2718 上进音 硅麦克风【2个】”购买。 | [商品](https://item.taobao.com/item.htm?id=996702312391) · [工程型号](https://item.szlcsc.com/8705873.html) |
| **Q1**<br>MMBT3906 / direction | MMBT3906<br>C727128 | SOT-23<br>晶体管类型:PNP；集电极电流(Ic):200mA；集射极击穿电压(Vceo):40V；耗散功率(Pd):200mW；直流电流增益(hFE):100@10mA,1V | MMBT3906 丝印2A SOT-23(50个)<br>选择 MMBT3906 / PNP / SOT-23 款式。 | [商品](https://item.taobao.com/item.htm?id=944306254140) · [工程型号](https://item.szlcsc.com/774233.html) |
| **Q2**<br>SI2312 / ideal diode MOS | SI2312CDS-T1-GE3<br>C142518 | SOT-23<br>数量:1个N沟道；漏源电压(Vdss):20V；连续漏极电流(Id):6A；导通电阻(RDS(on)):41.4mΩ@1.8V,5.6A；耗散功率(Pd):2.1W；阈值电压(Vgs(th)):1V@250uA | SI2312DS（AE9T）N沟道（20只）<br>实际使用：SI2312DS（AE9T）N沟道，20只包装。 | [商品](https://item.taobao.com/item.htm?id=909264246006) · [工程型号](https://item.szlcsc.com/153849.html) |
| **R1**<br>10k / INL | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R2**<br>10k / INR | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R3**<br>0R / SHDN high | 0603WAF0000T5E<br>C21189 | 0603<br>0Ω / ±1% / - / 100mW | 0R/0欧;0603 1%（100个）<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/21903.html) |
| **R4**<br>0R / MUTE high | 0603WAF0000T5E<br>C21189 | 0603<br>0Ω / ±1% / - / 100mW | 0R/0欧;0603 1%（100个）<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/21903.html) |
| **R5**<br>0R / MODE high | 0603WAF0000T5E<br>C21189 | 0603<br>0Ω / ±1% / - / 100mW | 0R/0欧;0603 1%（100个）<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/21903.html) |
| **R6**<br>10k / codec reset | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R7**<br>0R / MIC2L to GND | 0603WAF0000T5E<br>C21189 | 0603<br>0Ω / ±1% / - / 100mW | 0R/0欧;0603 1%（100个）<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/21903.html) |
| **R8**<br>100R | 0603WAF1000T5E<br>C22775 | 0603<br>100Ω / ±1% / ±200ppm/℃ / 100mW | 100R/100欧;0603 1%（100个）<br>100Ω / ±1% / 0603，用于 HAT R8。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://www.lcsc.com/product-detail/C22775.html) |
| **R12**<br>10k / SDA pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R13**<br>10k / SCL pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R22**<br>10k / MIC L bias | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R23**<br>10k / MIC R bias | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R26**<br>10k / UART TX pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R27**<br>10k / direction base | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R28**<br>20k / direction pull-down | 0603WAF2002T5E<br>C4184 | 0603<br>20kΩ / ±1% / ±100ppm/℃ / 100mW | 20K;0603 1%（100个）<br>20kΩ / ±1% / 0603。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/4591.html) |
| **R29**<br>10k / RX gate enable | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R31**<br>10k / RX pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R32**<br>10k / data pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R33**<br>150R / bus series | 0603WAF1500T5E<br>C22808 | 0603<br>150Ω / ±1% / ±100ppm/℃ / 100mW | 0603WAF0000T5E<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://www.lcsc.com/product-detail/C22808.html) |
| **TH1**<br>100R PTC | PRG18BB101MB1RB<br>C913703 | 0603<br>100Ω / PTC / 村田 | 100R  PRG18BB101MB1RB<br>TH1可使用原村田PRG18BB101MB1RB（100Ω PTC，0603），按原订单100R款式采购；R33使用0Ω。 | [商品](https://item.taobao.com/item.htm?id=582129955778) · [工程型号](https://item.szlcsc.com/984022.html) |
| **U1**<br>PAM8406D | PAM8406DR<br>C86270 | SOIC-16<br>功放类型:AB类功放；D类功放；扬声器通道数:双声道；输出功率:5Wx2@2Ω；静态电流(Iq):10mA | PAM8406DR<br>实际使用：PAM8406DR，订单标注 SOP16。 | [商品](https://item.taobao.com/item.htm?id=808484505787) · [工程型号](https://item.szlcsc.com/87446.html) |
| **U2**<br>TLV320AIC3104IRHBR | TLV320AIC3104IRHBR<br>C181753 | HVQFN-32-EP(5x5)<br>类型:编解码器；接口类型:I2S；I2C；采样率:8kHz~96kHz | 商品无选项，按商品标题完整型号购买<br>TLV320AIC3104IRHBR，按商品完整型号购买。 | [商品](https://item.taobao.com/item.htm?id=908248360601) · [工程型号](https://www.lcsc.com/product-detail/C181753.html) |
| **U3**<br>XC6206P182 / 1V8 | XC6206P182MR<br>C347373 | SOT-23<br>输出极性:正极；工作电压:8V；输出电压:1.8V；输出电流:250mA；电源纹波抑制比(PSRR):40dB@(1kHz)；输出类型:固定 | XC6206P182MR 65K5 SOT-23 (20个)<br>XC6206P182MR / 1.8V / SOT-23，20个包装。 | [商品](https://item.taobao.com/item.htm?id=762173333947) · [工程型号](https://item.szlcsc.com/324033.html) |
| **U5**<br>74LVC1G08 / RX gate | SN74LVC1G08DBVR<br>C7666 | SOT-23-5<br>逻辑类型:与门；通道数:1；工作电压:1.65V~5.5V；静态电流(Iq):10uA；传播延迟(tpd):4ns@5V,50pF | SN74LVC1G08DBVR;5个全国包邮<br>SN74LVC1G08DBVR / SOT-23-5 与门，按同页对应型号选项购买。 | [商品](https://item.taobao.com/item.htm?id=902117985110) · [工程型号](https://www.lcsc.com/product-detail/C7666.html) |
| **U6**<br>SN74LVC1G125 / RX | SN74LVC1G125DBVR-TP<br>C3040625 | SOT-23-5<br>输入类型:-；工作电压:1.65V~5.5V；元件数:1；每个元件位数:-；灌电流(IOL):24mA；拉电流(IOH):24mA | SN74LVC1G125DBVR;5个全国包邮<br>实际使用：SN74LVC1G125DBVR / SOT-23-5，5个包装。 | [商品](https://item.taobao.com/item.htm?id=902117985110) · [工程型号](https://item.szlcsc.com/3597950.html) |
| **U7**<br>SN74LVC1G126 / TX | SN74LVC1G126DBVR<br>C7834 | SOT-23-5<br>输入类型:-；工作电压:1.65V~5.5V；元件数:1；每个元件位数:1；灌电流(IOL):32mA；拉电流(IOH):32mA | SN74LVC1G126DBVR;5个全国包邮<br>实际使用：SN74LVC1G126DBVR / SOT-23-5，5个包装。 | [商品](https://item.taobao.com/item.htm?id=902117985110) · [工程型号](https://www.lcsc.com/product-detail/C7834.html) |
| **U9**<br>AP63205 / 5V buck | AP63205WU-7<br>C2071056 | TSOT-23-6<br>功能类型:降压型；工作电压:3.8V~32V；输出电压:5V；输出电流:2A；输出类型:固定 | AP63205WU-7<br>AP63205WU-7，固定5V降压芯片，按对应完整型号购买。 | [商品](https://item.taobao.com/item.htm?id=969642590399) · [工程型号](https://item.szlcsc.com/2162639.html) |
| **U10**<br>LM5050-1 | LM5050MKX-1/NOPB<br>C473393 | TSOT-23-6<br>LM5050-1 5V 至 75V、400uA IQ ORing FET 控制器 | SOT-23;LM5050MKX-1/NOPB  原装正品<br>LM5050MKX-1/NOPB，按完整型号购买。 | [商品](https://item.taobao.com/item.htm?id=1013388982214) · [工程型号](https://www.lcsc.com/product-detail/C473393.html) |
| **Y1**<br>12MHz | OT3EL89CJI-111YLC-12M<br>C7425459 | SMD2520-4P<br>12MHz | 12MHZ 1.2V~3.36V宽压[高精度10PPM];SMD2520-4P CMOS输出<br>实际使用：12MHz、2520-4P、CMOS输出有源晶振，宽压1.2V~3.36V（订单标称）。 | [商品](https://item.taobao.com/item.htm?id=944053669860) · [工程型号](https://item.szlcsc.com/8414369.html) |

</details>

<details>
<summary>IMU 完整位号 BOM（25个器件，点击展开）</summary>

| 位号 / 用途 | 工程型号 / 立创料号 | 工程封装 / 参数 | 实际购买款式 / 用料说明 | 链接 |
| --- | --- | --- | --- | --- |
| **C1**<br>4.7uF 25V | CL21A475KAQNNNE<br>C1779 | 0805<br>4.7uF / ±10% / 25V / X5R | 0805 4.7UF ±10% X7R;25V<br>实际采购：0805 / 4.7uF / ±10% / 25V / X7R。 | [商品](https://item.taobao.com/item.htm?id=977236759812) · [工程型号](https://www.lcsc.com/product-detail/C1779.html) |
| **C2**<br>100nF 50V | CL10B104JB8NNNC<br>C24452 | 0603<br>100nF / ±5% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/25192.html) |
| **C3**<br>4.7uF 25V | CL21A475KAQNNNE<br>C1779 | 0805<br>4.7uF / ±10% / 25V / X5R | 0805 4.7UF ±10% X7R;25V<br>实际采购：0805 / 4.7uF / ±10% / 25V / X7R。 | [商品](https://item.taobao.com/item.htm?id=977236759812) · [工程型号](https://www.lcsc.com/product-detail/C1779.html) |
| **C4**<br>100nF 50V | CL10B104JB8NNNC<br>C24452 | 0603<br>100nF / ±5% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/25192.html) |
| **C5**<br>100nF / MCU | CL10B104JB8NNNC<br>C24452 | 0603<br>100nF / ±5% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/25192.html) |
| **C6**<br>1uF / MCU | CL10A105KB8NNNC<br>C15849 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://item.szlcsc.com/16531.html) |
| **C7**<br>100nF / VDD_IO | CL10B104JB8NNNC<br>C24452 | 0603<br>100nF / ±5% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/25192.html) |
| **C8**<br>100nF / VDD | CL10B104JB8NNNC<br>C24452 | 0603<br>100nF / ±5% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/25192.html) |
| **C9**<br>1uF / IMU local | CL10A105KB8NNNC<br>C15849 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=630712731066) · [工程型号](https://item.szlcsc.com/16531.html) |
| **C10**<br>100nF / buffer | CL10B104JB8NNNC<br>C24452 | 0603<br>100nF / ±5% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [商品](https://item.taobao.com/item.htm?id=731471380840) · [工程型号](https://item.szlcsc.com/25192.html) |
| **D1**<br>PESD5V0S1BA / 5V bidirectional | PESD5V0S1BA<br>C330094 | SOD-323<br>反向截止电压(Vrwm):5V@Max；最大钳位电压:10V；峰值脉冲电流(Ipp)@10/1000us:5A@8/20us；击穿电压:5.8V | 商品无选项，按商品标题完整型号购买<br>PESD5V0S1BA / SOD-323 双向TVS，按商品完整型号购买。 | [商品](https://item.taobao.com/item.htm?id=891785167202) · [工程型号](https://www.lcsc.com/product-detail/C330094.html) |
| **D2**<br>DEBUG LED | 19-217/GHC-YR1S2/3T<br>C72043 | 0603<br>110mW | 0603 蓝色=100个<br>实际采购：0603 蓝色LED，100个包装。 | [商品](https://item.taobao.com/item.htm?id=1025817117811) · [工程型号](https://www.lcsc.com/product-detail/Light-Emitting-Diodes-LED_Everlight-Elec-19-217-GHC-YR1S2-3T_C72043.html) |
| **J1**<br>DXL BUS / JST EH 3P | B3B-EH-A(LF)(SN)<br>C160259 | 插件,P=2.5mm<br>250V / 3A | EH2.5MM 3P直针座（50个）<br>EH 3P 直针座，HAT 两只、IMU 一只。 | [商品](https://item.taobao.com/item.htm?id=832569969546) · [工程型号](https://item.szlcsc.com/171639.html) |
| **J2**<br>SWD 1x5 | PZ254V-11-05P<br>C492404 | 插件,P=2.54mm<br>3A | 1*5P直针 铜（30条）<br>1×5P / 2.54mm 直排针，用于SWD烧录口。 | [商品](https://item.taobao.com/item.htm?id=606816197525) · [工程型号](https://item.szlcsc.com/502960.html) |
| **R1**<br>0R / DXL_VDD link | 0603WAF0000T5E<br>C21189 | 0603<br>0Ω / ±1% / - / 100mW | 0R/0欧;0603 1%（100个）<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/21903.html) |
| **R2**<br>10k / NRST pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R3**<br>100k / BOOT0 pull-down | RC0603FR-07100KL<br>C14675 | 0603<br>100kΩ / ±1% / ±100ppm/℃ / 100mW | 100K;0603 1%（100个）<br>100kΩ / ±1% / 0603。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/15343.html) |
| **R4**<br>10k / IMU CS pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R5**<br>10k / TX disable pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/99429.html) |
| **R6**<br>33R / DXL TX series | 0603WAF330JT5E<br>C23140 | 0603<br>33Ω / ±1% / ±100ppm/℃ / 100mW | 33R/33欧;0603 1%（100个）<br>33Ω / ±1% / 0603，用于IMU R6。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/23867.html) |
| **R7**<br>1k / debug LED | 0603WAF1001T5E<br>C21190 | 0603<br>1kΩ / ±1% / ±100ppm/℃ / 100mW | 1K;0603 1%（100个）<br>1kΩ / ±1% / 0603，八月备料订单。 | [商品](https://item.taobao.com/item.htm?id=947267344247) · [工程型号](https://item.szlcsc.com/21904.html) |
| **U1**<br>STM32G031F8P6 | STM32G031F8P6<br>C529334 | TSSOP-20<br>CPU内核:ARM Cortex-M0+；CPU最大主频:64MHz；CPU位数:32 Bit | 全新原装<br>STM32G031F8P6 / TSSOP-20，按商品完整型号购买。 | [商品](https://item.taobao.com/item.htm?id=726808419708) · [工程型号](https://item.szlcsc.com/549612.html) |
| **U2**<br>LSM6DSV16XTR | LSM6DSV16XTR<br>C5267406 | LGA-14(2.5x3)<br>传感器类型:IMU(加速度计+陀螺仪)；接口类型:I2C；SPI | LSM6DSV16XTR<br>LSM6DSV16XTR / LGA-14；指定购买 LSM6DSV16XTR，参考单价 ¥13.80/个。 | [商品](https://e.tb.cn/h.j3ZZ8HNmUBbhzqy?tk=jMe5TxTIPLE) · [工程型号](https://item.szlcsc.com/5993815.html) |
| **U3**<br>TLV70433DBVR | TLV70433DBVR<br>C94917 | SOT-23-5<br>输出极性:正极；工作电压:24V；输出电压:3.3V；输出电流:150mA；电源纹波抑制比(PSRR):60dB@(100kHz)；输出类型:固定 | TLV70433DBVR<br>TLV70433DBVR / 3.3V / SOT-23-5。 | [商品](https://item.taobao.com/item.htm?id=747094785928) · [工程型号](https://www.lcsc.com/product-detail/C94917.html) |
| **U4**<br>SN74LVC2G125DCUR | SN74LVC2G125DCUR<br>C21404 | VSSOP-8<br>输入类型:-；工作电压:1.65V~5.5V；元件数:2；每个元件位数:1；灌电流(IOL):32mA；拉电流(IOH):32mA | 商品无选项，按商品标题完整型号购买<br>SN74LVC2G125DCUR / VSSOP-8，按商品完整型号购买。 | [商品](https://item.taobao.com/item.htm?id=705642638300) · [工程型号](https://www.lcsc.com/product-detail/C21404.html) |

</details>
