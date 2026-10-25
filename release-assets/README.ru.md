[English](README.en.md) | [简体中文](README.md) | **Русский**

<a id="飞特-hd1910-已编译固件-control43"></a>
<a id="compiled-feetech-hd1910-firmware-control43"></a>
# Скомпилированная прошивка Feetech HD1910 · control.43

<a id="飞特-hd1910-已编译固件--control43"></a>
<a id="compiled-feetech-hd1910-firmware--control43"></a>
**Установочный пакет служб робота ARM64 для Radxa ZERO 3W**, основанный на официальном Microduck 0.15.1 и предназначенный для Robot Console R17 V167, IPC API40. Включает скомпилированные `robotd`, `padd`, `robotctl`, службы камеры, библиотеки инференса, 10 моделей движений и установочные скрипты. **Для обычного использования компиляция исходников не требуется.**

[⬇️ Скачать скомпилированную прошивку .tar.gz](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/microduck-hd1910/firmware/console/updates/Microduck-Robotd-FT6-R17.tar.gz) · [Файл SHA256](Microduck-Robotd-FT6-R17.sha256) · [Идентификаторы и запись проверки](firmware-control43.json) · [Главная страница](../README.ru.md)

**Изменение: исправлено дрожание корпуса.**

**На новом IMU прошейте STM32 FT6 отдельно:** [загрузка и инструкция](../hardware/IMU-FIRMWARE.ru.md); установка control.43 на ZERO не программирует внешний IMU.

<a id="和镜像中控是什么关系"></a>
<a id="image-console-and-standalone-firmware"></a>
## Образ, консоль и отдельная прошивка

| Пакет | Назначение |
| --- | --- |
| Образ системы `.img.xz` | Чистая установка на microSD с предустановленными control.40 и окружением робота; обновление до control.43 выполняется прошивкой из V167. |
| Robot Console V167 `.zip` | Инструмент управления на компьютере; `updates/` содержит ту же скомпилированную прошивку. |
| Отдельный `.tar.gz` на этой странице | Точное содержимое прошивки V167, предложенное отдельно для обновления существующей системы. |

**Обычному пользователю нужны образ системы и Robot Console.** В образе R1 по-прежнему находится control.40. После записи образа установите прошивку из V167 для обновления до control.43. Этот пакет обновляет службы Linux на ZERO; для микроконтроллеров HAT/IMU используются отдельные `.bin`. Этот `.tar.gz` не является образом системы для microSD.

<a id="用中控安装"></a>
<a id="install-with-the-console"></a>
## Установка через консоль

Полностью распакуйте [Robot Console V167](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Console-R17-V167.zip), запустите `start.cmd` (macOS/Linux: `bash start.command`), подключитесь к ZERO по SSH и выберите **系统维护 → 随包固件** («Обслуживание системы → Прошивка из комплекта»). Консоль уже содержит этот пакет; для такого способа отдельная загрузка `.tar.gz` не нужна.

Импорт локальной прошивки принимает ZIP, а не отдельный `.tar.gz`. Если вы скачали отдельный пакет, поместите неизменённый архив в ZIP через Windows PowerShell:

```powershell
Compress-Archive -Path .\Microduck-Robotd-FT6-R17.tar.gz -DestinationPath .\Microduck-Firmware-control43.zip
```

Выберите этот ZIP в импорте прошивки V167. Сохраните имя внутреннего архива `Microduck-Robotd-FT6-R17.tar.gz`; консоль сверяет его SHA256 с соответствующей прошивкой из комплекта.

<a id="用-ssh-单独安装"></a>
<a id="install-separately-over-ssh"></a>
## Отдельная установка по SSH

Используйте этот способ на ZERO с уже установленным официальным Microduck 0.15.1 или окружением Public Image R1 из этого проекта. **Команды выполняются в SSH-терминале ZERO.** Для пустой microSD начните с образа системы.

```bash
(
  set -e
  microduck_fw_dir=$(mktemp -d "$HOME/microduck-control43.XXXXXX")
  curl -fL --progress-bar \
    -o "$microduck_fw_dir/Microduck-Robotd-FT6-R17.tar.gz" \
    "https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/microduck-hd1910/firmware/console/updates/Microduck-Robotd-FT6-R17.tar.gz"
  printf '%s  %s\n' \
    'bcfd5c183c697b9c4e0fdbd563d995eda6a48331a7c49b9e76d20bd156c65cce' \
    "$microduck_fw_dir/Microduck-Robotd-FT6-R17.tar.gz" | sha256sum -c -
  tar -xzf "$microduck_fw_dir/Microduck-Robotd-FT6-R17.tar.gz" -C "$microduck_fw_dir"
  sudo bash "$microduck_fw_dir/Microduck-Robotd-FT6-R17/service.sh" upgrade
)
```

Отображается прогресс загрузки; несовпадение контрольной суммы останавливает выполнение. Существующий процесс `service.sh upgrade` считывает и предпочитает корректную локальную калибровку и сохранённые настройки. Дождитесь этапов запуска 1/4–4/4, проверьте суставы и IMU этой сборки и завершите HOME до включения движения.

<a id="版本与校验"></a>
<a id="identity-and-checksum"></a>
## Идентификаторы и контрольная сумма

| Параметр | Значение |
| --- | --- |
| Сборка | `1fa8438-feetech-ft6-control.43` |
| Официальная база / API | `0.15.1` / `40` |
| Консоль | `R17 V167` |
| Архитектура | Linux AArch64 / ARM64 |
| Размер | 34138802 байта (около 32.56 MiB) |
| SHA256 | `bcfd5c183c697b9c4e0fdbd563d995eda6a48331a7c49b9e76d20bd156c65cce` |

При описанной в оригинале очистке проверены побайтовое совпадение с прошивкой из V167 и все 160 записей контрольных сумм архива. Предыдущие записи сборки находятся в [руководстве V167](../microduck-hd1910/firmware/BUILDING-V167.ru.md).

[Исходники и версии прошивки](../microduck-hd1910/firmware/README-R17.ru.md) · [Сборка из исходников](../microduck-hd1910/docs/BUILD.ru.md) · [Лицензии компонентов](../microduck-hd1910/LICENSE)
