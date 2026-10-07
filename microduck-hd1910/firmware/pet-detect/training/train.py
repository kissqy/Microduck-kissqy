#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "torch>=2.2",
#   "numpy",
#   "onnx",
#   "onnxscript",
# ]
# ///
"""Train the petting classifier.

Features are extracted by the `pet-features` Rust binary so that the training
features exactly match what the runtime computes — no risk of a Python/Rust
log-mel discrepancy biasing the model.

Run from the repo root:
    cargo build --release -p pet-detect --bin pet-features
    uv run training/train.py
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import onnx
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
MODEL_OUT = REPO / "models" / "pet_detect.onnx"
# The workspace root is two levels up (pet-detect/training/ -> repo).
FEATURES_BIN = REPO.parent / "target" / "release" / "pet-features"

# Must match src/lib.rs.
N_MELS = 40
WINDOW_FRAMES = 100
BLOCK_BYTES = N_MELS * WINDOW_FRAMES * 4  # f32 LE


def extract_blocks(wav: Path) -> np.ndarray:
    """Run the Rust pet-features bin on `wav`, return [N, N_MELS, WINDOW_FRAMES] f32."""
    res = subprocess.run(
        [str(FEATURES_BIN), str(wav)],
        capture_output=True,
        check=True,
    )
    raw = res.stdout
    if len(raw) % BLOCK_BYTES != 0:
        raise RuntimeError(f"{wav}: feature byte count {len(raw)} not divisible by {BLOCK_BYTES}")
    n = len(raw) // BLOCK_BYTES
    arr = np.frombuffer(raw, dtype=np.float32).reshape(n, N_MELS, WINDOW_FRAMES).copy()
    return arr


def load_class(label_dir: Path, label: int) -> tuple[np.ndarray, np.ndarray]:
    wavs = sorted(label_dir.glob("*.wav"))
    if not wavs:
        raise RuntimeError(f"no wavs in {label_dir}")
    feats = [extract_blocks(w) for w in wavs]
    X = np.concatenate(feats, axis=0)
    y = np.full(X.shape[0], label, dtype=np.int64)
    print(f"  {label_dir.name}: {X.shape[0]} windows from {len(wavs)} file(s)")
    return X, y


class TinyAudioCNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(1, 8, kernel_size=3, padding=1),
            nn.BatchNorm2d(8),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(8, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(16, 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, 1, N_MELS, WINDOW_FRAMES]
        return torch.softmax(self.net(x), dim=1)


def main() -> None:
    if not FEATURES_BIN.exists():
        raise SystemExit(f"missing {FEATURES_BIN} — run `cargo build --release -p pet-detect --bin pet-features` first")

    print("Extracting features...")
    Xn, yn = load_class(DATA / "normal", 0)
    Xp, yp = load_class(DATA / "petting", 1)
    X = np.concatenate([Xn, Xp], axis=0)[:, None, :, :]  # add channel dim
    y = np.concatenate([yn, yp], axis=0)

    # Per-dataset mean/std normalization. Stored in the ONNX as a Sub/Div is overkill;
    # since features.rs and detect.rs share lib.rs, we normalize inside training only —
    # the model will learn batch-norm offsets to absorb it. Keep features unnormalized
    # to avoid train/infer drift.

    # Shuffle and split 80/20.
    rng = np.random.default_rng(42)
    idx = rng.permutation(X.shape[0])
    X, y = X[idx], y[idx]
    split = int(0.8 * X.shape[0])
    Xtr, ytr = X[:split], y[:split]
    Xva, yva = X[split:], y[split:]
    print(f"Train: {Xtr.shape[0]}  Val: {Xva.shape[0]}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = TinyAudioCNN().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)

    tr_loader = DataLoader(
        TensorDataset(torch.from_numpy(Xtr), torch.from_numpy(ytr)),
        batch_size=32,
        shuffle=True,
    )
    Xva_t = torch.from_numpy(Xva).to(device)
    yva_t = torch.from_numpy(yva).to(device)

    for epoch in range(1000):
        model.train()
        total = 0.0
        for xb, yb in tr_loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            probs = model(xb)
            # CrossEntropy expects logits; our forward applies softmax, so use NLL on log(probs).
            loss = nn.functional.nll_loss(torch.log(probs + 1e-8), yb)
            loss.backward()
            opt.step()
            total += loss.item() * xb.shape[0]
        model.eval()
        with torch.no_grad():
            va_probs = model(Xva_t)
            va_pred = va_probs.argmax(dim=1)
            va_acc = (va_pred == yva_t).float().mean().item()
        print(f"epoch {epoch:02d}  train_loss={total / len(tr_loader.dataset):.4f}  val_acc={va_acc:.3f}")

    # Export ONNX.
    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.zeros(1, 1, N_MELS, WINDOW_FRAMES, device=device)
    torch.onnx.export(
        model,
        dummy,
        MODEL_OUT,
        input_names=["input"],
        output_names=["probs"],
        dynamic_axes={"input": {0: "batch"}, "probs": {0: "batch"}},
        opset_version=18,
    )

    # The new dynamo exporter writes weights to a sidecar `.onnx.data` file by
    # default. Consolidate everything back into a single .onnx so the runtime
    # only needs one artifact.
    sidecar = MODEL_OUT.with_suffix(".onnx.data")
    if sidecar.exists():
        m = onnx.load(str(MODEL_OUT), load_external_data=True)
        onnx.save_model(m, str(MODEL_OUT), save_as_external_data=False)
        sidecar.unlink()
    print(f"wrote {MODEL_OUT}")


if __name__ == "__main__":
    main()
