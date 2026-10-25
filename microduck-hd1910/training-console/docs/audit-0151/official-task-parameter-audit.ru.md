[English](official-task-parameter-audit.en.md) | [简体中文](official-task-parameter-audit.zh-CN.md) | **Русский**

# Аудит официальных параметров каждой задачи (7 октября 2026 года)
<a id="官方动作逐任务参数核验2026-10-07"></a>
<a id="official-per-task-parameter-audit-october-7-2026"></a>

Обучение остаётся закреплено на `8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec`; на момент аудита оно сопоставлено с develop `273afe0b31c4ab365b9ff806a927b63ac92b5ddd`. Импорт обоих реестров даёт одинаковые 33 upstream-задачи. Два локальных псевдонима удара левой ногой вызывают официальную параметризованную фабрику, доводя число задач консоли до 35. Незарегистрированные сочетания не выдумывались по сводкам README.

Свидетельства: `official-task-parameter-matrix.json` записывает события, параметры, награды, курсы, завершения, действия, наблюдения, оптимизатор и различия обучения / просмотра каждой задачи. `official-resolved-*.json` — полные фактические результаты фабрик. `official-compiled-physics.json` компилирует девять исходных upstream Entity робота без HD1910 или активной рандомизации.

## Фактически зарегистрированные сочетания
<a id="实际注册组合"></a>
<a id="actual-registered-combinations"></a>

| Семейство | Число | Rough | Backlash | Рельеф / примечания |
| --- | ---: | --- | --- | --- |
| BallKick | 2 | Нет | Да | Только плоскость |
| GroundPick | 4 | Да | Да | Плоскость / генератор Rough |
| RollerCrouch | 2 | Нет | Да | Плоскость; оборудование с роликами |
| RollerSlope | 2 | Нет | Да | Flat в ID, фактически генератор склона |
| RollerStandUp | 1 | Нет | Нет | Плоскость; оборудование с роликами |
| Roulade | 1 | Нет | Нет | Только плоскость |
| SitStand | 4 | Да | Да | Плоскость / генератор Rough |
| Spin | 1 | Нет | Нет | Плоскость; оборудование с роликами |
| StandUp | 4 | Да | Да | Плоскость / генератор Rough |
| VelStand | 4 | Да | Да | Плоскость / генератор Rough |
| Velocity | 4 | Да | Да | Плоскость / генератор Rough |
| RollersVelocity | 2 | Нет | Да | Плоскость; оборудование с роликами |
| Swizzle | 2 | Нет | Да | Плоскость; оборудование с роликами |

У Roulade, RollerStandUp и Spin нет регистраций Backlash. Ни у одного семейства роликов нет Rough. У переката вперёд нет ни Rough, ни Backlash. Команды, курсы осей и результаты коротких шагов шести семейств роликов приведены в [аудите роликов](roller-audit/official-roller-audit.ru.md).

## Физические различия
<a id="不能混淆的真实物理"></a>
<a id="physical-distinctions"></a>

- Все управляются на 50 Hz: физика 5 ms / decimation 4; 14 активных суставов, 61 измерение actor. Действия — Home+scale×raw policy, официальный scale 1, без EMA цели. Память награды head_pose_bias не является фильтрацией действий.
- Upstream использует XL330 BAM M6/P200, консоль — HD1910/P5; числа напрямую несопоставимы. Построенная upstream Entity: kt 0.3660134969, R 2.8113923539, armature 0.0018077433, max_pwm 1, **стандартный max_current BAM 1.75 A**. Отсутствие явной настройки не означает неограниченный ток. Статическая верхняя граница полного момента мотора ≈0.64052 N·m не учитывает трение и не является измеренным длительным моментом.
- Напряжение при запуске 6.5–8.2 V, коэффициент просадки под нагрузкой 0–0.2, минимум 6 V; задержка привода 3–6 физических шагов =15–30 ms. IMU обычно 0–1 шаг управления; GroundPick 0–3 =0–60 ms; скорость суставов 1 шаг. Настройки шума / удержания / обновления приведены в JSON.
- Масса обычного upstream-робота 737.24318 g, с роликами 736.82962 g, а не пользовательские 820 g. studio_inspection_summary отдельно компилирует 35 задач HD1910 P5/scale 1/без EMA: обычный 820.000 g, роликовый 819.58644 g. Зафиксирована разница 0.41356 g, а не точное равенство.
- foot_friction без роликов — равномерная абсолютная величина [0.7, 1.3] при запуске, общая для стоп; mjlab axes=[0] рандомизирует только скольжение, не каждый сброс. Официальный просмотр сохраняет её.
- Компоненты кручения / качения обычно [0.005, 0.0001] не рандомизируются; condim 3 стоп включает скольжение. После FULL_COLLISION большинство именованных геометрий вне стоп используют condim 1. Итоговая размерность также зависит от приоритетов обеих геометрий, поэтому один компонент не устанавливает обученное трение каждого столкновения.
- Шины роликов — **mesh, тип MuJoCo 7**; четыре пассивных шарнира колёс перемежаются с активными суставами. У шин condim 3/friction [1, 0.005, 0.0001]. У шести семейств нет рандомизации geom_friction. randomize_wheel_friction меняет dof_frictionloss оси, то есть сопротивление подшипника; большинство границ интервалов курса одинаковы.
- Внутреннее трение и armature BAM обычно рандомизируются при сбросе [0.9, 1.1] независимо от трения стоп. Перечислены фактические события / селекторы без предположений по переключателям в комментариях.
- Спецификации столкновений различаются: Velocity=walk; StandUp / SitStand / GroundPick / BallKick / Roulade=groundcontact; VelStand=allcollisions. Комментарий «No task uses it yet» устарел. Backlash выбирает соответствующие спецификации, 14 осей по ±1°.

