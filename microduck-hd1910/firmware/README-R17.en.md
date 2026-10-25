[简体中文](README-R17.zh-CN.md) | **English** | [Русский](README-R17.ru.md)

# Microduck control.43 firmware and R17 V167 console

This directory contains **control.43** source based on official Microduck **0.15.1**, using IPC API **40**. Its paired Robot Console is **R17 V167**.

V167 is paired with control.43. Update: Fixed body jitter.

- [Compiled control.43 download and installation](../../release-assets/README.en.md)
- [Robot Console startup and usage](console/USER-GUIDE.en.md)
- [Firmware configuration, models, and installation](packaging/README.en.md)
- [Compile from source on a new machine](../docs/BUILD.en.md)
- [Current baseline and acceptance scope](../docs/BASELINE.en.md)
- [V167 build and test records](BUILDING-V167.en.md)
- [Upstream workspace development](CONTRIBUTING.md)

Rust, Python, web pages, models, and native programs were synchronized from delivered files. Source publication organized documentation and version indexes. Each robot must still use and check its own joint, direction, limit, and IMU calibration.
