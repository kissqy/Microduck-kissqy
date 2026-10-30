// Documentation-backed wiring facts. Board meshes and cable routes are schematic.
// Do not derive connector pin direction from the simplified 3D geometry.
const repository='https://github.com/kissqy/Microduck-kissqy/blob/main/';
const hardware=repository+'hardware/';
const authorBoards='https://item.taobao.com/item.htm?id=1095121548583';

export const COMPONENTS=Object.freeze({
  hub:{
    id:'hub',label:'HUB 分线板',shortLabel:'HUB',
    description:'将电池电源与三线舵机总线集中分配，并在总电源网络上并联缓冲电容。',
    dimensionsMm:[23,34],
    locationNote:'HUB 平放在 10、20 舵机上方，长边沿机身前后方向。板卡保持水平，端子和线束跟随安装朝向。',
    purchase:{label:'联系作者确认 HUB',url:repository+'docs/assets/purchase-wechat-qr.jpg'},
    source:{label:'HUB V2 模型与接口数据',url:repository+'docs/assets/assembly-hub-layout.json'},
    sourceNote:'HUB 外形、孔位、正反面布局与端子网络依据作者 2026-10-30 的 DXL_HUB_V2 工程；插座塑料外形和器件高度为视觉近似。端子位号按本工程 J1–J4 / CN1 显示。',
    facts:[
      'PCB 外形约 23 × 34 mm；四个安装孔约 Ø2.4 mm，孔中心距约 19 × 30 mm。',
      'CN1 为电池输入：1=GND，2=VIN。',
      'J1 / J2 位于正面，J3 / J4 位于背面，均为 A2007WR-3P 弯插 AMP2.0 接口。各口均为 1=SERVO_BUS，2=VIN，3=GND，三条网络分别共线。',
      'C1 为 1000 µF / 16V，1 脚接 VIN，2 脚接 GND，电容位于 PCB 正面。',
      '可选打印件：电池仓_M2.5螺丝_HUB组合.stl。',
      '针号是各自工程编号，不代表照片左右或现成线束顺序；按 GND、电源、DATA 信号与实板丝印核对并确认导通，不因编号不同就直接交叉线束。',
      '当前仓库未提供 HUB 独立购买链接，先向作者确认实际型号。',
    ],
  },
  imu:{
    id:'imu',label:'独立躯干 IMU',shortLabel:'IMU',
    description:'读取躯干姿态，通过总线向 ZERO 提供反馈；作者成品已预烧录 FT6，到手无需另行烧录。',
    dimensionsMm:[22.225,25.654],
    locationNote:'IMU 贴合电池仓背部的主安装板面，总线端子 J1 朝上。接线接入 J1 的三针触点，安装后在中控核对姿态与方向。',
    purchase:{label:'购买作者同款 IMU',url:authorBoards},
    source:{label:'IMU 接口与 FT6 固件说明',url:hardware+'IMU-FIRMWARE.md'},
    facts:[
      '模型按公开 IMU PCB 板框建模，竖向显示约 22.2 × 25.7 mm；主要芯片、插座与焊盘位置来自工程。',
      '作者成品 IMU 已预烧录 FT6；安装后仍需完成本机 IMU 标定。',
      '当前飞特 FT6 固件：1 Mbps、固定 ID 200，与 15 个 HD1910 共用总线。',
      'AMP2.0 版 J1：1=GND，2=DXL_VDD，3=DXL_DATA；按焊盘针号识别方向。',
      'J2 是供自焊新板、换芯片或维护升级使用的 SWD 烧录口；不是舵机总线口，3V3 不能接 5V。',
    ],
    extraSources:[{label:'AMP2.0 针序',url:hardware+'AMP2.0-VERSION.md'},{label:'IMU 尺寸记录',url:hardware+'IMU-TIMELINE.md'}],
  },
  hat:{
    id:'hat',label:'HAT 供电与通信板',shortLabel:'HAT',
    description:'连接 ZERO 与舵机总线，提供降压供电、通信和音频外围。',
    dimensionsMm:[65,30.9],
    locationNote:'安装位置按作者实机修正：HAT 与 ZERO 3W 组合在鸭脸内部，贴近面部安装区域。打开头盖、选择 HAT 可放大查看，线束沿头颈部向下连接。',
    purchase:{label:'购买作者同款 HAT',url:authorBoards},
    source:{label:'HAT 与 IMU 硬件说明',url:hardware+'README.md'},
    facts:[
      '作者自行设计绘制，成品由嘉立创 SMT 贴片生产，经长期真机使用与迭代验证。',
      '公开 HAT-V5 记录尺寸约 65 × 30.9 mm。',
      '三维外观按公开 PCB 的元件位置细化排针、插座、芯片和焊盘；封装高度为显示简化。',
      'J4 是底面的 40 针 ZERO 配对座，承载电源与通信；按板上 1 脚标记与实际朝向对齐。',
      'AMP2.0 版 J13 / J14：1=GND，2=BATT_IN，3=DXL_DATA。',
      'J5 是 ToF / Qwiic 接口，不是 ZERO 的 40 针连接座。',
      'AMP2.0 和 EH2.5 两版接口不同，线束按所用实板版本选择。',
    ],
    extraSources:[{label:'AMP2.0 针序',url:hardware+'AMP2.0-VERSION.md'},{label:'HAT 尺寸记录',url:hardware+'HAT-TIMELINE.md'},{label:'J4 / J5 原始 PCB 工程',url:hardware+'ProPrj_HAT_REVA_SCH_2026-10-15.epro2'}],
  },
  zero:{
    id:'zero',label:'Radxa ZERO 3W',shortLabel:'ZERO 3W',
    description:'运行机器人系统、中控服务与运动模型的主控。',
    dimensionsMm:[65,30],
    locationNote:'安装位置按作者实机修正：ZERO 3W 与 HAT 组合在鸭脸内部，不放在后脑顶部。GPIO 接座朝向、支柱间距以实际板卡和头壳为准。',
    purchase:{label:'购买 ZERO 3W',url:'https://item.taobao.com/item.htm?id=763812025816'},
    source:{label:'本项目主控采购款式',url:repository+'DUCK-SHOPPING-LIST.md'},
    facts:[
      '采购清单的参考款式为 2 GB、无 eMMC、带排针。',
      '官方板卡尺寸 65 × 30 mm，具有 40 针 GPIO 扩展座。',
      '三维外观参考官方板卡照片与尺寸图，增加 USB-C、HDMI、排针、芯片和卡槽细节。',
      '在本组合中通过配套 HAT 的 J4 40 针座连接；不要把 BATT_IN 电池电源当作 ZERO 的 5V / 3V3。',
      'GPIO 为 3.3V 逻辑；外部接线按主板与 HAT 原理图核对。',
    ],
    extraSources:[{label:'Radxa 官方尺寸与接口',url:'https://docs.radxa.com/zero/zero3'},{label:'Radxa GPIO 电压说明',url:'https://docs.radxa.com/zero/zero3/hardware-design/hardware-interface'}],
  },
});

