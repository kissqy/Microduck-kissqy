"""Shared photo steps for the web assembly route and bilingual Markdown guides."""
from html import escape
from pathlib import Path

STEPS = [
    {
        "slug": "01-tof-mount",
        "zh": ("先固定 ToF 模块", "将 ToF 固定在鸭脸内侧的小板安装位，四根线从侧面引出，给摄像头和上层板卡留出空间。", "按本图朝向，模块焊孔自上而下：黄 VIN、绿 GND、红 SCL、黑 SDA。"),
        "en": ("Mount the ToF module", "Fasten the ToF module to its mounting points inside the face panel. Route its four wires to the side, leaving room for the camera and the boards above it.", "In this photo, the module pads run top to bottom: yellow VIN, green GND, red SCL, black SDA."),
    },
    {
        "slug": "02-camera-ribbon",
        "zh": ("安装 IMX219 与摄像头排线", "摄像头对准鸭脸开孔，按四角安装位固定。将摄像头排线接到 ZERO 的 CSI 接口，确认插入到位、锁扣扣好。", "先选与摄像头版本对应的鸭脸打印件；排线接触面按实际接口确认。"),
        "en": ("Install the IMX219 and its ribbon cable", "Align the camera with the face opening and secure its four mounting points. Connect the camera ribbon to the ZERO's CSI connector and close the latch after seating it fully.", "Choose the face-panel print for your camera variant. Check the actual connector to determine ribbon contact orientation."),
    },
    {
        "slug": "03-zero-clearance",
        "zh": ("固定 ZERO，留出排线弯曲空间", "将 ZERO 装到鸭脸立柱上，参照侧视图检查摄像头与主控之间的间距。排线沿空隙自然折回，避开螺丝和立柱。", "排线不绷紧、不折成死角；核对 40 针排针与 HAT 配对座的朝向。"),
        "en": ("Mount the ZERO and leave room for the ribbon", "Mount the ZERO on the face-panel standoffs. Use this side view to check the space behind the camera. Let the ribbon bend naturally through the gap, clear of screws and standoffs.", "Keep the ribbon relaxed without sharp creases. Check the orientation of the 40-pin header and the HAT's mating socket."),
    },
    {
        "slug": "04-hat-wiring",
        "zh": ("连接 HAT 的 ToF 与喇叭", "四芯 ToF 线束接 HAT J5，红黑喇叭线接 J1。J2、J9 为麦克风接口；外围接好后，再核对 HAT 与 ZERO 的配对朝向。", "按接口编号和信号名核对线序；ToF 与喇叭的完整针序见下方。"),
        "en": ("Connect the ToF and speaker to the HAT", "Connect the four-wire ToF harness to HAT J5 and the red/black speaker lead to J1. J2 and J9 are microphone connectors. Check the mating orientation before joining the HAT and ZERO.", "Match connector numbers and signal names. The ToF and speaker pin tables are below."),
    },
    {
        "slug": "05-head-overview",
        "zh": ("装入头壳，整理并固定线束", "将叠装好的 ZERO／HAT 和喇叭装入头部，余线收进两侧空隙，参照照片固定。给舵机、嘴部活动和开盖留出余量。", "合盖前检查：排线不卡立柱，线束不碰活动件，插头未被拉扯。"),
        "en": ("Fit the head shell and secure the wiring", "Fit the stacked ZERO/HAT assembly and speaker into the head. Tuck spare cable into the side gaps and secure it as shown. Leave slack for the servos, mouth and opening the cover.", "Before closing: keep the ribbon clear of standoffs, wiring clear of moving parts, and plugs free of tension."),
    },
]


def render_gallery():
    cards = []
    for number, step in enumerate(STEPS, 1):
        title, body, detail = map(escape, step["zh"])
        image = "../assets/head-assembly/" + step["slug"] + ".jpg"
        if number == 4:
            image += "?v=20261109-retouched"
        featured = " head-step--overview" if number == 5 else ""
        photo_style = " head-step__photo--wiring" if number == 4 else ""
        cards.append(
            f'<article class="head-step{featured}">'
            f'<a class="head-step__photo{photo_style}" href="{image}" target="_blank" rel="noopener" aria-label="放大查看：{title}">'
            f'<img src="{image}" alt="步骤 {number}：{title}的实机安装照片" width="1086" height="1448" loading="lazy" decoding="async"></a>'
            '<div class="head-step__copy">'
            f'<span class="head-step__number">{number:02d}</span><h4>{title}</h4>'
            f'<p>{body}</p><p class="head-step__detail">{detail}</p>'
            '</div></article>'
        )
    return (
        '<section class="head-photos" id="head-photos" aria-labelledby="head-photos-title">'
        '<div class="head-photos__heading"><div><p class="eyebrow">HEAD ASSEMBLY / PHOTO GUIDE</p>'
        '<h3 id="head-photos-title">头部安装，跟着五张实拍完成</h3></div>'
        '<span class="badge">ToF · IMX219 · ZERO · HAT</span></div>'
        '<p class="head-photos__intro">从鸭脸内侧开始，按 ToF → 摄像头 → ZERO → HAT → 整理线束的顺序完成。断电后装配，点击照片可放大查看。</p>'
        '<div class="head-photo-grid">' + ''.join(cards) + '</div>'
        '<p class="head-photos__more"><a href="https://github.com/kissqy/Microduck-kissqy/blob/main/docs/HEAD-ASSEMBLY.md">查看完整图文说明 ↗</a> · '
        '<a href="#hat-wiring">核对 ToF 与喇叭针序 ↓</a></p></section>'
    )