## Скрытые различия Rough и просмотра
<a id="rough-与-play-的隐藏差别"></a>
<a id="hidden-rough-and-play-differences"></a>

Rough объявляет 10×20, но фактический импорт реестра даёт 5×5: обучение / просмотр разделяют генератор, и просмотр меняет размеры. generator.curriculum никогда не объявлялся True; mjlab по умолчанию использует False, поэтому просмотр не отключал True, а скрытое изменение на True не оправдано. terrain_levels — отдельный курс. Аудит сохраняет устоявшееся фактическое поведение 5×5 / случайной сложности.
play=True не является универсальным отключением рандомизации. Шум, DR BAM / поверхности и курсы часто сохраняются; некоторые задачи усиливают толчки. У Rollers / Swizzle / Crouch / Spin нет ветки просмотра. JSON записывает различия; «оценка» не устанавливает бесшумность / стабильность поведения.

## Исходный сбой upstream и минимальное локальное исправление
<a id="原官方故障与本地最小修复"></a>
<a id="original-upstream-failure-and-minimal-local-repair"></a>

Исходный RollerStandUp падает на первом шаге: функции награды используют представления 14 сервоприводов, а конфигурация сохраняет 18 индексов слотов, включая 14. Ошибка есть в обоих коммитах. Локальный адаптер переназначает joint_indices / target_overrides для трёх затронутых наград по фактическим именам суставов, не меняя исходные индексы сброса, веса или курсы. Пройдены пять независимых тестов, включая 2 среды / 10 шагов; журналы исходного сбоя сохранены. Одна регистрация не является приёмкой выполнения.
Crouch / Spin не вызывают expand_bam_friction_fields явно, но оба проходят сброс + 2 шага в 2 средах: сопротивление колёс расширяет нужные поля. Статическое отсутствие не доказывает сломанное обучение; предупреждения аудита всё равно требуют реальных шагов.

## Закреплённая версия и develop на момент аудита
<a id="冻结版本与当前-develop"></a>
<a id="frozen-version-versus-develop-at-audit-time"></a>

Реестр, обёртка Backlash, константы робота, все env_cfg кроме VelStand, шесть семейств роликов и файлы симметрии побайтово идентичны. Изменения сосредоточены в VelStand, mdp команд корпуса и distill. Включённые команды корпуса стоя добавляют roll / pitch ≈±12°, z от −2.5 до +1 cm и меняют награды / пути BC; ENABLE_YAW_FIX остаётся False. Добавление действий не требует обновления устоявшегося поведения; сохраните закрепление 8d0.

## Краткий указатель по задачам
<a id="逐任务快速索引"></a>
<a id="per-task-quick-index"></a>

