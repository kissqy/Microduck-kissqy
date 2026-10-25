[简体中文](OFFICIAL-CHANGES.zh-CN.md) | **English** | [Русский](OFFICIAL-CHANGES.ru.md)

# R17 v1.0.137 / official 0.15.1 changes

Additional upstream-source changes relative to v1.0.136:

- `duck-control/src/deployment.rs`: accepts a rough-terrain contract explicitly disabling filtering; requires head / leg alpha 1. Records this model's passthrough flag without changing global parameters.
- `robotd/src/control.rs`: bypasses the original low-pass processing when the active model explicitly requires passthrough, restores original parameters after leaving it, and exposes actual active filtering.
- `robotd/src/main.rs`: adds `active_target_filters` readback to bus data; other control and telemetry paths remain.
- `robotd/src/feetech_commissioning.rs`: updates the build identity to control.21.

LB uses the existing official named-skill interface with the 11000-iteration recovery teacher and base scale 1.0. The Python importer accepts the same contract. The console displays actual model filtering without adding a filter toggle. Original model contracts and ONNX files are unchanged.

Official skill scheduling, UART / HAT, calibration-unit conversion, HOME cancellation, sound, and the physical-gamepad bridge carry over from v136. Global filter algorithms and configuration remain unchanged; official voltage compensation still affects actual scaling. Only robotd was rebuilt; other binaries were reused from v136. See [R17 changes](R17-CHANGES.en.md) and [settings design](docs/design/r17-settings-design.en.md) for earlier modifications and temporary servo testing. Complete file differences are in `R17-SOURCE-MANIFEST.json`.