def render_markdown(language):
    english = language == "en"
    lines = [
        '[简体中文](HEAD-ASSEMBLY.md) | **English**' if english else '**简体中文** | [English](HEAD-ASSEMBLY.en.md)',
        '',
        '# Head assembly and wiring · photo guide' if english else '# 头部安装与接线 · 五步实拍',
        '',
        ('Follow the real assembly photos: ToF → IMX219 → ZERO 3W → HAT → cable routing. Assemble with power disconnected. Select the face-panel print for your IMX219 camera variant.' if english else '从鸭脸内侧开始，按 **ToF → IMX219 → ZERO 3W → HAT → 整理线束** 的顺序完成。断电后装配；鸭脸打印件需与实际 IMX219 摄像头版本对应。'),
        '',
        ('[Open the web photo guide (Chinese)](https://kissqy.github.io/Microduck-kissqy/build/assembly.html#head-photos) · [3D head reference](https://kissqy.github.io/Microduck-kissqy/assembly.html?part=head)' if english else '[在线查看五步实拍](https://kissqy.github.io/Microduck-kissqy/build/assembly.html#head-photos) · [打开头颈 3D 参考](https://kissqy.github.io/Microduck-kissqy/assembly.html?part=head)'),
        '',
    ]
    for number, step in enumerate(STEPS, 1):
        title, body, detail = step[language]
        image = 'assets/head-assembly/' + step['slug'] + '.jpg'
        if number == 4:
            image += "?v=20261109-retouched"
        lines += [f'## {number:02d} · {title}', '', body, '', f'<a href="{image}"><img src="{image}" width="480" alt="{escape(title, quote=True)}" /></a>', '', detail, '']
    if english:
        lines += ['## ToF and speaker pinout', '', 'HAT J5 is the ToF connector (SH1.0 / 4P). The order of the module pads differs from the HAT pin numbering; match signals using this table.', '', '| HAT J5 pin | Wire in these photos | HAT signal | ToF module pad |', '| --- | --- | --- | --- |', '| 1 | Green | GND | GND |', '| 2 | Yellow | 3V3 (3.3 V) | VIN |', '| 3 | Black | SDA | SDA |', '| 4 | Red | SCL | SCL |', '', 'The speaker connects to HAT J1 (HP1.25 / 2P).', '', '| HAT J1 pin | Wire in these photos | Speaker signal |', '| --- | --- | --- |', '| 1 | Red | SPK_R_P (+) |', '| 2 | Black | SPK_R_N (−) |', '', '**The black speaker wire is the SPK_R_N differential output, not GND.** J2 and J9 are microphone connectors. Wire colors describe this harness; check pin numbers and signals when changing cables.', '', '[HAT connector reference](../hardware/AMP2.0-VERSION.en.md#tof-and-speaker-wiring-photo) · [Full build guide](MICRODUCK-BUILD-GUIDE.en.md)']
    else:
        lines += ['## ToF 与喇叭针序', '', '**ToF 接 HAT J5（SH1.0 / 4P）**。模块焊孔顺序与 HAT 针序不同，按信号对应接线。', '', '| HAT J5 针号 | 本组照片线色 | HAT 信号 | ToF 模块焊孔 |', '| --- | --- | --- | --- |', '| 1 | 绿色 | GND | GND |', '| 2 | 黄色 | 3V3（3.3 V） | VIN |', '| 3 | 黑色 | SDA | SDA |', '| 4 | 红色 | SCL | SCL |', '', '**喇叭接 HAT J1（HP1.25 / 2P）。**', '', '| HAT J1 针号 | 本组照片线色 | 喇叭信号 |', '| --- | --- | --- |', '| 1 | 红色 | SPK_R_P（＋） |', '| 2 | 黑色 | SPK_R_N（−） |', '', '**喇叭黑线是 SPK_R_N 差分输出，不是 GND。** J2、J9 为麦克风接口。线色对应本组实拍，换线束时按针号和信号核对。', '', '[HAT 接口完整说明](../hardware/AMP2.0-VERSION.md#tof-与喇叭实拍接线) · [返回复刻总教程](MICRODUCK-BUILD-GUIDE.md)']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    for language, filename in [('zh', 'HEAD-ASSEMBLY.md'), ('en', 'HEAD-ASSEMBLY.en.md')]:
        (root / 'docs' / filename).write_text(render_markdown(language))
    print('Rendered Chinese and English head assembly photo guides.')
