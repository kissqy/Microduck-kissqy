[简体中文](official-roller-route.md) | **English** | [Русский](official-roller-route.ru.md)

# Official roller recovery route review

Target: 0.15.1 / 1 fa 84386. Retained `robotd-params/src/lib.rs` defaults Roller to `stand=None`; `set_standing_disabled` in `robotd/src/main.rs` is true for Roller. The original export contract also declares `manual_skill`, `slot=null`, and `required_skill_settings=null`.

Public upstream documentation checked October 11, 2026; `main` may be newer than 0.15.1:

- <https://github.com/pollen-robotics/microduck/blob/main/docs/policy-manifest.md>: perpetual models without `duration_s` require `--hold`; they do not automatically become timed actions.
- <https://github.com/pollen-robotics/microduck/blob/main/duck-control/src/policy.rs>: Roller does not select Stand for zero speed.

The v162 conclusion was to install / verify original recovery weights and display them as unbound. Do not turn training episode length or invented seconds into an execution window, or overwrite LB left-foot kick. Later manual-test configuration is described in [the current console guide](../../console/USER-GUIDE.en.md).
