[Оригинал](README.md) | **Русский**

<a id="microduck-training-studio-r1527-tests"></a>
# Тесты Microduck Training Studio R1.5.27

Полный набор тестов Python (CPU / тестовые фикстуры выполняются локально, проверки с внешними зависимостями могут пропускаться):

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Статические проверки JavaScript:

```bash
node --check training/static/training.js
node tests/test_target_limit_ui.cjs
node tests/test_recovery_ui.cjs
node tests/test_r1524_roller_ui.cjs
node tests/test_queue_status.cjs
```

В реестре задач содержатся 14 профилей действий и 35 задач. Существующие запуски обучения, контрольные точки и экспортированные модели хранятся вне пакета и не изменяются установщиком.

Ранее сохранённые свидетельства официальной базовой проверки 35 задач остаются в `docs/audit-0151/`. Успешные локальные тесты не подтверждают GPU-обучение или качество выполнения на физическом роботе.
