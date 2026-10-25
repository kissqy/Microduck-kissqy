[Оригинал](CONTRIBUTING.md) | **Русский**

<a id="contributing"></a>
# Участие в разработке

Для работы над самими службами. Если вы хотите пользоваться роботом, а не менять его, см. [README](README.ru.md).

<a id="building-and-testing"></a>
## Сборка и тестирование

Требуется Rust **1.99+** (stable). Робот использует aarch64 Linux; разработка ведётся на Linux или macOS, и поведение сборки немного различается, как описано ниже.

```bash
cargo test --workspace
```

Без оборудования, сети и Docker. Если тесты проходят, рабочая копия исправна.

**На Linux** сначала нужны C-библиотеки, устанавливаемые и в CI: `padd` обращается к `libudev` через `gilrs`, а конвейер `mediad` имеет `cfg(target_os = "linux")`, поэтому Linux собирает GStreamer, в отличие от Mac.

```bash
sudo apt-get install -y libudev-dev libgstreamer1.0-dev
```

```bash
sudo apt-get install -y libgstreamer-plugins-base1.0-dev libgstreamer-plugins-bad1.0-dev
```

**На macOS** достаточно команды выше: **942 проходящих теста** без исключений. Два теста самого драйвера ToF там не запускаются, поскольку драйвера нет: `vendor/platform.c` работает с шиной через `linux/i2c.h`; `build.rs` собирает его только для Linux, а `sensor.rs` предоставляет `Sensor`, который нельзя открыть. `tofd` всё же собирается, `tofd --fake` отдаёт кадры — единственный способ работы вне платы.

Эти тесты покрывают и ошибки механизма: плохую подпись, нездоровый выпуск, отказ post-install hook, потерю питания между переключением и контролем здоровья. Каждый внедряет сбой в настоящий механизм, а не его имитацию; поэтому `updater/tests/apply.rs` точнее ручных проверок отвечает, что именно гарантируется.

Один crate за раз и форматирование:

```bash
cargo test -p <crate>
```

```bash
cargo fmt --all
```

Клиент NetworkManager в `configd` и BlueZ в `btd` работают **только на Linux**. Успешная сборка и тесты хоста о них ничего не говорят. Выполняйте lint для целевой платы, иначе ошибка попадёт в выпуск:

```bash
RUSTFLAGS="-D warnings" cargo clippy -p configd --all-targets --target aarch64-unknown-linux-gnu
```

`scripts/board-test.sh` в CI кросс-собирает для платы и исполняет 60 проверок на поставляемой пользовательской системе Debian 13 (Trixie): откат, отказ подменённому артефакту, восстановление по счётчику загрузок, режимы сокетов, авторизация по учётным данным процесса, действия `setup-board.sh` и `install.sh`. `BOARD_IMAGES=` выбирает другую систему.

Для запуска изменения на роботе без публикации `scripts/dev-push.sh <user@board>` собирает здесь и устанавливает там как обычное обновление с проверкой здоровья. По умолчанию используется `cargo zigbuild`; `--docker` собирает в пользовательской системе платы без локальной настройки toolchain. Подготовка, флаги и ошибки: [`docs/robot/dev-push.md`](docs/robot/dev-push.ru.md).

<a id="the-layout"></a>
## Структура

```
the daemons — one crate each, one unit each, all in the same release artifact
  robotd/         control daemon: the 50 Hz loop, the voice, the theremin, the chorale
  updater/        engine + updaterd
  configd/        wifi · robot name · pairing PIN · reboot · gamepad pairing
  btd/            the BLE front door
  padd/           gamepad → intents — an ordinary socket client, no privileged access
  mediad/         camera, mic, WebRTC, the remote gateway, and the console it serves
  tof/            tofd: the head's 8×8 depth sensor. Publishes frames, reads nothing

the libraries they drive — no sockets, no systemd, nothing starts them
  duck-ipc-proto/ the wire contract
  duck-control/   the control core: model · bus · IMU · observations · policy · safety
  kinematics/     the MJCF model and forward kinematics; head and hand chains
  odometry/       where the robot has been, from foot contacts and the IMU
  sounds/         synthesis, per-robot voice personality, the chorale's score
  pet-detect/     a small CNN that hears head scratches on the onboard mic
  robotd-params/  robotd's startup parameters: schema, defaults, validation

the tools
  robotctl/       the local CLI, including `monitor`
  duckctl/        the laptop-side client — never shipped, never cross-built
  xtask/          package · sign · promote — build tooling, never shipped
  test-support/   signed-release fixtures for tests; never shipped

deploy/         what a robot is configured with: updater.toml, robotd.toml, trust anchor, journald
hooks/          preinstall · postinstall — what runs inside an update, from the artifact,
                and the only thing that runs on every board on every update: anything
                install.sh does to a board belongs here too (updater-design.md §9.1)
scripts/        provision-board.sh · dev-push.sh + dev-build.Dockerfile (from your machine) ·
                provision.sh → setup-board.sh → setup-gstreamer.sh · setup-rkaiq.sh ·
                migrate-network.sh · install.sh (on the board) ·
                setup-login.sh · setup-quiet-boot.sh (install.sh and postinstall both run these) ·
                robot-boot-check · robot-rescue (recovery, installed to /usr/local/sbin) ·
                pad-link-test.sh · pad-stack-report.sh (gamepad radio, on the board) ·
                board-test.sh · systemd-test.sh (CI) · cross-sysroot.sh (cross-builds) ·
                bake-duck-mesh.py (the monitor's 3D model, run by hand)
docs/           robot/ (using one) · design/ (how it works) · project/ (roadmap, records) ·
                ideas/ (not designed yet)
```

