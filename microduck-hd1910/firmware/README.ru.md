[English](README.en.md) | [简体中文](README.md) | **Русский**

> **Отдельная прошивка IMU FT6 (STM32):** [загрузка, подключение и запись](../../hardware/IMU-FIRMWARE.ru.md) · [исходники](firmware/imu-source/README.ru.md). Пакет control.43 ниже устанавливается на ZERO; IMU программируется отдельно через ST-LINK.

> **Скомпилированная прошивка HD1910:** control.43 — готовый установочный пакет AArch64. См. [загрузку и установку](../../release-assets/README.ru.md); компиляция исходников необязательна.

> **Текущие опубликованные исходники: Microduck 0.15.1 / HD1910 control.43 для R17 V167.** V167 используется вместе с control.43. Изменение: исправлено дрожание корпуса.

<p align="center">
  <img src="https://github.com/user-attachments/assets/c2f7c245-8217-46a1-8d1e-e0ba967cd969" alt="Робот Microduck" width="820">
</p>

<h1 align="center">Microduck</h1>

<p align="center">
  <em>Маленький двуногий робот, двигающийся с помощью политик управления, обученных с подкреплением.</em>
</p>

<p align="center">
  <a href="https://pollen-robotics.com/microduck"><b>Приобрести робота</b></a> ·
  <a href="docs/robot/cheatsheet.ru.md">Шпаргалка</a> ·
  <a href="https://github.com/pollen-robotics/microduck_rl">Обучение политик</a> ·
  <a href="docs/design/architecture.ru.md">Как устроен</a> ·
  <a href="CONTRIBUTING.ru.md">Участие в разработке</a>
</p>

<p align="center">
  <a href="https://github.com/pollen-robotics/microduck/actions/workflows/ci.yml"><img src="https://github.com/pollen-robotics/microduck/actions/workflows/ci.yml/badge.svg" alt="Статус CI upstream"></a>
</p>

---

**Этот репозиторий — мозг утки.** Робот высотой около 25 см и массой 800 г управляется несколькими службами Rockchip RK3566: цикл 50 Гц ведёт пятнадцать сервоприводов нейросетевыми политиками; работают радио, камера и механизм обновлений, доставляющий новое ПО без превращения робота в «кирпич».

Здесь есть всё для работы Microduck. **Хотите такого — [приобрести можно здесь](https://pollen-robotics.com/microduck).**

Политики обучаются в соседнем **[microduck_rl](https://github.com/pollen-robotics/microduck_rl)**: MuJoCo, PPO, перенос из симуляции в реальность и экспорт ONNX, загружаемого этим репозиторием.

> Примечание переводчика: далее сохранён обзор официального проекта upstream. Сведения именно о реплике HD1910 и её лицензиях находятся на [главной странице реплики](../../README.ru.md) и в [описании версий выпуска](../docs/BASELINE.ru.md).

<a id="it-does-things"></a>
## Что умеет робот

<table>
<tr>
<td width="50%">
  <video src="https://github.com/user-attachments/assets/356a6011-8e0d-4b28-bda9-da78646583a3" controls width="100%"></video>
</td>
<td width="50%">
  <video src="https://github.com/user-attachments/assets/abfbf250-1b1c-42cb-8430-00267e2b148a" controls width="100%"></video>
</td>
</tr>
<tr>
<td><b>Ходит.</b> Возьмите геймпад и управляйте.</td>
<td><b>Ездит на роликах.</b> Установите колёса, удерживайте стрелку вверх на D-pad — загрузится другая модель управления.</td>
</tr>
<tr>
<td width="50%">
  <video src="https://github.com/user-attachments/assets/7e70c1da-e120-428f-ae0b-f4de62f25984" controls width="100%"></video>
</td>
<td width="50%">
  <video src="https://github.com/user-attachments/assets/3eef63a5-6f84-47cf-90de-e717e6d7f8f0" controls width="100%"></video>
</td>
</tr>
<tr>
<td><b>Поднимает предметы.</b> Клюв к полу, одна кнопка.</td>
<td><b>Встаёт обратно.</b> После падения поднимается самостоятельно.</td>
</tr>
</table>

Также садится, пинает мяч, делает кувырок вперёд по команде и крякает собственным голосом.

<a id="where-to-find-things"></a>
## Где что искать

<a id="you-have-a-duck"></a>
### Если у вас есть утка

| | |
|---|---|
| [Шпаргалка](docs/robot/cheatsheet.ru.md) | Все команды `robotctl`: движение, настройка, голос, хор, терменвокс, Wi-Fi, обновления, журналы. Начните здесь. |
| [Геймпад](docs/robot/cheatsheet.ru.md#gamepad-configd) | Полная раскладка кнопок, сопряжение [один раз на геймпад](docs/robot/pair-a-gamepad.ru.md) и действия при отказе создания пары. |
| [`duckctl`](docs/robot/duckctl.ru.md) | Управление с ноутбука по Bluetooth без сети и SSH. |
| [Обновления](docs/robot/cheatsheet.ru.md#updates-updaterd) | Установка, откат, закрепление версии. Каждое обновление проверено, проходит контроль здоровья и обратимо. |

<a id="you-are-building-on-it"></a>
### Если вы разрабатываете на этой платформе

| | |
|---|---|
| [microduck_rl](https://github.com/pollen-robotics/microduck_rl) | Обучение политик: MuJoCo, PPO, рандомизация параметров среды и экспорт ONNX. |
| [Устройство системы](docs/design/architecture.ru.md) | Вся система на странице: службы, шина, доставка обновления, далее отдельная страница на часть. |
| [Подготовка платы разработки](docs/robot/install-dev.ru.md) | От пустой платы до робота, принимающего сборки веток. |
| [Шпаргалка разработчика](docs/robot/cheatsheet-dev.ru.md) | Ветки, кандидаты выпуска, управление с ноутбука и ловушки перезапуска после обновления. |
| [Отправка своей ветки](docs/robot/dev-push.ru.md) | Сборка на компьютере, установка по SSH примерно за минуту. |
| [Утка в симуляции](docs/robot/simulation.ru.md) | Нет робота? `scripts/duck-sim` запускает настоящие службы с телом MuJoCo: одну утку в окне или четыре как машины для входа. |
| [Участие в разработке](CONTRIBUTING.ru.md) | Сборка, тестирование, структура, соглашения, выпуски. |
| [Каталог документации](docs/README.ru.md) | Всё, включая проектные страницы и открытые вопросы. |

<a id="under-the-hood"></a>
## Внутреннее устройство

Rust, без фреймворка, единый workspace. `robotd` владеет циклом управления и шиной моторов; `updaterd` ставит подписанные выпуски и откатывает нездоровые; `configd` отвечает за Wi-Fi и идентичность; `btd` — Bluetooth-путь телефона; `padd` читает геймпад; `mediad` передаёт камеру через WebRTC; `tofd` обслуживает глубину. Общий контракт JSON-RPC проходит через Unix-сокеты; каждый клиент — приложение, консоль, геймпад, ваш скрипт — отправляет ровно те же вызовы.

Существенные решения записаны: [`docs/design/`](docs/design/) объясняет причины устройства системы, [`docs/project/`](docs/project/) — что ломалось и как это закрыть.

<a id="a-note-on-ducks"></a>
## Несколько слов об утках

При создании этого робота ни одна утка не пострадала. С несколькими проконсультировались.
