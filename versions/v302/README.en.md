[简体中文](README.md) | **English**

# Microduck Console Studio V302 Beta

**Console-only update; reuses unchanged control.102 firmware and the existing 11 ONNX models. R2 / R10 remain unchanged.** Existing control.102 users do not reinstall firmware or reflash their card.

| Content | Entry |
| --- | --- |
| Features, changes and HAT numbering | [V302 page](https://kissqy.github.io/Microduck-kissqy/console-v302/en.html) |
| Console runtime · 42.3 MB | [Microduck-Console-Studio-V302.zip](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v302/Microduck-Console-Studio-V302.zip) |
| Release notes | [V302 Release](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v302) · [repository notes (中文)](../../docs/releases/console-studio-v302.md) |
| Size and SHA256 | [release-assets/](release-assets/) |
| Console source | Complete Python / JavaScript source and local verification records are included in the runtime |
| Native firmware and source | [control.102 guide](../v260/README.en.md) · [V260 firmware source](../v260/firmware/) |
| New system image | [R2 image and stable firmware](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260) |

Close the old console and fully extract the package. Windows: `start.cmd`; macOS / Linux: `bash start.command`. Open `http://127.0.0.1:8090`. Entering Number or Hardware test prepares isolated maintenance modules without replacing native motion firmware.

V302 improves scan reuse, midpoint waits, maintenance sessions and entry checks. It retains four workspaces, 3D zero/HOME references, label avoidance and the two-column IMU layout.

Scan manually before changing IDs; rescan after rewiring, power cycles or device changes. Connect one unknown-ID servo at a time. Right leg 10–14; left leg 20–24; neck/head 30–34; IMU 200. Recalibrate a joint after changing its midpoint.

This is a pre-release. Local regressions do not extend physical Known-Good. Next single task: validate numbering, midpoint calibration and mode changes on Reference Duck / control.102, recording actual results and latency. GitHub automatic Source code snapshots are not complete runtimes.