Службы взаимодействуют по unix-сокетам: JSON-RPC 2.0, один объект на строку. Контракт находится в `duck-ipc-proto`, зависящем только от serde и semver; поэтому `btd` и `robotd` не наследуют дерево http/tar/crypto обновлятора.

[`docs/design/architecture.md`](docs/design/architecture.ru.md), §1, объясняет назначение и отдельный процесс каждой службы. [`docs/project/roadmap.md`](docs/project/roadmap.ru.md) описывает фактическую готовность на момент записи.

<a id="conventions"></a>
## Соглашения

- **Комментарии объясняют причины, а не действия.** Обоснование решения переживает сам код.
- **Каждое неочевидное решение сопровождается тестом**, комментарий которого называет предотвращаемый сбой. Особенно откаты: они выполняются после другой ошибки и легче всего ломаются незаметно.
- **Сначала ищите существующий crate**, а не пишите свой. Оптимизируется удобство поддержки, не количество зависимостей.
- Для помощи ИИ trailer коммита — `Assisted-by:`, не `Co-Authored-By:`.

<a id="media-in-the-readme"></a>
## Медиа в README

Видео и главное изображение — **вложения GitHub, а не файлы репозитория**. Перетащите ролик в поле комментария issue или PR, чтобы получить `https://github.com/user-attachments/assets/<id>`. Нечего коммитить и синхронизировать; в клоне файлов тоже нет, поэтому без сети эти блоки пусты.

Внутри `<table>` README URL должен быть в элементе: Markdown не разбирается в блочном HTML, голая ссылка останется текстом:

```html
<video src="https://github.com/user-attachments/assets/<id>" controls width="100%"></video>
```

**Видео не может автоматически запускаться или повторяться.** Это проверено самим renderer (`POST https://api.github.com/markdown`): из `src autoplay muted loop controls playsinline preload poster width` очистку переживают только `src`, `muted`, `controls`, `width`. Видео ждёт нажатия. Автоматически движется лишь анимированное изображение — GIF или гораздо меньший WebP:

```bash
ffmpeg -i clip.mp4 -vf "fps=15,scale=560:-1:flags=lanczos" -loop 0 -q:v 55 walk.webp
```

Две-три секунды как движущаяся миниатюра. Видео используйте, когда важны звук или длительность.

<a id="releasing"></a>
## Выпуски

Выпуски подписываются **в CI**, не локально. Точка входа — страница GitHub Releases; действие определяет тег:

| Что создаётся | Действия CI |
|---|---|
| **Предварительный выпуск** с `daemon-staging-v0.4.0` | Сборка, подпись, проверка настоящим механизмом, публикация в **staging** |
| **Выпуск** с `daemon-v0.4.0` | **Продвижение** существующего staging 0.4.0 с теми же байтами и новой подписью либо прямая сборка 0.4.0 |

Отправка любого тега из терминала даёт тот же результат:

```bash
git tag daemon-staging-v0.4.0 && git push --tags
```

Двухшаговый путь намерен: предварительный выпуск, установка на робот, затем выпуск. Создать выпуск без staging допустимо; примечания явно говорят, что он проверен CI, но не роботом.

Сначала повысьте версию workspace. `xtask package` отвергает тег, не совпадающий с `Cargo.toml`, предотвращая ложный отчёт робота о версии.

`gh workflow run promote --field version=0.4.0` выполняет то же продвижение без предварительного создания выпуска; здесь задаётся `min_supported`.

[`docs/project/ci-setup.md`](docs/project/ci-setup.ru.md) описывает хранение ключей, секреты и смену ключа.
