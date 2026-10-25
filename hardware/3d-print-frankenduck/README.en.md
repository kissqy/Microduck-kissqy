[简体中文](README.md) | **English** | [Русский](README.ru.md)

# 🖨️ Complete duck printing parts · FrankenDuck edition

**This set combines improvements from several community makers with modifications kissqy made while assembling, running, and maintaining the real robot. That is why it is called the “FrankenDuck” edition.** The changes are numerous and are not listed individually. This package supplies the author's complete duck printing parts and reference plate layout.

**[⬇️ Download the complete package (RAR, 14.54 MiB)](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/hardware/3d-print-frankenduck/Microduck-Print-FrankenDuck-20261015.rar)** · [SHA256](SHA256SUMS) · [Package file list](FILES.md) · [Duck shopping guide](../../DUCK-SHOPPING-LIST.en.md) · [Homepage](../../README.en.md)

Published **October 15, 2026**. The archive contains **36 STL files and one 3MF project with 5 plates**. Original filenames and layouts are preserved; file counts are not assembly quantities. The original archive is supplied without editing the models or plate project.

**October 21, 2026 update:**

- **Added ramps to the leg supports** to ease foot installation and reduce the chance of forcing the foot apart during assembly.
- **Removed the outer counterbores from both leg shells** to retain more material around the screw holes and reduce the risk of breakage in a fall.
- **Integrated an interchangeable-foot design based on the official roller shoes**, making it easier to swap feet and roller assemblies without removing the servos.

## Read these first

- **The foot kit allows rollers to be installed without removing the servos.** This makes installation and maintenance easier.
- **Choose one of two battery holders.** One clamps a HUB board; the other follows the official-style structure with thicker latch sections.
- **Both holders have an IMU mount designed for this repository's DIY IMU.** For another IMU, adapt the mount to your board shape, dimensions, and attachment method.
- **The rollers use 623ZZ bearings: 3 mm bore × 10 mm outer diameter × 4 mm width.** [Product from the supplied order](https://item.taobao.com/item.htm?id=618009195719), seller **EVT进口轴承**, exact order variant **“623 内3外10厚4”**.

## Choose the battery holder

Both files are under `3D打印缝合怪版/stl模型/躯体部分/` in the archive:

| Variant | Filename | Use |
| --- | --- | --- |
| **HUB-clamping holder** | `电池仓_M2.5螺丝_HUB组合.stl` | Choose when the holder also needs to clamp the HUB board. HUB combination structure using M2.5 screws; choose as needed. |
| **Official-style holder with thicker latches** | `电池仓_卡扣加厚.stl` | Official-style battery holder with thicker latch sections; import this STL to replace the holder on the plate if preferred. |

Both fit [this repository's IMU](../README.en.md). Flashing and wiring instructions are in the [FT6 guide](../IMU-FIRMWARE.en.md).

## Use the package

1. Download and extract the RAR. **`缝合怪摆盘.3mf`** at its root is the reference plate project; `stl模型/` contains the individual models by category.
2. Open the 3MF as a project in Bambu Studio. Its recorded setup is **BambuStudio 02.08.02.61 / Bambu Lab P2S / 0.4 mm nozzle / 0.20 mm Standard**. Adjust the printer, nozzle, and material settings for your setup.
3. Choose the battery-holder variant. Import the individual STL files to change layout or quantities, or to reprint a part.
4. **Plate 5 is named TPU; `TPU部分/` contains the two soles and the tire.** The saved project material presets are PLA. Before printing this plate, select the **TPU material profile** you actually use.

Choose slicing settings for rigid parts according to your material, printer, and assembly needs. The supplied layout preserves the author's arrangement, and its settings must be adapted to the target equipment.

## Original plate previews

These images come directly from the supplied 3MF project. Plate 5 is the TPU group.

<table>
  <tr>
    <td align="center"><b>Plate 1</b><br><img src="plate-1.png" width="240" alt="Original FrankenDuck plate 1 preview"></td>
    <td align="center"><b>Plate 2</b><br><img src="plate-2.png" width="240" alt="Original FrankenDuck plate 2 preview"></td>
    <td align="center"><b>Plate 3</b><br><img src="plate-3.png" width="240" alt="Original FrankenDuck plate 3 preview"></td>
  </tr>
  <tr>
    <td align="center"><b>Plate 4</b><br><img src="plate-4.png" width="240" alt="Original FrankenDuck plate 4 preview"></td>
    <td align="center"><b>Plate 5 · TPU</b><br><img src="plate-5.png" width="240" alt="Original FrankenDuck TPU plate 5 preview"></td>
  </tr>
</table>

## Sources and assembly

This set starts from the official Microduck structure, incorporates improvements from multiple community makers, and combines them with kissqy's practical robot modifications. Credit belongs to the upstream project and the contributing makers. Original works retain their source rights and licenses; kissqy's additions follow this project's [component licenses](../../microduck-hd1910/LICENSE).

Archive paths, sizes, and SHA256 hashes are recorded in [FILE-MANIFEST.json](FILE-MANIFEST.json).
