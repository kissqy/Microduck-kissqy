[English](official-roller-audit.en.md) | [简体中文](official-roller-audit.zh-CN.md) | **Русский**

# Аудит официальных параметров шести семейств роликов (7 октября 2026 года)
<a id="官方轮滑六族参数审计2026-10-07"></a>
<a id="official-six-family-roller-parameter-audit-october-7-2026"></a>

Сравнение только для чтения закреплённого `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec` и develop на момент аудита `273afe0b31c4ab365b9ff806a927b63ac92b5ddd`. Шесть env_cfg, реестр, обёртка люфта, константы и два XML роликов побайтово идентичны. Изменения общего mdp не меняют включённое здесь поведение. JSON содержит фактическую конфигурацию фабрики для обучения / просмотра; короткие тесты — в smoke-frozen.json.

## Регистрации и интерфейс действий
<a id="真实注册与动作接口"></a>
<a id="registrations-and-action-interface"></a>

| Семейство | Базовая регистрация | Регистрация Backlash | Rough | Фактическая команда |
| --- | --- | --- | --- | --- |
| RollersVelocity | `Mjlab-Velocity-Flat-MicroDuck-Rollers` | `Mjlab-Velocity-Flat-Backlash-MicroDuck-Rollers` | Нет | twist x положительный=отталкивание, ноль=качение по инерции, отрицательный=торможение; x[-0.5, 0.6], y=0; ошибка курса z ограничена нулём, поворот не обучается. 4 поля головы / 6 корпуса заполнены точными нулями. |
| Swizzle | `Mjlab-Velocity-Swizzle-MicroDuck` | `Mjlab-Velocity-Swizzle-Backlash-MicroDuck` | Нет | twist x[-.6,.6] положительный=отталкивание вперёд, отрицательный=назад (НЕ торможение), y=0, ошибка курса z±.5. 4 поля головы — текущие отклонения от HOME, 6 корпуса — точные нули. |
| RollerCrouch | `Mjlab-RollerCrouch-Flat-MicroDuck` | `Mjlab-RollerCrouch-Flat-Backlash-MicroDuck` | Нет | twist=[cos(2πphase), sin(2πphase), 0], период 5 s, фаза сброса 0; 4 поля головы / 6 корпуса — точные нули. |
| RollerSlope | `Mjlab-RollerSlope-Flat-MicroDuck` | `Mjlab-RollerSlope-Flat-Backlash-MicroDuck` | Нет | Все twist=0, доля стояния 1; 4 поля головы / 6 корпуса — точные нули. |
| RollerStandUp | `Mjlab-RollerStandUp-Flat-MicroDuck` | Нет | Нет | VelocityCommandCommandOnly twist x, y±.01, z±.05; повторный выбор 6–12 s; 4 поля головы / 6 корпуса — точные нули. |
| Spin | `Mjlab-Spin-Flat-MicroDuck` | Нет | Нет | twist=[cos(2πphase), sin(2πphase), 0], период 4 s, фаза сброса 0; 4 поля головы / 6 корпуса — точные нули. |

## Общая физика и выборка
<a id="共享真实物理-采样"></a>
<a id="shared-physics-and-sampling"></a>
<a id="共享真实物理--采样"></a>

- Управление 50 Hz, шаг MuJoCo 0.005 s, decimation 4; 14-мерный JointPositionAction, scale 1, смещение HOME, без EMA / явного ограничения действия. Upstream XL330 BAM M6/P200 отличается от XML kp 0.55 и пользовательского HD1910.
- Задержка привода 3–6 физических шагов =15–30 ms; IMU 0–1 шаг управления, обновление каждые 64 шага; скорость суставов 1 шаг. actor 61 = gyro 3 + gravity 3 + jointpos 14 + jointvel 14 + lastaction 14 + twist 3 + head 4 + body 6.
- Четыре пассивных колеса перемежаются с 14 сервоприводами без действий колёс. Четыре сетки шин сохраняют значения XML; entity collisions=(). Скомпилированные condim 3/friction [1, 0.005, 0.0001] поддерживают нормальные / скользящие ограничения, а не доказывают обучение трения кручения / качения.
- Все шесть удаляют foot_friction без DR geom_friction. dof_frictionloss оси — сопротивление подшипника, отличное от коэффициентов поверхности. Большинство диапазонов курса колёс имеют одинаковые границы и детерминированы для стадии.
- Напряжение при запуске 6.5–8.2 V, коэффициент просадки 0–0.2, минимум 6 V; сброс трения / armature BAM 0.9–1.1; энкодер при запуске ±0.015 rad; фиксированное для каждой среды крепление IMU ≤6°; alpha псевдоинерции туловища [log(.95)/2, log(1.05)/2]. Центр масс ±3→±5→±10 mm; Slope удаляет этот курс и остаётся на ±3 mm.
- Стандартный эпизод 20 s, RollerStandUp 6 s. Обычные роликовые задачи завершаются при наклоне 70°; Slope — 1 rad и уход в пустоту; RollerStandUp удаляет fell_over. Все сохраняют завершение по NaN.

