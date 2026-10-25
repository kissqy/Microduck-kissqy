[简体中文](IMU-TIMELINE.md) | **English** | [Русский](IMU-TIMELINE.ru.md)

# IMU build timeline

> 🛒 **[Buy HAT / IMU boards from the author](https://item.taobao.com/item.htm?id=1095121548583)**
>
> **Please note: these boards are fabricated at JLCPCB (嘉立创) and populated by the author. Ready to use on arrival, they are the same boards the author uses, validated through extended real-robot operation, with no jumper bridging required and no packet loss. Feetech AMP2.0 connectors make them convenient and easy to use.**

🎬 **[Watch the complete IMU build (Bilibili)](https://www.bilibili.com/video/BV1qapz6PERs/)**

**For the Feetech build, start with [current IMU FT6 download and flashing](IMU-FIRMWARE.en.md).** The timeline below records hardware fabrication and Feetech adaptation.

All dates below are in 2026. The process first established independent IMU hardware and real pose readings, then connected it to the bus. After the original Dynamixel version worked, the same hardware was adapted for Feetech.

**Current status, confirmed October 12, 2026: validated through extended use in the complete robot; operating normally with no identified issues.**

| Date | Work completed |
| --- | --- |
| Aug 31–Sep 2 | Established the need for an independent torso-mounted IMU. Complete official board-level instructions were unavailable at that point, so sensor, processor, and bus responsibilities were examined first. |
| Sep 3–4 | Selected the initial interface: **ID 200, 1 Mbps, Dynamixel Protocol 2.0**, and aligned the pose data format. |
| Sep 4 | Selected **LSM6 DSV16 X, STM32 G031, TLV70433, and 74 LVC2 G125**; completed the schematic and placement by functional group. |
| Sep 4–7 | Completed an approximately **22.7 × 25.6 mm two-layer IMU PCB** and submitted it for fabrication. |
| Sep 7 | Purchased the confirmed components and packages. |
| Sep 8–9 | Placed components, reflowed, and inspected solder joints on the first board. |
| Sep 9 | Measured approximately **3.31 V** on the 3.3 V rail. Reworked soldering, flashed firmware, and used synthetic data to verify MCU and bus communication first. |
| Sep 9 | Built a second board after abnormal sensor readings on the first, checking communication and actual sensor operation separately. |
| Sep 9–10 | Enabled real pose readings and the sensor's **SFLP fusion**, replacing synthetic data with actual sensor output. |
| Sep 10 | Changed UART reception to interrupts. A **50 Hz test with 3, 393 transactions and zero failures** passed; real orientation readout and bus communication on the independent board were confirmed. |
| Sep 12 | Planned Feetech adaptation while preserving the existing hardware, mainly changing the protocol and readout. |
| Sep 20 | Implemented the Feetech protocol and corrected timing on the shared servo line. A **3, 000/3, 000** test passed. |
| Sep 22–23 | Ran the IMU alongside 15 servos, recording **over 70, 000 communication rounds without new errors**, moving from board testing to full-robot validation. |
| Sep 23–28 | Used the IMU in actual standing and walking, continuing to check pose feedback and control in the full robot. |

## Projects and firmware

- [IMU EasyEDA project: ProPrj_imu_to_dxl_RevA_V1_2026-10-07.epro 2](ProPrj_imu_to_dxl_RevA_V1_2026-10-07.epro2)
- [IMU firmware source and version guides](../microduck-hd1910/firmware/firmware/imu-source/)
- [HAT build timeline](HAT-TIMELINE.en.md)

**Record baseline:** Feetech adaptation builds on the validated DIY hardware. The current IMU has passed extended full-robot use, operates normally, and has no identified issues. Communication counts in the table are development-stage test records.
