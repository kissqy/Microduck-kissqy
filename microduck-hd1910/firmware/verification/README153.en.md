[简体中文](README153.md) | **English** | [Русский](README153.ru.md)

# v153 verification records

Native Rust source did not change for v153. Existing control.32 binaries were reused after checking all source SHA values. v152 native builds and 29 startup tests remain historical evidence; old-package startup success is not treated as validation of this delivery.

Added release checks:

- `python-integrity153.log`: 23 ELF, copy-integrity, and installation-order tests.
- `python-diagnostic153.log`: 5 read-only diagnostic tests.
- `python-connection153.log`: 4 reconnection, 5 diagnostic, and 20 raw-telemetry / SSH regressions. Diagnostics duplicate the preceding log and are not counted twice.
- `frontend-startup153.log`, `frontend-gamepad153.log`: startup error, diagnostic download, and gamepad-repair UI regressions.
- `reproduction153.json`: five models each with old / new ARM programs passed using complete libraries; two truncated-library SIGBUS controls.
- `baseline-restored153.json`: archive SHA, original SHA values for 127 files, and restoration readback.
- `release-audit153.json`: final firmware, console ZIP, and source tar readback plus production firmware import.

QEMU covers loading and first inference, not physical UART or motion. Physical power-cycle boot, temperature, and walking were not tested in this record.
