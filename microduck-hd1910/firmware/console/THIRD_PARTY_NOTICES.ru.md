[English](THIRD_PARTY_NOTICES.en.md) | [简体中文](THIRD_PARTY_NOTICES.md) | **Русский**

Базовая среда R17 v1.0.97: Pollen Robotics microduck 0.15.1 / `1fa84386f07884e27866411bc1ba166977bced95`, Apache-2.0. Изменения исходников перечислены в `OFFICIAL-CHANGES.zh-CN.md` полного исходного пакета; лицензия: `licenses/MICRODUCK-APACHE-2.0.txt`.

Ранние записи об авторстве геометрии утки R17, Three.js, STLLoader и тренировочных моделей сохранены ниже. Лицензия ПО не меняет лицензирование весов, обученных пользователем. Лицензия ONNX Runtime 1.28.0 и ThirdPartyNotices находятся в каталоге `onnxruntime` пакета службы.

<a id="本次音源与手柄来源"></a>
<a id="sound-and-gamepad-sources"></a>
# Источники звука и управления геймпадом

`audio/generator/{rng,personality,synth,voices}.rs` без изменений взяты из закреплённого коммита Pollen Robotics microduck `590b986bd8c0d50ae02cb3ea2f59c463b6828168`, Apache-2.0; см. `licenses/MICRODUCK-APACHE-2.0.txt`. Добавленные WAV сгенерированы этими модулями; main.rs пакета оборачивает запись WAV. Раскладка геймпада происходит из `padd/src/main.rs` того же официального коммита.

<a id="第三方来源版本与许可"></a>
<a id="third-party-sources-versions-and-licenses"></a>
# Сторонние источники, версии и лицензии

Этот независимый инструмент наблюдения и ручного управления не является официальным выпуском Pollen Robotics и не подразумевает одобрения официальным проектом или сообществом. Компоненты и ресурсы сохраняют собственные лицензии; Apache/MIT для ПО не заменяют лицензий моделей.

<a id="官方运行时协议和模型"></a>
<a id="official-runtime-protocol-and-model"></a>
## Официальная среда выполнения, протокол и модель

