[English](README.en.md) | [简体中文](README.md) | **Русский**

<div align="center">

<a id="-microduck-飞特-hd1910-复刻-中文中控强化学习训练与自制硬件"></a>
<a id="-microduck-feetech-hd1910-replica-build-control-and-reinforcement-learning"></a>
# 🦆 Реплика Microduck с Feetech HD1910 · Сборка, управление и обучение с подкреплением

<a id="-microduck-飞特-hd1910-复刻--中文中控强化学习训练与自制硬件"></a>
<a id="-microduck-feetech-hd1910-replica--build-control-and-reinforcement-learning"></a>
Личный проект работающей реплики Pollen Robotics Microduck. Здесь собраны **образ системы для Radxa ZERO 3W, прошивка для Feetech HD1910, китайские консоли управления и обучения, проекты самодельных плат HAT / IMU и полный комплект файлов для 3D-печати**, необходимые для сборки, эксплуатации и обучения двуногого робота-утки.

**Стабильный опубликованный выпуск: V167 / control.43 · Автор: kissqy**

[🚀 Полное руководство по сборке](docs/MICRODUCK-BUILD-GUIDE.ru.md) · [❓ Частые вопросы](docs/MICRODUCK-FAQ.ru.md) · [🌐 Читать руководства онлайн](https://kissqy.github.io/Microduck-kissqy/guides/ru.html)

**Готовый образ для ZERO 3W · Официальный Microduck 0.15.1 · Поддержка Feetech HD1910 · Две консоли с китайским интерфейсом**

**Версии: Robot Console R17 V167 · Прошивка control.43 · Training Studio R1.5.27 · Настройка Wi-Fi при первом запуске R5**

[🦆 **Список покупок для робота**](DUCK-SHOPPING-LIST.ru.md) · [🖨️ **Полный комплект для печати · FrankenDuck**](hardware/3d-print-frankenduck/README.ru.md) · [📥 Загрузки](#downloads-and-versions) · [📚 Документация](docs/README.ru.md) · [🛠️ Исходники](microduck-hd1910/README.ru.md) · [🌱 Как учился автор](docs/AUTHOR-JOURNEY.ru.md)

[🎮 Онлайн-демонстрация Robot Console](https://kissqy.github.io/Microduck-kissqy/) · [🧠 Онлайн-демонстрация Training Studio](https://kissqy.github.io/Microduck-kissqy/training/)

<table align="center">
  <tr>
    <td align="center" valign="top">
      <b>💬 Группа в WeChat</b><br><br>
      <a href="docs/assets/community-wechat-qr.png"><img width="220" alt="QR-код группы сообщества в WeChat" src="docs/assets/community-wechat-qr.png" /></a><br>
      <sub>Отсканируйте в WeChat или нажмите на код, чтобы открыть исходное изображение.<br>Этот QR-код действует до 29 октября 2026 года.</sub>
    </td>
  </tr>
</table>

<a id="-看看鸭鸭的真实表现7-段视频"></a>
<a id="-see-the-duck-in-action-7-real-robot-videos"></a>
## 🎬 Утка в действии — 7 видео настоящего робота

<a id="-see-the-duck-in-action--7-real-robot-videos"></a>
<table>
<tr>
  <td width="10%"><video src="https://github.com/user-attachments/assets/0ec5b46b-1ec0-483a-a95d-3b3f307e155f" controls></video></td>
  <td width="10%"><video src="https://github.com/user-attachments/assets/71fc2c95-8499-49f6-924b-837df42814cf" controls></video></td>
  <td width="10%"><video src="https://github.com/user-attachments/assets/d09a6bfe-7a28-4266-ba90-de2b331472ad" controls></video></td>
  <td width="10%"><video src="https://github.com/user-attachments/assets/a604c0e0-af01-413f-ab00-99ccd26db8d5" controls></video></td>
  <td width="10%"><video src="https://github.com/user-attachments/assets/4508d91c-e91c-40f4-8c3e-5ca5a3f959c3" controls></video></td>
  <td width="10%"><video src="https://github.com/user-attachments/assets/fd0dfafd-dd02-4852-940c-33706c287e9d" controls></video></td>
  <td width="10%"><video src="https://github.com/user-attachments/assets/693a3272-d814-42f6-86b3-be5cb3b35b0f" controls></video></td>
</tr>
</table>

<sub>В этих роликах показан настоящий робот. Онлайн-демонстрации соответствуют интерфейсам Robot Console R17 V167 и Training Studio R1.5.27. Они используют имитационные данные, не подключаются к вашему роботу и не запускают настоящее обучение.</sub>

</div>

> ✅ **Образ Public Image R1 доступен!** Готовый образ прошёл проверку установки на чистую карту: загрузка, настройка Wi-Fi, SSH, связь с роботом и распознавание в R17. **Самостоятельно компилировать прошивку робота не требуется.**
>
> 📦 **Robot Console R17 V167 и Training Studio R1.5.27 готовы к загрузке.** Также опубликованы скомпилированная прошивка control.43 и исходники обеих консолей. Ссылки собраны в таблице ниже.

<a id="-从你要做的事情开始"></a>
<a id="-start-with-your-goal"></a>
## 🧭 Выберите свою задачу

| Задача | Куда перейти |
| --- | --- |
| Собрать Microduck с сервоприводами Feetech | [От покупки деталей до первых шагов](docs/MICRODUCK-BUILD-GUIDE.ru.md) |
| Прошить, откалибровать и запустить собранную утку | [Руководство пользователя V167](microduck-hd1910/firmware/console/USER-GUIDE.ru.md) |
| Обучить ходьбе, вставанию после падения или собственным движениям | [Training Studio R1.5.27](microduck-hd1910/training-console/USER-GUIDE.ru.md) |
| Изготовить HAT и отдельный IMU | [Проекты плат, изготовление и прошивка](hardware/README.ru.md) |
| Решить проблемы сети, перезагрузки, IMU или калибровки | [Частые вопросы и диагностика](docs/MICRODUCK-FAQ.ru.md) |

---

<a id="-不用从零配置一堆软件"></a>
<a id="-skip-the-software-setup-from-scratch"></a>
## ✨ Готовое программное окружение

Эта утка умеет **ходить, садиться, поднимать предметы, пинать мяч и делать кувырок вперёд**. С роликами можно исследовать **движение «фонариком», приседания, вращение и вставание после падения**. Для управления используется физический геймпад; для обучения собственным движениям есть отдельная Training Studio.

**Образ Public Image R1 опубликован и проверен повторной прошивкой настоящей платы.** Он объединяет официальную систему с предустановленными службами робота и моделями движений этого проекта. Запишите его на карту для Radxa ZERO 3W, подключитесь к Wi-Fi и откройте консоль — программное окружение готово без компиляции прошивки из исходников.

<a id="-三步开始"></a>
<a id="-start-in-three-steps"></a>
## 🚀 Начало работы за три шага

1. **Запишите образ** — возьмите `.img.xz` из таблицы загрузок. В [Armbian Imager](https://imager.armbian.com/) выберите собственный образ и карту microSD, затем запустите запись. **Распаковывать файл вручную не нужно:** программа делает это при записи.
2. **Подключите Wi-Fi** — при первом запуске подключитесь к точке доступа `Microduck-kissqy` с паролем `12345678`. На странице настройки укажите домашнюю сеть Wi-Fi и задайте новый пароль входа в систему. Если страница не открылась автоматически, перейдите на `http://10.42.0.1:8088`.
3. **Откройте консоль** — полностью распакуйте ZIP Robot Console и запустите `start.cmd`. Подключитесь к утке, проверьте калибровку и выполните HOME перед включением движения. Для обучения распакуйте Training Studio и запустите `start-training.cmd`.

> 🛠️ **Даже с предустановленным ПО нужна калибровка вашей сборки.** После сборки или замены сервоприводов проверьте нулевое положение, направление, ограничения каждого сустава и IMU, прежде чем разрешать движение. Не копируйте калибровку эталонной утки без проверки.

<div align="center">
  <img src="docs/assets/wifi-setup-desktop.webp" width="760" alt="Точка доступа и страница настройки Wi-Fi Microduck при первом запуске" />
  <p><sub>Пример настройки Wi-Fi при первом запуске. Фактический экран определяется версией, включённой в Public Image R1.</sub></p>
</div>

<a id="下载与版本"></a>
<a id="downloads-and-versions"></a>
## Загрузки и версии

| Пакет | Назначение | Скачать |
| --- | --- | --- |
| **Образ системы R1** · Официальная 0.15.1 / control.40 | Установка на чистую ZERO 3W; службы робота и модели движений предустановлены | [⬇️ .img.xz](https://github.com/kissqy/Microduck-kissqy/releases/download/public-image-r1/microduck-zero3w-0.15.1-R1.img.xz) |
| **Robot Console R17 V167** | Подключение к утке и управление с компьютера; содержит соответствующий пакет прошивки | [⬇️ ZIP](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Console-R17-V167.zip) |
| **Training Studio R1.5.27** | Обучение, оценка и экспорт собственных моделей | [⬇️ ZIP](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/release-assets/Microduck-Training-Studio-R1.5.27.zip) |
| **Скомпилированная прошивка Feetech HD1910 control.43** | Обновление служб ZERO в существующей системе; установочный пакет ARM64 | [⬇️ .tar.gz](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/microduck-hd1910/firmware/console/updates/Microduck-Robotd-FT6-R17.tar.gz) |
| **Прошивка IMU FT6 (STM32)** | Отдельная прошивка нового IMU корпуса; 8.2 KiB, конфигурация Feetech HD1910 | [⬇️ .bin](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/microduck-hd1910/firmware/console/updates/imu_to_feetech_ReVA_FT6_SYNC15_UART_IRQ_v1.bin) · [Инструкция](hardware/IMU-FIRMWARE.ru.md) |
| **Полный комплект для печати · FrankenDuck** | 36 файлов STL, проект 3MF с 5 столами печати, два варианта держателя аккумулятора | [⬇️ RAR](https://github.com/kissqy/Microduck-kissqy/raw/refs/heads/main/hardware/3d-print-frankenduck/Microduck-Print-FrankenDuck-20261015.rar) · [Руководство](hardware/3d-print-frankenduck/README.ru.md) |

**Для обычного использования скачайте образ системы и Robot Console.** Training Studio устанавливается по необходимости. Отдельная прошивка соответствует control.43 из комплекта V167. В образе R1 по-прежнему находится control.40; после записи образа установите прошивку из V167 для обновления. Компиляция не требуется. **Новый IMU также требует отдельного файла FT6 `.bin`: образ системы и обновления служб ZERO его не прошивают.**

[Руководство Robot Console](microduck-hd1910/firmware/console/README.ru.md) · [Руководство Training Studio](microduck-hd1910/training-console/README.ru.md) · [Установка отдельной прошивки и контрольные суммы](release-assets/README.ru.md) · [Руководство по образу системы](docs/releases/public-image-r1.ru.md)

Исходники: [прошивка](microduck-hd1910/firmware/README.ru.md) · [Robot Console](microduck-hd1910/firmware/console/README.ru.md) · [Training Studio](microduck-hd1910/training-console/README.ru.md) · [инструкция по сборке](microduck-hd1910/docs/BUILD.ru.md). Текущие исходники соответствуют V167 / control.43; дублирующиеся скомпилированные ресурсы восстанавливаются по необходимости.

**Изменение V167: исправлено дрожание корпуса.**

<a id="-两个中控各做各的事"></a>
<a id="-two-consoles-two-jobs"></a>
## 🎮 Две консоли для разных задач

| 🐣 Robot Console · R17 V167 | 🧠 Training Studio · R1.5.27 |
| --- | --- |
| Положение в 3D в реальном времени, камера, данные суставов / IMU, калибровка сервоприводов | Задачи и рецепты обучения, очередь, прогресс и графики вознаграждения |
| Управление физическим геймпадом, обслуживание прошивки, состояние моделей | Визуальная симуляция, оценка политик управления, экспорт ONNX |
| Самостоятельно компилировать службы ZERO не нужно | Требуется компьютер с окружением для обучения; сам интерфейс работает без ZERO |

**В V167 включено 10 моделей движений: 6 обычных и 4 для роликов.** Служба управления исполняет модели; вручную программировать движения сервоприводов не требуется. Движение на роликах и вставание зависят от сборки, калибровки и обучения и всё ещё требуют тщательной проверки на настоящем роботе.

**Инструкции на русском:** [Robot Console](microduck-hd1910/firmware/console/README.ru.md) · [Training Studio](microduck-hd1910/training-console/README.ru.md) · [Установка образа](docs/releases/public-image-r1.ru.md) · [Исходники и сборка](microduck-hd1910/README.ru.md). В текущих загрузках интерфейсы приложений остаются китайскими; в руководствах при необходимости приведены исходные подписи кнопок.

<a id="-鸭子全套打印件-缝合怪版"></a>
<a id="-complete-printing-set-frankenduck"></a>
## 🖨️ Полный комплект для печати · FrankenDuck

<a id="-鸭子全套打印件--缝合怪版"></a>
<a id="-complete-printing-set--frankenduck"></a>
Комплект объединяет улучшения сообщества и доработки автора, проверенные на настоящем роботе: файлы STL и пример размещения на столах печати. **Ролики устанавливаются без снятия сервоприводов.** Выберите держатель аккумулятора с зажимом HUB или вариант официального типа с утолщёнными защёлками; оба крепления IMU подходят к IMU этого репозитория. Для роликов нужны подшипники **623ZZ (3×10×4 мм)**.

[Файлы для печати, раскладка и держатели аккумулятора](hardware/3d-print-frankenduck/README.ru.md) · [Покупка 623ZZ](DUCK-SHOPPING-LIST.ru.md#optional-roller-bearings)

**Обновление печатных деталей от 21 октября:** добавлены опорные скосы на ногах для удобной установки стоп, удалены наружные углубления под головки винтов на кожухах ног, чтобы уменьшить разрушение отверстий при падениях; добавлены сменные стопы на основе официальных роликовых башмаков, которые меняются без снятия сервоприводов.

<a id="-hat-与-imu-自制记录"></a>
<a id="-diy-hat-and-imu"></a>
## 🔧 Самодельные HAT и IMU

> 🛒 **[Купить платы HAT / IMU у автора](https://item.taobao.com/item.htm?id=1095121548583)**
>
> **Обратите внимание: платы изготовлены в JLCPCB (嘉立创), монтаж компонентов выполнен автором. Они готовы к использованию; автор применяет такие же платы. По его данным, они проверены длительной работой на настоящем роботе, не требуют перемычек и не теряют пакеты. Разъёмы Feetech AMP2.0 удобны в подключении.**

🎬 **[Полное видео изготовления IMU · Bilibili](https://www.bilibili.com/video/BV1qapz6PERs/)**

По данным автора, собственная HAT и отдельный IMU корпуса прошли длительную эксплуатацию на настоящем роботе, работают нормально, известных проблем не выявлено.

**Доступны два варианта разъёмов: исходный EH2.5 и AMP2.0.** В HAT AMP2.0 установлены гнёзда HP1.25 для динамика / микрофона и добавлены зелёный светодиод и резистор 1 кОм. [Обе версии проектов](hardware/README.ru.md) · [Руководство и детали AMP2.0](hardware/AMP2.0-VERSION.ru.md)

[Загрузка и запись прошивки IMU](hardware/IMU-FIRMWARE.ru.md) · [Хронология изготовления HAT](hardware/HAT-TIMELINE.ru.md) · [Хронология изготовления IMU](hardware/IMU-TIMELINE.ru.md) · [Проекты и заметки по электронике](hardware/README.ru.md) · [🔧 Детали плат HAT / IMU](hardware/README.ru.md#shopping-list)

<a id="-分享给大家也尊重原创"></a>
<a id="-sharing-the-project-and-crediting-its-creators"></a>
## ❤️ Распространение проекта и благодарности

Это **личный учебный проект**, основанный на [официальном Microduck от Pollen Robotics](https://github.com/pollen-robotics/microduck) `0.15.1`, а не официальный выпуск. **За исключением явно обозначенных исходных и сторонних кода, моделей и ресурсов, дополнительные адаптации прошивки, консоли, инструменты, документация и результаты обучения автора разработаны автором проекта с помощью ИИ при программировании.**

**Оригинальные материалы, которыми автор владеет и которые вправе лицензировать, предоставляются только для личного обучения, исследований и некоммерческого использования. Для коммерческого использования требуется письменное разрешение автора**, в том числе для коммерческих продуктов, платных услуг или распространения вместе с продаваемыми роботами. Исходное ПО Apache-2.0, сторонние компоненты MIT, официальная геометрия и другие ресурсы сохраняют собственные лицензии; личные условия автора не отменяют права третьих лиц.

Подробности: [Лицензии компонентов](microduck-hd1910/LICENSE) · [Условия личного некоммерческого использования](microduck-hd1910/LICENSES/Personal-NonCommercial.txt) · [Сторонние источники](microduck-hd1910/docs/THIRD-PARTY.ru.md)

Этот проект вырос из одной платы, одной утки и множества отладочных сессий. Я самостоятельный разработчик, и ИИ помогал мне с частью кода. Надеюсь, эти файлы помогут вам быстрее запустить собственную утку. Буду рад звёздам ⭐, обсуждениям и отзывам.

<table align="center">
  <tr>
    <td align="center" valign="top" width="50%">
      <b>❤️ Поддержать автора</b><br><br>
      <img width="180" alt="QR-код для поддержки автора" src="https://github.com/user-attachments/assets/49054608-65ba-41d6-b3f1-a97941976c4b" />
    </td>
    <td align="center" valign="top" width="50%">
      <b>🛒 Купить собранного робота</b><br><br>
      <a href="docs/assets/purchase-wechat-qr.jpg"><img width="220" alt="Контактный QR-код WeChat для покупки готового робота" src="docs/assets/purchase-wechat-qr.jpg" /></a><br>
      <sub>Отсканируйте в WeChat, чтобы узнать о покупке собранного робота.<br>Нажмите на QR-код для просмотра исходного изображения.</sub>
    </td>
  </tr>
</table>
