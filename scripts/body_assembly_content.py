"""Photo references for the HUB, torso, legs and head/neck connection."""
from html import escape
from pathlib import Path

STEPS = [
    {
        "slug": "01-hub-harness", "group": "body",
        "zh": ("先接好 HUB 四路分线", "将四组三芯线束接入 HUB，插头插到底。四路总线分别用于头颈、左腿、右腿和 IMU，按实际装配位置安排线长。", "四个总线口电气共网，不限定哪一个口接哪条支路。全黑线束按 GND、电源、DATA 信号核对，不凭线色判断。"),
        "en": ("Prepare the four HUB branches", "Seat four three-wire harnesses in the HUB. The branches serve the head/neck, left leg, right leg and IMU. Choose cable lengths for their installed locations.", "The four bus ports share the same electrical nets; branch-to-port positions are not fixed. Match GND, power and DATA signals rather than relying on the all-black wire colors."),
    },
    {
        "slug": "02-body-prewire", "group": "body",
        "zh": ("躯干总成预接线，先留出各支路", "参照实拍将 HUB、躯干舵机和 IMU 支路预先接好，先把线束从支架空隙中引出，再装电池仓，避免固定后难以穿线。", "这张图是预接线阶段：IMU 暂未固定，下一步要装到电池仓定位位，不能悬空运行。"),
        "en": ("Prewire the torso and leave the branches accessible", "Connect the HUB, torso servos and IMU branch as shown. Route the harnesses through the bracket gaps before installing the battery holder, while the wiring is still accessible.", "This is the prewiring stage: the IMU is temporarily loose. Secure it to the battery-holder mounting position in the next step before operation."),
    },
    {
        "slug": "03-imu-holder", "group": "body",
        "zh": ("固定电池仓与 IMU，收好余线", "将电池仓装到躯干总成，把 IMU 贴合固定在背板定位位，保持规定的安装方向。线束沿两侧收纳，给电池滑入和卡扣动作留出空间。", "板卡与插头固定后再整理余线，避开舵机、轴承和连接件的活动区；IMU 的朝向与 3D 装配说明一致。"),
        "en": ("Secure the battery holder and IMU, then tuck the wiring", "Install the battery holder on the torso and fasten the IMU flat against its locating position on the backplate, in the specified orientation. Tuck spare cable to the sides, clear of the battery slide and latch.", "Secure the board and plugs before tucking spare cable. Keep wiring clear of servos, bearings and moving brackets, and match the IMU orientation in the 3D assembly reference."),
    },
    {
        "slug": "04-legs-body", "group": "legs", "landscape": True,
        "zh": ("两条腿与躯干合装", "两腿分别装好后，与躯干总成连接。对照实拍检查白色连接件、金属支撑板和脚掌朝向，再核对各关节的位置与编号。", "左右以鸭子自身为准：右腿 10–14，左腿 20–24。跨关节的线束保留活动余量，不要拉紧或夹在连接件之间。"),
        "en": ("Join both legs to the torso", "Attach the assembled legs to the torso. Compare the white brackets, metal support plates and foot orientation with the photograph, then check each joint position and ID.", "Left and right refer to the robot itself: right leg 10–14, left leg 20–24. Leave slack across joints, with no cable trapped between brackets."),
    },
    {
        "slug": "05-head-neck", "group": "neck",
        "zh": ("连接头部与颈部，预留线束活动量", "将头壳与白色颈部支架连接，核对连接件、轴承和螺丝位置。黑色总线线束从支架侧面引出，给转头和俯仰保留自然弯曲的余量。", "不要把余线夹在头壳开口与支架之间。本图为头颈连接参考，颈部总成仍需继续与躯干连接。"),
        "en": ("Connect the head and neck, leaving cable slack", "Join the head shell to the white neck bracket, checking the bracket, bearing and fastener positions. Route the black bus harness along the side with a relaxed bend for head rotation and pitch movement.", "Do not trap spare cable between the head-shell opening and the bracket. This photo shows the head/neck connection; the neck assembly must still be joined to the torso."),
    },
]

GROUPS = {
    "body": ("body-photos", "HUB、IMU 与电池仓，跟着实拍接好装稳", "先分线，再预接躯干总成，最后固定电池仓与 IMU。照片中的黑线按信号名核对；点击图片可放大查看。", "HUB · IMU · 电池仓"),
    "legs": ("leg-photos", "双腿与躯干合装参考", "对照实拍看脚掌、连接件与躯干的相对位置，配合 3D 视角核对左右方向。", "HD1910 · 双腿 · 躯干"),
    "neck": ("neck-photos", "头颈连接与线束预留", "头部内部装好后，再核对颈部连接件和线束出口，让关节活动时线束有余量。", "头壳 · 颈部支架 · 理线"),
}


