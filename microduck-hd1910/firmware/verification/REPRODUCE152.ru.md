[Оригинал](REPRODUCE152.md) | **Русский**

<a id="r152-verification"></a>
# Проверка R152

Нативный компилятор: Rust 1.99.0, cargo-zigbuild 0.23.4 и Zig 0.14.1. Хеши скачанного и фактически наблюдавшиеся версии находятся в `toolchain-provenance152.json`; зафиксированные ссылки загрузки остаются в `toolchain-provenance150.json`. Cargo.lock не менялся с R150.

Выполняйте эти проверки из корня исходников с зафиксированным набором инструментов, C-зависимостями хоста и настроенным ORT_DYLIB_PATH:

```sh
cargo test -p robotd --bin robotd --frozen startup -- --test-threads=1
cargo test -p robotd --bin robotd --frozen cold_reopen -- --test-threads=1
cargo test -p robotd --bin robotd --frozen reopened_uart -- --test-threads=1
cargo test -p robotd --bin robotd --frozen r17_empty_snapshot -- --test-threads=1
cargo test -p duck-control --lib --frozen hd1910_transport_tests -- --test-threads=1
cargo zigbuild -p robotd --release --target aarch64-unknown-linux-gnu.2.31 --frozen
```

Из `packaging` запустите проверки служб выпуска:

```sh
python -m unittest -v test_runtime test_uart_startup test_uart_state test_upgrade_units test_release_identity test_gamepad test_webpad_startup test_firmware_console
python -m unittest -v test_dashboard_connection test_socket_transport test_control_socket test_maintenance_input test_status_and_volume
```

Из `console` запустите новые диагностические и сохранённые проверки геймпада:

```sh
python -m unittest discover -s verification -p test_startup_diagnostic.py -v
python -m unittest discover -s verification -p test_gamepad_repair.py -v
node verification/test_startup_ui.mjs static
node verification/test_gamepad_repair_ui.mjs static
```

`native-build152-final.json` фиксирует точные входные хеши нативных исходников и SHA256 собранного robotd. `release-audit152.json` фиксирует изменения содержимого пакета и проверку рабочего импортёра прошивки. Локальные скрипты `run152.py`/`package152.py` сохраняют структуру рабочей среды сборки; для воспроизведения упаковки в другом месте эту структуру нужно адаптировать.

Сохранённые рядом журналы R150/R151 являются историческими. Они не проверяют R152 и не подтверждают поведение физической перезагрузки, беспроводной связи или температуры. Текущие результаты R152 находятся в `recovery152.json`; пересобран только robotd, а robotctl, padd, мост GameSir, модели и калибровка проверены относительно старого содержимого пакета.
