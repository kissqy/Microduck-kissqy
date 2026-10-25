[Русский](README.ru.md)

# Microduck Training Studio R1.5.27 tests

Full Python tests (CPU/fixture paths run locally, external dependencies may skip):

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Static JavaScript checks:

```bash
node --check training/static/training.js
node tests/test_target_limit_ui.cjs
node tests/test_recovery_ui.cjs
node tests/test_r1524_roller_ui.cjs
node tests/test_queue_status.cjs
```

The registered task catalog contains 14 action profiles and 35 tasks.
Existing training runs, checkpoints and exported models are stored outside the
package and are not modified by the installer.

Previously saved official baseline 35-task evidence remains under `docs/audit-0151/`.
Successful local tests do not establish GPU training or physical rollout quality.
