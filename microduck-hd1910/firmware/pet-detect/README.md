# pet-detect

A tiny audio classifier that hears when the robot's head is being scratched (the onboard
mic sits there). ~20 KB CNN over 40-band log-mel windows, sub-millisecond inference.

Ported from `apirrone/microduck_pet_detect`; the arecord worker and the ambient sound
sentry from the prototype's `pet_worker.rs` live here too, so everything that listens to
the mic is one crate. `robotd` runs the worker (see `[audio]` in `deploy/robotd.toml`) and
coos when petting starts.

- **Library**: `PettingDetector` (streaming, hysteresis) and `worker::PetHandle`
  (arecord subprocess + event channels).
- **`pet-detect`** (binary): pipe `arecord -D plughw:aic3104,0 -f S16_LE -r 16000 -c 1 -t raw`
  into it and watch the probability while you scratch the head.
- **`pet-features`** (binary): dumps log-mel features of a WAV — the training side of the
  train/infer parity contract.
- **`models/pet_detect.onnx`**: the trained model, shipped in the release as
  `models/pet_detect.onnx`.

## Retraining

`training/train.py` (PyTorch) extracts features THROUGH the `pet-features` binary — the
same code path the robot runs, so there is no train/infer drift. Record data on the robot:

```bash
arecord -D plughw:aic3104,0 -f S16_LE -r 16000 -c 1 -d 30 /tmp/petting_01.wav
```

into `data/petting/` and `data/normal/` (walking, motors, ambient — anything that isn't
petting; the recordings themselves are not vendored here), then:

```bash
cargo build --release -p pet-detect --bin pet-features
uv run --with torch --with onnx training/train.py
```

and commit the refreshed `models/pet_detect.onnx`.
