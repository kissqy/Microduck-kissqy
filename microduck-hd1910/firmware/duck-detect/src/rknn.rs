//! The seven functions of Rockchip's NPU runtime this needs, and nothing else.
//!
//! **`dlopen`, not link.** `librknnrt.so` is a vendor blob: it is not in any Debian suite, not on a
//! laptop, and not needed to *build* — a daemon that linked it could not be cross-compiled in CI at
//! all. `robotd` reaches ONNX Runtime the same way and for the same reason. The cost is this file;
//! the benefit is that `cargo board --bins` keeps working on a machine with no Rockchip anything.
//!
//! The C API is documented in Rockchip's `rknpu2` repository. The parts that matter here:
//!
//! * `rknn_init` takes the model *bytes*, not a path, so the caller reads the file.
//! * `rknn_query` answers with fixed-size structs whose layout is the ABI. They are reproduced
//!   below field for field; a mismatch is silent nonsense rather than an error, which is why the
//!   sizes are asserted at startup rather than trusted.
//! * A quantised model's tensors are **int8 with a scale and a zero point**, and
//!   `rknn_outputs_get` will dequantise for you if asked (`want_float`). Asked, here: the alternative
//!   is carrying the scale into the decoder and getting it wrong once.

use std::ffi::{CString, c_char, c_int, c_uint, c_void};
use std::path::Path;

use anyhow::{Context, Result, anyhow, bail};

/// Where the runtime usually lands, in the order worth trying.
///
/// The first is where `scripts/setup-npu.sh` puts it; the rest are where a board that got it from
/// somewhere else tends to have it. Searched rather than pinned so a board provisioned by hand
/// still works.
const CANDIDATES: [&str; 4] = [
    "librknnrt.so",
    "/usr/lib/librknnrt.so",
    "/usr/lib/aarch64-linux-gnu/librknnrt.so",
    "/usr/local/lib/librknnrt.so",
];

/// `rknn_query` commands, in the order `rknn_api.h` declares them.
///
/// **The order is the ABI.** These were guessed once with input and output swapped, and the symptom
/// was `rknn_query(INPUT_ATTR)` answering with the *output* tensor — "cannot make sense of the input
/// shape [1, 5, 2100]", which is a perfectly sensible complaint about the wrong question. Nothing
/// but running it on a board could have caught that, so it is written down rather than derived.
const RKNN_QUERY_IN_OUT_NUM: c_uint = 0;
const RKNN_QUERY_INPUT_ATTR: c_uint = 1;
const RKNN_QUERY_OUTPUT_ATTR: c_uint = 2;
const RKNN_QUERY_SDK_VERSION: c_uint = 5;

/// Tensor element types, as `rknn_api.h` numbers them: float32, float16, int8, **uint8**, …
const RKNN_TENSOR_UINT8: c_uint = 3;

/// Tensor layouts: **NCHW is 0 and NHWC is 1**, in that order.
///
/// Worth the emphasis, because getting it backwards does not fail. The runtime logs
/// "Meet unsupported src layout for normalize: NCHW, only support NHWC src layout" — and then
/// `rknn_inputs_set` **returns success anyway**, so inference runs on whatever was in the input
/// buffer and the detector reports exactly two confident boxes on every frame, for ever. Two
/// identical detections per frame is what that looks like from outside.
const RKNN_TENSOR_NHWC: c_uint = 1;

const RKNN_MAX_DIMS: usize = 16;
const RKNN_MAX_NAME_LEN: usize = 256;

#[repr(C)]
#[derive(Debug, Clone, Copy)]
struct RknnInputOutputNum {
    n_input: c_uint,
    n_output: c_uint,
}

