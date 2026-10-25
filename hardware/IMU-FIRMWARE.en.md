[简体中文](IMU-FIRMWARE.md) | **English** | [Русский](IMU-FIRMWARE.ru.md)

# IMU firmware FT6: download, flash, and check

**A newly built torso IMU needs its own STM32 firmware. The current Feetech HD1910 setup uses FT6. An already programmed IMU that works correctly does not need reflashing.** This firmware reads real angular velocity and fused orientation from the LSM6DSV16X and supplies them to the ZERO control service over the Feetech bus.

**The IMU project has EH2.5 and AMP2.0 connector variants.** [Both projects](README.en.md) · [AMP2.0 version](AMP2.0-VERSION.en.md). Both use the same J2 SWD pin assignments.

## Choose the correct file

| Component | Where it is written | Current project version |
| --- | --- | --- |
| **IMU firmware `.bin`** | **STM32G031F8P6** on the independent IMU, using ST-LINK / SWD | **FT6_SYNC15_UART_IRQ_v1** |
| ZERO robot service `.tar.gz` | Linux on Radxa ZERO 3W, installed through the console or SSH | control.43, paired with R17 V167 |
| System image `.img.xz` | ZERO microSD card | Public Image R1, preinstalled control.40 |

**Flashing the system image or upgrading ZERO services from the console does not program the external IMU.** The PCB project retains the hardware name `imu_to_dxl_RevA_V1`; for Feetech HD1910, select the **Feetech FT6** firmware below.

## Download current IMU firmware

**[⬇️ Download IMU FT6 `.bin` (8.2 KiB)](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/microduck-hd1910/firmware/console/updates/imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin)** · [SHA256 file](../release-assets/imu-ft6.sha256) · [Complete source](../microduck-hd1910/firmware/firmware/imu-source/README.en.md)

| Item | Value |
| --- | --- |
| Filename | `imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin` |
| Hardware | This repository's [IMU RevA project](ProPrj_imu_to_dxl_RevA_V1_2026-10-07.epro2): STM32G031F8P6 + LSM6DSV16X |
| Bus | Feetech protocol, **1 Mbps, fixed ID 200**; shares the bus with 15 HD1910 servos |
| Host | Current R17 V167 / control.43 Feetech backend |
| Flash start address | **`0x08000000`**, defined in the [linker script](../microduck-hd1910/firmware/firmware/imu-source/linker/STM32G031F8PX_FLASH.ld) |
| Size | **8,428 bytes** (about 8.23 KiB) |
| SHA256 | `d7bd2f37a6a4e0e15d1f9650a3959bcf4d8c704524d8ec319d72d8bdf104ab6d` |

The link points to the existing file bundled with V167. You can download it directly without the much larger console ZIP, and no duplicate binary has been added. This documentation change does not modify or rebuild firmware.

On Windows, check the downloaded file from PowerShell in its directory:

```powershell
Get-FileHash .\imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin -Algorithm SHA256
```

Use `sha256sum filename` on Linux or `shasum -a 256 filename` on macOS. The result must match the table.

## Flash with ST-LINK

Prepare an ST-LINK, wires, and ST's [STM32CubeProgrammer](https://www.st.com/en/development-tools/stm32cubeprog.html). These instructions apply to the RevA board linked above.

### 1. Connect J2 (SWD 1×5)

Pin numbers come from the **PCB nets in the October 7, 2026 project**. Find the pad-1 marking rather than guessing left/right from a photo.

| J2 pin | Board signal | ST-LINK signal |
| --- | --- | --- |
| **1** | **3V3** | Target voltage reference VTref / VAPP; the board requires a stable 3.3 V supply |
| **2** | **SWDIO** | SWDIO |
| **3** | **GND** | GND |
| **4** | **SWCLK** | SWCLK |
| **5** | **NRST** | NRST / RESET |

**VTref is a voltage reference and does not necessarily power the board.** Follow your ST-LINK model's manual to distinguish reference inputs from power outputs. J2 3V3 connects to the MCU supply and must not receive 5 V. Wire with power off, use one defined power source when programming, and leave the servo bus disconnected during programming.

### 2. Connect and program

1. Connect ST-LINK to the computer and power the IMU. Open STM32CubeProgrammer, select **ST-LINK → SWD → Connect**, and confirm STM32G031 is detected.
2. In the programming panel, select `imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin`.
3. Set **Start address / Address to `0x08000000`**, enable **Verify after programming**, and click **Start Programming**. A `.bin` file does not carry its address, so you must specify it.
4. Confirm programming and verification succeed. Disconnect, power off, remove ST-LINK, and power the board again to run it.

The procedure follows ST's [internal flash programming instructions](https://dev.st.com/stm32cube-docs/prog/2.23.0/en/docs/markup/CubeProg_UserManual/Memory_programming_and_erasing.html). Alternatively, with the installed CLI on PATH, write and verify using this command, then power-cycle as in step 4:

```sh
STM32_Programmer_CLI -c port=SWD -w imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin 0x08000000 -v
```

On Windows the executable is `STM32_Programmer_CLI.exe`. See ST's [command reference](https://dev.st.com/stm32cube-docs/prog/2.23.0/en/docs/markup/CubeProg_Command_Lines.html).

## Confirm it works

Keep robot torque disabled, connect the IMU to the Feetech bus through the HAT, and view IMU data using the matching ZERO services and V167 console. Keep standing and walking disabled during these checks.

| Check | Expected result |
| --- | --- |
| Programming | Both programming and Verify succeed in STM32CubeProgrammer |
| Bus identity | ID 200, 1 Mbps; protocol identity major version 6 |
| Sensor data | Slowly rotating or tilting the IMU changes angular velocity and orientation; samples keep updating while stationary |
| Communication | After warm-up, IMU is ready without persistent communication errors or stale data |
| LED | Two flashes on startup; may be off when healthy and idle; very short activity pulses when fresh-data responses succeed; solid on for initialization failure or a prolonged absence of new orientation data |

Current FT6 LED behavior is defined by [`main.c`](../microduck-hd1910/firmware/firmware/imu-source/src/main.c) and [`ft_led_status.c`](../microduck-hd1910/firmware/firmware/imu-source/src/ft_led_status.c). Use actual sensor data, readiness, and communication status for the final check.

| Symptom | First checks |
| --- | --- |
| STM32 is not detected | Board 3.3 V supply, common ground, J2 pin numbers, SWDIO / SWCLK, NRST, and ST-LINK driver |
| Programming succeeds but the host cannot read it | FT6 binary, bus wiring and power, 1 Mbps, and another device using ID 200 |
| Responses arrive but orientation is frozen / LED stays on | LSM6DSV16X soldering, power, SPI connections, and real sensor data; a response alone does not prove the sensor works |
| Configuration says `feetech-ft5` | This is a retained compatibility path name; it alone does not identify old firmware. See the FT6 protocol guide below |

## Current source and build

For a normal build, flash the `.bin` above without compiling. The developer entry is [`Makefile.feetech`](../microduck-hd1910/firmware/firmware/imu-source/Makefile.feetech). Toolchain and pinned dependencies are listed in [Build IMU firmware](../microduck-hd1910/docs/BUILD.en.md#imu-stm32); protocol details are in [FT6 protocol and compatibility](../microduck-hd1910/firmware/firmware/imu-source/README_FT6_SYNC15.en.md). The fast block is address 56, 15 bytes, with ID 200 first in Sync Read; address 124 retains a 20-byte diagnostic block.

[IMU build video and timeline](IMU-TIMELINE.en.md) · [Hardware and shopping](README.en.md) · [Project homepage](../README.en.md)
