# R152 verification

Native compiler: Rust 1.99.0, cargo-zigbuild 0.23.4 and Zig 0.14.1. Download hashes and observed versions are in `toolchain-provenance152.json`; the pinned download references remain in `toolchain-provenance150.json`. Cargo.lock is unchanged from R150.

Use the source root for these checks with the pinned toolchain, host C dependencies and ORT_DYLIB_PATH configured:

```sh
cargo test -p robotd --bin robotd --frozen startup -- --test-threads=1
cargo test -p robotd --bin robotd --frozen cold_reopen -- --test-threads=1
cargo test -p robotd --bin robotd --frozen reopened_uart -- --test-threads=1
cargo test -p robotd --bin robotd --frozen r17_empty_snapshot -- --test-threads=1
cargo test -p duck-control --lib --frozen hd1910_transport_tests -- --test-threads=1
cargo zigbuild -p robotd --release --target aarch64-unknown-linux-gnu.2.31 --frozen
```

From `packaging`, run the release's service checks:

```sh
python -m unittest -v test_runtime test_uart_startup test_uart_state test_upgrade_units test_release_identity test_gamepad test_webpad_startup test_firmware_console
python -m unittest -v test_dashboard_connection test_socket_transport test_control_socket test_maintenance_input test_status_and_volume
```

From `console`, run the new diagnostic and retained gamepad checks:

```sh
python -m unittest discover -s verification -p test_startup_diagnostic.py -v
python -m unittest discover -s verification -p test_gamepad_repair.py -v
node verification/test_startup_ui.mjs static
node verification/test_gamepad_repair_ui.mjs static
```

`native-build152-final.json` records exact native source input hashes and the built robotd SHA256. `release-audit152.json` records payload changes and the production firmware importer check. The retired `run152.py`/`package152.py` scripts used a historical workspace layout. Retrieve their original bytes from [the pre-cleanup Git revision](https://github.com/kissqy/Microduck-kissqy/tree/c1a53b2c28ecbb6f890296fb668156987871ba76/microduck-hd1910/firmware/verification); the current build entry is [BUILDING-V167.md](../BUILDING-V167.md).

R150/R151 logs retained beside these files are historical. They do not validate R152 or establish physical reboot, wireless or temperature behavior. R152's current results are in `recovery152.json`; only robotd was rebuilt, while robotctl, padd, the GameSir bridge, models and calibration were checked against the old payload.
