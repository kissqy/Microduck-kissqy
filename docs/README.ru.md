[English](README.en.md) | [简体中文](README.md) | **Русский**

# Документация Microduck на русском

Здесь собраны переводы пользовательских руководств, инструкций по сборке, описаний электроники, архитектуры, дневников разработки и отчётов о проверках. Файлы программы, команды, числовые параметры, контрольные суммы и исторические результаты сохранены. Интерфейсы консолей остаются китайскими; в переводе оригинальные надписи кнопок даны рядом с русскими пояснениями.

**Актуальная отправная точка:** [полное руководство по сборке](MICRODUCK-BUILD-GUIDE.ru.md), [вопросы и ответы](MICRODUCK-FAQ.ru.md), [публичный выпуск](../START-HERE.ru.md), [загрузки](../README.ru.md#downloads-and-versions), [Robot Console V167](../microduck-hd1910/firmware/console/USER-GUIDE.ru.md) и [Training Studio R1.5.27](../microduck-hd1910/training-console/USER-GUIDE.ru.md). Готовый образ R1 содержит `control.40`; обновление через V167 устанавливает `control.43`.

**Исторические материалы** ниже описывают состояние проекта на дату соответствующей записи. Их версии и результаты не заменяют [текущий состав выпуска](../microduck-hd1910/docs/BASELINE.ru.md). Отдельные противоречия исходных документов пояснены примечаниями переводчика в переводах.

Лицензии и юридические NOTICE, сырые логи, служебные инструкции для агентов и неизменяемые снимки upstream не переводились. Их оригиналы доступны по ссылкам из соответствующих руководств.

## Начало работы, сборка и выпуск

| Документ | Исходник |
| --- | --- |
| [🦆 Список покупок для Microduck](../DUCK-SHOPPING-LIST.ru.md) | [English](../DUCK-SHOPPING-LIST.ru.md) · [中文 / оригинал](../DUCK-SHOPPING-LIST.ru.md) |
| [🦆 Реплика Microduck с Feetech HD1910 · Сборка, управление и обучение с подкреплением](../README.ru.md) | [English](../README.ru.md) · [中文 / оригинал](../README.ru.md) |
| [Текущий опубликованный выпуск Microduck](../START-HERE.ru.md) | [English](../START-HERE.ru.md) · [中文 / оригинал](../START-HERE.ru.md) |
| [🔧 Примечания по сборке и эксплуатации](ASSEMBLY-NOTES.ru.md) | [English](ASSEMBLY-NOTES.ru.md) · [中文 / оригинал](ASSEMBLY-NOTES.ru.md) |
| [🧰 Инструменты для сборки и расходные материалы](BUILD-TOOLS.ru.md) | [English](BUILD-TOOLS.ru.md) · [中文 / оригинал](BUILD-TOOLS.ru.md) |
| [Сборка реплики Microduck с Feetech HD1910: детали, 3D-печать, прошивка, калибровка и обучение](MICRODUCK-BUILD-GUIDE.ru.md) | [English](MICRODUCK-BUILD-GUIDE.ru.md) · [中文 / оригинал](MICRODUCK-BUILD-GUIDE.ru.md) |
| [Частые вопросы о реплике Microduck с Feetech: установка, калибровка, IMU, помехи Wi-Fi от геймпада и перезагрузки из-за питания](MICRODUCK-FAQ.ru.md) | [English](MICRODUCK-FAQ.ru.md) · [中文 / оригинал](MICRODUCK-FAQ.ru.md) |
| [Структура репозитория и повторяющиеся ресурсы](REPOSITORY-LAYOUT.ru.md) | [English](REPOSITORY-LAYOUT.ru.md) · [中文 / оригинал](REPOSITORY-LAYOUT.ru.md) |
| [🦆 Готовый образ системы Microduck R1](releases/public-image-r1.ru.md) | [English](releases/public-image-r1.ru.md) · [中文 / оригинал](releases/public-image-r1.ru.md) |
| [Microduck HD1910](../microduck-hd1910/README.ru.md) | [English](../microduck-hd1910/README.ru.md) · [中文 / оригинал](../microduck-hd1910/README.ru.md) |
| [Базовая версия выпуска и границы проверки](../microduck-hd1910/docs/BASELINE.ru.md) | [English](../microduck-hd1910/docs/BASELINE.ru.md) · [中文 / оригинал](../microduck-hd1910/docs/BASELINE.ru.md) |
| [Сборка control.43 из исходников](../microduck-hd1910/docs/BUILD.ru.md) | [English](../microduck-hd1910/docs/BUILD.ru.md) · [中文 / оригинал](../microduck-hd1910/docs/BUILD.ru.md) |
| [Скомпилированная прошивка Feetech HD1910 · control.43](../release-assets/README.ru.md) | [English](../release-assets/README.ru.md) · [中文 / оригинал](../release-assets/README.ru.md) |
| [База для воспроизводимой сборки](../release-assets/build-baselines/README.ru.md) | [English](../release-assets/build-baselines/README.ru.md) · [中文 / оригинал](../release-assets/build-baselines/README.ru.md) |

## Электроника, печать и компоненты

| Документ | Исходник |
| --- | --- |
| [Состав пакета](../hardware/3d-print-frankenduck/FILES.ru.md) | [中文 / оригинал](../hardware/3d-print-frankenduck/FILES.ru.md) |
| [🖨️ Полный комплект деталей утки для печати · FrankenDuck](../hardware/3d-print-frankenduck/README.ru.md) | [English](../hardware/3d-print-frankenduck/README.ru.md) · [中文 / оригинал](../hardware/3d-print-frankenduck/README.ru.md) |
| [HAT / IMU · Версия с разъёмами AMP2.0](../hardware/AMP2.0-VERSION.ru.md) | [English](../hardware/AMP2.0-VERSION.ru.md) · [中文 / оригинал](../hardware/AMP2.0-VERSION.ru.md) |
| [🦆 Список покупок для утки](../hardware/DUCK-SHOPPING-LIST.ru.md) | [English](../hardware/DUCK-SHOPPING-LIST.ru.md) · [中文 / оригинал](../hardware/DUCK-SHOPPING-LIST.ru.md) |
| [История изготовления HAT](../hardware/HAT-TIMELINE.ru.md) | [English](../hardware/HAT-TIMELINE.ru.md) · [中文 / оригинал](../hardware/HAT-TIMELINE.ru.md) |
| [Прошивка IMU FT6: скачать, записать и проверить](../hardware/IMU-FIRMWARE.ru.md) | [English](../hardware/IMU-FIRMWARE.ru.md) · [中文 / оригинал](../hardware/IMU-FIRMWARE.ru.md) |
| [История изготовления IMU](../hardware/IMU-TIMELINE.ru.md) | [English](../hardware/IMU-TIMELINE.ru.md) · [中文 / оригинал](../hardware/IMU-TIMELINE.ru.md) |
| [Самодельные платы HAT и IMU](../hardware/README.ru.md) | [English](../hardware/README.ru.md) · [中文 / оригинал](../hardware/README.ru.md) |
| [Исходники отдельного IMU корпуса · текущая FT6](../microduck-hd1910/firmware/firmware/imu-source/README.ru.md) | [English](../microduck-hd1910/firmware/firmware/imu-source/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/firmware/imu-source/README.ru.md) |
| [Протокол и совместимость](../microduck-hd1910/firmware/firmware/imu-source/README_FT6_SYNC15.ru.md) | [English](../microduck-hd1910/firmware/firmware/imu-source/README_FT6_SYNC15.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/firmware/imu-source/README_FT6_SYNC15.ru.md) |

## Управление роботом

| Документ | Исходник |
| --- | --- |
| [Microduck R17 V167 / control.43](../microduck-hd1910/firmware/console/PUBLICATION-NOTE.ru.md) | [English](../microduck-hd1910/firmware/console/PUBLICATION-NOTE.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/console/PUBLICATION-NOTE.ru.md) |
| [🎮 Microduck Robot Console · R17 V167](../microduck-hd1910/firmware/console/README.ru.md) | [English](../microduck-hd1910/firmware/console/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/console/README.ru.md) |
| [Источники звука и управления геймпадом](../microduck-hd1910/firmware/console/THIRD_PARTY_NOTICES.ru.md) | [English](../microduck-hd1910/firmware/console/THIRD_PARTY_NOTICES.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/console/THIRD_PARTY_NOTICES.ru.md) |
| [Руководство пользователя Microduck R17 V167 / control.43](../microduck-hd1910/firmware/console/USER-GUIDE.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/console/USER-GUIDE.ru.md) · [English](../microduck-hd1910/firmware/console/USER-GUIDE.ru.md) |
| [Происхождение параметров консоли R17 — проектная запись v148](../microduck-hd1910/firmware/console/docs/joint-scale-design148.ru.md) | [English](../microduck-hd1910/firmware/console/docs/joint-scale-design148.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/console/docs/joint-scale-design148.ru.md) |
| [Записи проверки R147](../microduck-hd1910/firmware/console/verification/README.ru.md) | [English](../microduck-hd1910/firmware/console/verification/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/console/verification/README.ru.md) |

## Обучение и Training Studio

| Документ | Исходник |
| --- | --- |
| [Примечание к публикации Microduck Training Studio R1.5.27](../microduck-hd1910/training-console/PUBLICATION-NOTE.ru.md) | [English](../microduck-hd1910/training-console/PUBLICATION-NOTE.ru.md) · [中文 / оригинал](../microduck-hd1910/training-console/PUBLICATION-NOTE.ru.md) |
| [🧠 Microduck Training Studio · R1.5.27](../microduck-hd1910/training-console/README.ru.md) | [English](../microduck-hd1910/training-console/README.ru.md) · [中文 / оригинал](../microduck-hd1910/training-console/README.ru.md) |
| [Microduck Training Studio R1.5.27](../microduck-hd1910/training-console/USER-GUIDE.ru.md) | [中文 / оригинал](../microduck-hd1910/training-console/USER-GUIDE.ru.md) · [English](../microduck-hd1910/training-console/USER-GUIDE.ru.md) |

## Прошивка, модели и движения

| Документ | Исходник |
| --- | --- |
| [Комплектная прошивка Microduck R17 V167 / control.43](../microduck-hd1910/firmware/packaging/README.ru.md) | [English](../microduck-hd1910/firmware/packaging/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/packaging/README.ru.md) |
| [Самостоятельно обученная модель HD1910 · Целевая прошивка 0.15.1](../microduck-hd1910/firmware/packaging/models/1cbf8730eadd75a5704332c9f3c10f60/README.ru.md) | [English](../microduck-hd1910/firmware/packaging/models/1cbf8730eadd75a5704332c9f3c10f60/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/packaging/models/1cbf8730eadd75a5704332c9f3c10f60/README.ru.md) |
| [Самостоятельно обученная модель HD1910 · Целевая прошивка 0.15.1](../microduck-hd1910/firmware/packaging/models/59e15d7b04d0c40e9b11b8a70bdecae6/README.ru.md) | [English](../microduck-hd1910/firmware/packaging/models/59e15d7b04d0c40e9b11b8a70bdecae6/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/packaging/models/59e15d7b04d0c40e9b11b8a70bdecae6/README.ru.md) |
| [Самостоятельно обученная модель HD1910 · Целевая прошивка 0.15.1](../microduck-hd1910/firmware/packaging/models/67ad09d82f4865d222a7ae06f250cf9f/README.ru.md) | [English](../microduck-hd1910/firmware/packaging/models/67ad09d82f4865d222a7ae06f250cf9f/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/packaging/models/67ad09d82f4865d222a7ae06f250cf9f/README.ru.md) |
| [Самостоятельно обученная модель HD1910 · Целевая прошивка 0.15.1](../microduck-hd1910/firmware/packaging/models/a481d9f211f31d9476ab1a319fe362a2/README.ru.md) | [English](../microduck-hd1910/firmware/packaging/models/a481d9f211f31d9476ab1a319fe362a2/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/packaging/models/a481d9f211f31d9476ab1a319fe362a2/README.ru.md) |
| [Самостоятельно обученная модель HD1910 · Целевая прошивка 0.15.1](../microduck-hd1910/firmware/packaging/models/b14e3a8b56ddbb8d2d831e727774a168/README.ru.md) | [English](../microduck-hd1910/firmware/packaging/models/b14e3a8b56ddbb8d2d831e727774a168/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/packaging/models/b14e3a8b56ddbb8d2d831e727774a168/README.ru.md) |
| [Самостоятельно обученная модель HD1910 · Целевая прошивка 0.15.1](../microduck-hd1910/firmware/packaging/models/ee0376c927044cdece056ba1d3e6eac7/README.ru.md) | [English](../microduck-hd1910/firmware/packaging/models/ee0376c927044cdece056ba1d3e6eac7/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/packaging/models/ee0376c927044cdece056ba1d3e6eac7/README.ru.md) |
| [Самостоятельно обученная модель HD1910 · Целевая прошивка 0.15.1](../microduck-hd1910/firmware/packaging/roller/standup/README.ru.md) | [English](../microduck-hd1910/firmware/packaging/roller/standup/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/packaging/roller/standup/README.ru.md) |
| [Базовая версия политик — R17 v1.0.146 / официальная 0.15.1](../microduck-hd1910/firmware/policies/README.ru.md) | [English](../microduck-hd1910/firmware/policies/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/policies/README.ru.md) |
| [Самостоятельно обученная модель HD1910 · Целевая прошивка 0.15.1](../microduck-hd1910/firmware/policies/ground_pick/README.ru.md) | [English](../microduck-hd1910/firmware/policies/ground_pick/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/policies/ground_pick/README.ru.md) |
| [Самостоятельно обученная модель HD1910 · Целевая прошивка 0.15.1](../microduck-hd1910/firmware/policies/kick_left/README.ru.md) | [English](../microduck-hd1910/firmware/policies/kick_left/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/policies/kick_left/README.ru.md) |
| [Самостоятельно обученная модель HD1910 · Целевая прошивка 0.15.1](../microduck-hd1910/firmware/policies/roulade/README.ru.md) | [English](../microduck-hd1910/firmware/policies/roulade/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/policies/roulade/README.ru.md) |
| [Самостоятельно обученная модель HD1910 · Целевая прошивка 0.15.1](../microduck-hd1910/firmware/policies/stand/README.ru.md) | [English](../microduck-hd1910/firmware/policies/stand/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/policies/stand/README.ru.md) |
| [Самостоятельно обученная модель HD1910 · Целевая прошивка 0.15.1](../microduck-hd1910/firmware/policies/walk/README.ru.md) | [English](../microduck-hd1910/firmware/policies/walk/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/policies/walk/README.ru.md) |
| [Самостоятельно обученная модель HD1910 · Целевая прошивка 0.15.1](../microduck-hd1910/firmware/test-data/walk-teacher14000/README.ru.md) | [English](../microduck-hd1910/firmware/test-data/walk-teacher14000/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/test-data/walk-teacher14000/README.ru.md) |

## Команды, установка и обслуживание

| Документ | Исходник |
| --- | --- |
| [Развёртывание: конфигурация уровня ОС](../microduck-hd1910/firmware/deploy/README.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/deploy/README.ru.md) |
| [Ключ разработки команды](../microduck-hd1910/firmware/deploy/dev-key/README.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/deploy/dev-key/README.ru.md) |
| [Доверенные открытые ключи](../microduck-hd1910/firmware/deploy/trusted_keys/README.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/deploy/trusted_keys/README.ru.md) |
| [Исправление повторной записи загрузочной конфигурации Armbian](../microduck-hd1910/firmware/docs/robot/armbian-boot-config.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/robot/armbian-boot-config.ru.md) |
| [Шпаргалка для платы разработчика](../microduck-hd1910/firmware/docs/robot/cheatsheet-dev.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/robot/cheatsheet-dev.ru.md) |
| [Шпаргалка](../microduck-hd1910/firmware/docs/robot/cheatsheet.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/robot/cheatsheet.ru.md) |
| [Сборка на компьютере и установка на плату](../microduck-hd1910/firmware/docs/robot/dev-push.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/robot/dev-push.ru.md) |
| [duckctl: все команды](../microduck-hd1910/firmware/docs/robot/duckctl.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/robot/duckctl.ru.md) |
| [Ручная установка по шагам](../microduck-hd1910/firmware/docs/robot/install-by-hand.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/robot/install-by-hand.ru.md) |
| [Установка на плату разработчика](../microduck-hd1910/firmware/docs/robot/install-dev.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/robot/install-dev.ru.md) |
| [Сопряжение геймпада](../microduck-hd1910/firmware/docs/robot/pair-a-gamepad.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/robot/pair-a-gamepad.ru.md) |
| [Симулируемый робот](../microduck-hd1910/firmware/docs/robot/simulation.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/robot/simulation.ru.md) |

## Архитектура и проектные решения

| Документ | Исходник |
| --- | --- |
| [Путь приложения — btd и configd](../microduck-hd1910/firmware/docs/design/app-path-design.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/design/app-path-design.ru.md) |
| [Архитектура демона робота](../microduck-hd1910/firmware/docs/design/architecture.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/design/architecture.ru.md) |
| [Защитное восстановление при загрузке](../microduck-hd1910/firmware/docs/design/boot-recovery-net.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/design/boot-recovery-net.ru.md) |
| [Приложение для телефона: из чего оно состоит](../microduck-hd1910/firmware/docs/design/mobile-app.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/design/mobile-app.ru.md) |
| [Канал политик — политики из Hub](../microduck-hd1910/firmware/docs/design/policy-channel-design.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/design/policy-channel-design.ru.md) |
| [База R17 v1.0.157-Fix 9 / control.36](../microduck-hd1910/firmware/docs/design/r17-connection-design.ru.md) | [English](../microduck-hd1910/firmware/docs/design/r17-connection-design.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/docs/design/r17-connection-design.ru.md) |
| [Происхождение параметров консоли R17](../microduck-hd1910/firmware/docs/design/r17-settings-design.ru.md) | [English](../microduck-hd1910/firmware/docs/design/r17-settings-design.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/docs/design/r17-settings-design.ru.md) |
| [Удалённый доступ: учётная запись и посредник](../microduck-hd1910/firmware/docs/design/remote-access-design.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/design/remote-access-design.ru.md) |
| [WebRTC: сеансы, сигнализация и канал управления](../microduck-hd1910/firmware/docs/design/remote-webrtc.ru.md) | [English](../microduck-hd1910/firmware/docs/design/remote-webrtc.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/docs/design/remote-webrtc.ru.md) |
| [Что и когда перезапускается](../microduck-hd1910/firmware/docs/design/restart-order.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/design/restart-order.ru.md) |
| [Базовая версия R17 v1.0.157-Fix6 / control.36](../microduck-hd1910/firmware/docs/design/robotd-design.ru.md) | [English](../microduck-hd1910/firmware/docs/design/robotd-design.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/docs/design/robotd-design.ru.md) |
| [Симуляция: те же службы, тело в MuJoCo](../microduck-hd1910/firmware/docs/design/simulation.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/design/simulation.ru.md) |
| [Система обновления демонов робота — проект](../microduck-hd1910/firmware/docs/design/updater-design.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/design/updater-design.ru.md) |
| [Клиент WebRTC: от тестовой страницы к консоли робота](../microduck-hd1910/firmware/docs/design/webrtc-console.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/design/webrtc-console.ru.md) |
| [Стек автономного поведения: наследуемые возможности и идеи на будущее](../microduck-hd1910/firmware/docs/ideas/autonomous_behavior.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/ideas/autonomous_behavior.ru.md) |

## Разработка ПО и справочные материалы

| Документ | Исходник |
| --- | --- |
| [Публикация этого репозитория](../microduck-hd1910/docs/PUBLISH.ru.md) | [English](../microduck-hd1910/docs/PUBLISH.ru.md) · [中文 / оригинал](../microduck-hd1910/docs/PUBLISH.ru.md) |
| [Сторонние источники и области действия лицензий](../microduck-hd1910/docs/THIRD-PARTY.ru.md) | [English](../microduck-hd1910/docs/THIRD-PARTY.ru.md) · [中文 / оригинал](../microduck-hd1910/docs/THIRD-PARTY.ru.md) |
| [Руководство по сборке R17 V167 / control.43](../microduck-hd1910/firmware/BUILDING-V167.ru.md) | [English](../microduck-hd1910/firmware/BUILDING-V167.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/BUILDING-V167.ru.md) |
| [Участие в разработке](../microduck-hd1910/firmware/CONTRIBUTING.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/CONTRIBUTING.ru.md) |
| [Изменения R17 v1.0.137 / официальной версии 0.15.1](../microduck-hd1910/firmware/OFFICIAL-CHANGES.ru.md) | [English](../microduck-hd1910/firmware/OFFICIAL-CHANGES.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/OFFICIAL-CHANGES.ru.md) |
| [Геймпад R17 v1.0.97 / официальной версии 0.15.1](../microduck-hd1910/firmware/OFFICIAL-GAMEPAD.ru.md) | [English](../microduck-hd1910/firmware/OFFICIAL-GAMEPAD.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/OFFICIAL-GAMEPAD.ru.md) |
| [История изменений R17](../microduck-hd1910/firmware/R17-CHANGES.ru.md) | [English](../microduck-hd1910/firmware/R17-CHANGES.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/R17-CHANGES.ru.md) |
| [Прошивка Microduck control.43 и консоль R17 V167](../microduck-hd1910/firmware/README-R17.ru.md) | [English](../microduck-hd1910/firmware/README-R17.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/README-R17.ru.md) |
| [Что умеет робот](../microduck-hd1910/firmware/README.ru.md) | [English](../microduck-hd1910/firmware/README.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/README.ru.md) |
| [Самостоятельно обученные модели R17 v1.0.137 / официальной версии 0.15.1](../microduck-hd1910/firmware/SELF-TRAINED.ru.md) | [English](../microduck-hd1910/firmware/SELF-TRAINED.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/SELF-TRAINED.ru.md) |
| [sysusers.d / README.ru.md](../microduck-hd1910/firmware/configd/systemd/sysusers.d/README.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/configd/systemd/sysusers.d/README.ru.md) |
| [Документация Microduck R17 V164 / control.40](../microduck-hd1910/firmware/docs/README.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/README.ru.md) |
| [Частые вопросы](../microduck-hd1910/firmware/docs/faq.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/faq.ru.md) |
| [Манифест политики, схема 2](../microduck-hd1910/firmware/docs/policy-manifest.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/policy-manifest.ru.md) |
| [Рекуррентные политики ONNX](../microduck-hd1910/firmware/docs/recurrent-policies.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/recurrent-policies.ru.md) |
| [Регрессионный тест отключения GameSir](../microduck-hd1910/firmware/gamepad-r7/tests/README.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/gamepad-r7/tests/README.ru.md) |
| [microduck console](../microduck-hd1910/firmware/mediad/webclient/space/README.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/mediad/webclient/space/README.ru.md) |
| [pet-detect](../microduck-hd1910/firmware/pet-detect/README.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/pet-detect/README.ru.md) |
| [hello duck](../microduck-hd1910/firmware/spaces/hello/README.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/spaces/hello/README.ru.md) |
| [Площадка политик управления microduck](../microduck-hd1910/firmware/spaces/policy-playground/README.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/spaces/policy-playground/README.ru.md) |
| [Демонстрация зрения microduck](../microduck-hd1910/firmware/spaces/vision-demo/README.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/spaces/vision-demo/README.ru.md) |

## Дневник разработки и технические исследования

| Документ | Исходник |
| --- | --- |
| [Настройка CI](../microduck-hd1910/firmware/docs/project/ci-setup.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/project/ci-setup.ru.md) |
| [Что делает робот, когда к нему никто не обращается](../microduck-hd1910/firmware/docs/project/idle-cpu.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/project/idle-cpu.ru.md) |
| [У пути установки не было теста](../microduck-hd1910/firmware/docs/project/install-path-gap.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/project/install-path-gap.ru.md) |
| [Запуск медиатракта на оборудовании](../microduck-hd1910/firmware/docs/project/media-bringup.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/project/media-bringup.ru.md) |
| [NPU и работающий на нём детектор утки](../microduck-hd1910/firmware/docs/project/npu-bringup.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/project/npu-bringup.ru.md) |
| [Минимальная конфигурация, в которой геймпад создаёт сопряжение](../microduck-hd1910/firmware/docs/project/pad-minimal-pairing.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/project/pad-minimal-pairing.ru.md) |
| [Дорожная карта](../microduck-hd1910/firmware/docs/project/roadmap.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/project/roadmap.ru.md) |
| [Запуск этапа slice 2 на оборудовании](../microduck-hd1910/firmware/docs/project/slice-2-bringup.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/project/slice-2-bringup.ru.md) |
| [Датчики головы, когда никто не смотрит](../microduck-hd1910/firmware/docs/project/tof-on-demand.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/project/tof-on-demand.ru.md) |
| [Обновление робота с телефона](../microduck-hd1910/firmware/docs/project/update-over-ble.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/docs/project/update-over-ble.ru.md) |

## Исторические отчёты о проверках

| Документ | Исходник |
| --- | --- |
| [verification / MERGE-149.ru.md](../microduck-hd1910/firmware/verification/MERGE-149.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/verification/MERGE-149.ru.md) |
| [Записи проверки v153](../microduck-hd1910/firmware/verification/README153.ru.md) | [English](../microduck-hd1910/firmware/verification/README153.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/verification/README153.ru.md) |
| [verification / REPRODUCE.ru.md](../microduck-hd1910/firmware/verification/REPRODUCE.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/verification/REPRODUCE.ru.md) |
| [Проверка R152](../microduck-hd1910/firmware/verification/REPRODUCE152.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/verification/REPRODUCE152.ru.md) |
| [Архивный документ](../microduck-hd1910/firmware/verification/policy-manifest.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/verification/policy-manifest.ru.md) |
| [v160 / BUILD-REPORT.ru.md](../microduck-hd1910/firmware/verification/v160/BUILD-REPORT.ru.md) | [中文 / оригинал](../microduck-hd1910/firmware/verification/v160/BUILD-REPORT.ru.md) |
| [Проверка официального пути восстановления на роликах](../microduck-hd1910/firmware/verification/v162/official-roller-route.ru.md) | [English](../microduck-hd1910/firmware/verification/v162/official-roller-route.ru.md) · [中文 / оригинал](../microduck-hd1910/firmware/verification/v162/official-roller-route.ru.md) |

## История обучения и проверок

| Документ | Исходник |
| --- | --- |
| [Сервоприводы Feetech, upstream-конфигурация и проверка совместного обучения](../microduck-hd1910/training-console/docs/Servo-training-audit.ru.md) | [English](../microduck-hd1910/training-console/docs/Servo-training-audit.ru.md) · [中文 / оригинал](../microduck-hd1910/training-console/docs/Servo-training-audit.ru.md) |
| [Учитель подъёма на 11000 итераций: предложение курса переворота](../microduck-hd1910/training-console/docs/StandUp-11000-rollover-plan.ru.md) | [English](../microduck-hd1910/training-console/docs/StandUp-11000-rollover-plan.ru.md) · [中文 / оригинал](../microduck-hd1910/training-console/docs/StandUp-11000-rollover-plan.ru.md) |
| [Отчёт о проверке удалённого обучения R1.5.15](../microduck-hd1910/training-console/docs/Verification.ru.md) | [English](../microduck-hd1910/training-console/docs/Verification.ru.md) · [中文 / оригинал](../microduck-hd1910/training-console/docs/Verification.ru.md) |
| [История версий Training Studio](../microduck-hd1910/training-console/docs/Version-history.ru.md) | [English](../microduck-hd1910/training-console/docs/Version-history.ru.md) · [中文 / оригинал](../microduck-hd1910/training-console/docs/Version-history.ru.md) |
| [Аудит официальных параметров каждой задачи (7 октября 2026 года)](../microduck-hd1910/training-console/docs/audit-0151/official-task-parameter-audit.ru.md) | [English](../microduck-hd1910/training-console/docs/audit-0151/official-task-parameter-audit.ru.md) · [中文 / оригинал](../microduck-hd1910/training-console/docs/audit-0151/official-task-parameter-audit.ru.md) |
| [Аудит официальных параметров шести семейств роликов (7 октября 2026 года)](../microduck-hd1910/training-console/docs/audit-0151/roller-audit/official-roller-audit.ru.md) | [English](../microduck-hd1910/training-console/docs/audit-0151/roller-audit/official-roller-audit.ru.md) · [中文 / оригинал](../microduck-hd1910/training-console/docs/audit-0151/roller-audit/official-roller-audit.ru.md) |
| [Аудит совместимости действий с зафиксированной версией robotd 0.15.1](../microduck-hd1910/training-console/docs/audit-0151/runtime-audit.ru.md) | [中文 / оригинал](../microduck-hd1910/training-console/docs/audit-0151/runtime-audit.ru.md) |
| [Тесты Microduck Training Studio R1.5.27](../microduck-hd1910/training-console/tests/README.ru.md) | [中文 / оригинал](../microduck-hd1910/training-console/tests/README.ru.md) |
| [docs / R1.5.17-verification.ru.md](../microduck-hd1910/training-console/docs/R1.5.17-verification.ru.md) | [中文 / оригинал](../microduck-hd1910/training-console/docs/R1.5.17-verification.ru.md) |
| [docs / R1.5.18-verification.ru.md](../microduck-hd1910/training-console/docs/R1.5.18-verification.ru.md) | [中文 / оригинал](../microduck-hd1910/training-console/docs/R1.5.18-verification.ru.md) |
| [docs / R1.5.19-verification.ru.md](../microduck-hd1910/training-console/docs/R1.5.19-verification.ru.md) | [中文 / оригинал](../microduck-hd1910/training-console/docs/R1.5.19-verification.ru.md) |
| [docs / R1.5.20-verification.ru.md](../microduck-hd1910/training-console/docs/R1.5.20-verification.ru.md) | [中文 / оригинал](../microduck-hd1910/training-console/docs/R1.5.20-verification.ru.md) |
| [docs / R1.5.21-CalibUI1-verification.ru.md](../microduck-hd1910/training-console/docs/R1.5.21-CalibUI1-verification.ru.md) | [中文 / оригинал](../microduck-hd1910/training-console/docs/R1.5.21-CalibUI1-verification.ru.md) |

## Обзор и история проекта

| Документ | Исходник |
| --- | --- |
| [От новичка к создателю: путь автора в проекте Microduck](AUTHOR-JOURNEY.ru.md) | [English](AUTHOR-JOURNEY.ru.md) · [中文 / оригинал](AUTHOR-JOURNEY.ru.md) |
| [Документация Microduck на русском](README.ru.md) | [English](README.ru.md) · [中文 / оригинал](README.ru.md) |

---

[Главная страница проекта](../README.ru.md) · [Русское руководство в браузере](guides/ru.html)