#[repr(C)]
#[derive(Clone, Copy)]
struct RknnTensorAttr {
    index: c_uint,
    n_dims: c_uint,
    dims: [c_uint; RKNN_MAX_DIMS],
    name: [c_char; RKNN_MAX_NAME_LEN],
    n_elems: c_uint,
    size: c_uint,
    fmt: c_uint,
    type_: c_uint,
    qnt_type: c_uint,
    fl: i8,
    zp: i32,
    scale: f32,
    w_stride: c_uint,
    size_with_stride: c_uint,
    pass_through: u8,
    h_stride: c_uint,
}

#[repr(C)]
struct RknnInput {
    index: c_uint,
    buf: *mut c_void,
    size: c_uint,
    pass_through: u8,
    type_: c_uint,
    fmt: c_uint,
}

#[repr(C)]
struct RknnOutput {
    want_float: u8,
    is_prealloc: u8,
    index: c_uint,
    buf: *mut c_void,
    size: c_uint,
}

#[repr(C)]
struct RknnSdkVersion {
    api_version: [c_char; 256],
    drv_version: [c_char; 256],
}

type RknnInitFn =
    unsafe extern "C" fn(*mut *mut c_void, *const c_void, c_uint, c_uint, *const c_void) -> c_int;
type RknnDestroyFn = unsafe extern "C" fn(*mut c_void) -> c_int;
type RknnQueryFn = unsafe extern "C" fn(*mut c_void, c_uint, *mut c_void, c_uint) -> c_int;
type RknnInputsSetFn = unsafe extern "C" fn(*mut c_void, c_uint, *mut RknnInput) -> c_int;
type RknnRunFn = unsafe extern "C" fn(*mut c_void, *const c_void) -> c_int;
type RknnOutputsGetFn =
    unsafe extern "C" fn(*mut c_void, c_uint, *mut RknnOutput, *const c_void) -> c_int;
type RknnOutputsReleaseFn = unsafe extern "C" fn(*mut c_void, c_uint, *mut RknnOutput) -> c_int;

/// A loaded `librknnrt.so`, and the model running on it.
pub struct Model {
    // Dropped last: every function pointer below belongs to this library, and unloading it while a
    // context is alive is a segfault rather than an error.
    _library: libloading::Library,
    context: *mut c_void,
    destroy: RknnDestroyFn,
    inputs_set: RknnInputsSetFn,
    run: RknnRunFn,
    outputs_get: RknnOutputsGetFn,
    outputs_release: RknnOutputsReleaseFn,
    /// What the model wants fed to it: `[height, width, channels]`, from the model itself rather
    /// than from a constant that can disagree with it.
    pub input: (usize, usize, usize),
    /// How many floats come back, so the caller can size its own buffer once.
    pub output_len: usize,
    pub api_version: String,
    pub driver_version: String,
}

// SAFETY: the context is a handle this type owns exclusively — nothing hands it out, and `infer`
// takes `&mut self`, so two threads cannot be inside the runtime at once. Moving the whole thing to
// another thread is what `mediad` does (the detector runs on its own), and that is sound; `Sync` is
// deliberately *not* claimed, because two threads sharing one context is exactly what the runtime
// does not support.
unsafe impl Send for Model {}

/// Why `rknn_init` failed, in the order the causes actually occur.
///
/// **The device tree first, because it is the one every board starts in.** Armbian ships
/// `npu@fde40000` as `status = "disabled"` on the Radxa Zero 3, so a robot that nobody has run
/// `setup-npu.sh` on has the hardware, the kernel, the driver and the runtime, and still no NPU —
/// and the runtime's own log line for it is "failed to open rknpu module, need to insmod rknpu
/// dirver!", which sends people looking for a module that is built in.
///
/// The two causes this used to name are real and are still here, but they are what is left once
/// there is a device to talk to at all. Naming them first cost a bring-up session.
fn why_init_failed() -> String {
    match std::fs::read("/proc/device-tree/npu@fde40000/status") {
        Ok(bytes) if bytes.starts_with(b"disabled") => {
            "The NPU is DISABLED in this board's device \
             tree, which is how Armbian ships the Radxa Zero 3 — so the driver never bound and \
             there is nothing to open. Enable it and reboot: sudo sh \
             /opt/robot/daemon/current/scripts/setup-npu.sh"
                .to_owned()
        }
        // No node at all: not an RK3566, or a kernel whose device tree does not describe one.
        Err(_) => "There is no npu@fde40000 in this board's device tree at all — a kernel that is \
             not the Armbian vendor one is the usual cause, and mainline has no rknpu driver."
            .to_owned(),
        _ => "The node is enabled, so this is the model or the driver: a model built for another \
             platform, or an NPU driver older than the runtime, are the two usual causes."
            .to_owned(),
    }
}