## Курсы, сброс и просмотр семейств
<a id="各族实际课程reset及-play差别"></a>
<a id="family-curricula-reset-and-play"></a>

### RollersVelocity

Исходное свидетельство: `/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_rollers_env_cfg.py`: 85

- Рельеф: плоскость.
- Основные награды: wheel_speed 10, glide 4, single_support 3, skating_air_time 1.5, heading_hold 1; upright 2/pose 2; action_rate начальный −1→−1.5@250→−2@500.
- Просмотр: аргумент play фабрикой не используется; весь шум / DR / курсы обучения сохранены.
- Курс трения оси колеса (итерация, значение): [[0, 0.0], [2000, 0.0005], [3500, 0.001], [5000, 0.0015]].

### Swizzle

Исходное свидетельство: `/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_swizzle_env_cfg.py`: 34

- Рельеф: плоскость.
- Основные награды: убраны шаговые single_support / glide / skating_air_time / gait_symmetry / hip_roll_neutral; добавлены leg_symmetry 2 и grounded 1; удалены торможение и штраф HOME шеи; pose только для ног; heading_hold 1→0, а heading_tracking 0→3 к 2500; head_tracking 0→4 к 3000.
- Просмотр: отдельной ветки нет; шум / DR / курсы обучения сохранены.

### RollerCrouch

Исходное свидетельство: `/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_crouch_env_cfg.py`: 116

- Рельеф: плоскость.
- Сброс: суставы HOME и скорость основания вперёд .2–.5 m / s; смещение z основания .1335–.1435 относительно корня по умолчанию. Начальные скорости колёс НЕ синхронизируются с поступательной скоростью.
- Основные награды: именованные измеренные цели суставов стоя / в приседе: gaussian 6 std .4 + самостоятельно меняющий знак штраф L1 с весом +2; сохранение скорости вперёд 1; наклон вперёд в приседе 1 при .08 rad; upright 2; график плавности −.5/−.8/−1.
- Просмотр: аргумент play не используется; шум / DR / курсы сохранены.
- Статическая проблема: нет явного стартового события expand_bam_friction_fields. Реальный сброс + 2 шага в 2 мирах пройдены: событие трения колёс расширяет dof_frictionloss; damping при записи BAM — постоянный скаляр. Это не доказанный сбой выполнения.
- Курс трения оси колеса (итерация, значение): [[0, 0]].

### RollerSlope

Исходное свидетельство: `/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_slope_env_cfg.py`: 66

- Рельеф: генератор, несмотря на Flat в имени реестра: 10 строк × 1 столбец, плитки 15 m × 4 m; 2 m плоскости + 3–8 m случайной горизонтальной длины спуска + 4 m выката; угол 2°→20° по уровню; старт на .3 m от начала рампы.
- Сброс: yaw 0; очищается унаследованная скорость основания; reset_rolling_entry применяет согласованную скорость качения основания + колёс .25–.45 m / s.
- Основные награды: upright 3 (std .2), alive 1, wheel_glide 2 (предел .35 m / s), heading_hold 1.5, feet_flat −2, neck_action_rate −.5, neck_joint_pos −.75, torques −.001, action_rate −1.
- Курс: удаляет ВСЕ унаследованные курсы, включая нарастание трения колёс и смещения центра масс; оставляет только terrain_levels_slope. Повышение при расстоянии >0.4×15=6 m; понижение при <0.2×15=3 m.
- Просмотр: стандартный max_init_terrain_level=None допускает все строки; необязательный SLOPE_PLAY_DIFFICULTY фиксирует сложность 0–1; унаследованные шум / DR сохраняются; курс рельефа сохраняется.
- Курс трения оси колеса (итерация, значение): [[0, 0]].

### RollerStandUp

Исходное свидетельство: `/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_standup_env_cfg.py`: 135

