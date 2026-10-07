# Verification

R1.5.17 adds recovery evaluation checks. The portable subset covers launch
isolation, per-pose result accounting and the existing viewer/transport paths:

```bash
python -m unittest tests.test_recovery_api tests.test_recovery_evaluation.RecoveryResultsTests tests.test_eval_push_dependencies -v
node tests/test_recovery_ui.cjs
```

The Node check executes the actual selection/render/click/request code with
DOM/HTTP fixtures; it does not validate real browser CSS or WebGL rendering.
The real-source check builds CPU physics and starts a real Viser server:

```bash
MICRODUCK_OFFICIAL_SOURCE=/path/to/pinned/microduck_rl python -m unittest tests.test_recovery_evaluation.RecoveryUpstreamTests -v
```

See `docs/R1.5.17-verification.txt` for the delivered version's actual results.

R1.5.10 adds `test_training_queue.py` and `test_browser_queue.cjs`. The latter
uses real HTTP and the real queue scheduling thread, with explicit simulated
completion receipts instead of GPU training. It tests page-independent dispatch,
teacher dependencies, snapshot preservation, pause/retry and responsive layout.
Actual WSL process survival is not established by the simulated completion test.

Portable checks (Python 3.10+, no robot):

```bash
python -m unittest discover -s tests -p 'test*.py'
```

Some simulation/viewer tests require MuJoCo, NumPy and Viser. `RealOfficialSourceTests` additionally requires the frozen official microduck_rl source plus its locked dependencies. It skips when that source is unavailable. HTTP and process-lifecycle tests bind only loopback addresses. No test connects to ZERO.

Optional real 4K browser check, with Playwright and a Chromium executable installed:

```bash
node tests/test_browser_official0151.cjs
```

Set `PLAYWRIGHT_MODULE`, `CHROMIUM_PATH` and `TEST_PYTHON` when those tools are outside their default locations. The browser fixture uses local synthetic checkpoints; it does not train or actuate a robot. Actual CPU PPO/BC/export validation is documented separately in docs/Verification.md.

`test_v2_compatibility.py` covers V2 model selection, alias/recipe migration, current-source execution with original asset paths, teacher contracts and truthful export provenance. The browser fixture includes native, compatible V2 and unsupported legacy records.

`test_sample_alignment.py` covers sample-equivalent stage thresholds, comparator boundaries, budgets, non-mutating/idempotent config changes, checkpoint sample clocks and teacher warm starts. The browser check also covers editable budgets, 2048/1024 schedules and keeping the active job's schedule independent of subsequent form edits.

Optional real-source CPU integration (install the pinned official dependencies first, including its BAM checkout):

```bash
MICRODUCK_OFFICIAL_SOURCE=/path/to/pinned/microduck_rl \
python -m unittest discover -s tests -p 'test_sampling_upstream.py' -v
```

The three integration tests read all real task configs, run the official joint curriculum manager at scaled boundaries, and save/reload an actual PT with a changed parallel count. They use 1–2 CPU worlds and fresh test weights; they do not measure policy convergence or GPU memory. If BAM is not installed, add the locked BAM checkout to `PYTHONPATH`.

`test_current_actions.py` covers the current deployed set, old hidden recipe evaluation, fixed sitstand scale, exact 14 backlash ranges, encoder position/velocity conventions, HD1910 reset/friction recognition, left-foot factories, roller-crouch physics and actual PPO/PT/ONNX export. Enable CPU integration with MICRODUCK_OFFICIAL_SOURCE. Real owner/reconnect tests require PID and /proc namespaces to match; they skip in incompatible execution sandboxes.