def render_photo_group(group):
    identifier, title, intro, badge = GROUPS[group]
    selected = [s for s in STEPS if s["group"] == group]
    cards = []
    for number, step in enumerate(selected, 1):
        heading, body, detail = map(escape, step["zh"])
        image = "../assets/body-assembly/" + step["slug"] + ".jpg"
        original = "../assets/body-assembly/originals/" + step["slug"] + ".jpg"
        overview = " head-step--overview" if len(selected) == 1 or number == len(selected) else ""
        landscape = " body-step--landscape" if step.get("landscape") else ""
        width, height = (1448, 1086) if step.get("landscape") else (1086, 1448)
        cards.append(
            f'<article class="head-step{overview}{landscape}">'
            f'<a class="head-step__photo" href="{image}" target="_blank" rel="noopener" aria-label="放大查看：{heading}">'
            f'<img src="{image}" alt="{heading}的装配实拍" width="{width}" height="{height}" loading="lazy" decoding="async"></a>'
            f'<div class="head-step__copy"><span class="head-step__number">{number:02d}</span><h4>{heading}</h4>'
            f'<p>{body}</p><p class="head-step__detail">{detail}</p>'
            f'<a class="head-step__original" href="{original}" target="_blank" rel="noopener">查看原始实拍 ↗</a></div></article>'
        )
    return (
        f'<section class="head-photos body-photos" id="{identifier}" aria-labelledby="{identifier}-title">'
        '<div class="head-photos__heading"><div><p class="eyebrow">ASSEMBLY / PHOTO REFERENCE</p>'
        f'<h3 id="{identifier}-title">{title}</h3></div><span class="badge">{badge}</span></div>'
        f'<p class="head-photos__intro">{intro}</p><div class="head-photo-grid">' + ''.join(cards) + '</div>'
        '<p class="head-photos__more"><a href="https://github.com/kissqy/Microduck-kissqy/blob/main/docs/BODY-ASSEMBLY.md">查看躯干、双腿与头颈完整实拍 ↗</a></p></section>'
    )


def render_markdown(language):
    english = language == "en"
    lines = [
        '[简体中文](BODY-ASSEMBLY.md) | **English**' if english else '**简体中文** | [English](BODY-ASSEMBLY.en.md)', '',
        '# Torso, legs and head/neck connections · photo guide' if english else '# 躯干、双腿与头颈连接 · 装配实拍', '',
        ('These photos cover the four-way HUB harness, torso prewiring, battery-holder and IMU mounting, the leg/torso assembly and the head/neck connection. Assemble with power disconnected. Follow the connector signals and the actual mounting positions.' if english else '这组实拍补齐 **HUB 四路分线 → 躯干预接线 → 电池仓与 IMU 固定 → 双腿合装 → 头颈连接**。断电后装配，按接口信号与实际安装位核对。'), '',
        ('[Web assembly guide (Chinese)](https://kissqy.github.io/Microduck-kissqy/build/assembly.html#body-photos) · [Inside the head](HEAD-ASSEMBLY.en.md) · [3D reference](https://kissqy.github.io/Microduck-kissqy/assembly.html)' if english else '[在线查看对应装配章节](https://kissqy.github.io/Microduck-kissqy/build/assembly.html#body-photos) · [头部内部安装五步实拍](HEAD-ASSEMBLY.md) · [3D 装配参考](https://kissqy.github.io/Microduck-kissqy/assembly.html)'), '',
    ]
    for number, step in enumerate(STEPS, 1):
        title, body, detail = step[language]
        image = 'assets/body-assembly/' + step['slug'] + '.jpg'
        original = 'assets/body-assembly/originals/' + step['slug'] + '.jpg'
        width = 680 if step.get('landscape') else 480
        lines += [f'## {number:02d} · {title}', '', body, '', f'<a href="{original}"><img src="{image}" width="{width}" alt="{escape(title, quote=True)}" /></a>', '', detail, '', f'[Original photo]({original})' if english else f'[查看原始实拍]({original})', '']
    if english:
        lines += ['## Match the branch connections', '', '| Branch | Connection reference |', '| --- | --- |', '| Head/neck | HAT → 34 → 33 → 32 → 31 → 30 → HUB |', '| Right leg | HUB → 10 → 11 → 12 → 13 → 14 |', '| Left leg | HUB → 20 → 21 → 22 → 23 → 24 |', '| IMU | HUB → IMU bus connector J1 |', '', 'The four HUB bus ports share their nets. Port-to-branch positions in a photo are not mandatory. With an all-black harness, check GND, power and DATA by connector signals rather than wire color.', '', '[HUB hardware and power connections](../hardware/README.en.md) · [Full build guide](MICRODUCK-BUILD-GUIDE.en.md)']
    else:
        lines += ['## 对照支路连接关系', '', '| 支路 | 连接参考 |', '| --- | --- |', '| 头颈 | HAT → 34 → 33 → 32 → 31 → 30 → HUB |', '| 右腿 | HUB → 10 → 11 → 12 → 13 → 14 |', '| 左腿 | HUB → 20 → 21 → 22 → 23 → 24 |', '| IMU | HUB → IMU 总线端子 J1 |', '', 'HUB 四个总线口电气共网，不把照片中的端口位置规定为固定支路。全黑线束按 GND、电源、DATA 信号核对，不按线色判断。', '', '[HUB 硬件与取电说明](../hardware/README.md) · [返回复刻总教程](MICRODUCK-BUILD-GUIDE.md)']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    for language, filename in [('zh', 'BODY-ASSEMBLY.md'), ('en', 'BODY-ASSEMBLY.en.md')]:
        (root / 'docs' / filename).write_text(render_markdown(language))
    print('Rendered Chinese and English body assembly photo guides.')