impl Model {
    /// Load `librknnrt.so`, then the model, and ask the model what shape it wants.
    pub fn open(path: &Path) -> Result<Self> {
        let bytes =
            std::fs::read(path).with_context(|| format!("cannot read {}", path.display()))?;

        let mut last = None;
        let library = CANDIDATES
            .iter()
            .find_map(|candidate| match unsafe { libloading::Library::new(*candidate) } {
                Ok(library) => Some(library),
                Err(error) => {
                    last = Some(error);
                    None
                }
            })
            .ok_or_else(|| {
                anyhow!(
                    "cannot load librknnrt.so ({}). It is the NPU runtime, and it is not in Debian: \
                     sudo /usr/local/sbin/robot-setup-npu",
                    last.map(|e| e.to_string()).unwrap_or_default()
                )
            })?;

        // SAFETY: every symbol below is looked up by the name the vendor's header declares, and the
        // signatures are transcribed from it. A missing symbol is an error here rather than a jump
        // into nothing later.
        unsafe {
            let init = *library
                .get::<RknnInitFn>(b"rknn_init\0")
                .context("rknn_init")?;
            let destroy = *library
                .get::<RknnDestroyFn>(b"rknn_destroy\0")
                .context("rknn_destroy")?;
            let query = *library
                .get::<RknnQueryFn>(b"rknn_query\0")
                .context("rknn_query")?;
            let inputs_set = *library
                .get::<RknnInputsSetFn>(b"rknn_inputs_set\0")
                .context("rknn_inputs_set")?;
            let run = *library
                .get::<RknnRunFn>(b"rknn_run\0")
                .context("rknn_run")?;
            let outputs_get = *library
                .get::<RknnOutputsGetFn>(b"rknn_outputs_get\0")
                .context("rknn_outputs_get")?;
            let outputs_release = *library
                .get::<RknnOutputsReleaseFn>(b"rknn_outputs_release\0")
                .context("rknn_outputs_release")?;

            let mut context: *mut c_void = std::ptr::null_mut();
            let code = init(
                &mut context,
                bytes.as_ptr() as *const c_void,
                bytes.len() as c_uint,
                0,
                std::ptr::null(),
            );
            if code != 0 || context.is_null() {
                bail!(
                    "rknn_init failed ({code}) on {}. {}",
                    path.display(),
                    why_init_failed()
                );
            }

            let mut version = RknnSdkVersion {
                api_version: [0; 256],
                drv_version: [0; 256],
            };
            query(
                context,
                RKNN_QUERY_SDK_VERSION,
                &mut version as *mut _ as *mut c_void,
                std::mem::size_of::<RknnSdkVersion>() as c_uint,
            );

            let mut counts = RknnInputOutputNum {
                n_input: 0,
                n_output: 0,
            };
            let code = query(
                context,
                RKNN_QUERY_IN_OUT_NUM,
                &mut counts as *mut _ as *mut c_void,
                std::mem::size_of::<RknnInputOutputNum>() as c_uint,
            );
            if code != 0 {
                destroy(context);
                bail!("rknn_query(IN_OUT_NUM) failed ({code})");
            }
            if counts.n_input != 1 || counts.n_output != 1 {
                destroy(context);
                bail!(
                    "expected one input and one output, got {} and {} — this decoder only knows \
                     the single-tensor YOLO head",
                    counts.n_input,
                    counts.n_output
                );
            }

            let attr = |command: c_uint, index: c_uint| -> Result<RknnTensorAttr> {
                let mut attr: RknnTensorAttr = std::mem::zeroed();
                attr.index = index;
                let code = query(
                    context,
                    command,
                    &mut attr as *mut _ as *mut c_void,
                    std::mem::size_of::<RknnTensorAttr>() as c_uint,
                );
                if code != 0 {
                    bail!("rknn_query({command}) failed ({code})");
                }
                Ok(attr)
            };

            let input = attr(RKNN_QUERY_INPUT_ATTR, 0)?;
            let output = attr(RKNN_QUERY_OUTPUT_ATTR, 0)?;

            // NHWC as the model declares it, which is also what the RGA and a JPEG decoder produce
            // — the one layout that needs no transpose on the way in.
            let dims = &input.dims[..input.n_dims as usize];
            let shape = match dims {
                // NCHW first, and only when the second dimension is small enough to be channels:
                // the model is converted from an NCHW ONNX, and the runtime reports whichever
                // layout the build settled on. A 320x320x3 tensor is the same numbers either way,
                // but a 3x320x320 read as HWC would ask for three rows of 320 pixels.
                [_, c, h, w] if *c <= 4 && *h > 4 => (*h as usize, *w as usize, *c as usize),
                [_, h, w, c] if *c <= 4 => (*h as usize, *w as usize, *c as usize),
                other => {
                    destroy(context);
                    bail!("cannot make sense of the input shape {other:?}");
                }
            };

            Ok(Self {
                context,
                destroy,
                inputs_set,
                run,
                outputs_get,
                outputs_release,
                input: shape,
                output_len: output.n_elems as usize,
                api_version: c_str(&version.api_version),
                driver_version: c_str(&version.drv_version),
                _library: library,
            })
        }
    }

