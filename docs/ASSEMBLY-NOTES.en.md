[简体中文](ASSEMBLY-NOTES.md) | **English** | [Русский](ASSEMBLY-NOTES.ru.md)

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

## Add a 1000 µF capacitor across the main power input

**For this build, install a 1000 µF capacitor in parallel across the robot's main power input.** In the author's experience, without this buffer capacitor, transient loads when the servos deliver full power can cause ZERO to reboot.

- Mount it close to the main power inlet with short leads, across the main supply feeding the servos and HAT.
- For a polarized capacitor, **connect positive to supply positive and negative to GND**. Disconnect power before wiring and avoid reversed polarity or shorts.
- Choose a voltage rating above the highest input voltage, with margin. For this project's approximately 7.3 V supply, a **1000 µF, 16 V capacitor** is an option; reassess the rating for other supply voltages.
- This is an external buffer on the main supply input, not a connection to ZERO's GPIO or a modification of its 5 V rail.
- A capacitor buffers transient loads; it does not replace an adequately rated battery, supply, wiring, or reliable connectors. If reboots persist, check supply voltage drops under load and the wiring.

[Documentation index](README.en.md) · [HAT / IMU hardware guide](../hardware/README.en.md)