| ID задачи | Секунды | Трение контакта обучение / просмотр | Начальная задержка IMU при обучении | Спецификация робота |
|---|---:|---|---|---|
| `Mjlab-BallKick-Flat-Backlash-MicroDuck` | 5 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_backlash_spec` |
| `Mjlab-BallKick-Flat-MicroDuck` | 5 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_standup_spec` |
| `Mjlab-GroundPick-Flat-Backlash-MicroDuck` | 20 | при запуске 0.7–1.3 / сохранено | 0–3 шагов | `get_backlash_spec` |
| `Mjlab-GroundPick-Flat-MicroDuck` | 20 | при запуске 0.7–1.3 / сохранено | 0–3 шагов | `get_ground_pick_spec` |
| `Mjlab-GroundPick-Rough-Backlash-MicroDuck` | 20 | при запуске 0.7–1.3 / сохранено | 0–3 шагов | `get_backlash_spec` |
| `Mjlab-GroundPick-Rough-MicroDuck` | 20 | при запуске 0.7–1.3 / сохранено | 0–3 шагов | `get_ground_pick_spec` |
| `Mjlab-RollerCrouch-Flat-Backlash-MicroDuck` | 20 | Без DR геометрии / нет | 0–1 шагов | `get_rollers_backlash_spec` |
| `Mjlab-RollerCrouch-Flat-MicroDuck` | 20 | Без DR геометрии / нет | 0–1 шагов | `get_walk_rollers_spec` |
| `Mjlab-RollerSlope-Flat-Backlash-MicroDuck` | 20 | Без DR геометрии / нет | 0–1 шагов | `get_rollers_backlash_spec` |
| `Mjlab-RollerSlope-Flat-MicroDuck` | 20 | Без DR геометрии / нет | 0–1 шагов | `get_walk_rollers_spec` |
| `Mjlab-RollerStandUp-Flat-MicroDuck` | 6 | Без DR геометрии / нет | 0–1 шагов | `get_walk_rollers_spec` |
| `Mjlab-Roulade-Flat-MicroDuck` | 5 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_standup_spec` |
| `Mjlab-SitStand-Flat-Backlash-MicroDuck` | 12 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_backlash_spec` |
| `Mjlab-SitStand-Flat-MicroDuck` | 12 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_standup_spec` |
| `Mjlab-SitStand-Rough-Backlash-MicroDuck` | 12 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_backlash_spec` |
| `Mjlab-SitStand-Rough-MicroDuck` | 12 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_standup_spec` |
| `Mjlab-Spin-Flat-MicroDuck` | 20 | Без DR геометрии / нет | 0–1 шагов | `get_walk_rollers_spec` |
| `Mjlab-StandUp-Flat-Backlash-MicroDuck` | 6 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_backlash_spec` |
| `Mjlab-StandUp-Flat-MicroDuck` | 6 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_standup_spec` |
| `Mjlab-StandUp-Rough-Backlash-MicroDuck` | 6 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_backlash_spec` |
| `Mjlab-StandUp-Rough-MicroDuck` | 6 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_standup_spec` |
| `Mjlab-VelStand-Flat-Backlash-MicroDuck` | 20 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_allcollisions_backlash_spec` |
| `Mjlab-VelStand-Flat-MicroDuck` | 20 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_allcollisions_spec` |
| `Mjlab-VelStand-Rough-Backlash-MicroDuck` | 20 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_allcollisions_backlash_spec` |
| `Mjlab-VelStand-Rough-MicroDuck` | 20 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_allcollisions_spec` |
| `Mjlab-Velocity-Flat-Backlash-MicroDuck` | 20 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_walk_backlash_spec` |
| `Mjlab-Velocity-Flat-Backlash-MicroDuck-Rollers` | 20 | Без DR геометрии / нет | 0–1 шагов | `get_rollers_backlash_spec` |
| `Mjlab-Velocity-Flat-MicroDuck` | 20 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_walk_spec` |
| `Mjlab-Velocity-Flat-MicroDuck-Rollers` | 20 | Без DR геометрии / нет | 0–1 шагов | `get_walk_rollers_spec` |
| `Mjlab-Velocity-Rough-Backlash-MicroDuck` | 20 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_walk_backlash_spec` |
| `Mjlab-Velocity-Rough-MicroDuck` | 20 | при запуске 0.7–1.3 / сохранено | 0–1 шагов | `get_walk_spec` |
| `Mjlab-Velocity-Swizzle-Backlash-MicroDuck` | 20 | Без DR геометрии / нет | 0–1 шагов | `get_rollers_backlash_spec` |
| `Mjlab-Velocity-Swizzle-MicroDuck` | 20 | Без DR геометрии / нет | 0–1 шагов | `get_walk_rollers_spec` |

## Первичные исходники
<a id="主源定位"></a>
<a id="primary-source-locations"></a>

- BallKick: [исходник фабрики](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_ball_kick_env_cfg.py#L132).
- GroundPick: [исходник фабрики](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_ground_pick_env_cfg.py#L114).
- RollerCrouch: [исходник фабрики](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_crouch_env_cfg.py#L116).
- RollerSlope: [исходник фабрики](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_slope_env_cfg.py#L66).
- RollerStandUp: [исходник фабрики](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roller_standup_env_cfg.py#L135).
- Roulade: [исходник фабрики](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_roulade_env_cfg.py#L147).
- SitStand: [исходник фабрики](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_sitstand_env_cfg.py#L195).
- Spin: [исходник фабрики](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_spin_env_cfg.py#L87).
- StandUp: [исходник фабрики](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_standup_env_cfg.py#L152).
- VelStand: [исходник фабрики](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velstand_env_cfg.py#L377).
- Velocity: [исходник фабрики](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py#L193).
- RollersVelocity: [исходник фабрики](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_rollers_env_cfg.py#L85).
- Swizzle: [исходник фабрики](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_swizzle_env_cfg.py#L34).
- `src/mjlab_microduck/tasks/__init__.py`: [строка 78](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/__init__.py#L78).
- `src/mjlab_microduck/robot/microduck_constants.py`: [строка 142](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/robot/microduck_constants.py#L142).
- `src/mjlab_microduck/tasks/backlash.py`: [строка 42](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/backlash.py#L42).
- `src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py`: [строка 130](https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py#L130).

Ссылки на зависимость mjlab 1.3.0: envs / mdp / dr / geom.py: 117–145 (оси трения по умолчанию), terrains / terrain_generator.py: 92 (curriculum по умолчанию False). Полные версии указаны в JSON. Аудит устанавливает конфигурацию и исполнимость коротких шагов, а не сходимость или пригодность физического робота.
