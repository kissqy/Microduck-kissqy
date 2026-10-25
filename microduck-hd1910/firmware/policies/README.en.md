[简体中文](README.md) | **English** | [Русский](README.ru.md)

# Policy baseline — R17 v1.0.146 / official 0.15.1

This historical baseline uses one Walk model: a 9600-iteration joint walking / fall-recovery policy, with base scale 0.9, head filter 0.5, and leg filter 0.7. The old 14000-iteration walking model was removed from firmware and retained only in `test-data/walk-teacher14000` for numerical source regression. LB manual recovery retained the 11000-iteration teacher (base 1.0, head / leg passthrough), with automatic Stand unbound; sit / stand, pick, and forward roll remained.

Original training records and independent runtime settings are explained in [robotd design](../docs/design/robotd-design.en.md). Import, unique-slot binding, retired-model cleanup, and upgrade preservation are in [settings design](../docs/design/r17-settings-design.en.md). For current V164 mappings, see [the console guide](../console/USER-GUIDE.en.md).
