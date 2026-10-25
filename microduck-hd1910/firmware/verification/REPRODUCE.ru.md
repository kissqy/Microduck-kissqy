[Оригинал](REPRODUCE.txt) | **Русский**

Используйте Rust 1.99.0, cargo-zigbuild 0.23.4, Zig 0.14.1 и ONNX Runtime 1.28.0.
restore_toolchain147.py восстанавливает фактические наборы инструментов и фиксирует SHA256 загрузок.

```sh
PYTHONPATH="$PWD/packaging:$PWD/console" python3 -m unittest discover -s packaging -p 'test_*.py' -v
cargo test -p robotd --bin robotd --locked
cargo test -p duck-control --lib --locked
cargo test -p robotd-params -p duck-ipc-proto --lib --bins --locked
```

Кросс-компиляция:

```sh
cargo zigbuild -p robotd -p robotctl --release --target aarch64-unknown-linux-gnu.2.31 --locked
```

build_native147.py хеширует точные исходники Rust/Cargo до и после компиляции и записывает инструменты, журналы и ARM-программы.
padd повторно используется из v146; проверено, что API40, исходники padd и SHA бинарного файла не изменились.
package147.py ожидает work-r17-146 как базу и work-r17-147 с текущими исходниками / журналами, а также два исходных ZIP в upload/.
Он побайтово проверяет все исходные файлы моделей, сохраняет Walk/LB/sitstand, дважды устанавливает настоящий пакет с предварительно импортированными моделями и без них и импортирует оба ZIP-формата через PreparedFirmware.
Исторические фикстуры roll/pick из исходного test-data намеренно исключены из рабочего пакета.
Каталог official-reference-from146 сохранён как историческое свидетельство, а не новая проверка официального источника.
checkpoint.pt никогда не десериализуется и не развёртывается. Тесты синтетической модели и фиктивного оборудования не подтверждают физическое поведение.
В этом выпуске не выполнялись движение Zero, проверка настоящего геймпада, активация systemd/uinput, рендеринг браузера или измерение температуры.
