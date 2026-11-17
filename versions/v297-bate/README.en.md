[简体中文](README.md) | **English**

# Microduck Console Studio V297 BATE

Independent console pre-release for **control.102 / System Image R2 / Wi-Fi setup R10**.

| Item | Entry |
| --- | --- |
| Features and HAT numbering guide | [V297 BATE page](https://kissqy.github.io/Microduck-kissqy/console-bate/en.html) |
| Complete change log | [Release notes (Chinese)](../../docs/releases/console-studio-v297-bate.md) |
| Console runtime · 42.2 MB | [Microduck-Console-Studio-V297-BATE.zip](https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v297-bate/Microduck-Console-Studio-V297-BATE.zip) · [release notes](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v297-bate) |
| Version file directory | [release-assets/](release-assets/) |
| Console source | Python and frontend source are included in the console runtime. Any separate source archive will be listed in Release Assets when uploaded |
| Matching firmware and source | [V260 / control.102](../v260/README.md) · [firmware source](../v260/firmware/) |
| Stable release | [V260 / R2](../v260/) |

Existing R2 / control.102 users only replace the desktop console. Extract the full package, run `start.cmd` on Windows or `bash start.command` on macOS/Linux, then open `http://127.0.0.1:8090`.

Connect only one unnumbered or possibly duplicate-ID servo at a time. Verified distinct IDs can be chained. Right leg: 10–14; left leg: 20–24; neck/head: 30–34, viewed from the robot’s own perspective. ID 200 is the IMU. Recalibrate a joint after changing its midpoint.

GitHub’s automatic Source code archives are repository snapshots, not complete console runtimes. The existing record contains 35 passing local controlled cases; physical-robot acceptance is still pending. Existing hardware Known-Good records are unchanged. The next single task is V297 BATE acceptance on the reference robot.
