//! The same detector on the CPU, for a board whose NPU is switched off.
//!
//! **Why this exists at all.** The RK3566 has an NPU, the vendor kernel has the driver — and on
//! this board the device tree ships `npu@fde40000` as `disabled`, with the only overlay Armbian
//! offers being one that disables it further. Enabling it is an overlay and a reboot, which is a
//! decision about somebody's robot rather than a detail of a detector. So the detector runs on four
//! A55 cores until that happens, and moves to the NPU by changing one config value.
//!
//! ONNX Runtime is already on every provisioned board — `setup-board.sh` installs it for robotd's
//! policies — and `ort` dlopens it, so this costs no new dependency on the robot.

use std::path::Path;

use anyhow::{Context, Result, bail};
use ort::session::{Session, builder::GraphOptimizationLevel};
use ort::value::Tensor;

/// A YOLO detector on the CPU.
pub struct Model {
    session: Session,
    /// `[height, width, channels]`, as the graph declares it.
    pub input: (usize, usize, usize),
}

impl Model {
    pub fn open(path: &Path) -> Result<Self> {
        let session = Session::builder()
            .context("ort session builder")?
            .with_optimization_level(GraphOptimizationLevel::Level3)
            .context("ort optimisation level")?
            // **Two threads, not four.** The other two belong to `robotd`'s control loop and to
            // GStreamer; a detector that takes the whole SoC to find a duck 3 m away has taken
            // something more important than it gave.
            .with_intra_threads(2)
            .context("ort threads")?
            .commit_from_file(path)
            .with_context(|| format!("cannot load {}", path.display()))?;

        // NCHW, as exported: [1, 3, H, W].
        let shape = session
            .inputs()
            .first()
            .and_then(|input| input.dtype().tensor_shape().map(|dims| dims.to_vec()))
            .unwrap_or_default();
        let input = match shape.as_slice() {
            [_, c, h, w] if *c == 3 => (*h as usize, *w as usize, *c as usize),
            other => bail!("expected a [1, 3, H, W] input, got {other:?}"),
        };
        Ok(Self { session, input })
    }

    /// One letterboxed RGB frame in, the raw head out — the same layout the NPU path returns, so
    /// [`crate::decode`] does not care which one produced it.
    pub fn infer(&mut self, frame: &[u8], out: &mut Vec<f32>) -> Result<()> {
        let (height, width, channels) = self.input;
        if frame.len() != height * width * channels {
            bail!(
                "frame is {} bytes, the model wants {}",
                frame.len(),
                height * width * channels
            );
        }

        // HWC bytes to NCHW floats, normalised the way the export expects (0..1). The NPU runtime
        // does this itself from the mean/std baked into the .rknn; here it is ours to do.
        let mut planar = vec![0.0f32; frame.len()];
        for y in 0..height {
            for x in 0..width {
                for c in 0..channels {
                    planar[c * height * width + y * width + x] =
                        frame[(y * width + x) * channels + c] as f32 / 255.0;
                }
            }
        }

        let tensor = Tensor::from_array((
            [1_usize, channels, height, width],
            planar.into_boxed_slice(),
        ))
        .context("building the input tensor")?;
        let outputs = self
            .session
            .run(ort::inputs!["images" => tensor])
            .context("inference failed")?;
        let (_, data) = outputs[0]
            .try_extract_tensor::<f32>()
            .context("the output is not f32")?;
        out.clear();
        out.extend_from_slice(data);
        Ok(())
    }
}