export const CONNECTIONS=Object.freeze([
  {
    id:'battery-hub',from:'battery',to:'hub',label:'电池 → HUB CN1',kind:'power',
    signals:[['负极 / GND','GND'],['正极 / 电源','VIN']],
    detail:'按用户当前 HUB PCB 网络：CN1 的 1 脚接 GND，2 脚接 VIN。C1 为 1000 µF / 16V，正极网络为 VIN、负极为 GND；元件极性和安装方向按实板核对。',
    sourceUrl:hardware+'3d-print-frankenduck/README.md',
    sourceNote:'针序依据用户提供的 DXL_HUB_V2（2026-10-30）工程；链接为配套机械说明。',
    extraSourceUrl:repository+'docs/ASSEMBLY-NOTES.md',
  },
  {
    id:'hat-zero',from:'hat',to:'zero',label:'J4 · 40 针配对连接',kind:'header',
    detail:'HAT 的 J4 为底面 40 针配对座，电源与 UART / I²C / 音频等信号经该座连接 ZERO。图示不是逐针插接图；按实板 1 脚和朝向对齐。J5 是 ToF 口，不能混淆。',
    sourceUrl:hardware+'ProPrj_HAT_REVA_SCH_2026-10-15.epro2',
  },
  {
    id:'hub-hat',from:'hub',to:'hat',label:'HUB / HAT · 同一总线信号',kind:'bus',
    signals:[['GND','GND'],['VIN','BATT_IN'],['SERVO_BUS','DXL_DATA']],
    detail:'工程网络：HUB J1～J4 的 1=SERVO_BUS、2=VIN、3=GND；HAT J13/J14 的 3=DXL_DATA、2=BATT_IN、1=GND。针号是各自工程编号，不代表照片左右或现成线束顺序；按信号名与实板丝印核对并确认导通，不因编号不同就直接交叉线束。',
    sourceUrl:hardware+'AMP2.0-VERSION.md',
    sourceNote:'HUB 一侧依据用户当前 HUB 工程；HAT 一侧依据公开 AMP2.0 工程。',
  },
  {
    id:'hub-imu',from:'hub',to:'imu',label:'HUB / IMU · 同一总线信号',kind:'bus',
    signals:[['GND','GND'],['VIN','DXL_VDD'],['SERVO_BUS','DXL_DATA']],
    detail:'信号关系：HUB 的 SERVO_BUS / VIN / GND，对应 IMU J1 的 DXL_DATA / DXL_VDD / GND。HUB 工程编号为 1=DATA、2=电源、3=GND；IMU AMP2.0 工程编号为 3=DATA、2=电源、1=GND。工程编号不代表插头物理左右或现成线束顺序，按实板信号核对并确认导通。IMU 与 15 个 HD1910 共用总线，可按实际装配经舵机菊链接入。',
    sourceUrl:hardware+'AMP2.0-VERSION.md',
    sourceNote:'HUB 一侧依据用户当前 HUB 工程；IMU 一侧依据公开 AMP2.0 工程。',
  },
]);

export const WIRING_NOTE='线束以独立芯线接入模型端子：黑色 GND、红色电源、白色 DATA；HAT / ZERO 之间单独显示排针连接。颜色仅用于辨认信号，下方表格仍按信号名核对；不能仅凭示意颜色或两端工程编号交叉接线。';
