# imu-to-dxl RevA — official-format live IMU firmware M8-A5

This build combines the two RevA paths already proven on physical hardware:

- STM32G031F8P6 ↔ LSM6DSV16X SPI
- Dynamixel Protocol 2.0 ↔ U2D2 at 1 Mbps, ID 200

The LSM6DSV16X runs ST's SFLP game-rotation engine. The board exposes the
12-byte block consumed by MicroDuck at control-table address 124.

## Exact host-facing block

| Bytes | Value |
|---|---|
| 0..5 | gyro X/Y/Z, signed i16 little-endian, ±500 dps |
| 6..11 | SFLP quaternion X/Y/Z, IEEE binary16 little-endian |

The host reconstructs positive W as `sqrt(1 - X² - Y² - Z²)`. Firmware uses
120 Hz accel, gyro and SFLP output. Direct Ping, direct Read and broadcast Sync
Read are supported.

## Board status LED

- Two slow flashes: firmware started.
- Slow flashing continues: IMU answers, but no SFLP quaternion has arrived yet.
- Solid on: a live SFLP quaternion has been received.
- Continuous fast flashing: WHO_AM_I or IMU initialization failed.

## Flash

Flash this file at `0x08000000`:

`build/imu_to_dxl_ReVA_M8A5_UART_IRQ_v1.bin`

After programming, disconnect ST-Link before the U2D2 test.

## Mac live test through official ROBOTIS SDK

Use the U2D2 Power Hub with an external regulated 5 V supply. Connect RevA J1:

| RevA J1 | Dynamixel bus |
|---:|---|
| 1 | GND |
| 2 | VDD / 5 V |
| 3 | DATA |

Do not connect a servo for this IMU-only test.

One-time setup:

```sh
python3 -m pip install dynamixel-sdk
```

Run from this source directory:

```sh
python3 tools/imu_live_mac.py --port /dev/cu.usbserial-FTC1TTXP --hz 50
```

The tool finds the U2D2 serial port, pings ID 200, reads address 124 length 12,
and displays live gyro, quaternion and projected gravity at 50 Hz. It uses
ROBOTIS's official Dynamixel SDK for all bus traffic and mirrors MicroDuck's
official mount transform and decoder. Any transient communication error is
retained on the `最后错误` line instead of disappearing on the next successful
read.

If port auto-selection is ambiguous:

```sh
python3 tools/imu_live_mac.py --port /dev/cu.usbserial-XXXXXXXX
```

This M8-A5 build receives Dynamixel requests with a USART interrupt and a
64-byte ring buffer. IMU SPI polling can no longer make the MCU miss incoming
request bytes.

Pass criteria (run continuously for 60 seconds at 50 Hz):

- LED becomes solid.
- State reaches `OK` after 25 live quaternion samples.
- Rotating the board changes gyro immediately.
- Tilting/flipping the board changes the gravity direction.
- Raw 12-byte data changes and communication failures remain zero after any
  one-time startup transient.

## Fixed RevA pin map

| Function | MCU |
|---|---|
| DEBUG_LED | PA0 |
| DXL_TX_EN, active low | PA1 |
| USART2 TX/RX | PA2 / PA3 |
| IMU CS/SCK/MISO/MOSI | PA4 / PA5 / PA6 / PA7 |
| IMU INT1 | PB0 |

## Sources

- STMicroelectronics official `lsm6dsv16x_reg.c/.h`
- STMicroelectronics official LSM6DSV16X sensor-fusion example
- MicroDuck `duck-control/src/imu.rs` and `bus.rs`
- ROBOTIS official Dynamixel SDK on the Mac
