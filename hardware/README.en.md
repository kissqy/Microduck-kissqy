[简体中文](README.md) | **English**

# DIY HAT and IMU hardware

> [!WARNING]
> Only the **HAT, IMU and HUB** versions published in this repository are supported.
>
> No commercial organization has been authorized. For commercial use, [contact the author](https://github.com/kissqy/Microduck-kissqy/blob/main/docs/assets/purchase-wechat-qr.jpg) and follow the [license terms](https://github.com/kissqy/Microduck-kissqy/blob/main/LICENSE).

> 🛒 **[Buy HAT / IMU boards from the author](https://item.taobao.com/item.htm?id=1095121548583)**
>
> **The author's assembled HAT / IMU boards are designed and laid out by the author, refined through extended real-robot use, and SMT assembled by JLCPCB, with a focus on stability and easier replication.**
>
> They combine power, communication, audio and orientation-feedback requirements to reduce separate purchases and DIY fabrication costs.
>
> **The assembled IMU comes preflashed with FT6 firmware; no initial flashing is needed.** Each robot still requires its own servo and IMU calibration after installation.
>
> Original designs and project files that the author has the right to license are provided for personal learning and noncommercial replication. Commercial use, mass production or reproduction for sale requires the author's prior written permission. Third-party material retains its original license; see the [board design license](LICENSE) · [component licenses](../LICENSE).

**[🔧 Assembly notes: 5 GHz Wi-Fi for ZERO; the HUB includes the 1000 µF main-power buffer capacitor, with no separate purchase needed; wiring and precautions](../docs/ASSEMBLY-NOTES.en.md)**

**The original HAT and independent torso IMU have passed extended real-robot use and operate normally. An AMP2.0 connector variant is also available.**

**Use the [IMU FT6 download and flashing guide](IMU-FIRMWARE.en.md) for a self-soldered board, replacement MCU, maintenance or upgrades. The author's assembled IMU already has FT6 and needs no reflashing for initial assembly.** STM32 IMU firmware and ZERO control.43 services are installed separately.

🖨️ The [complete FrankenDuck printing set and plate project](3d-print-frankenduck/README.en.md) is available separately, with two battery holders and a foot kit that accepts rollers without removing servos.

**Both connector versions are retained. Choose for your wiring.** [AMP2.0 connectors, LED, and parts](AMP2.0-VERSION.en.md).

| Hardware | Original EH2.5 · October 7, 2026 | AMP2.0 · October 15, 2026 | Build record |
| --- | --- | --- | --- |
| HAT | [EH2.5 project](ProPrj_HAT_REVA_SCH_2026-10-07.epro2) | [AMP2.0 project](ProPrj_HAT_REVA_SCH_2026-10-15.epro2), HP1.25 audio, added LED + 1kΩ | [Timeline](HAT-TIMELINE.en.md) |
| Torso IMU | [EH2.5 project](ProPrj_imu_to_dxl_RevA_V1_2026-10-07.epro2) | [AMP2.0 project](ProPrj_imu_to_dxl_RevA_V1_2026-10-15.epro2) | [Build video](https://www.bilibili.com/video/BV1qapz6PERs/) · [Timeline](IMU-TIMELINE.en.md) |

The HAT started with a study of the official components and their surrounding circuits. Unneeded functions were removed, and the board was made using a two-layer PCB and home reflow. The IMU first established working independent hardware and the original protocol, then reused that hardware on the Feetech bus with 15 servos.

The timelines follow the build history organized on October 12, 2026. Original projects are dated October 7, 2026; the AMP2.0 variant is dated October 15, 2026. Differences between physical-board tuning and the project BOM are documented in the HAT guide.

**Current baseline, confirmed October 12, 2026:** fabrication, full-robot integration, and extended real-robot validation are complete for both boards. IMU fabrication and Feetech adaptation test records are in the timeline.

> [!NOTE]
> **🌙 A little aside · An evening for building a board**
>
> Pick an evening when your wife and kids are asleep and you have no work tomorrow. Dinner is finished, the house is clean, and you have had a shower.
>
> Unpack the PCB that arrived today and your pile of components. Pick up your tweezers and put on a song you love. 🎵
>
> One by one, the components settle into place as time quietly slips by. Before you know it, a perfect circuit board is finished. ✨

## Shopping list

**Version scope: the procurement tables, historical prices, and Excel below describe the original EH2.5 version. For AMP2.0 connectors and added parts, use the [separate parts guide](AMP2.0-VERSION.en.md).**

> [!IMPORTANT]
> **Purchased by the author, selected after price comparisons, and verified on the real robot**
>
> Every item in this list was selected by the author after comparing prices at the time of purchase, favoring **free shipping and competitive prices** wherever possible while meeting the project's needs and keeping build costs down.
>
> The listed items have been verified through a period of actual use. **HAT and IMU communication, functionality, and operating stability meet the project's requirements.** Use the product links and select the exact models and variants listed in the tables.

**Current procurement: TH1 can use the original Murata PRG18BB101MB1RB (100Ω PTC, 0603); R33 uses 0Ω / 0603.**

This is the duck build’s **🔧 PCB procurement branch**. Preview the HAT and IMU shopping tables directly below; no spreadsheet download is required.

**Quantities:** one HAT plus one IMU, with **84 + 25 = 109 board-mounted components** across 46 BOM groups. Duck body parts and tools are separate categories in the main duck guide. Select the **exact purchase variant** in each row; project model links provide the engineering reference. Taobao variant labels, specifications, and purchase notes are retained in Chinese to match the seller pages.

Minimum pack counts below apply to each row for one set. Rows with the same product and variant can be combined before rounding up to whole packs.

[🦆 Main duck shopping guide](../DUCK-SHOPPING-LIST.en.md) · [Build cost](#build-cost) · [Board components](#board-components) · [Bare PCB fabrication](#bare-pcbs-and-fabrication) · [Full reference-designator BOMs](#full-reference-designator-boms) · [🧰 Tools](../docs/BUILD-TOOLS.en.md) · [Excel snapshot (2026-10-13, Chinese; use this page for current purchases)](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/hardware/Microduck-HAT-IMU-Shopping-List-20261013.xlsx)

### Build cost

| Board | DIY materials · free PCB coupons | DIY materials · no coupons | Assembled board |
| --- | ---: | ---: | ---: |
| HAT | ¥16.72 | ¥20.72 | [¥119](https://item.taobao.com/item.htm?id=1095121548583) |
| IMU (assembled: FT6 preflashed) | ¥20.38 | ¥24.38 | [¥99](https://item.taobao.com/item.htm?id=1095121548583) |
| **Both boards** | **¥37.11** | **¥45.11** | **¥218** |

DIY amounts above cover parts fitted to the boards, excluding tools and labor. For the first purchase, use full-pack amounts below and add **¥800–1000** for [tools and consumables](../docs/BUILD-TOOLS.en.md#budgeting-for-tools-from-scratch); assembled boards are ready to use.

| First component purchase | HAT only | IMU only | Both, shared packs combined |
| --- | ---: | ---: | ---: |
| Free PCB coupons | ¥66.88 | ¥35.20 | ¥94.22 |
| No coupons · five PCBs per design | ¥86.88 | ¥55.20 | ¥134.22 |

PCB reference: ¥20 for five of one design without coupons. U2 LSM6DSV16XTR: ¥13.80 each; other component costs use historical order allocations. Stencils are included in the separate tool budget; shipping is extra.

<details>
<summary>Component cost breakdown — 46 BOM groups</summary>

Recorded product prices are per purchase unit. Allocated per-component costs include proportional historical shipping and payment adjustments. Totals are calculated before rounding.

| Model / purchase variant | Pieces per pack | Recorded product price per pack | Allocated cost per piece | HAT: pcs / cost | IMU: pcs / cost |
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

### Board components

#### HAT and IMU board components

##### Capacitors

| Project model / current component | Exact purchase variant and notes | HAT: pcs / refs | IMU: pcs / refs | Pack / minimum packs per set | Shop / product |
| --- | --- | --- | --- | --- | --- |
| [CC0603KRX5R9BB105](https://www.lcsc.com/product-detail/C128624.html)<br>0603；1uF / ±10% / 50V / X5R | **0603 1uF ±10% X7R;50V**<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | **15**<br>C1, C2, C3, C4, C6, C10, C27, C29, C31, C33, C35, C40, C41, C42, C43 | — | 1 pcs / pack<br>**15 pack(s)** | 深圳市宏宸电子<br>[Product](https://item.taobao.com/item.htm?id=630712731066) |
| [C1608X5R1A106KT000E](https://item.szlcsc.com/77735.html)<br>0603；10uF / ±10% / 10V / X5R | **0603 10uF ±10% X5R;10V**<br>实际采购：0603 / 10uF / ±10% / 10V / X5R。 | **5**<br>C5, C7, C12, C13, C37 | — | 1 pcs / pack<br>**5 pack(s)** | 深圳市宏宸电子<br>[Product](https://item.taobao.com/item.htm?id=630712731066) |
| [0603CG221J500NT](https://item.szlcsc.com/167743.html)<br>0603；220pF / ±5% / 50V / C0G | **0603 220pF ±5% NPO/COG;50V;100个**<br>选 220pF、50V、C0G(NPO)、±5%、0603；同页其他容量分别选购。 | **2**<br>C8, C9 | — | 100 pcs / pack<br>**1 pack(s)** | 深圳市宏宸电子<br>[Product](https://item.taobao.com/item.htm?id=1005108810412) |
| [CC0603KRX7R9BB104](https://item.szlcsc.com/15331.html)<br>0603；100nF / ±10% / 50V / X7R | **0603 100nF ±10% X7R;50V;100个**<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | **13**<br>C11, C14, C16, C17, C18, C20, C26, C28, C30, C32, C36, C38, C39 | — | 100 pcs / pack<br>**1 pack(s)** | 深圳市宏宸电子<br>[Product](https://item.taobao.com/item.htm?id=731471380840) |
| [C3216X7R1V106KT000E](https://item.szlcsc.com/77793.html)<br>1206；10uF / ±10% / 35V / X7R | **1206 10UF ±10% X7R;35V**<br>C15 使用 1206、10uF、35V、X7R 款式。 | **1**<br>C15 | — | 1 pcs / pack<br>**1 pack(s)** | 深圳市宏宸电子<br>[Product](https://item.taobao.com/item.htm?id=730407108775) |
| [GRM188R61A226ME15D](https://item.szlcsc.com/85589.html)<br>0603；22uF / ±20% / 10V / X5R | **22UF 226K 10% X5R;10V;0603=100个**<br>实际采购：0603 / 22uF / ±10% / 10V / X5R。 | **2**<br>C21, C22 | — | 100 pcs / pack<br>**1 pack(s)** | 优好电子<br>[Product](https://item.taobao.com/item.htm?id=993202872551) |
| [CC0603KRX7R9BB103](https://item.szlcsc.com/101256.html)<br>0603；10nF / ±10% / 50V / X7R | **0603 10NF 50V 10% 100个**<br>实际采购：0603 / 10nF / ±10% / 50V / X7R。 | **1**<br>C34 | — | 100 pcs / pack<br>**1 pack(s)** | 欧贝顿旗舰店<br>[Product](https://item.taobao.com/item.htm?id=610558214623) |
| [CL21A475KAQNNNE](https://www.lcsc.com/product-detail/C1779.html)<br>0805；4.7uF / ±10% / 25V / X5R | **0805 4.7UF ±10% X7R;25V**<br>实际采购：0805 / 4.7uF / ±10% / 25V / X7R。 | — | **2**<br>C1, C3 | 1 pcs / pack<br>**2 pack(s)** | 深圳市宏宸电子<br>[Product](https://item.taobao.com/item.htm?id=977236759812) |
| [CL10B104JB8NNNC](https://item.szlcsc.com/25192.html)<br>0603；100nF / ±5% / 50V / X7R | **0603 100nF ±10% X7R;50V;100个**<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | — | **6**<br>C2, C4, C5, C7, C8, C10 | 100 pcs / pack<br>**1 pack(s)** | 深圳市宏宸电子<br>[Product](https://item.taobao.com/item.htm?id=731471380840) |
| [CL10A105KB8NNNC](https://item.szlcsc.com/16531.html)<br>0603；1uF / ±10% / 50V / X5R | **0603 1uF ±10% X7R;50V**<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | — | **2**<br>C6, C9 | 1 pcs / pack<br>**2 pack(s)** | 深圳市宏宸电子<br>[Product](https://item.taobao.com/item.htm?id=630712731066) |

##### Resistors and PTC thermistors

| Project model / current component | Exact purchase variant and notes | HAT: pcs / refs | IMU: pcs / refs | Pack / minimum packs per set | Shop / product |
| --- | --- | --- | --- | --- | --- |
| [RC0603FR-0710KL](https://item.szlcsc.com/99429.html)<br>0603；10kΩ / ±1% / ±100ppm/℃ / 100mW | **10K;0603 1%（100个）**<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | **12**<br>R1, R2, R6, R12, R13, R22, R23, R26, R27, R29, R31, R32 | **3**<br>R2, R4, R5 | 100 pcs / pack<br>**1 pack(s)** | 深圳市永芯泰电子企业店<br>[Product](https://item.taobao.com/item.htm?id=947267344247) |
| [0603WAF0000T5E](https://item.szlcsc.com/21903.html)<br>0603；0Ω / ±1% / 0603 | **0R/0欧;0603 1%（100个）**<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | **5**<br>R3, R4, R5, R7, R33 | **1**<br>R1 | 100 pcs / pack<br>**1 pack(s)** | 深圳市永芯泰电子企业店<br>[Product](https://item.taobao.com/item.htm?id=947267344247) |
| [0603WAF1000T5E](https://www.lcsc.com/product-detail/C22775.html)<br>0603；100Ω / ±1% / ±200ppm/℃ / 100mW | **100R/100欧;0603 1%（100个）**<br>100Ω / ±1% / 0603，用于 HAT R8。 | **1**<br>R8 | — | 100 pcs / pack<br>**1 pack(s)** | 深圳市永芯泰电子企业店<br>[Product](https://item.taobao.com/item.htm?id=947267344247) |
| [0603WAF2002T5E](https://item.szlcsc.com/4591.html)<br>0603；20kΩ / ±1% / ±100ppm/℃ / 100mW | **20K;0603 1%（100个）**<br>20kΩ / ±1% / 0603。 | **1**<br>R28 | — | 100 pcs / pack<br>**1 pack(s)** | 深圳市永芯泰电子企业店<br>[Product](https://item.taobao.com/item.htm?id=947267344247) |
| [PRG18BB101MB1RB](https://item.szlcsc.com/984022.html)<br>0603；100Ω / PTC / 村田 | **100R  PRG18BB101MB1RB**<br>TH1可使用原村田PRG18BB101MB1RB（100Ω PTC，0603），按原订单100R款式采购；R33使用0Ω。 | **1**<br>TH1 | — | 1 pc / purchase unit<br>**1 unit minimum** | 贤辉亿芯<br>[Product](https://item.taobao.com/item.htm?id=582129955778) |
| [RC0603FR-07100KL](https://item.szlcsc.com/15343.html)<br>0603；100kΩ / ±1% / ±100ppm/℃ / 100mW | **100K;0603 1%（100个）**<br>100kΩ / ±1% / 0603。 | — | **1**<br>R3 | 100 pcs / pack<br>**1 pack(s)** | 深圳市永芯泰电子企业店<br>[Product](https://item.taobao.com/item.htm?id=947267344247) |
| [0603WAF330JT5E](https://item.szlcsc.com/23867.html)<br>0603；33Ω / ±1% / ±100ppm/℃ / 100mW | **33R/33欧;0603 1%（100个）**<br>33Ω / ±1% / 0603，用于IMU R6。 | — | **1**<br>R6 | 100 pcs / pack<br>**1 pack(s)** | 深圳市永芯泰电子企业店<br>[Product](https://item.taobao.com/item.htm?id=947267344247) |
| [0603WAF1001T5E](https://item.szlcsc.com/21904.html)<br>0603；1kΩ / ±1% / ±100ppm/℃ / 100mW | **1K;0603 1%（100个）**<br>1kΩ / ±1% / 0603，八月备料订单。 | — | **1**<br>R7 | 100 pcs / pack<br>**1 pack(s)** | 深圳市永芯泰电子企业店<br>[Product](https://item.taobao.com/item.htm?id=947267344247) |

##### Ferrite beads, inductors, oscillator and microphone

| Project model / current component | Exact purchase variant and notes | HAT: pcs / refs | IMU: pcs / refs | Pack / minimum packs per set | Shop / product |
| --- | --- | --- | --- | --- | --- |
| [BLM18KG601SN1D](https://item.szlcsc.com/87009.html)<br>0603；±25% / 600Ω@100MHz / 1.3A | **0603_600R_1.3A_±25%【100只】**<br>实际采购：0603 / 600Ω@100MHz / 1.3A / ±25%。 | **1**<br>FB1 | — | 100 pcs / pack<br>**1 pack(s)** | 科芯奇旗舰店<br>[Product](https://item.taobao.com/item.htm?id=931081429973) |
| [PE-0603PFB121ST](https://item.szlcsc.com/2753383.html)<br>0603；±25% / 120Ω@100MHz / 2A | **0603_120R_2A_±25%【100只】**<br>实际采购：0603 / 120Ω@100MHz / 2A / ±25%。 | **2**<br>FB2, FB3 | — | 100 pcs / pack<br>**1 pack(s)** | 科芯奇旗舰店<br>[Product](https://item.taobao.com/item.htm?id=931081429973) |
| [SWPA6045S6R8MT](https://item.szlcsc.com/58286.html)<br>SMD,6x6mm；6.8uH / ±20% / 3A | **合金0630 6.8UH 印6R8 10个 6A 一体**<br>实际使用：合金0630、6.8uH、6A一体成型电感（订单标称）。 | **1**<br>L4 | — | 10 pcs / pack<br>**1 pack(s)** | 迪林旗舰店<br>[Product](https://item.taobao.com/item.htm?id=598174251748) |
| [LMA2718T421-OA5-2](https://item.szlcsc.com/8705873.html)<br>SMD-4P,2.8x1.9mm；指向性:全指向；信噪比:55dB；灵敏度:-42dB；阻抗:300Ω | **2718 上进音 硅麦克风【2个】**<br>实际使用：2718 上进音模拟 MEMS 麦克风，按“2718 上进音 硅麦克风【2个】”购买。 | **1**<br>MK1 | — | 2 pcs / pack<br>**1 pack(s)** | 深圳市华源芯电子有限公司 电子元器件配单<br>[Product](https://item.taobao.com/item.htm?id=996702312391) |
| [OT3EL89CJI-111YLC-12M](https://item.szlcsc.com/8414369.html)<br>SMD2520-4P；12MHz | **12MHZ 1.2V~3.36V宽压[高精度10PPM];SMD2520-4P CMOS输出**<br>实际使用：12MHz、2520-4P、CMOS输出有源晶振，宽压1.2V~3.36V（订单标称）。 | **1**<br>Y1 | — | 1 pcs / pack<br>**1 pack(s)** | 深圳市晶诺源电子<br>[Product](https://item.taobao.com/item.htm?id=944053669860) |

##### Board connectors

| Project model / current component | Exact purchase variant and notes | HAT: pcs / refs | IMU: pcs / refs | Pack / minimum packs per set | Shop / product |
| --- | --- | --- | --- | --- | --- |
| [B2B-EH-A(LF)(SN)](https://item.szlcsc.com/171642.html)<br>插件,P=2.5mm；250V / 3A | **EH2.5MM 2P直针座（50个）**<br>EH 2P 直针座；按 EH2.5MM 2P 直针座选项购买。 | **3**<br>J1, J2, J9 | — | 50 pcs / pack<br>**1 pack(s)** | 启色数码旗舰店<br>[Product](https://item.taobao.com/item.htm?id=832569969546) |
| [FH-00339](https://item.szlcsc.com/2784386.html)<br>SMD,P=2.54mm；3A | **2*20P 贴片排母【2个】**<br>双排 2×20P、2.54mm、贴片排母，安装在 HAT 底面。 | **1**<br>J4 | — | 2 pcs / pack<br>**1 pack(s)** | 海雀数码专营店<br>[Product](https://item.taobao.com/item.htm?id=533725557959) |
| [BM04B-SRSS-TB(LF)(SN)](https://item.szlcsc.com/171770.html)<br>SMD,P=1mm；50V / 1A | **4P立贴（15个）**<br>SH1.0 / 4P / 立贴，按“4P立贴（15个）”选项购买。 | **1**<br>J5 | — | 15 pcs / pack<br>**1 pack(s)** | 信容芯旗舰店<br>[Product](https://item.taobao.com/item.htm?id=920058690376) |
| [B3B-EH-A(LF)(SN)](https://item.szlcsc.com/171639.html)<br>插件,P=2.5mm；250V / 3A | **EH2.5MM 3P直针座（50个）**<br>EH 3P 直针座，HAT 两只、IMU 一只。 | **2**<br>J13, J14 | **1**<br>J1 | 50 pcs / pack<br>**1 pack(s)** | 启色数码旗舰店<br>[Product](https://item.taobao.com/item.htm?id=832569969546) |
| [PZ254V-11-05P](https://item.szlcsc.com/502960.html)<br>插件,P=2.54mm；3A | **1*5P直针 铜（30条）**<br>1×5P / 2.54mm 直排针，用于SWD烧录口。 | — | **1**<br>J2 | 30 pcs / pack<br>**1 pack(s)** | zxin旗舰店<br>[Product](https://item.taobao.com/item.htm?id=606816197525) |

##### ICs, diodes and transistors

| Project model / current component | Exact purchase variant and notes | HAT: pcs / refs | IMU: pcs / refs | Pack / minimum packs per set | Shop / product |
| --- | --- | --- | --- | --- | --- |
| [BAT54SW,115](https://item.szlcsc.com/79742.html)<br>SOT-323；二极管配置:1对串联式；正向压降(Vf):800mV@100mA；直流反向耐压(Vr):30V；整流电流:200mA | **BAT54SW 印字44t（20只）**<br>选择 BAT54SW / SOT-323 款式。 | **1**<br>D1 | — | 20 pcs / pack<br>**1 pack(s)** | 深圳市乐桥微科技<br>[Product](https://item.taobao.com/item.htm?id=793455311175) |
| [BZT52C5V1S-7-F](https://item.szlcsc.com/162688.html)<br>SOD-323；二极管配置:1个独立式；稳压值(标称值):5.1V；稳压值(范围值):4.8V~5.4V；耗散功率(Pd):200mW | **BZT52C5V1S W8 SOD-323 (50个)**<br>选择 BZT52C5V1S / 5.1V / SOD-323 款式。 | **1**<br>D4 | — | 50 pcs / pack<br>**1 pack(s)** | 稳泊仕旗舰店<br>[Product](https://item.taobao.com/item.htm?id=943185002457) |
| [MMBT3906](https://item.szlcsc.com/774233.html)<br>SOT-23；晶体管类型:PNP；集电极电流(Ic):200mA；集射极击穿电压(Vceo):40V；耗散功率(Pd):200mW；直流电流增益(hFE):100@10mA,1V | **MMBT3906 丝印2A SOT-23(50个)**<br>选择 MMBT3906 / PNP / SOT-23 款式。 | **1**<br>Q1 | — | 50 pcs / pack<br>**1 pack(s)** | 稳泊仕旗舰店<br>[Product](https://item.taobao.com/item.htm?id=944306254140) |
| [SI2312CDS-T1-GE3](https://item.szlcsc.com/153849.html)<br>SOT-23；数量:1个N沟道；漏源电压(Vdss):20V；连续漏极电流(Id):6A；导通电阻(RDS(on)):41.4mΩ@1.8V,5.6A；耗散功率(Pd):2.1W；阈值电压(Vgs(th)):1V@250uA | **SI2312DS（AE9T）N沟道（20只）**<br>实际使用：SI2312DS（AE9T）N沟道，20只包装。 | **1**<br>Q2 | — | 20 pcs / pack<br>**1 pack(s)** | 一芯向上电子<br>[Product](https://item.taobao.com/item.htm?id=909264246006) |
| [PAM8406DR](https://item.szlcsc.com/87446.html)<br>SOIC-16；功放类型:AB类功放；D类功放；扬声器通道数:双声道；输出功率:5Wx2@2Ω；静态电流(Iq):10mA | **PAM8406DR**<br>实际使用：PAM8406DR，订单标注 SOP16。 | **1**<br>U1 | — | 1 pcs / pack<br>**1 pack(s)** | 深圳市远大芯程科技<br>[Product](https://item.taobao.com/item.htm?id=808484505787) |
| [TLV320AIC3104IRHBR](https://www.lcsc.com/product-detail/C181753.html)<br>HVQFN-32-EP(5x5)；类型:编解码器；接口类型:I2S；I2C；采样率:8kHz~96kHz | **商品无选项，按商品标题完整型号购买**<br>TLV320AIC3104IRHBR，按商品完整型号购买。 | **1**<br>U2 | — | 1 pcs / pack<br>**1 pack(s)** | 淼鑫电子科技<br>[Product](https://item.taobao.com/item.htm?id=908248360601) |
| [XC6206P182MR](https://item.szlcsc.com/324033.html)<br>SOT-23；输出极性:正极；工作电压:8V；输出电压:1.8V；输出电流:250mA；电源纹波抑制比(PSRR):40dB@(1kHz)；输出类型:固定 | **XC6206P182MR 65K5 SOT-23 (20个)**<br>XC6206P182MR / 1.8V / SOT-23，20个包装。 | **1**<br>U3 | — | 20 pcs / pack<br>**1 pack(s)** | 启色数码旗舰店<br>[Product](https://item.taobao.com/item.htm?id=762173333947) |
| [SN74LVC1G08DBVR](https://www.lcsc.com/product-detail/C7666.html)<br>SOT-23-5；逻辑类型:与门；通道数:1；工作电压:1.65V~5.5V；静态电流(Iq):10uA；传播延迟(tpd):4ns@5V,50pF | **SN74LVC1G08DBVR;5个全国包邮**<br>SN74LVC1G08DBVR / SOT-23-5 与门，按同页对应型号选项购买。 | **1**<br>U5 | — | 5 pcs / pack<br>**1 pack(s)** | 深圳市德明电子贸易商城<br>[Product](https://item.taobao.com/item.htm?id=902117985110) |
| [SN74LVC1G125DBVR-TP](https://item.szlcsc.com/3597950.html)<br>SOT-23-5；输入类型:-；工作电压:1.65V~5.5V；元件数:1；每个元件位数:-；灌电流(IOL):24mA；拉电流(IOH):24mA | **SN74LVC1G125DBVR;5个全国包邮**<br>实际使用：SN74LVC1G125DBVR / SOT-23-5，5个包装。 | **1**<br>U6 | — | 5 pcs / pack<br>**1 pack(s)** | 深圳市德明电子贸易商城<br>[Product](https://item.taobao.com/item.htm?id=902117985110) |
| [SN74LVC1G126DBVR](https://www.lcsc.com/product-detail/C7834.html)<br>SOT-23-5；输入类型:-；工作电压:1.65V~5.5V；元件数:1；每个元件位数:1；灌电流(IOL):32mA；拉电流(IOH):32mA | **SN74LVC1G126DBVR;5个全国包邮**<br>实际使用：SN74LVC1G126DBVR / SOT-23-5，5个包装。 | **1**<br>U7 | — | 5 pcs / pack<br>**1 pack(s)** | 深圳市德明电子贸易商城<br>[Product](https://item.taobao.com/item.htm?id=902117985110) |
| [AP63205WU-7](https://item.szlcsc.com/2162639.html)<br>TSOT-23-6；功能类型:降压型；工作电压:3.8V~32V；输出电压:5V；输出电流:2A；输出类型:固定 | **AP63205WU-7**<br>AP63205WU-7，固定5V降压芯片，按对应完整型号购买。 | **1**<br>U9 | — | 1 pcs / pack<br>**1 pack(s)** | 深圳市远大芯程科技<br>[Product](https://item.taobao.com/item.htm?id=969642590399) |
| [LM5050MKX-1/NOPB](https://www.lcsc.com/product-detail/C473393.html)<br>TSOT-23-6；LM5050-1 5V 至 75V、400uA IQ ORing FET 控制器 | **SOT-23;LM5050MKX-1/NOPB  原装正品**<br>LM5050MKX-1/NOPB，按完整型号购买。 | **1**<br>U10 | — | 1 pcs / pack<br>**1 pack(s)** | 深圳市安芯选电子<br>[Product](https://item.taobao.com/item.htm?id=1013388982214) |
| [PESD5V0S1BA](https://www.lcsc.com/product-detail/C330094.html)<br>SOD-323；反向截止电压(Vrwm):5V@Max；最大钳位电压:10V；峰值脉冲电流(Ipp)@10/1000us:5A@8/20us；击穿电压:5.8V | **商品无选项，按商品标题完整型号购买**<br>PESD5V0S1BA / SOD-323 双向TVS，按商品完整型号购买。 | — | **1**<br>D1 | 1 pcs / pack<br>**1 pack(s)** | 深圳市优信电子科技有限公司<br>[Product](https://item.taobao.com/item.htm?id=891785167202) |
| [19-217/GHC-YR1S2/3T](https://www.lcsc.com/product-detail/Light-Emitting-Diodes-LED_Everlight-Elec-19-217-GHC-YR1S2-3T_C72043.html)<br>0603；110mW | **0603 蓝色=100个**<br>实际采购：0603 蓝色LED，100个包装。 | — | **1**<br>D2 | 100 pcs / pack<br>**1 pack(s)** | 泰辰电子<br>[Product](https://item.taobao.com/item.htm?id=1025817117811) |
| [STM32G031F8P6](https://item.szlcsc.com/549612.html)<br>TSSOP-20；CPU内核:ARM Cortex-M0+；CPU最大主频:64MHz；CPU位数:32 Bit | **全新原装**<br>STM32G031F8P6 / TSSOP-20，按商品完整型号购买。 | — | **1**<br>U1 | 1 pcs / pack<br>**1 pack(s)** | 深圳市新纶电子<br>[Product](https://item.taobao.com/item.htm?id=726808419708) |
| [LSM6DSV16XTR](https://item.szlcsc.com/5993815.html)<br>LGA-14(2.5x3)；传感器类型:IMU(加速度计+陀螺仪)；接口类型:I2C；SPI | **LSM6DSV16XTR**<br>LSM6DSV16XTR / LGA-14；指定购买 LSM6DSV16XTR，参考单价 ¥13.80/个。 | — | **1**<br>U2 | 1 pcs / pack<br>**1 pack(s)** | Taobao<br>[Product](https://e.tb.cn/h.j3ZZ8HNmUBbhzqy?tk=jMe5TxTIPLE) |
| [TLV70433DBVR](https://www.lcsc.com/product-detail/C94917.html)<br>SOT-23-5；输出极性:正极；工作电压:24V；输出电压:3.3V；输出电流:150mA；电源纹波抑制比(PSRR):60dB@(100kHz)；输出类型:固定 | **TLV70433DBVR**<br>TLV70433DBVR / 3.3V / SOT-23-5。 | — | **1**<br>U3 | 1 pcs / pack<br>**1 pack(s)** | 深圳市恒芯科创电子<br>[Product](https://item.taobao.com/item.htm?id=747094785928) |
| [SN74LVC2G125DCUR](https://www.lcsc.com/product-detail/C21404.html)<br>VSSOP-8；输入类型:-；工作电压:1.65V~5.5V；元件数:2；每个元件位数:1；灌电流(IOL):32mA；拉电流(IOH):32mA | **商品无选项，按商品标题完整型号购买**<br>SN74LVC2G125DCUR / VSSOP-8，按商品完整型号购买。 | — | **1**<br>U4 | 1 pcs / pack<br>**1 pack(s)** | 深圳市垚鑫电子科技<br>[Product](https://item.taobao.com/item.htm?id=705642638300) |

#### Bare PCBs and fabrication

| Item | Exact variant / specification | Quantity / use | Recorded price / purchase unit | Shop / product |
| --- | --- | --- | --- | --- |
| HAT 裸板 | **定制打样入口，不是现成商品**<br>HAT-V5，65×30.9mm，两层板；按对应工程生成生产资料 | 有券免费；无券20元5张（4元/张）<br>裸板需定制；R33按0Ω采购，TH1可用原村田PRG18BB101MB1RB；使用本项目对应工程。 | — | PCB打样平台<br>[Product](https://www.jlc.com/) |
| IMU 裸板 | **定制打样入口，不是现成商品**<br>IMU-TO-DLX-V2；按对应工程生成生产资料 | 有券免费；无券20元5张（4元/张）<br>使用对应 IMU 工程，裸板不是可直接购买的标准模块。 | — | PCB打样平台<br>[Product](https://www.jlc.com/) |

### Full reference-designator BOMs

Expand either table to inspect each component. Project attributes and the actual purchase variant are shown side by side. HAT R33 uses 0Ω; TH1 can use the original Murata PRG18BB101MB1RB (100Ω PTC, 0603). The original engineering values remain visible below.

<details>
<summary>HAT: full reference-designator BOM (84 components)</summary>

| Ref / function | Project model / part code | Project package / specification | Actual purchase variant / notes | Links |
| --- | --- | --- | --- | --- |
| **C1**<br>1uF / left AC coupling | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C2**<br>1uF / right AC coupling | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C3**<br>1uF / VREF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C4**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C5**<br>10uF | C1608X5R1A106KT000E<br>C76608 | 0603<br>10uF / ±10% / 10V / X5R | 0603 10uF ±10% X5R;10V<br>实际采购：0603 / 10uF / ±10% / 10V / X5R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://item.szlcsc.com/77735.html) |
| **C6**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C7**<br>10uF | C1608X5R1A106KT000E<br>C76608 | 0603<br>10uF / ±10% / 10V / X5R | 0603 10uF ±10% X5R;10V<br>实际采购：0603 / 10uF / ±10% / 10V / X5R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://item.szlcsc.com/77735.html) |
| **C8**<br>0603CG221J500NT | 0603CG221J500NT<br>C156398 | 0603<br>220pF / ±5% / 50V / C0G | 0603 220pF ±5% NPO/COG;50V;100个<br>选 220pF、50V、C0G(NPO)、±5%、0603；同页其他容量分别选购。 | [Product](https://item.taobao.com/item.htm?id=1005108810412) · [Project model](https://item.szlcsc.com/167743.html) |
| **C9**<br>0603CG221J500NT | 0603CG221J500NT<br>C156398 | 0603<br>220pF / ±5% / 50V / C0G | 0603 220pF ±5% NPO/COG;50V;100个<br>选 220pF、50V、C0G(NPO)、±5%、0603；同页其他容量分别选购。 | [Product](https://item.taobao.com/item.htm?id=1005108810412) · [Project model](https://item.szlcsc.com/167743.html) |
| **C10**<br>1uF / onboard MIC coupling | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C11**<br>100nF / onboard MIC | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/15331.html) |
| **C12**<br>10uF / 1V8 | C1608X5R1A106KT000E<br>C76608 | 0603<br>10uF / ±10% / 10V / X5R | 0603 10uF ±10% X5R;10V<br>实际采购：0603 / 10uF / ±10% / 10V / X5R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://item.szlcsc.com/77735.html) |
| **C13**<br>10uF / 3V3 | C1608X5R1A106KT000E<br>C76608 | 0603<br>10uF / ±10% / 10V / X5R | 0603 10uF ±10% X5R;10V<br>实际采购：0603 / 10uF / ±10% / 10V / X5R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://item.szlcsc.com/77735.html) |
| **C14**<br>100nF / oscillator | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/15331.html) |
| **C15**<br>C3216X7R1V106KT000E | C3216X7R1V106KT000E<br>C76666 | 1206<br>10uF / ±10% / 35V / X7R | 1206 10UF ±10% X7R;35V<br>C15 使用 1206、10uF、35V、X7R 款式。 | [Product](https://item.taobao.com/item.htm?id=730407108775) · [Project model](https://item.szlcsc.com/77793.html) |
| **C16**<br>100nF / U5 | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/15331.html) |
| **C17**<br>100nF / U6 | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/15331.html) |
| **C18**<br>100nF / U7 | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/15331.html) |
| **C20**<br>100nF 50V / bootstrap | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/15331.html) |
| **C21**<br>22uF 10V X5R | GRM188R61A226ME15D<br>C84419 | 0603<br>22uF / ±20% / 10V / X5R | 22UF 226K 10% X5R;10V;0603=100个<br>实际采购：0603 / 22uF / ±10% / 10V / X5R。 | [Product](https://item.taobao.com/item.htm?id=993202872551) · [Project model](https://item.szlcsc.com/85589.html) |
| **C22**<br>22uF 10V X5R | GRM188R61A226ME15D<br>C84419 | 0603<br>22uF / ±20% / 10V / X5R | 22UF 226K 10% X5R;10V;0603=100个<br>实际采购：0603 / 22uF / ±10% / 10V / X5R。 | [Product](https://item.taobao.com/item.htm?id=993202872551) · [Project model](https://item.szlcsc.com/85589.html) |
| **C26**<br>100nF / 1V8 | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/15331.html) |
| **C27**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C28**<br>100nF | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/15331.html) |
| **C29**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C30**<br>100nF | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/15331.html) |
| **C31**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C32**<br>100nF | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/15331.html) |
| **C33**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C34**<br>10nF | CC0603KRX7R9BB103<br>C100042 | 0603<br>10nF / ±10% / 50V / X7R | 0603 10NF 50V 10% 100个<br>实际采购：0603 / 10nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=610558214623) · [Project model](https://item.szlcsc.com/101256.html) |
| **C35**<br>1uF | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C36**<br>100nF | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/15331.html) |
| **C37**<br>10uF / 3V3 | C1608X5R1A106KT000E<br>C76608 | 0603<br>10uF / ±10% / 10V / X5R | 0603 10uF ±10% X5R;10V<br>实际采购：0603 / 10uF / ±10% / 10V / X5R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://item.szlcsc.com/77735.html) |
| **C38**<br>100nF / codec reset | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/15331.html) |
| **C39**<br>100nF 50V | CC0603KRX7R9BB104<br>C14663 | 0603<br>100nF / ±10% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/15331.html) |
| **C40**<br>1uF / MIC R coupling | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C41**<br>1uF / MIC L coupling | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C42**<br>1uF / MIC supply | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **C43**<br>1uF / MIC supply | CC0603KRX5R9BB105<br>C128624 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://www.lcsc.com/product-detail/C128624.html) |
| **D1**<br>BAT54SW / diode 1 used | BAT54SW,115<br>C78606 | SOT-323<br>二极管配置:1对串联式；正向压降(Vf):800mV@100mA；直流反向耐压(Vr):30V；整流电流:200mA | BAT54SW 印字44t（20只）<br>选择 BAT54SW / SOT-323 款式。 | [Product](https://item.taobao.com/item.htm?id=793455311175) · [Project model](https://item.szlcsc.com/79742.html) |
| **D4**<br>5V1 / bus clamp | BZT52C5V1S-7-F<br>C151348 | SOD-323<br>二极管配置:1个独立式；稳压值(标称值):5.1V；稳压值(范围值):4.8V~5.4V；耗散功率(Pd):200mW | BZT52C5V1S W8 SOD-323 (50个)<br>选择 BZT52C5V1S / 5.1V / SOD-323 款式。 | [Product](https://item.taobao.com/item.htm?id=943185002457) · [Project model](https://item.szlcsc.com/162688.html) |
| **FB1**<br>600R@100MHz 1.3A | BLM18KG601SN1D<br>C85833 | 0603<br>±25% / 600Ω@100MHz / 1.3A | 0603_600R_1.3A_±25%【100只】<br>实际采购：0603 / 600Ω@100MHz / 1.3A / ±25%。 | [Product](https://item.taobao.com/item.htm?id=931081429973) · [Project model](https://item.szlcsc.com/87009.html) |
| **FB2**<br>120R@100MHz 2A | PE-0603PFB121ST<br>C2661472 | 0603<br>±25% / 120Ω@100MHz / 2A | 0603_120R_2A_±25%【100只】<br>实际采购：0603 / 120Ω@100MHz / 2A / ±25%。 | [Product](https://item.taobao.com/item.htm?id=931081429973) · [Project model](https://item.szlcsc.com/2753383.html) |
| **FB3**<br>120R@100MHz 2A | PE-0603PFB121ST<br>C2661472 | 0603<br>±25% / 120Ω@100MHz / 2A | 0603_120R_2A_±25%【100只】<br>实际采购：0603 / 120Ω@100MHz / 2A / ±25%。 | [Product](https://item.taobao.com/item.htm?id=931081429973) · [Project model](https://item.szlcsc.com/2753383.html) |
| **J1**<br>SPK R / JST-EH 2P | B2B-EH-A(LF)(SN)<br>C160262 | 插件,P=2.5mm<br>250V / 3A | EH2.5MM 2P直针座（50个）<br>EH 2P 直针座；按 EH2.5MM 2P 直针座选项购买。 | [Product](https://item.taobao.com/item.htm?id=832569969546) · [Project model](https://item.szlcsc.com/171642.html) |
| **J2**<br>MIC L / JST-EH 2P | B2B-EH-A(LF)(SN)<br>C160262 | 插件,P=2.5mm<br>250V / 3A | EH2.5MM 2P直针座（50个）<br>EH 2P 直针座；按 EH2.5MM 2P 直针座选项购买。 | [Product](https://item.taobao.com/item.htm?id=832569969546) · [Project model](https://item.szlcsc.com/171642.html) |
| **J4**<br>FH-00339 stock pins / Zero pair-map / bottom | FH-00339<br>C2685112 | SMD,P=2.54mm<br>3A | 2*20P 贴片排母【2个】<br>双排 2×20P、2.54mm、贴片排母，安装在 HAT 底面。 | [Product](https://item.taobao.com/item.htm?id=533725557959) · [Project model](https://item.szlcsc.com/2784386.html) |
| **J5**<br>ToF / Qwiic / pad 0 GND | BM04B-SRSS-TB(LF)(SN)<br>C160390 | SMD,P=1mm<br>50V / 1A | 4P立贴（15个）<br>SH1.0 / 4P / 立贴，按“4P立贴（15个）”选项购买。 | [Product](https://item.taobao.com/item.htm?id=920058690376) · [Project model](https://item.szlcsc.com/171770.html) |
| **J9**<br>MIC R / JST-EH 2P | B2B-EH-A(LF)(SN)<br>C160262 | 插件,P=2.5mm<br>250V / 3A | EH2.5MM 2P直针座（50个）<br>EH 2P 直针座；按 EH2.5MM 2P 直针座选项购买。 | [Product](https://item.taobao.com/item.htm?id=832569969546) · [Project model](https://item.szlcsc.com/171642.html) |
| **J13**<br>Dynamixel TTL 3P | B3B-EH-A(LF)(SN)<br>C160259 | 插件,P=2.5mm<br>250V / 3A | EH2.5MM 3P直针座（50个）<br>EH 3P 直针座，HAT 两只、IMU 一只。 | [Product](https://item.taobao.com/item.htm?id=832569969546) · [Project model](https://item.szlcsc.com/171639.html) |
| **J14**<br>Dynamixel TTL 3P | B3B-EH-A(LF)(SN)<br>C160259 | 插件,P=2.5mm<br>250V / 3A | EH2.5MM 3P直针座（50个）<br>EH 3P 直针座，HAT 两只、IMU 一只。 | [Product](https://item.taobao.com/item.htm?id=832569969546) · [Project model](https://item.szlcsc.com/171639.html) |
| **L4**<br>6.8uH / 3A / Isat 4.3A | SWPA6045S6R8MT<br>C57254 | SMD,6x6mm<br>6.8uH / ±20% / 3A | 合金0630 6.8UH 印6R8 10个 6A 一体<br>实际使用：合金0630、6.8uH、6A一体成型电感（订单标称）。 | [Product](https://item.taobao.com/item.htm?id=598174251748) · [Project model](https://item.szlcsc.com/58286.html) |
| **MK1**<br>Onboard analog MEMS MIC | LMA2718T421-OA5-2<br>C7587901 | SMD-4P,2.8x1.9mm<br>指向性:全指向；信噪比:55dB；灵敏度:-42dB；阻抗:300Ω | 2718 上进音 硅麦克风【2个】<br>实际使用：2718 上进音模拟 MEMS 麦克风，按“2718 上进音 硅麦克风【2个】”购买。 | [Product](https://item.taobao.com/item.htm?id=996702312391) · [Project model](https://item.szlcsc.com/8705873.html) |
| **Q1**<br>MMBT3906 / direction | MMBT3906<br>C727128 | SOT-23<br>晶体管类型:PNP；集电极电流(Ic):200mA；集射极击穿电压(Vceo):40V；耗散功率(Pd):200mW；直流电流增益(hFE):100@10mA,1V | MMBT3906 丝印2A SOT-23(50个)<br>选择 MMBT3906 / PNP / SOT-23 款式。 | [Product](https://item.taobao.com/item.htm?id=944306254140) · [Project model](https://item.szlcsc.com/774233.html) |
| **Q2**<br>SI2312 / ideal diode MOS | SI2312CDS-T1-GE3<br>C142518 | SOT-23<br>数量:1个N沟道；漏源电压(Vdss):20V；连续漏极电流(Id):6A；导通电阻(RDS(on)):41.4mΩ@1.8V,5.6A；耗散功率(Pd):2.1W；阈值电压(Vgs(th)):1V@250uA | SI2312DS（AE9T）N沟道（20只）<br>实际使用：SI2312DS（AE9T）N沟道，20只包装。 | [Product](https://item.taobao.com/item.htm?id=909264246006) · [Project model](https://item.szlcsc.com/153849.html) |
| **R1**<br>10k / INL | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R2**<br>10k / INR | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R3**<br>0R / SHDN high | 0603WAF0000T5E<br>C21189 | 0603<br>0Ω / ±1% / - / 100mW | 0R/0欧;0603 1%（100个）<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/21903.html) |
| **R4**<br>0R / MUTE high | 0603WAF0000T5E<br>C21189 | 0603<br>0Ω / ±1% / - / 100mW | 0R/0欧;0603 1%（100个）<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/21903.html) |
| **R5**<br>0R / MODE high | 0603WAF0000T5E<br>C21189 | 0603<br>0Ω / ±1% / - / 100mW | 0R/0欧;0603 1%（100个）<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/21903.html) |
| **R6**<br>10k / codec reset | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R7**<br>0R / MIC2L to GND | 0603WAF0000T5E<br>C21189 | 0603<br>0Ω / ±1% / - / 100mW | 0R/0欧;0603 1%（100个）<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/21903.html) |
| **R8**<br>100R | 0603WAF1000T5E<br>C22775 | 0603<br>100Ω / ±1% / ±200ppm/℃ / 100mW | 100R/100欧;0603 1%（100个）<br>100Ω / ±1% / 0603，用于 HAT R8。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://www.lcsc.com/product-detail/C22775.html) |
| **R12**<br>10k / SDA pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R13**<br>10k / SCL pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R22**<br>10k / MIC L bias | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R23**<br>10k / MIC R bias | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R26**<br>10k / UART TX pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R27**<br>10k / direction base | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R28**<br>20k / direction pull-down | 0603WAF2002T5E<br>C4184 | 0603<br>20kΩ / ±1% / ±100ppm/℃ / 100mW | 20K;0603 1%（100个）<br>20kΩ / ±1% / 0603。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/4591.html) |
| **R29**<br>10k / RX gate enable | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R31**<br>10k / RX pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R32**<br>10k / data pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R33**<br>150R / bus series | 0603WAF1500T5E<br>C22808 | 0603<br>150Ω / ±1% / ±100ppm/℃ / 100mW | 0603WAF0000T5E<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://www.lcsc.com/product-detail/C22808.html) |
| **TH1**<br>100R PTC | PRG18BB101MB1RB<br>C913703 | 0603<br>100Ω / PTC / 村田 | 100R  PRG18BB101MB1RB<br>TH1可使用原村田PRG18BB101MB1RB（100Ω PTC，0603），按原订单100R款式采购；R33使用0Ω。 | [Product](https://item.taobao.com/item.htm?id=582129955778) · [Project model](https://item.szlcsc.com/984022.html) |
| **U1**<br>PAM8406D | PAM8406DR<br>C86270 | SOIC-16<br>功放类型:AB类功放；D类功放；扬声器通道数:双声道；输出功率:5Wx2@2Ω；静态电流(Iq):10mA | PAM8406DR<br>实际使用：PAM8406DR，订单标注 SOP16。 | [Product](https://item.taobao.com/item.htm?id=808484505787) · [Project model](https://item.szlcsc.com/87446.html) |
| **U2**<br>TLV320AIC3104IRHBR | TLV320AIC3104IRHBR<br>C181753 | HVQFN-32-EP(5x5)<br>类型:编解码器；接口类型:I2S；I2C；采样率:8kHz~96kHz | 商品无选项，按商品标题完整型号购买<br>TLV320AIC3104IRHBR，按商品完整型号购买。 | [Product](https://item.taobao.com/item.htm?id=908248360601) · [Project model](https://www.lcsc.com/product-detail/C181753.html) |
| **U3**<br>XC6206P182 / 1V8 | XC6206P182MR<br>C347373 | SOT-23<br>输出极性:正极；工作电压:8V；输出电压:1.8V；输出电流:250mA；电源纹波抑制比(PSRR):40dB@(1kHz)；输出类型:固定 | XC6206P182MR 65K5 SOT-23 (20个)<br>XC6206P182MR / 1.8V / SOT-23，20个包装。 | [Product](https://item.taobao.com/item.htm?id=762173333947) · [Project model](https://item.szlcsc.com/324033.html) |
| **U5**<br>74LVC1G08 / RX gate | SN74LVC1G08DBVR<br>C7666 | SOT-23-5<br>逻辑类型:与门；通道数:1；工作电压:1.65V~5.5V；静态电流(Iq):10uA；传播延迟(tpd):4ns@5V,50pF | SN74LVC1G08DBVR;5个全国包邮<br>SN74LVC1G08DBVR / SOT-23-5 与门，按同页对应型号选项购买。 | [Product](https://item.taobao.com/item.htm?id=902117985110) · [Project model](https://www.lcsc.com/product-detail/C7666.html) |
| **U6**<br>SN74LVC1G125 / RX | SN74LVC1G125DBVR-TP<br>C3040625 | SOT-23-5<br>输入类型:-；工作电压:1.65V~5.5V；元件数:1；每个元件位数:-；灌电流(IOL):24mA；拉电流(IOH):24mA | SN74LVC1G125DBVR;5个全国包邮<br>实际使用：SN74LVC1G125DBVR / SOT-23-5，5个包装。 | [Product](https://item.taobao.com/item.htm?id=902117985110) · [Project model](https://item.szlcsc.com/3597950.html) |
| **U7**<br>SN74LVC1G126 / TX | SN74LVC1G126DBVR<br>C7834 | SOT-23-5<br>输入类型:-；工作电压:1.65V~5.5V；元件数:1；每个元件位数:1；灌电流(IOL):32mA；拉电流(IOH):32mA | SN74LVC1G126DBVR;5个全国包邮<br>实际使用：SN74LVC1G126DBVR / SOT-23-5，5个包装。 | [Product](https://item.taobao.com/item.htm?id=902117985110) · [Project model](https://www.lcsc.com/product-detail/C7834.html) |
| **U9**<br>AP63205 / 5V buck | AP63205WU-7<br>C2071056 | TSOT-23-6<br>功能类型:降压型；工作电压:3.8V~32V；输出电压:5V；输出电流:2A；输出类型:固定 | AP63205WU-7<br>AP63205WU-7，固定5V降压芯片，按对应完整型号购买。 | [Product](https://item.taobao.com/item.htm?id=969642590399) · [Project model](https://item.szlcsc.com/2162639.html) |
| **U10**<br>LM5050-1 | LM5050MKX-1/NOPB<br>C473393 | TSOT-23-6<br>LM5050-1 5V 至 75V、400uA IQ ORing FET 控制器 | SOT-23;LM5050MKX-1/NOPB  原装正品<br>LM5050MKX-1/NOPB，按完整型号购买。 | [Product](https://item.taobao.com/item.htm?id=1013388982214) · [Project model](https://www.lcsc.com/product-detail/C473393.html) |
| **Y1**<br>12MHz | OT3EL89CJI-111YLC-12M<br>C7425459 | SMD2520-4P<br>12MHz | 12MHZ 1.2V~3.36V宽压[高精度10PPM];SMD2520-4P CMOS输出<br>实际使用：12MHz、2520-4P、CMOS输出有源晶振，宽压1.2V~3.36V（订单标称）。 | [Product](https://item.taobao.com/item.htm?id=944053669860) · [Project model](https://item.szlcsc.com/8414369.html) |

</details>

<details>
<summary>IMU: full reference-designator BOM (25 components)</summary>

| Ref / function | Project model / part code | Project package / specification | Actual purchase variant / notes | Links |
| --- | --- | --- | --- | --- |
| **C1**<br>4.7uF 25V | CL21A475KAQNNNE<br>C1779 | 0805<br>4.7uF / ±10% / 25V / X5R | 0805 4.7UF ±10% X7R;25V<br>实际采购：0805 / 4.7uF / ±10% / 25V / X7R。 | [Product](https://item.taobao.com/item.htm?id=977236759812) · [Project model](https://www.lcsc.com/product-detail/C1779.html) |
| **C2**<br>100nF 50V | CL10B104JB8NNNC<br>C24452 | 0603<br>100nF / ±5% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/25192.html) |
| **C3**<br>4.7uF 25V | CL21A475KAQNNNE<br>C1779 | 0805<br>4.7uF / ±10% / 25V / X5R | 0805 4.7UF ±10% X7R;25V<br>实际采购：0805 / 4.7uF / ±10% / 25V / X7R。 | [Product](https://item.taobao.com/item.htm?id=977236759812) · [Project model](https://www.lcsc.com/product-detail/C1779.html) |
| **C4**<br>100nF 50V | CL10B104JB8NNNC<br>C24452 | 0603<br>100nF / ±5% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/25192.html) |
| **C5**<br>100nF / MCU | CL10B104JB8NNNC<br>C24452 | 0603<br>100nF / ±5% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/25192.html) |
| **C6**<br>1uF / MCU | CL10A105KB8NNNC<br>C15849 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://item.szlcsc.com/16531.html) |
| **C7**<br>100nF / VDD_IO | CL10B104JB8NNNC<br>C24452 | 0603<br>100nF / ±5% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/25192.html) |
| **C8**<br>100nF / VDD | CL10B104JB8NNNC<br>C24452 | 0603<br>100nF / ±5% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/25192.html) |
| **C9**<br>1uF / IMU local | CL10A105KB8NNNC<br>C15849 | 0603<br>1uF / ±10% / 50V / X5R | 0603 1uF ±10% X7R;50V<br>实际采购：0603 / 1uF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=630712731066) · [Project model](https://item.szlcsc.com/16531.html) |
| **C10**<br>100nF / buffer | CL10B104JB8NNNC<br>C24452 | 0603<br>100nF / ±5% / 50V / X7R | 0603 100nF ±10% X7R;50V;100个<br>实际采购：0603 / 100nF / ±10% / 50V / X7R。 | [Product](https://item.taobao.com/item.htm?id=731471380840) · [Project model](https://item.szlcsc.com/25192.html) |
| **D1**<br>PESD5V0S1BA / 5V bidirectional | PESD5V0S1BA<br>C330094 | SOD-323<br>反向截止电压(Vrwm):5V@Max；最大钳位电压:10V；峰值脉冲电流(Ipp)@10/1000us:5A@8/20us；击穿电压:5.8V | 商品无选项，按商品标题完整型号购买<br>PESD5V0S1BA / SOD-323 双向TVS，按商品完整型号购买。 | [Product](https://item.taobao.com/item.htm?id=891785167202) · [Project model](https://www.lcsc.com/product-detail/C330094.html) |
| **D2**<br>DEBUG LED | 19-217/GHC-YR1S2/3T<br>C72043 | 0603<br>110mW | 0603 蓝色=100个<br>实际采购：0603 蓝色LED，100个包装。 | [Product](https://item.taobao.com/item.htm?id=1025817117811) · [Project model](https://www.lcsc.com/product-detail/Light-Emitting-Diodes-LED_Everlight-Elec-19-217-GHC-YR1S2-3T_C72043.html) |
| **J1**<br>DXL BUS / JST EH 3P | B3B-EH-A(LF)(SN)<br>C160259 | 插件,P=2.5mm<br>250V / 3A | EH2.5MM 3P直针座（50个）<br>EH 3P 直针座，HAT 两只、IMU 一只。 | [Product](https://item.taobao.com/item.htm?id=832569969546) · [Project model](https://item.szlcsc.com/171639.html) |
| **J2**<br>SWD 1x5 | PZ254V-11-05P<br>C492404 | 插件,P=2.54mm<br>3A | 1*5P直针 铜（30条）<br>1×5P / 2.54mm 直排针，用于SWD烧录口。 | [Product](https://item.taobao.com/item.htm?id=606816197525) · [Project model](https://item.szlcsc.com/502960.html) |
| **R1**<br>0R / DXL_VDD link | 0603WAF0000T5E<br>C21189 | 0603<br>0Ω / ±1% / - / 100mW | 0R/0欧;0603 1%（100个）<br>0Ω / 0603；HAT R33 按后续 0Ω / C21189 补丁计入。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/21903.html) |
| **R2**<br>10k / NRST pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R3**<br>100k / BOOT0 pull-down | RC0603FR-07100KL<br>C14675 | 0603<br>100kΩ / ±1% / ±100ppm/℃ / 100mW | 100K;0603 1%（100个）<br>100kΩ / ±1% / 0603。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/15343.html) |
| **R4**<br>10k / IMU CS pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R5**<br>10k / TX disable pull-up | RC0603FR-0710KL<br>C98220 | 0603<br>10kΩ / ±1% / ±100ppm/℃ / 100mW | 10K;0603 1%（100个）<br>10kΩ / ±1% / 0603；HAT 十二只、IMU 三只。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/99429.html) |
| **R6**<br>33R / DXL TX series | 0603WAF330JT5E<br>C23140 | 0603<br>33Ω / ±1% / ±100ppm/℃ / 100mW | 33R/33欧;0603 1%（100个）<br>33Ω / ±1% / 0603，用于IMU R6。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/23867.html) |
| **R7**<br>1k / debug LED | 0603WAF1001T5E<br>C21190 | 0603<br>1kΩ / ±1% / ±100ppm/℃ / 100mW | 1K;0603 1%（100个）<br>1kΩ / ±1% / 0603，八月备料订单。 | [Product](https://item.taobao.com/item.htm?id=947267344247) · [Project model](https://item.szlcsc.com/21904.html) |
| **U1**<br>STM32G031F8P6 | STM32G031F8P6<br>C529334 | TSSOP-20<br>CPU内核:ARM Cortex-M0+；CPU最大主频:64MHz；CPU位数:32 Bit | 全新原装<br>STM32G031F8P6 / TSSOP-20，按商品完整型号购买。 | [Product](https://item.taobao.com/item.htm?id=726808419708) · [Project model](https://item.szlcsc.com/549612.html) |
| **U2**<br>LSM6DSV16XTR | LSM6DSV16XTR<br>C5267406 | LGA-14(2.5x3)<br>传感器类型:IMU(加速度计+陀螺仪)；接口类型:I2C；SPI | LSM6DSV16XTR<br>LSM6DSV16XTR / LGA-14；指定购买 LSM6DSV16XTR，参考单价 ¥13.80/个。 | [Product](https://e.tb.cn/h.j3ZZ8HNmUBbhzqy?tk=jMe5TxTIPLE) · [Project model](https://item.szlcsc.com/5993815.html) |
| **U3**<br>TLV70433DBVR | TLV70433DBVR<br>C94917 | SOT-23-5<br>输出极性:正极；工作电压:24V；输出电压:3.3V；输出电流:150mA；电源纹波抑制比(PSRR):60dB@(100kHz)；输出类型:固定 | TLV70433DBVR<br>TLV70433DBVR / 3.3V / SOT-23-5。 | [Product](https://item.taobao.com/item.htm?id=747094785928) · [Project model](https://www.lcsc.com/product-detail/C94917.html) |
| **U4**<br>SN74LVC2G125DCUR | SN74LVC2G125DCUR<br>C21404 | VSSOP-8<br>输入类型:-；工作电压:1.65V~5.5V；元件数:2；每个元件位数:1；灌电流(IOL):32mA；拉电流(IOH):32mA | 商品无选项，按商品标题完整型号购买<br>SN74LVC2G125DCUR / VSSOP-8，按商品完整型号购买。 | [Product](https://item.taobao.com/item.htm?id=705642638300) · [Project model](https://www.lcsc.com/product-detail/C21404.html) |

</details>
