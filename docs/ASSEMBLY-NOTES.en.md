[简体中文](ASSEMBLY-NOTES.md) | **English**

# 🔧 Assembly and operating notes

These notes record kissqy's experience assembling and running this project's real robot, dated October 22, 2026.

## Connect ZERO to 5 GHz Wi-Fi

**When using a wireless gamepad, connect the Radxa ZERO 3W to your router's 5 GHz Wi-Fi.** “5G Wi-Fi” here means the 5 GHz Wi-Fi band.

The author encountered interference between ZERO's 2.4 GHz Wi-Fi and the gamepad's 2.4 GHz wireless communication, causing network disconnections and SSH timeouts or failed connections. Configure this build to use **5 GHz Wi-Fi for ZERO** to avoid sharing the 2.4 GHz band with the gamepad.

- Enable the router's 5 GHz network. If band steering makes the selection unclear, give the two bands separate SSIDs and connect ZERO explicitly to the 5 GHz one.
- If connecting the gamepad causes network or SSH failures, first check ZERO's actual Wi-Fi band. An SSID containing “5G” alone does not confirm the band.
- Run this read-only command in ZERO's terminal to see the frequency of the current connection (marked `*` in `IN-USE`):

```bash
nmcli -f IN-USE,SSID,FREQ,SIGNAL device wifi list
```

## ToF and speaker connections

[View the wiring photo and pin table](../hardware/AMP2.0-VERSION.en.md#tof-and-speaker-wiring-photo), or [open it in the assembly guide](https://kissqy.github.io/Microduck-kissqy/build/assembly.html#hat-wiring). ToF connects to J5: green GND, yellow VIN (3.3 V), black SDA, red SCL. Speaker connects to J1: red SPK_R_P (+), black SPK_R_N (−); the black speaker output is not GND.

## Battery power and HUB connection

The HUB's CN1 power input uses XH2.54-2P. Connect an XH2.54 power lead to the repository battery holder's M2.6 screw contacts for a quick, convenient connection; plug in a battery with a matching XH2.54 connector, voltage and polarity directly; or solder the XH2.54 lead to a banana board. Connect positive to VIN (+) and negative to GND (−), following the board markings.

## The HUB includes the main-power buffer capacitor

**This repository’s HUB costs CNY 69 and includes the 1000 µF main-power buffer capacitor to buffer transient servo loads and help prevent ZERO restarts caused by supply voltage dips. No separate capacitor purchase or duplicate installation is needed.** Connect battery power to HUB VIN / GND.

- Check input polarity and capacitor polarity against the board markings.
- The capacitor buffers transient servo loads; the battery, wires and power contacts still need reliable connections.

[Documentation index](README.en.md) · [HAT / IMU / HUB board guide](../hardware/README.en.md)
