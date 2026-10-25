[English](README.en.md) | [简体中文](README.md) | **Русский**

# Microduck HD1910

Адаптация для Feetech HD1910 на основе официального Microduck **0.15.1**, включающая прошивку робота, Robot Console R17 и независимую Training Studio. Эталонное оборудование: Radxa ZERO 3W, официальный корпус и 15 сервоприводов HD1910. Это личный проект участника сообщества, официально не связанный с Pollen Robotics.

**Исходный код опубликован; оригинальные разработки автора разрешены только для личного некоммерческого использования. Сторонние материалы сохраняют исходные лицензии. См. [LICENSE](LICENSE).**

**Скомпилированная прошивка доступна.** В исходном обзоре указано, что control.43 поставляется в Public Image R1 и Robot Console V167; см. [отдельный пакет и руководство по установке](../release-assets/README.ru.md).

> Примечание переводчика: согласно [описанию базовой версии](docs/BASELINE.ru.md), образ Public Image R1 содержит control.40. Прошивка control.43 входит в Robot Console V167 и устанавливается после записи образа.

**На вновь собранный IMU прошивку STM32 FT6 нужно записать отдельно:** [скачивание и инструкция](../hardware/IMU-FIRMWARE.ru.md). Установка control.43 на ZERO не программирует внешний IMU.

<a id="当前版本与源码"></a>
<a id="current-versions-and-source"></a>
## Текущие версии и исходники

| Компонент | Текущая версия | Исходники |
| --- | --- | --- |
| Прошивка робота и службы устройства | Официальная 0.15.1 · control.43 · API40 | [firmware/](firmware/README.ru.md) |
| Robot Console | R17 V167 (1.0.167) | [Руководство Robot Console](firmware/console/README.ru.md) |
| Training Studio | R1.5.27 | [Руководство Training Studio](training-console/README.ru.md) |
| Общедоступный образ системы | Public Image R1 · настройка первого запуска R5 | [Выпуск образа](https://github.com/kissqy/Microduck-kissqy/releases/tag/public-image-r1) |

V167 включает скомпилированную прошивку **control.43**. Обновление: **исправлено дрожание корпуса.** Текущий `firmware/BUILD.json` совпадает с записью BUILD внутри пакета V167. Исходники программ обеих консолей соответствуют их ZIP-архивам.

<a id="下载与使用"></a>
<a id="download-and-use"></a>
## Скачивание и использование

1. [Скачайте образ R1](https://github.com/kissqy/Microduck-kissqy/releases/download/public-image-r1/microduck-zero3w-0.15.1-R1.img.xz) и запишите его на microSD через [Armbian Imager](https://imager.armbian.com/).
2. При первом запуске подключитесь к `Microduck-kissqy` (пароль `12345678`), затем настройте домашнюю Wi-Fi и новый пароль входа в систему. Если страница не открылась автоматически, перейдите на `http://10.42.0.1:8088`.
3. [Скачайте Robot Console V167](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Console-R17-V167.zip), полностью распакуйте архив и запустите `start.cmd`; в macOS / Linux выполните `bash start.command`. Локальная страница: `http://127.0.0.1:8090`.
4. Укажите свои `username@robot-IP` и данные SSH. Проверьте калибровку своего робота, затем соблюдайте порядок **HOME → hold → walk**. Службы робота уже установлены в образе; существующую систему обновляйте через «系统维护 → 随包固件» («Обслуживание системы → Комплектная прошивка»).
5. Для обучения [скачайте Training Studio R1.5.27](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Training-Studio-R1.5.27.zip), запустите `start-training.cmd` или `bash start-training.command` и откройте `http://127.0.0.1:8092`.

Для обучения используются NVIDIA GPU и Linux / WSL2. Сначала установите Git и [uv](https://docs.astral.sh/uv/getting-started/installation/). При первичной подготовке скачиваются зафиксированная версия движка обучения и зависимости. Сейчас доступны 14 категорий действий и 35 конфигураций задач; см. [руководство по обучению](training-console/USER-GUIDE.ru.md).

<a id="从源码使用"></a>
<a id="using-the-source"></a>
## Работа с исходниками

- Запуск Robot Console: `firmware/console/start.cmd` или `start.command`.
- Запуск Training Studio: `training-console/start-training.cmd` или `start-training.command`.
- Сборка прошивки: [BUILD.md](docs/BUILD.ru.md). Для повседневного использования компиляция не нужна.
- Версии выпуска и границы проверки: [BASELINE.md](docs/BASELINE.ru.md). Происхождение и контрольные суммы: [PUBLICATION-MANIFEST.json](PUBLICATION-MANIFEST.json).
- Лицензирование и сторонние источники: [LICENSE](LICENSE) · [THIRD-PARTY.md](docs/THIRD-PARTY.ru.md).

Для каждого робота нужно отдельно проверить нули, направления, пределы суставов и IMU. Программы, модели и существующая реализация управления синхронизированы с поставляемыми пакетами; публикация исходников не расширяет исходный объём испытаний на реальном роботе.
