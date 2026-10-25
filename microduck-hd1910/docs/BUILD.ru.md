[English](BUILD.en.md) | [简体中文](BUILD.md) | **Русский**

<a id="从源码编译-control43"></a>
<a id="build-control43-from-source"></a>
# Сборка control.43 из исходников

Для повседневного использования скачайте образ системы и консоль V167; компиляция не нужна. Эта страница описывает пересборку программ ZERO после изменения исходников. Текущая прошивка — **control.43**, распространяемая с V167.

В Windows используйте терминал WSL / Linux в VS Code. После клонирования репозитория сначала перейдите в `microduck-hd1910`.

<a id="安装编译环境"></a>
<a id="install-the-build-environment"></a>
## Установка среды сборки

```bash
sudo apt-get update
sudo apt-get install -y build-essential pkg-config libudev-dev python3-venv curl ca-certificates xz-utils binutils dpkg
```

Если rustup отсутствует, установите официальные инструменты Rust; иначе пропустите этот шаг:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain none
source "$HOME/.cargo/env"
```

Установите зафиксированный в записях выпуска набор инструментов:

```bash
rustup toolchain install 1.99.0 --profile minimal --target aarch64-unknown-linux-gnu
python3 -m venv .build/firmware-tools
.build/firmware-tools/bin/python -m pip install cargo-zigbuild==0.23.4 ziglang==0.15.1
```

<a id="构建-zero-程序"></a>
<a id="build-zero-programs"></a>
## Сборка программ ZERO

```bash
bash tools/build-firmware.sh --check
bash tools/build-firmware.sh
```

`--check` проверяет установленные инструменты и записи зафиксированных зависимостей без скачивания или компиляции. Сборка использует `Cargo.lock`, Rust **1.99.0**, cargo-zigbuild **0.23.4** и Zig **0.15.1** с целевой платформой `aarch64-unknown-linux-gnu.2.31`. Это соответствует записям control.43; для release-сборки `robotd` и `pet-detect` устанавливается codegen-units=1.

Результат находится в **`.build/firmware/bin/`**:

| Файл | Назначение |
| --- | --- |
| `robotd` | Служба управления роботом |
| `robotctl` | CLI робота |
| `padd` | Служба ввода с геймпада |
| `sounds` | Синтез звука |
| `gamesir-xboxd` | Мост ввода GameSir → Xbox |
| `BUILD-LOCAL.json`, `SHA256SUMS` | Идентификация сборки и контрольные суммы |

Эти программы предназначены для ARM64 Linux / ZERO. Данная точка входа только собирает программы: она не подключается к роботу, не устанавливает службы и не создаёт полный импортируемый ZIP прошивки. Для работы служб также нужны конфигурация, модели, вспомогательные программы и ARM64 ONNX Runtime. Исходники `mediad` находятся в рабочем пространстве, но не входят в эту сборку пяти программ. Для сборки `mediad` в Linux нужен GStreamer; см. [разработку в рабочем пространстве](../firmware/CONTRIBUTING.ru.md).

<a id="libudev-依赖"></a>
<a id="libudev-dependency"></a>
### Зависимость libudev

Программе геймпада нужна libudev. Пакет `libudev-dev` на компьютере сборки обслуживает этапы, выполняемые на хосте. Зависимости ARM64 скачиваются по [`build-environment150-libudev-sysroot.json`](../firmware/verification/build-environment150-libudev-sysroot.json), где зафиксированы `libudev-dev` и `libudev1` Debian Trixie **257.13-1~deb 13 u 1**. Скрипт проверяет зафиксированные URL и SHA256, затем распаковывает их в `.build/firmware/sysroot/arm64`; ARM-библиотеки на хост не устанавливаются. Запись сохраняет исходное имя с номером 150 и остаётся актуальным источником зависимостей кросс-компиляции.

<a id="与交付程序的关系"></a>
<a id="relationship-to-delivered-programs"></a>
### Связь с поставляемыми программами

Идентификатор текущей сборки и хеши бинарных файлов находятся в [`firmware/BUILD.json`](../firmware/BUILD.json). Воспроизведение выпуска и предыдущие записи тестов описаны в [BUILDING-V167.en.md](../firmware/BUILDING-V167.ru.md) и [`verification/v167/`](../firmware/verification/v167/): 237 тестов Rust, 18 тестов Python и десять моделей ARM64/QEMU.

Неиспользуемые скрипты сборки и упаковки V160/V162/V163 удалены. Для воспроизведения текущего выпуска используйте `firmware/build-V167.sh` и `package-V167.py`; см. [руководство V167](../firmware/BUILDING-V167.ru.md). Обычная сборка исходников по-прежнему выполняется через `tools/build-firmware.sh`.

При синхронизации исходников среду сборки повторно не скачивали и прошивку не пересобирали. Добавленную точку входа проверили на синтаксис shell, вывод справки и зафиксированные записи; это не утверждение о новой успешной сборке или побайтовом совпадении с исходными бинарными файлами. Сборка фиксирует архитектуру выходных ELF, максимальную версию символов GLIBC и SHA256.

## Windows SSH ASKPASS

Robot Console включает `ssh-askpass.exe`; исходник — [`firmware/scripts/ssh-askpass-windows.c`](../firmware/scripts/ssh-askpass-windows.c). Этот обработчик Windows OpenSSH не относится к ARM64-прошивке. Инструкция пересборки находится в заголовке C-файла. Консоль Linux использует Python-файл `firmware/console/ssh-askpass`, которому компиляция не нужна.

## IMU (STM32)

Прошивка отдельного STM32 IMU использует Arm GNU Toolchain **14.3.Rel1**. Точка входа сборки — [`Makefile.feetech`](../firmware/firmware/imu-source/Makefile.feetech), текущая версия — **FT6_SYNC15_UART_IRQ_v1**. Подготовьте STM32 CubeG0 и задайте `TOOLCHAIN` и `CUBE` согласно Makefile.

| Зависимость | Зафиксированная версия исходников |
| --- | --- |
| STM32 CubeG0 / CMSIS Core | `446ebe396489ca75679caa80887d7257efe92e3d` |
| Подмодуль устройства STM32 G0 | `f576c24e123edf3332988ecd49512c0f35f85186` |

```bash
make -C firmware/firmware/imu-source -f Makefile.feetech \
  TOOLCHAIN=/path/to/your/toolchain/bin/arm-none-eabi- \
  CUBE=/path/to/your/STM32CubeG0
```

Результат находится в `firmware/firmware/imu-source/build-feetech-ft6/`. Компиляция не прошивает плату. Готовый бинарный файл и порядок записи описаны в [прошивке IMU FT6](../../hardware/IMU-FIRMWARE.ru.md).
