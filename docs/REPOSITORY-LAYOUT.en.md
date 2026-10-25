[简体中文](REPOSITORY-LAYOUT.md) | **English** | [Русский](REPOSITORY-LAYOUT.ru.md)

# Repository layout and repeated resources

## Firmware source is public

Current release: **R17 V167 / control.43**. Rust firmware and Feetech adaptation source are in [firmware/](../microduck-hd1910/firmware/); console source is in its `console/` directory. See [BUILD.en.md](../microduck-hd1910/docs/BUILD.en.md).

## Larger files

| Content | Location and purpose |
| --- | --- |
| Ready-to-use downloads | Console ZIPs in `release-assets/` and standalone firmware in `firmware/console/updates/`. |
| Training configuration and references | `microduck-hd1910/training-console/data/`, used by the local training console. |
| Online-demo resources | `docs/`, the GitHub Pages publication directory; copied geometry and training parameters keep the demo independent. |
| Build baseline | One pinned V164 ZIP in `release-assets/build-baselines/`, used to reproduce the V167 installer. |
| Historical reference evidence | `firmware/verification/official-reference/`, containing pinned upstream sources, models and original capture records. |

Git uses the same file object for identical bytes at different paths, while a complete directory ZIP includes each path separately.

## Cleanup

- Consolidated identical official-reference snapshots, preserving original bytes and source records. The old duplicate directory is deleted; a SHA256 mapping remains in `REFERENCE-LAYOUT.json`.
- Removed the duplicate left-kick model alias and redirected the documentation index to the active directory.
- Deleted unused V160/V162/V163 build scripts, the V147 packager and the outdated standalone stand-up test; V167 remains the current build entry.
- Restored two historical stand-model binary copies from `policies/stand/` through checksum-verified `prepare-V167.py`, retaining old test paths.
- Updated online-demo labels to V167 / control.43; telemetry remains simulated.
- Added navigation pages for archived relative links without editing original snapshot bytes.

Compiled firmware and console ZIPs, model weights and training configuration data retain their published contents. Git history is retained, so old large files may still exist in historical objects.