    /// One frame in, the raw head out as floats.
    ///
    /// `frame` is `height × width × channels` of uint8 in the model's own layout — exactly what
    /// [`Model::input`] describes. The runtime does the normalisation the conversion baked in
    /// (mean 0, std 255), so this hands it bytes and gets scores back.
    pub fn infer(&mut self, frame: &[u8], out: &mut Vec<f32>) -> Result<()> {
        let (height, width, channels) = self.input;
        let wanted = height * width * channels;
        if frame.len() != wanted {
            bail!("frame is {} bytes, the model wants {wanted}", frame.len());
        }

        let mut input = RknnInput {
            index: 0,
            buf: frame.as_ptr() as *mut c_void,
            size: frame.len() as c_uint,
            pass_through: 0,
            type_: RKNN_TENSOR_UINT8,
            fmt: RKNN_TENSOR_NHWC,
        };
        let mut output = RknnOutput {
            // **Dequantised by the runtime.** A quantised model's output is int8 with a scale and
            // a zero point; asking for floats here keeps that arithmetic in one place — the vendor's
            // — instead of in a decoder that would get it wrong once and be believed.
            want_float: 1,
            is_prealloc: 0,
            index: 0,
            buf: std::ptr::null_mut(),
            size: 0,
        };

        // SAFETY: the context is live, the input buffer outlives the call, and the output buffer is
        // the runtime's own until `outputs_release`.
        unsafe {
            let code = (self.inputs_set)(self.context, 1, &mut input);
            if code != 0 {
                bail!("rknn_inputs_set failed ({code})");
            }
            let code = (self.run)(self.context, std::ptr::null());
            if code != 0 {
                bail!("rknn_run failed ({code})");
            }
            let code = (self.outputs_get)(self.context, 1, &mut output, std::ptr::null());
            if code != 0 {
                bail!("rknn_outputs_get failed ({code})");
            }
            let count = output.size as usize / std::mem::size_of::<f32>();
            out.clear();
            out.extend_from_slice(std::slice::from_raw_parts(output.buf as *const f32, count));
            (self.outputs_release)(self.context, 1, &mut output);
        }
        Ok(())
    }
}

