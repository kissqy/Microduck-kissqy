[简体中文](README_FT6_SYNC15.md) | **English** | [Русский](README_FT6_SYNC15.ru.md)

**Current IMU firmware: FT6_SYNC15_UART_IRQ_v1.** [Download, wiring, flashing, and checks](../../../../hardware/IMU-FIRMWARE.en.md) · [Source directory guide](README.en.md). This page owns the protocol and host compatibility contract.

## Protocol and compatibility

Addresses 56–70: gyro XYZ i 16 little-endian (6 bytes), quaternion XYZ binary 16 little-endian (6 bytes), then u 8 sample counter, status, and reserved zero (1 byte each).

Status bit 0=not ready, bit 1=stale, bit 3=at least five new samples since the last read. The host also refuses bit 2 errors; bits 4–7 must be zero. Bit 3 reports sample / read cadence and is not a sensor-failure indication.

The counter increments only on actual new quaternions; 255→0 is normal wraparound. Before transmission, firmware checks cached timestamps and sets bit 1 above 30 ms. If sampling stalls while UART still replies, data cannot continue being reported fresh.

The host checks status, three consecutive identical counters, quaternion validity, and a 50 ms budget combining the 30 ms bound with full-cycle elapsed time. Official installation transforms and readiness checks remain.

Addresses 124–143 provide the complete 20-byte diagnostic format: 12 core bytes, u 32 sequence, u 16 age, ready, schema=1. Normal control does not poll this region.

This aligns with the community's 15-byte fast layout. Diagnostics, firmware identity, and low-level implementation remain project-defined. ID200 must be first in Sync Read; other ordering logic not physically tested on this HAT is not imported.

Current firmware uses USART interrupt reception, ISR fast replies, double-buffer publication, waiting for TC before bus release, restoring RX before releasing the driver, original GPIO / SPI / IMU initialization, 120 Hz SFLP, and the documented LED behavior.

Only the existing Feetech backend and service entry are changed; official joint order, calibration files, and policies are preserved. Config keys and paths continue using `feetech-ft5` / `feetech-ft5-r5` for compatibility; those paths do not identify old running firmware. Startup remains torque-off and does not automatically run an XL330 policy.

## Build

Use Arm GNU Toolchain 14.3.Rel1:

```bash
make -f Makefile.feetech TOOLCHAIN=/path/to/toolchain/bin/arm-none-eabi-
```

Before compilation, prepare STM32CubeG0 with CMSIS Core from pinned commit `446ebe396489ca75679caa80887d7257efe92e3d` and device submodule `f576c24e123edf3332988ecd49512c0f35f85186`.

Community references:

- <https://github.com/fanhao375/microduck-replica/blob/master/hardware/imu_to_dxl/总线协议.md>
- <https://github.com/fanhao375/microduck-replica/blob/master/hardware/imu_to_dxl/firmware/Core/Src/control_table.c>

The current implementation is this project's Feetech FT6; it does not directly flash community HEX files.
