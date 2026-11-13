[简体中文](REPOSITORY-LAYOUT.md) | **English**

# Repository layout and versions

## Choose a version directory

Robot Console, firmware source and matching downloads are grouped under [versions/](../versions/) on main, separated into **V167** and **V260**. No branch switching is needed.

| Directory | Version and contents |
| --- | --- |
| [versions/v260/](../versions/v260/) | Current release: Studio V260 / control.102 / Image R2 / Wi-Fi R10. Console source is in `console/`; firmware source is in `firmware/`. |
| [versions/v167/](../versions/v167/README.en.md) | Historical R17 V167 / control.43. Preserves the relative layout of `microduck-hd1910/` source and `release-assets/` build resources. Image R1 originally includes control.40. |
| `microduck-hd1910/` | Preserved source compatibility path. The root `release-assets/` directory is retired; packages and build baselines now use `versions/v167/release-assets/`. |
| `microduck-hd1910/training-console/` | Independent Training Studio R1.5.27; its version number is separate from Robot Console versions. |
| `hardware/` | Shared board projects, 3D printing files and hardware documentation. |
| `docs/` | Shared guides and GitHub Pages demos using simulated data. |

V167 console source is in [microduck-hd1910/firmware/console/](../versions/v167/microduck-hd1910/firmware/console/), and firmware source in [microduck-hd1910/firmware/](../versions/v167/microduck-hd1910/firmware/). See [BUILD.en.md](../versions/v167/microduck-hd1910/docs/BUILD.en.md). Preserving their relative depth lets packaging scripts locate the pinned build baseline at the original relative path.

This updates navigation and the resource paths used by legacy root packaging tools. Frozen version source and runtime packages retain their original bytes; it does not add real-robot Known-Good results. The next single main task remains V260 acceptance on the reference card.

## Larger files

| Content | Location and purpose |
| --- | --- |
| Ready-to-use downloads | The two V260 runtime ZIPs and R2 image are on the [release page](https://github.com/kissqy/Microduck-kissqy/releases/tag/console-studio-v260); V167 downloads are grouped in [its version directory](../versions/v167/README.en.md). The former root download paths are retired; use the version-directory URLs. |
| Training configuration and references | `microduck-hd1910/training-console/data/`, for the independent training console; the V167 snapshot retains its original training material. |
| Online-demo resources | `docs/`, the GitHub Pages publication directory; copied geometry and training parameters keep the demo independent. |
| Build baseline | One pinned V164 ZIP in `versions/v167/release-assets/build-baselines/`, used to reproduce V167. The root copy is removed; updated links and the legacy source packaging tools use this archive. |
| Historical reference evidence | `versions/v167/microduck-hd1910/firmware/verification/official-reference/`, containing pinned upstream sources, models and original capture records. |

The duplicate root `release-assets/` directory is removed. Archived ZIPs, checksum files and the fixed build baseline reuse existing file objects; only download and resource-location paths are adjusted. Frozen version source and release packages are unchanged.

## November 12, 2026 source cleanup

Removed 41 retired one-shot tools and one unlinked experiment module from the public V167/control.43 source. Another 59 identical model metadata copies are now restored from `policies/` by checksum-verified `prepare-V167.py`. In total, 101 tracked files / about 3.99 MiB were removed from the source tree; published runtime archives and Git history are unchanged.

See the [source cleanup audit (中文)](../versions/v167/microduck-hd1910/docs/SOURCE-CLEANUP-20261112.md) for the exact manifest, verification limits and pre-existing test incompatibilities.

## Earlier cleanup

- Consolidated identical official-reference snapshots, preserving original bytes and source records. The old duplicate directory is deleted; a SHA256 mapping remains in `REFERENCE-LAYOUT.json`.
- Removed the duplicate left-kick model alias and redirected the documentation index to the active directory.
- Deleted unused V160/V162/V163 build scripts, the V147 packager and the outdated standalone stand-up test; V167 remains the current build entry.
- Restored two historical stand-model binary copies from `policies/stand/` through checksum-verified `prepare-V167.py`, retaining old test paths.
- Updated online-demo labels to V167 / control.43; telemetry remains simulated.
- Added navigation pages for archived relative links without editing original snapshot bytes.

Compiled firmware and console ZIPs, model weights and training configuration data retain their published contents. Git history is retained, so old large files may still exist in historical objects.