- Рельеф: плоскость.
- Сброс: событие состояния на земле выполняется последним; z на животе / спине .076–.09, стоя .134–.144; наклон стоя ±10°; категории сидения нет.
- Основные награды: HOME ног 8 + L1 с весом 5; цель высоты .138 m gaussian 4 (std .04)+4 (std .015)+L1 с весом 30; скорость вверх 3; upright linear 6/sharp 6; мультипликативная составная награда 15; gentle_rise +.02 (самостоятельно отрицательная); torque_rate −.2. action_rate настроен −.6, после применения стадии курса −.4/−.8/−1.
- Просмотр: необязательный STANDUP_PLAY_FACE_UP фиксирует вероятность спины и удаляет только ground_state_mix; без него по умолчанию стадия курса 0 (0% спины). Остальные DR / шум / курсы сохранены, включая высокое начальное сопротивление колёс.
- Статическая проблема: _LEG_JOINTS=[0, 1, 2, 3, 4, 11, 12, 13, 14, 15] — исходные индексы 18 слотов, но pose_target_match, pose_l1_penalty, standing_composite_score теперь индексируют 14-мерные представления сервоприводов. 14/15 выходят за границы.
- Курс трения оси колеса (итерация, значение): [[0, 0.05], [1000, 0.02], [2000, 0.008], [3000, 0.003], [4000, 0.0015]].

### Spin

Исходное свидетельство: `/workspace/scratch/9f94b8b8f4de/training-actions-update/analysis/official-sources/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_spin_env_cfg.py`: 87

- Рельеф: плоскость.
- Сброс: суставы HOME; скорость основания вперёд 0–.3 m / s; начальные скорости колёс не обновляются согласованно.
- Основные награды: yaw rate gaussian 6 (std 1.5)+L1 с весом +.5; дрейф положения −3 с коэффициентом запуска .2; differential wheel 1; legantisym 1→.5@1500→.25@3000; grounded .5; сохраняет upright 2 и штраф угловой скорости roll / pitch −.05; намеренно удаляет angular_momentum; head_yaw не удерживается в HOME.
- Просмотр: аргумент play не используется; шум / DR / курсы обучения сохранены.
- Статическая проблема: нет явного стартового события expand_bam_friction_fields; реальный сброс + 2 шага в 2 мирах пройдены. Селектор пассивных колёс ^passive_.* широк, но регистрация SpinBacklash сейчас отсутствует.
- Курс трения оси колеса (итерация, значение): [[0, 0]].

## Проблемы исходников, требующие проверки короткими шагами
<a id="需要短步核验的明确源码问题"></a>
<a id="source-issues-requiring-short-step-checks"></a>

1. RollerStandUp _LEG_JOINTS использует 18 слотов, включая 14/15, но pose_target_match / pose_l1_penalty / standing_composite_score сначала выбирают 14-мерные сервоприводы. Независимые 2 мира падают на первом pose_target_match с index 14/size 14 в обоих коммитах.
2. Crouch / Spin не имеют expand_bam_friction_fields из Rollers, но оба проходят сброс + 2 шага в 2 мирах: события колёс расширяют dof_frictionloss, а damping BAM пишет скаляр. Доказанного сбоя выполнения нет.
3. Не копируйте комментарии: docstring Crouch говорит 4 s, константа — 5 s; docstring RelativeHeadingVelocityCommand говорит positive CW, но target_yaw−current_yaw даёт положительное CCW.
4. Просмотр по умолчанию — не оценка конечного курса: четыре фабрики игнорируют play; RollerStandUp начинает с 0% спины / сопротивления колёс 0.05, если STANDUP_PLAY_FACE_UP не меняет только вероятность спины, но не курс колёс.

## Файлы
<a id="文件"></a>
<a id="files"></a>

- official-roller-audit.json: машиночитаемые общие выводы, сводки семейств, фактическая конфигурация фабрик обучения / просмотра, хеши / свидетельства исходников.
- smoke-frozen.json / smoke-frozen.log: upstream-фабрика только для чтения, сброс + 2 шага в 2 мирах, нулевые действия, без обучения / оборудования.

## Локальное исправление адаптера и считывание (R1.5.21)
<a id="本地中控适配修复与读回r1521"></a>
<a id="local-adapter-repair-and-readback-r1521"></a>

Разрешённое локальное исправление training / official_adapter.py переназначает три награды позы RollerStandUp с 18 на 14 слотов по фактическим именам, включая joint_indices / необязательные target_overrides: правая нога 11–15→9–13, шея / голова 7–10→5–8. Сброс / события / веса сохранены. Describe / train / export используют общий адаптер и запись исправления. Свидетельства исходного сбоя upstream не означают, что исправленная локальная задача всё ещё падает.

Пройдены шесть целевых тестов: реальный HD1910, 2 среды / сброс + 10 шагов, конечные actor 61 / награды; корректные цели ног / шеи для трёх наград; идемпотентность, отсутствие частичной порчи, согласованность describe / train / export; считывание трения стоп / шин / сопротивления оси без изменения состояния. Полный журнал — adapter-tests.log. friction_readback первого шага — одно считывание после DR, а не длительный охват или успех задачи.