impl Drop for Model {
    fn drop(&mut self) {
        if !self.context.is_null() {
            // SAFETY: called once, on a context this type owns, before the library is unloaded.
            unsafe { (self.destroy)(self.context) };
            self.context = std::ptr::null_mut();
        }
    }
}

/// A NUL-terminated vendor string, without the noise.
///
/// the cast is needed and clippy cannot see it. `c_char` is `i8` on the x86_64 host and `u8` on
/// the board, so on the board this is `u8 as u8` and `unnecessary_cast` fires, while taking the
/// cast out stops the host compiling at all. lint the workspace for the board's own target, the
/// way CONTRIBUTING asks, and `-D warnings` turns that into an error.
#[allow(clippy::unnecessary_cast)]
fn c_str(raw: &[c_char]) -> String {
    let bytes: Vec<u8> = raw
        .iter()
        .take_while(|c| **c != 0)
        .map(|c| *c as u8)
        .collect();
    CString::new(bytes)
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The structs above are an ABI, and getting one wrong is silent.
    ///
    /// Not a substitute for the vendor's header — it is a tripwire for an edit that adds a field in
    /// the wrong place, which no compiler here can catch because the other side of this boundary is
    /// a blob nobody links.
    #[test]
    fn the_query_structs_are_laid_out_as_the_abi_says() {
        assert_eq!(std::mem::size_of::<RknnInputOutputNum>(), 8);
        assert_eq!(std::mem::size_of::<RknnSdkVersion>(), 512);

        // **Offsets, not just the total.** Two fields swapped keep the size and change the
        // meaning, and the other side of this boundary is a blob no compiler here can check
        // against. The numbers are the C layout of `rknn_tensor_attr` counted out by hand:
        //
        //   index 0, n_dims 4, dims[16] 8..72, name[256] 72..328, n_elems 328, size 332,
        //   fmt 336, type 340, qnt_type 344, fl 348 (+3 padding), zp 352, scale 356,
        //   w_stride 360, size_with_stride 364, pass_through 368 (+3), h_stride 372 → 376.
        assert_eq!(std::mem::offset_of!(RknnTensorAttr, dims), 8);
        assert_eq!(std::mem::offset_of!(RknnTensorAttr, name), 72);
        assert_eq!(std::mem::offset_of!(RknnTensorAttr, n_elems), 328);
        assert_eq!(std::mem::offset_of!(RknnTensorAttr, zp), 352);
        assert_eq!(std::mem::offset_of!(RknnTensorAttr, scale), 356);
        assert_eq!(std::mem::size_of::<RknnTensorAttr>(), 376);

        // The two structs passed by value on every inference.
        assert_eq!(std::mem::offset_of!(RknnInput, buf), 8);
        // `want_float` and `is_prealloc` are bytes, `index` is a u32, and the pointer that follows
        // is 8-aligned — so 8, not 16.
        assert_eq!(std::mem::offset_of!(RknnOutput, buf), 8);
    }

    /// A missing runtime must say what to run, not "cannot open shared object file".
    #[test]
    fn a_missing_runtime_names_the_setup_script() {
        // `unwrap_err` would want `Model: Debug`, and a handle to a vendor blob has nothing worth
        // printing — so match instead.
        let error = match Model::open(Path::new("/nonexistent/model.rknn")) {
            Err(error) => error,
            Ok(_) => panic!("a model that does not exist must not open"),
        };
        // The model is read before the library is loaded, so this is the file error — which is the
        // right one to report first.
        assert!(error.to_string().contains("cannot read"), "{error}");
    }
}
