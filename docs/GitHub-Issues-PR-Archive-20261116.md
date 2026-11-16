# Microduck-kissqy GitHub Issues 与 PR 公开归档

源仓库：[kissqy/Microduck-kissqy](https://github.com/kissqy/Microduck-kissqy)。归档日期：2026-11-16；下列原始时间均为 UTC。

本文件为原仓库公开 Issues、PR 及评论的原文快照，供 Gitee 读者查阅；状态以归档时读取结果为准，后续更新见各条目原链接。

共 **9 个 Issues、5 个 PR、8 条评论**；状态按本次读取的 GitHub 公开记录标注。PR 评论读取包含普通讨论、行内审阅与审阅提交，本次未取得额外的行内审阅或审阅正文。正文及评论使用 Markdown 原文代码块保存，附件与外部内容保留原链接。

| 编号 | 类型 | 原状态 | 作者 | 标题 |
| --- | --- | --- | --- | --- |
| [#1](https://github.com/kissqy/Microduck-kissqy/issues/1) | Issue | 开放 / open | [@wayneyuan11](https://github.com/wayneyuan11) | 想要个vx啊哥 |
| [#2](https://github.com/kissqy/Microduck-kissqy/pull/2) | PR | 已合并 / merged | [@lxm](https://github.com/lxm) | fix: 提供 Armbian 启动配置断电保护修复工具 |
| [#3](https://github.com/kissqy/Microduck-kissqy/issues/3) | Issue | 开放 / open | [@javierbo21-glitch](https://github.com/javierbo21-glitch) | Donde comprar la placa |
| [#4](https://github.com/kissqy/Microduck-kissqy/issues/4) | Issue | 开放 / open | [@jaquestechnology-dev](https://github.com/jaquestechnology-dev) | Purchase of 2 HAT-V5 + 2 IMU boards for Microduck |
| [#5](https://github.com/kissqy/Microduck-kissqy/pull/5) | PR | 已关闭，未合并 / closed | [@proskurin-core](https://github.com/proskurin-core) | docs: добавь русскую документацию Microduck |
| [#6](https://github.com/kissqy/Microduck-kissqy/issues/6) | Issue | 开放 / open | [@polygoku](https://github.com/polygoku) | MAKHEX request: permission scope to mirror Microduck CAD/PCB files for signed-in makers |
| [#7](https://github.com/kissqy/Microduck-kissqy/issues/7) | Issue | 开放 / open | [@buklyakovsv2-prog](https://github.com/buklyakovsv2-prog) | Contact for purchasing Microduck parts without WeChat |
| [#8](https://github.com/kissqy/Microduck-kissqy/pull/8) | PR | 已合并 / merged | [@kissqy](https://github.com/kissqy) | Fix HUB orientation and soften assembly cable bends |
| [#9](https://github.com/kissqy/Microduck-kissqy/issues/9) | Issue | 开放 / open | [@AchimPieters](https://github.com/AchimPieters) | Title: Building your Microduck and documenting the journey |
| [#10](https://github.com/kissqy/Microduck-kissqy/pull/10) | PR | 开放 / open | [@lxm](https://github.com/lxm) | Add Orange Pi Zero 3W firmware downloads and board support submodule |
| [#11](https://github.com/kissqy/Microduck-kissqy/issues/11) | Issue | 开放 / open | [@Kaahhllll](https://github.com/Kaahhllll) | Availability and US ordering for one HD1910 HAT/IMU/HUB set |
| [#12](https://github.com/kissqy/Microduck-kissqy/issues/12) | Issue | 已关闭 / closed | [@aminadav-ai](https://github.com/aminadav-ai) | . |
| [#13](https://github.com/kissqy/Microduck-kissqy/issues/13) | Issue | 开放 / open | [@aminadav-ai](https://github.com/aminadav-ai) | 🦆 致敬 Microduck-kissqy！我们将您的 R17-V167 中控台与全部 6 个飞特 HD-1910 .ONNX 模型完整移植到了 DuckSpace.org 3D 房间（在线可玩） |
| [#14](https://github.com/kissqy/Microduck-kissqy/pull/14) | PR | 开放 / open | [@xxxkkw](https://github.com/xxxkkw) | 为 R2 增加 USB-C 有线上网支持 |

## Issue #1 · 想要个vx啊哥

- 原链接：[#1](https://github.com/kissqy/Microduck-kissqy/issues/1)
- 作者：[@wayneyuan11](https://github.com/wayneyuan11)
- 原状态：开放 / open
- 创建：2026-10-14T09:05:39Z
- 最后更新：2026-10-14T12:13:23Z

### 正文原文

```markdown

```

### 评论与审阅（1）

#### 1. kissqy · 2026-10-14T12:13:23Z

- 原评论：[链接](https://github.com/kissqy/Microduck-kissqy/issues/1#issuecomment-6168069273)
- 作者：[@kissqy](https://github.com/kissqy)
- 创建：2026-10-14T12:13:23Z
- 最后更新：2026-10-14T12:13:23Z

```markdown
首页下面有扫码加群
```


## PR #2 · fix: 提供 Armbian 启动配置断电保护修复工具

- 原链接：[#2](https://github.com/kissqy/Microduck-kissqy/pull/2)
- 作者：[@lxm](https://github.com/lxm)
- 原状态：已合并 / merged
- 创建：2026-10-21T13:37:25Z
- 最后更新：2026-10-21T13:57:22Z
- 关闭：2026-10-21T13:57:22Z
- 合并：2026-10-21T13:57:22Z

### 正文原文

````markdown
Armbian 26.2.1 的 `add_usb_storage_quirks()` 每次启动都会通过多次 `sed -i` 重写 `/boot/armbianEnv.txt`，即使 USB 参数完全不变，随后仅后台 `sync &`。在 Radxa ZERO 3W 上遇到过 U-Boot 读取该文件为 0 字节、因默认设备树路径错误而停在启动阶段的故障；手动启动 Linux 回放文件系统日志后配置恢复。这与未完成的写入事务一致，但不是对具体断电时刻或硬件原因的确定归因。

本 PR 提供独立的 `scripts/repair-armbian-env.py`，让已有系统无需升级 Armbian 或重装机器人固件即可修补已确认的写入流程：

- 先在 `/tmp` 生成候选配置，内容不变则不重写启动文件；有变化时完整写入同文件系统临时文件、同步、原子替换并同步文件系统，保留属主与权限。
- 仅替换匹配已知内容哈希的 USB 函数，将它改为前台等待并传播错误，保留其他板级优化。未知/上游已修改的函数明确拒绝覆盖。
- 提供默认只读检查、备份后安装、重复执行及校验备份和当前脚本的回退；工具本身不重启系统/服务，也不执行硬件优化或运动命令。
- 添加中文使用与回退说明，以及旧函数测试摘录和对应 GPL-2.0 许可。

这是可单独使用的维护工具。没有修改已发布的 V167 载荷、版本号、固定版本复现流程或机器人控制代码；已有安装包不会自动包含本修复。使用方法见新增的 `docs/robot/armbian-boot-config.md`。

验证：

- 在隔离、禁用网络的 Linux ARM64 / Python 3.12 容器中，20 项 unittest 全部通过。先复现旧函数在内容不变时替换文件，再验证修复后的幂等性、USB 规则、其他启动字段、元数据保留及故障处理。
- 覆盖部分写入、同步、重命名失败，以及未知函数、备份损坏、后续系统修改时的覆盖拒绝。
- 在独立容器中实际执行 CLI 的 `--check → --apply → --check → --apply → --restore`，使用真实 `fsync` 和 GNU `sync -f`，通过。
- `git diff --check` 通过。没有做物理断电或本工具安装后的完整启动验证，也不声称可防止 TF 卡或供电硬件故障。

复现命令（仓库根目录）：

```bash
docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$PWD:/src:ro" -w /src/microduck-hd1910/firmware \
  python:3.12-slim-bookworm \
  python3 -m unittest discover -s scripts/tests -p test_repair_armbian_env.py -v
```
````

### 评论与审阅（0）

无公开评论或审阅正文。

## Issue #3 · Donde comprar la placa

- 原链接：[#3](https://github.com/kissqy/Microduck-kissqy/issues/3)
- 作者：[@javierbo21-glitch](https://github.com/javierbo21-glitch)
- 原状态：开放 / open
- 创建：2026-10-23T21:41:59Z
- 最后更新：2026-10-26T00:37:17Z

### 正文原文

```markdown
Hello, I am building your MicroDuck Feetech HD1910 project in Spain. I need one assembled HAT and one assembled torso IMU, both with AMP2.0 connectors. Could you send me the correct purchase link and the total price including shipping to Spain? Thank you.
```

### 评论与审阅（1）

#### 1. kissqy · 2026-10-26T00:37:17Z

- 原评论：[链接](https://github.com/kissqy/Microduck-kissqy/issues/3#issuecomment-6405628374)
- 作者：[@kissqy](https://github.com/kissqy)
- 创建：2026-10-26T00:37:17Z
- 最后更新：2026-10-26T00:37:17Z

```markdown
你可以在仓库清单中看到HAT和IMU成品的淘宝购买链接
```


## Issue #4 · Purchase of 2 HAT-V5 + 2 IMU boards for Microduck

- 原链接：[#4](https://github.com/kissqy/Microduck-kissqy/issues/4)
- 作者：[@jaquestechnology-dev](https://github.com/jaquestechnology-dev)
- 原状态：开放 / open
- 创建：2026-10-24T15:52:27Z
- 最后更新：2026-10-26T00:29:34Z

### 正文原文

```markdown
Hello kissqy,


I am from Brazil and I am building two complete FrankenDuck Microduck robots.

I am purchasing 30 Feetech HD-1910-C001 servos directly from FEETECH.

I would like to purchase:

- 2 × HAT-V5 AMP2.0 controller boards
- 2 × IMU-TO-DLX-V2 AMP2.0 boards

I need all four boards fully assembled and tested, with the FT6 firmware installed on both IMUs.

Could you please confirm:

1. Total price for the two complete sets.
2. Availability and delivery time.
3. Shipping options to Brazil or within China.
4. Whether cables and connectors are included.
5. How I can place the order and make payment.

Thank you very much!
```

### 评论与审阅（1）

#### 1. kissqy · 2026-10-26T00:29:33Z

- 原评论：[链接](https://github.com/kissqy/Microduck-kissqy/issues/4#issuecomment-6405541111)
- 作者：[@kissqy](https://github.com/kissqy)
- 创建：2026-10-26T00:29:33Z
- 最后更新：2026-10-26T00:29:33Z

```markdown
请看开源仓库中有HAT和IMU的淘宝购买链接，可以发货至中转仓，会烧录好固件
```


## PR #5 · docs: добавь русскую документацию Microduck

- 原链接：[#5](https://github.com/kissqy/Microduck-kissqy/pull/5)
- 作者：[@proskurin-core](https://github.com/proskurin-core)
- 原状态：已关闭，未合并 / closed
- 创建：2026-10-25T07:35:52Z
- 最后更新：2026-10-25T08:57:51Z
- 关闭：2026-10-25T07:39:02Z

### 正文原文

```markdown
Переведи 128 руководств и технических документов, свяжи языковые версии, добавь русское HTML-руководство и обнови контрольные суммы.
```

### 评论与审阅（1）

#### 1. chatgpt-codex-connector[bot] · 2026-10-25T07:36:00Z

- 原评论：[链接](https://github.com/kissqy/Microduck-kissqy/pull/5#issuecomment-6394947031)
- 作者：[@chatgpt-codex-connector[bot]](https://github.com/chatgpt-codex-connector[bot])
- 创建：2026-10-25T07:36:00Z
- 最后更新：2026-10-25T07:37:37Z

```markdown
<!-- codex-pull-request-review-summary -->
<!-- codex-review-state:v1 {"code_review":{"commit_sha":"99eda6a20417903de96f0e46391cd0087ba3f03c","has_any_findings":true,"has_unresolved_findings":true,"status":"failed"},"security_review":{"commit_sha":null,"has_any_findings":null,"has_unresolved_findings":null,"status":null}} -->

## Codex Review Summary

This comment shows the latest Codex review activity on this pull request.

| Review | Status | Commit | Review trigger |
| --- | --- | --- | --- |
| 📝 **Code Review** | ⚠️ **Failed** <relative-time datetime="2026-10-25T07:37:37.232520Z">2026-10-25T07:37:37.232520Z</relative-time><br/>We couldn’t complete this review. Comment `@codex review` to try again. | `99eda6a` | PR opened |



<details> <summary>ℹ️ About Codex in GitHub</summary>
<br/>

[Your team has set up Codex to review pull requests in this repo](https://chatgpt.com/codex/cloud/settings/general). Reviews are triggered when you
- Open a pull request for review
- Mark a draft as ready
- Comment "@codex review" or "@codex security review".

Codex reacts with 👀 while any review is running, comments if it has suggestions, and reacts with 👍 once all reviews finish with no findings.

</details>
```


## Issue #6 · MAKHEX request: permission scope to mirror Microduck CAD/PCB files for signed-in makers

- 原链接：[#6](https://github.com/kissqy/Microduck-kissqy/issues/6)
- 作者：[@polygoku](https://github.com/polygoku)
- 原状态：开放 / open
- 创建：2026-10-25T14:11:52Z
- 最后更新：2026-10-25T14:11:52Z

### 正文原文

```markdown
Hello kissqy — we are featuring and crediting Microduck on the independent maker site **MAKHEX** (https://makhex.com/projects/microduck-robot/) with links to your repository and guides. We already have permission from the MAKHEX owner to use the demo media, but **we are not assuming that permission covers CAD, PCB or firmware redistribution**. We reviewed the mixed-license notice and want to respect your rights and upstream contributors.

Could you confirm, **in writing**, whether you personally have rights to authorize any of the following for MAKHEX, and if so on what terms?

1. Host unmodified copies of the **FrankenDuck 36 STL files / 3MF print project** behind free MAKHEX maker-account login, with creator credits, original notices and links.
2. Host the **four EasyEDA Pro .epro2 HAT/IMU project files** (October 7 EH2.5 and October 15 AMP2.0 revisions) in the same member-only reference library, retaining your notices.
3. Separately: whether physical printed parts / assembled HAT/IMU boards derived from your own original contributions can be offered as optional paid components, without implying your endorsement. We will **not** sell or bundle derivatives until permitted by all relevant rights holders.

We recognize that some geometry, hardware and firmware originated with third parties and you cannot grant rights you do not hold; if permission is limited, a list of files/scopes permitted or other maintainers to contact would be very helpful. An explicit repo license/permission file or a written response on this issue will work for our documentation.

Until confirmed, MAKHEX links visitors to your original source downloads rather than republishing CAD binaries or selling their derivatives. Thank you for documenting the project.
```

### 评论与审阅（0）

无公开评论或审阅正文。

## Issue #7 · Contact for purchasing Microduck parts without WeChat

- 原链接：[#7](https://github.com/kissqy/Microduck-kissqy/issues/7)
- 作者：[@buklyakovsv2-prog](https://github.com/buklyakovsv2-prog)
- 原状态：开放 / open
- 创建：2026-10-26T10:34:16Z
- 最后更新：2026-10-29T06:20:18Z

### 正文原文

```markdown
您好，kissqy！我没有微信，想购买 Microduck 配件。请问您能提供联系邮箱或其他私信方式吗？谢谢！
```

### 评论与审阅（1）

#### 1. kissqy · 2026-10-29T06:20:17Z

- 原评论：[链接](https://github.com/kissqy/Microduck-kissqy/issues/7#issuecomment-6489526648)
- 作者：[@kissqy](https://github.com/kissqy)
- 创建：2026-10-29T06:20:17Z
- 最后更新：2026-10-29T06:20:17Z

```markdown
你直接在我的淘宝店铺购买就行 不需要通过微信联系我
```


## PR #8 · Fix HUB orientation and soften assembly cable bends

- 原链接：[#8](https://github.com/kissqy/Microduck-kissqy/pull/8)
- 作者：[@kissqy](https://github.com/kissqy)
- 原状态：已合并 / merged
- 创建：2026-10-30T14:27:58Z
- 最后更新：2026-10-30T14:28:36Z
- 关闭：2026-10-30T14:28:36Z
- 合并：2026-10-30T14:28:36Z

### 正文原文

```markdown
Correct the HUB front/back mounting direction and show C1 on the reverse PCB side, following the author's physical assembly. Add clearance-adaptive rounded cable bends while preserving connector endpoints, and refresh the precomputed paths.

Validated all 53 conductors in 8 assembled/open-lid/exploded states: 121,268 independent geometry segments checked, no model crossings. All 53 conductors retain rounded bends after cache loading; HUB-side and tangent-fillet checks pass.
```

### 评论与审阅（0）

无公开评论或审阅正文。

## Issue #9 · Title: Building your Microduck and documenting the journey

- 原链接：[#9](https://github.com/kissqy/Microduck-kissqy/issues/9)
- 作者：[@AchimPieters](https://github.com/AchimPieters)
- 原状态：开放 / open
- 创建：2026-11-01T14:29:36Z
- 最后更新：2026-11-01T17:35:49Z

### 正文原文

```markdown
# Building your Microduck and documenting the journey

Hi kissqy,

What a fantastic project! I’m going to try printing and building your duck, and I’ll be documenting the whole journey on my website.

I’ve already started sharing my progress in these posts:

- [Part 1 – The Plan](https://www.studiopieters.nl/microduck-build-part-1-the-plan/)
- [Part 2 – The Hardware](https://www.studiopieters.nl/microduck-build-part-2-the-hardware/)
- [Part 3 – Printing the Parts](https://www.studiopieters.nl/microduck-build-part-3-printing-the-parts/)
- [Part 4 – Too Many Ducks](https://www.studiopieters.nl/microduck-build-part-4-too-many-ducks/)
- [Part 5 – Starting Over](https://www.studiopieters.nl/microduck-build-part-5-starting-over/)

After looking at several different Microduck builds, yours really caught my attention and made me want to give it a go myself. Taking a robot from an idea to something other people can build takes a lot of time and patience, so thank you for sharing that work with the community!

I hope you’ll enjoy seeing your project come to life in someone else’s workshop. I’ll make sure to credit you and link back to your repository, so readers can find the person and project that inspired my build.

There will certainly be plenty for me to learn along the way. If I get stuck, I’d really appreciate being able to ask you a question here now and then. Any advice, useful tips, or pointers to things I should watch out for would be very welcome, whenever you have the time.

If there are any parts of the build you would recommend checking before I start ordering hardware or printing, I’d love to hear about them!

My next step is to go through the hardware requirements and start ordering the parts. I’ll keep you posted on my progress, and hopefully my notes and photos will also be useful to others who want to build your duck.

Thanks again for sharing your project. I’m excited to get started and see this little duck take its first steps!

Best wishes,  
Achim  
[StudioPieters](https://www.studiopieters.nl/)
```

### 评论与审阅（1）

#### 1. AchimPieters · 2026-11-01T17:35:49Z

- 原评论：[链接](https://github.com/kissqy/Microduck-kissqy/issues/9#issuecomment-6561463172)
- 作者：[@AchimPieters](https://github.com/AchimPieters)
- 创建：2026-11-01T17:35:49Z
- 最后更新：2026-11-01T17:35:49Z

```markdown
 Update: I have now ordered the boards through a forwarding service (Superbuy):
  the HAT, the HUB and the IMU TO DXL from your Taobao shop. Before I build, I
  have a few questions, so I do not make mistakes:

  1. **Version:** The HAT and IMU are available as AMP2.0 and EH2.5 in the repo.
  The shop listing only shows "HAT", "HUB" and "IMU TO DXL". Are the boards in
  the shop the **AMP2.0** version? That is the one I want.
  2. **IMU firmware:** Is the firmware already flashed on the IMU TO DXL when it
  is sold? (I read in an older issue that it is, but I want to be sure.)
  3. **HUB capacitor:** Does the HUB include the **1000 µF capacitor**? If not,
  which type and voltage should I buy myself?
  4. **Battery contacts:** Which contacts or wiring parts do I need for the
  NP-F550 battery holder? Are they sold in your shop, or should I buy them
  somewhere else?
  5. **Forwarding warehouse:** Can all three boards ship to a forwarding
  warehouse together? I already placed the orders, so please tell me if
  something is wrong.

  I write the blog so other beginners can follow along. I
  will keep your license in mind (personal, non-commercial use) and I will
  mention it in the blog. Thank you for your time and for sharing this project!
```


## PR #10 · Add Orange Pi Zero 3W firmware downloads and board support submodule

- 原链接：[#10](https://github.com/kissqy/Microduck-kissqy/pull/10)
- 作者：[@lxm](https://github.com/lxm)
- 原状态：开放 / open
- 创建：2026-11-03T04:25:03Z
- 最后更新：2026-11-04T14:11:03Z

### 正文原文

```markdown
Orange Pi Zero 3W（Allwinner A733）使用独立的刷卡镜像。根目录和 HD1910 的中英文 README 提供 [exp.1 镜像与 SHA-256](https://github.com/lxm/microduck-maker/releases/tag/orangepi-zero3w-exp.1)，并单独标明含 IMX219 摄像头的 Actions 构建入口。

执行 `git submodule update --init microduck-hd1910/boards/microduck-maker` 可取得 [固定版本的 BSP 与镜像源码](https://github.com/lxm/microduck-maker/tree/58ca093d4b208bad3d88bf8eaa1f1453eb1e333a/firmware/orangepi-zero3w)。子模块包含设备树、音频模块、IMX219 格式转换及镜像构建流程。服务沿用原版 robotd、tofd 和 mediad，板级配置使用 systemd drop-in。

在 A733 1 GB V1.5 测试板上验证了 IMX219 的 720p 和 1080p 实拍、WebRTC 浏览器解码以及 ONNX CPU 检测。默认 720p30，摄像头按需启动。公开 exp.1 早于摄像头适配。新镜像的刷卡启动仍待实测。含摄像头的完整 IMG/XZ 已通过文件系统检查与压缩读回校验。[下载该构建的镜像和 SHA-256](https://github.com/lxm/microduck-maker/actions/runs/41841226889/artifacts/13330971141) · [构建记录](https://github.com/lxm/microduck-maker/actions/runs/41841226889)

```

### 评论与审阅（0）

无公开评论或审阅正文。

## Issue #11 · Availability and US ordering for one HD1910 HAT/IMU/HUB set

- 原链接：[#11](https://github.com/kissqy/Microduck-kissqy/issues/11)
- 作者：[@Kaahhllll](https://github.com/Kaahhllll)
- 原状态：开放 / open
- 创建：2026-11-06T16:14:52Z
- 最后更新：2026-11-07T09:38:15Z

### 正文原文

```markdown
您好，kissqy！

我计划在美国个人制作一台 HD1910 版本的 Microduck，自己打印结构件。
想先确认您目前的配件供货和购买方式：

1. AMP2.0 HAT、已烧录 FT6 的躯干 IMU 和带 1000 µF 电容的 HUB，各 1 块，目前是否有货？参考价是否仍为 119、99、69 元？多久可以发货？
2. 能否直接寄美国？如果只能寄中国境内中转仓，您推荐怎样下单和付款？我看到您在 issue #4 中回复过可以发到中转仓。
3. 每块板包含哪些连接线/接头？希望确认是与您当前 HD1910 软件配套的版本。
4. 采购页面推荐的 fanhao375 HD-1910-C001 团购（99 元/只）现在是否仍开放？一台机器人需要 15 只，能否给出当前联系/下单方式？能否与板卡合并到同一中转仓？舵盘、线材和 URT2 是否另购？
5. 如果您也能代购配套 Radxa ZERO 3W（2GB、无 eMMC、带排针）或结构金属件，请提供型号、价格和供货情况；金属件希望确认具体零件和适配 CAD 版本。

希望获得当前货价、国内运费、发货时间和美国购买路径；国际运费如需地址可另行私下提供，不会贴在公开 issue 中。谢谢！

---

English:

Hello kissqy,

I am planning one personal HD1910 Microduck build in the United States and will print the mechanical parts myself. Could you confirm:

- Current availability and dispatch time for 1 × AMP2.0 HAT, 1 × FT6-preflashed torso IMU and 1 × HUB with the 1000 µF capacitor, and whether prices remain CNY 119/99/69? Which leads/connectors are included?
- Direct US delivery, or the ordering/payment process for delivery to a Chinese forwarding warehouse as mentioned in issue #4?
- Whether fanhao375's CNY 99 HD-1910-C001 group buy is currently open for 15 servos, the correct contact/order channel, included horns/leads/URT2, and whether motors/boards can reach the same forwarding warehouse?
- Availability/pricing of a matching Radxa ZERO 3W (2GB, no eMMC, with header) and any structural-metal set, with its exact contents/CAD revision?

An itemized goods/domestic-postage quote and ordering route would help. Any precise delivery address can be supplied privately if needed.

Thank you!
```

### 评论与审阅（1）

#### 1. kissqy · 2026-11-07T09:38:15Z

- 原评论：[链接](https://github.com/kissqy/Microduck-kissqy/issues/11#issuecomment-6705149729)
- 作者：[@kissqy](https://github.com/kissqy)
- 创建：2026-11-07T09:38:15Z
- 最后更新：2026-11-07T09:38:15Z

```markdown
国外比较麻烦 因为电子器件是出口管制
```


## Issue #12 · .

- 原链接：[#12](https://github.com/kissqy/Microduck-kissqy/issues/12)
- 作者：[@aminadav-ai](https://github.com/aminadav-ai)
- 原状态：已关闭 / closed
- 创建：2026-11-09T17:19:17Z
- 最后更新：2026-11-09T21:58:14Z
- 关闭：2026-11-09T21:58:14Z

### 正文原文

```markdown
.
```

### 评论与审阅（0）

无公开评论或审阅正文。

## Issue #13 · 🦆 致敬 Microduck-kissqy！我们将您的 R17-V167 中控台与全部 6 个飞特 HD-1910 .ONNX 模型完整移植到了 DuckSpace.org 3D 房间（在线可玩）

- 原链接：[#13](https://github.com/kissqy/Microduck-kissqy/issues/13)
- 作者：[@aminadav-ai](https://github.com/aminadav-ai)
- 原状态：开放 / open
- 创建：2026-11-10T19:00:26Z
- 最后更新：2026-11-10T19:00:26Z

### 正文原文

```markdown
您好！非常钦佩您在 **Microduck-kissqy** 项目中开源的飞特 HD-1910 固件栈（`robotd` R17-V167）与实机训练策略！🙌

为了方便国内和全球开发者在浏览器里免安装体验您的成果，我们在 **DuckSpace.org 技能广场 & 3D 物理实验室**（自带完整中文界面，国内免翻墙直连）中专门移植并收录了您的工作：
👉 **在线直接体验（中文版）：https://duckspace.org/?lang=zh**

我们在平台上完整还原了您的固件中控与全部 6 个模型（均已标注 `kissqy/Microduck-kissqy` 作者署名、SHA-256 模型短 ID 及原仓链接）：

1. **「🧠 AI 自主大脑」专区独立卡片：`kissqy · Microduck-Console-R17-V167`**：点击卡片上的紫色按钮 **「🧠 在 3D 房间运行此智能大脑」**，3D 房间侧边会打开 **R17-V167 实时中控面板（`robotd v1.0.143`）**：
   - 在 3D 房间内预载您训练的全部 6 个飞特 HD-1910 `.ONNX` 模型与单脚独立策略，支持一键热切换动作槽（`walk`、左右腿 `🦩 单脚独立`、`sit`、`stand`、`ground_pick [G]`、`roulade [R]`、`kick_left [Q]`）；
   - 支持在线实时调节 R17 固件参数 `action_scale`（`0.70` R17 真机默认值 / `0.85` / `1.00`）并显示 `head_filter=0.50`、`leg_filter=0.70` 与 FT6 飞特总线状态（14/14 舵机在线 · TCP 9102）。
2. **「⚡ .ONNX 动作」专区完整收录全部 6 个 R17 策略模型与单腿独立真机视频**：
   - 行走 `walk/policy.onnx`（`1cbf8730eadd` · ckpt 9599）；
   - 起坐 `sitstand/policy.onnx`（`1c94934c6421` · ckpt 10000，按 `[P]` 切换）；
   - 地面低头捡物 `ground_pick/policy.onnx`（`b14e3a8b56dd` · ckpt 9999，按 `[G]` 触发）；
   - 前滚翻 `roulade/policy.onnx`（`59e15d7b04d0` · ckpt 9999，按 `[R]` 触发）；
   - 左脚踢球 `kick_left/policy.onnx`（`ee0376c92704` · ckpt 9999，按 `[Q]` 踢球）；
   - 倒地起身 `stand/policy.onnx`（`a481d9f211f3` · ckpt 11000）以及您的飞特 HD-1910 单腿金鸡独立真机实拍展示（进入 3D 房间自动抬脚 9 厘米金鸡独立，按空格键可切换左右腿）。

欢迎您随时来体验！如果任何地方需要修改或有新训练的 `.ONNX` 模型想要发布（页面右上角有 **「＋」上传按钮** 和 **「💡 反馈」** 按钮），请随时告诉我们！🦆✨
```

### 评论与审阅（0）

无公开评论或审阅正文。

## PR #14 · 为 R2 增加 USB-C 有线上网支持

- 原链接：[#14](https://github.com/kissqy/Microduck-kissqy/pull/14)
- 作者：[@xxxkkw](https://github.com/xxxkkw)
- 原状态：开放 / open
- 创建：2026-11-15T08:48:40Z
- 最后更新：2026-11-15T09:15:30Z

### 正文原文

```markdown
R2 目前提供 Wi-Fi / 热点配网，但没有 USB 有线上网组件；单独添加 USB gadget 还会被 Wi-Fi 专用的 NetworkManager 策略标记为 unmanaged。此改动为 ZERO 3W 的 USB-C 1 / OTG 增加 CDC ECM 网卡，让设备通过 Mac 的互联网共享，经 USB DHCP 获取地址、网关和 DNS，同时保留 IPv6 链路本地连接。

复用现有 V260 系统安装器，部署 USB gadget 服务、USB 专用 NetworkManager profile、managed 例外与 udev 规则，并校验文件权限和开机启用链接。安装过程保留当前网络连接，USB 服务在下次开机生效。PR 仅涉及联网组件、安装清单与校验值、相关说明和安装回归测试；SSH 继续沿用设备现有认证，不包含个人公钥、密码工具或本机构建信息。

验证：

- 系统安装器回归测试 3 项通过，覆盖安装 / 重复安装、缺失和错误启用链接修复，以及现有 Wi-Fi、R10、SSH 授权和模型文件保留。
- USB gadget 脚本通过 `bash -n`；8 条受影响的打包 SHA256 记录已核验，`git diff --check` 通过。
- 本次为源码与离线安装验证；ZERO 3W 实体板的 USB 枚举、DHCP 和 Mac 网络共享仍需实机验收。
```

### 评论与审阅（1）

#### 1. kissqy · 2026-11-15T09:15:30Z

- 原评论：[链接](https://github.com/kissqy/Microduck-kissqy/pull/14#issuecomment-6892198544)
- 作者：[@kissqy](https://github.com/kissqy)
- 创建：2026-11-15T09:15:30Z
- 最后更新：2026-11-15T09:15:30Z

```markdown
感谢提交！USB 有线联网对配网和故障排查很有帮助。我们已审阅这次改动，并复跑了 3 项离线安装测试，均通过。

我们先保留这条 PR。USB 初始化顺序、断线回退，以及与现有 Wi-Fi／热点逻辑的兼容性，后续由我们结合实机环境统一评估，再确定合入安排。目前暂不发布新版本。
```

