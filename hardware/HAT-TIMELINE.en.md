[简体中文](HAT-TIMELINE.md) | **English** | [Русский](HAT-TIMELINE.ru.md)

# HAT build timeline

> 🛒 **[Buy HAT / IMU boards from the author](https://item.taobao.com/item.htm?id=1095121548583)**
>
> **Please note: these boards are fabricated at JLCPCB (嘉立创) and populated by the author. Ready to use on arrival, they are the same boards the author uses, validated through extended real-robot operation, with no jumper bridging required and no packet loss. Feetech AMP2.0 connectors make them convenient and easy to use.**

All dates below are in 2026. This records the process from studying the official design and choosing a two-layer board to home reflow and full-robot integration.

**Current status, confirmed October 12, 2026: validated through extended use in the complete robot; operating normally with no identified issues.**

**Current procurement, October 13, 2026:** TH1 can use the original Murata **PRG18BB101MB1RB (100Ω PTC, 0603)**; R33 uses **0Ω**. The 22Ω TH1 value below is an earlier physical-board tuning record. See the [PCB shopping guide](README.en.md#shopping-list) for the current purchase variants.

## Why build this board?

The official HAT was relatively expensive to fabricate and included functions this duck did not need yet. Each official component's role and surrounding circuit was reviewed before deciding what to keep and simplify.

There were two reasons to choose a **two-layer PCB**: a multilayer design would be more complex and harder to fabricate and reflow as an individual maker; starting with a simple, understandable board that could be assembled at home reduced the chance of mistakes on the first attempt. Understanding the circuit and finishing a working board came before pursuing high integration.

## Build process

| Date | Work completed |
| --- | --- |
| Aug 31 | Defined the roles of ZERO and HAT: ZERO runs the system and higher-level software; HAT provides power, communication interfaces, and device peripherals. Established a working reference first. |
| Sep 2 | Reconstructed the official HAT information, separated functional blocks, and studied component roles, peripherals, and connections. |
| Sep 3–5 | Simplified functions according to actual needs, moving from copying the official design to understanding what could be omitted. |
| Sep 5 | Chose a two-layer board, top-side reflow for the main components, and 0603 peripherals. Placed components by functional group, starting with each main IC and then its surrounding parts. |
| Sep 5–7 | Completed the approximately **65 × 30.9 mm HAT-V5**, adjusting functional groups, connectors, outline, and routing into a fabrication-ready design. |
| Sep 7 | Submitted the PCB for fabrication. |
| Sep 10–13 | Placed components, reflowed, and inspected solder joints to complete the physical HAT. |
| Sep 14 | Tested audio and a single servo separately, beginning with independent functions. |
| Sep 17 | Tested ranging and continued connecting peripherals one block at a time. |
| Sep 20 | Connected Feetech servos and the independent IMU, then tuned their shared communication link. |
| Sep 22–23 | Integrated the board into the complete robot for combined multi-servo, IMU, and control-service operation. |
| Sep 24–28 | Tuned the physical board for actual communication behavior, recording **R33 = 0Ω and TH1 = 22Ω**, and completed integration debugging. |

## Project files versus the physical board

The published project is [ProPrj_HAT_REVA_SCH_2026-10-07.epro 2](ProPrj_HAT_REVA_SCH_2026-10-07.epro2).

Source-data review on October 12, 2026 found:

- **R33** is already marked 0Ω in the project, on `DXL_DATA_INT → DXL_DATA_CLAMPED`.
- **TH1** is still marked **100 R PTC** in the project, on `DXL_DATA_CLAMPED → DXL_DATA`. The **22Ω** value in the timeline describes physical-board tuning and has not been copied into that project's BOM.
- R33 and TH1 are on the servo data line.