- Источник: [pollen-robotics / microduck, закреплённый 590b986](https://github.com/pollen-robotics/microduck/tree/590b986bd8c0d50ae02cb3ea2f59c463b6828168).
- Полный коммит: `590b986bd8c0d50ae02cb3ea2f59c463b6828168`; версия ПО workspace `0.10.0`.
- Протокол: `duck-ipc-proto/src/lib.rs`, `robotd/src/main.rs`, `tof/src/main.rs`, `mediad/webclient/`.
- Кинематика/модель: `robotctl/src/duck.rs`, `scripts/bake-duck-mesh.py`, `duck-control/src/model.rs`.
- Единицы IMU/сервоприводов: `duck-control/src/imu.rs`, `duck-control/src/bus.rs`, официальная документация ROBOTIS.
- ПО upstream: Apache-2.0, полный текст в `licenses/MICRODUCK-APACHE-2.0.txt`.

<a id="鸭子几何模型单独许可"></a>
<a id="duck-geometry-separately-licensed"></a>
### Геометрия утки — отдельное лицензирование

<a id="duck-geometry--separately-licensed"></a>
Модели и конструкции принадлежат Pollen Robotics и участникам upstream.

Отображаемый `static/assets/duck-visual.bin` преобразован из оригинальных STL/MJCF [официального коммита microduck_rl e8a2de5](https://github.com/pollen-robotics/microduck_rl/tree/e8a2de510b6cb5062e9ccab8b41f2d47f2186504/src/mjlab_microduck/robot/microduck) без уменьшения геометрии. Нормали используют порог жёсткого ребра 35°, скрытие внутренней электроники upstream сохранено. Используется зафиксированное дерево суставов runtime; визуальные элементы правой лодыжки преобразованы в зафиксированные координаты; клюв неподвижен. Генерация — комплектный `tools/bake_visual.py`; хеши входов/выходов — `static/assets/duck-visual.json`. Производная сохраняет требования атрибуции, некоммерческого использования и распространения на тех же условиях.

`static/assets/duck.bin` без изменений скопирован из зафиксированного `robotctl/assets/duck.bin` только для проверки эталонной кинематики.

SHA256:

```text
1e1200053e2326706632306bc80831d5e0dfa5462d792a677fc05a43f145651e
```

Зафиксированный скрипт преобразования указывает геометрию Microduck MJCF/STL. [README upstream об обучении/моделях](https://github.com/pollen-robotics/microduck_rl#license) отдельно заявляет Creative Commons BY-SA-NC для 3D-моделей. Атрибуция, некоммерческое использование и share-alike сохранены. Версия CC не указана; пакет не выдумывает её и не заявляет Apache-2.0 для геометрии. См. `licenses/MODEL-NOTICE.md`. Личная отладка робота не даёт дополнительных коммерческих прав.

## three.js 0.180.0

- Upstream: [mrdoob / three.js r180](https://github.com/mrdoob/three.js/tree/r180).
- Файлы: `static/vendor/three.module.min.js`, `three.core.min.js`, `OrbitControls.js`.
- Copyright ©2010–2025, авторы three.js; полный MIT: `licenses/THREE-MIT.txt`.
- Из официального npm `three@0.180.0`; единственная адаптация заменяет bare import OrbitControls локальным `./three.module.min.js` для офлайн-работы.

<a id="参考但不捆绑的社区项目"></a>
<a id="referenced-community-projects-not-bundled"></a>
## Изученные проекты сообщества, не включённые в пакет

- [microai-lab / microduck-studio](https://github.com/microai-lab/microduck-studio), рассмотрен на `4ad606d58b44d1708296a3b9d699e458388b9c7f`: повлиял на совместное отображение 3D, датчиков, актуаторов. Реализация и данные MuJoCo не включены.
- [7757/fanduck](https://github.com/7757/fanduck): изучены рабочее окружение образа и публичное объяснение лицензий моделей. Приложение и производные модели не включены. Полные визуальные поверхности взяты напрямую из официального закреплённого RL-коммита выше.

<a id="开发测试依赖"></a>
<a id="development-test-dependencies"></a>
## Зависимости тестирования разработки

DOM-тесты используют jsdom 26.1.0, браузерные регрессии — Playwright. Они не поставляются и не требуются для запуска консоли. При установке зависимостей разработки сохраняйте лицензии upstream.

CPU-тесты ONNX используют ONNX, ONNX Runtime, NumPy и создают маленькие математические модели во временных каталогах, удаляя их после проверки; это не веса обучения робота. Браузерные тесты используют явно имитационные состояния для проверки страницы и запросов управления, а не приёмку GPU-физики.

Ключи робота, SSH known_hosts, личная конфигурация и изображения камеры пользователя не включены.

<a id="官方鸭叫变体"></a>
<a id="official-chirp-variants"></a>
## Официальные варианты кряканья

`audio/chirp/chirp_a.wav` — `chirp_l.wav` сгенерированы синтезатором sounds 0.10.0 из официального 590b986, seed 590986, варианты 0–11; 48 кГц, 16 бит, моно. Они дают ручной резерв звука, если на ZERO нет звуковой библиотеки; существующие библиотеки приоритетнее. Исходники и рецепты — официальный Apache-2.0, см. `licenses/MICRODUCK-APACHE-2.0.txt`.

<a id="official-pad-expressions-v1062"></a>
## Официальные pad-expressions (v1.0.62)

Источник: <https://github.com/pollen-robotics/microduck/tree/5492ea602e3aef59b2a19d702977aab2da2cd88e>

<a id="pyyaml603"></a>
## PyYAML 6.0.3

Чистый Python-разбор текста в `_model_yaml/` пакета службы R17. Полный MIT — `_model_yaml/LICENSE`. BaseLoader читает экспортированные параметры обучения, не загружая Python-объекты или checkpoints.
