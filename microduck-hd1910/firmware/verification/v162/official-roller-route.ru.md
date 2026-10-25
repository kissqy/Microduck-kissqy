[English](official-roller-route.en.md) | [简体中文](official-roller-route.md) | **Русский**

<a id="官方滑轮起身路由核对"></a>
<a id="official-roller-recovery-route-review"></a>
# Проверка официального пути восстановления на роликах

Целевая версия: 0.15.1 / 1 fa 84386. Сохранённый `robotd-params/src/lib.rs` по умолчанию задаёт Roller `stand=None`; `set_standing_disabled` в `robotd/src/main.rs` для Roller равен true. Исходный контракт экспорта также объявляет `manual_skill`, `slot=null` и `required_skill_settings=null`.

Общедоступная upstream-документация проверена 11 октября 2026 года; `main` может быть новее 0.15.1:

- <https://github.com/pollen-robotics/microduck/blob/main/docs/policy-manifest.md>: непрерывные модели без `duration_s` требуют `--hold`; они не становятся автоматически действиями ограниченной длительности.
- <https://github.com/pollen-robotics/microduck/blob/main/duck-control/src/policy.rs>: Roller не выбирает Stand при нулевой скорости.

Вывод v162: установить / проверить исходные веса восстановления и показать их как неназначенные. Не превращайте длительность эпизода обучения или придуманные секунды в окно выполнения и не перезаписывайте удар левой ногой LB. Позднейшая конфигурация ручного теста описана в [текущем руководстве консоли](../../console/USER-GUIDE.ru.md).
