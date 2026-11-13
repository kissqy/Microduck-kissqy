//! One event-driven owner for the real camera. Signalling stays PLAYING while v4l2 stays NULL.
use std::collections::HashSet;
use std::sync::{Arc, Condvar, Mutex, Weak, mpsc};
use std::time::Duration;

use anyhow::{Context, Result, bail};
use glib::translate::IntoGlib;
use gst::prelude::*;
use gstreamer as gst;

#[derive(Default)]
struct State {
    peers: HashSet<String>,
    readers: usize,
    discovered: bool,
    active: bool,
    error: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use glib::subclass::prelude::*;
    use std::sync::OnceLock;
    use std::sync::atomic::{AtomicUsize, Ordering};

    mod signaller {
        use super::*;
        #[derive(Default)]
        pub struct Signaller {
            pub starts: AtomicUsize,
        }
        #[glib::object_subclass]
        impl ObjectSubclass for Signaller {
            const NAME: &'static str = "MicroduckDemandTestSignaller";
            type Type = super::TestSignaller;
        }
        impl ObjectImpl for Signaller {
            fn signals() -> &'static [glib::subclass::Signal] {
                static SIGNALS: OnceLock<Vec<glib::subclass::Signal>> = OnceLock::new();
                SIGNALS.get_or_init(|| {
                    vec![
                        glib::subclass::Signal::builder("start")
                            .run_last()
                            .return_type::<bool>()
                            .class_handler(|args| {
                                let this = args[0].get::<super::TestSignaller>().unwrap();
                                this.imp().starts.fetch_add(1, Ordering::SeqCst);
                                Some(false.to_value())
                            })
                            .accumulator(|_, _, value| std::ops::ControlFlow::Break(value.clone()))
                            .build(),
                    ]
                })
            }
        }
    }
    glib::wrapper! { pub struct TestSignaller(ObjectSubclass<signaller::Signaller>); }

    struct Rig {
        pipeline: gst::Pipeline,
        source: gst::Element,
        seed_count: Arc<AtomicUsize>,
        count: Arc<AtomicUsize>,
        pts: Arc<Mutex<Vec<gst::ClockTime>>>,
        capture: Capture,
    }
    impl Rig {
        fn new(discovered: bool) -> Self {
            gst::init().unwrap();
            let pipeline = gst::Pipeline::new();
            let source = gst::ElementFactory::make("videotestsrc")
                .property("is-live", true)
                .build()
                .unwrap();
            let sink = gst::ElementFactory::make("fakesink")
                .property("sync", false)
                .property("async", false)
                .build()
                .unwrap();
            pipeline.add_many([&source, &sink]).unwrap();
            let caps = gst::Caps::builder("video/x-raw")
                .field("format", "UYVY")
                .field("width", 64i32)
                .field("height", 48i32)
                .field("framerate", gst::Fraction::new(30, 1))
                .build();
            let (capture, selector) = Capture::build(&pipeline, &source, &caps).unwrap();
            selector.link(&sink).unwrap();
            let count = Arc::new(AtomicUsize::new(0));
            let pts = Arc::new(Mutex::new(Vec::new()));
            let c = count.clone();
            let p = pts.clone();
            source.static_pad("src").unwrap().add_probe(
                gst::PadProbeType::BUFFER,
                move |_, info| {
                    c.fetch_add(1, Ordering::SeqCst);
                    if let Some(gst::PadProbeData::Buffer(buffer)) = info.data.as_ref() {
                        if let Some(pts) = buffer.pts() {
                            p.lock().unwrap().push(pts);
                        }
                    }
                    gst::PadProbeReturn::Ok
                },
            );
            let seed_count = Arc::new(AtomicUsize::new(0));
            let c = seed_count.clone();
            sink.static_pad("sink")
                .unwrap()
                .add_probe(gst::PadProbeType::BUFFER, move |_, _| {
                    c.fetch_add(1, Ordering::SeqCst);
                    gst::PadProbeReturn::Ok
                });
            pipeline.set_state(gst::State::Playing).unwrap();
            let rig = Self {
                pipeline,
                source,
                seed_count,
                count,
                pts,
                capture,
            };
            if discovered {
                rig.discover();
            }
            rig
        }
        fn wait(&self, condition: impl Fn(&State) -> bool) {
            let state = self.capture.0.state.lock().unwrap();
            let (state, _) = self
                .capture
                .0
                .changed
                .wait_timeout_while(state, Duration::from_secs(2), |s| !condition(s))
                .unwrap();
            assert!(condition(&state));
        }
        fn discover(&self) {
            self.capture.0.events.send(Event::Discovered).unwrap();
            self.wait(|s| s.discovered);
        }
        fn sleep(&self) {
            self.wait(|s| !s.active);
        }
        fn frames(&self) -> usize {
            self.count.load(Ordering::SeqCst)
        }
    }
    impl Drop for Rig {
        fn drop(&mut self) {
            let _ = self.pipeline.set_state(gst::State::Null);
        }
    }

    #[test]
    fn boot_and_discovery_keep_real_camera_asleep() {
        let rig = Rig::new(true);
        std::thread::sleep(Duration::from_millis(100));
        assert_eq!(rig.frames(), 0);
        assert_eq!(rig.source.current_state(), gst::State::Null);
        assert_eq!(rig.pipeline.current_state(), gst::State::Playing);
        let seed = rig.seed_count.load(Ordering::SeqCst);
        std::thread::sleep(Duration::from_millis(100));
        assert_eq!(rig.seed_count.load(Ordering::SeqCst), seed);
    }
    #[test]
    fn last_viewer_sleeps_and_can_rejoin_three_times() {
        let rig = Rig::new(true);
        for _ in 0..3 {
            rig.capture.peer("page-a", true);
            assert!(rig.capture.ready());
            std::thread::sleep(Duration::from_millis(100));
            assert!(rig.frames() > 0);
            rig.capture.peer("page-a", false);
            rig.sleep();
            let seen = rig.frames();
            std::thread::sleep(Duration::from_millis(100));
            assert_eq!(rig.frames(), seen);
            assert_eq!(rig.pipeline.current_state(), gst::State::Playing);
        }
    }
    #[test]
    fn one_page_leaving_does_not_sleep_another() {
        let rig = Rig::new(true);
        rig.capture.peer("a", true);
        rig.capture.peer("b", true);
        assert!(rig.capture.ready());
        rig.capture.peer("a", false);
        std::thread::sleep(Duration::from_millis(100));
        assert!(rig.capture.0.state.lock().unwrap().active);
        rig.capture.peer("b", false);
        rig.sleep();
    }
    #[test]
    fn repeated_and_unknown_peer_events_do_not_corrupt_demand() {
        let rig = Rig::new(true);
        rig.capture.peer("a", true);
        rig.capture.peer("a", true);
        assert!(rig.capture.ready());
        rig.capture.peer("unknown", false);
        assert!(rig.capture.0.state.lock().unwrap().active);
        rig.capture.peer("a", false);
        rig.capture.peer("a", false);
        rig.sleep();
    }
    #[test]
    fn snapshot_leases_keep_capture_until_the_last_reader_returns() {
        let rig = Rig::new(true);
        let first = rig.capture.acquire();
        let second = rig.capture.acquire();
        assert!(rig.capture.ready());
        drop(first);
        std::thread::sleep(Duration::from_millis(50));
        assert!(rig.capture.0.state.lock().unwrap().active);
        drop(second);
        rig.sleep();
    }
    #[test]
    fn passive_meter_does_not_wake_capture() {
        let rig = Rig::new(true);
        let capture = rig.capture.clone();
        let (tx, rx) = mpsc::channel();
        let waiter = std::thread::spawn(move || {
            capture.wait_active();
            tx.send(()).unwrap();
        });
        assert!(rx.recv_timeout(Duration::from_millis(100)).is_err());
        assert_eq!(rig.frames(), 0);
        let _lease = rig.capture.acquire();
        assert!(rig.capture.ready());
        rx.recv_timeout(Duration::from_secs(2)).unwrap();
        waiter.join().unwrap();
    }
    #[test]
    fn early_demand_survives_codec_discovery() {
        let rig = Rig::new(false);
        let _lease = rig.capture.acquire();
        std::thread::sleep(Duration::from_millis(50));
        assert_eq!(rig.frames(), 0);
        rig.discover();
        assert!(rig.capture.ready());
    }
    #[test]
    fn resumed_frames_follow_the_running_sink_clock() {
        let rig = Rig::new(true);
        let lease = rig.capture.acquire();
        assert!(rig.capture.ready());
        std::thread::sleep(Duration::from_millis(150));
        drop(lease);
        rig.sleep();
        let old = rig.pts.lock().unwrap().last().copied().unwrap();
        std::thread::sleep(Duration::from_millis(150));
        let _lease = rig.capture.acquire();
        assert!(rig.capture.ready());
        std::thread::sleep(Duration::from_millis(100));
        let values = rig.pts.lock().unwrap();
        assert!(values.last().unwrap() > &old);
        assert!(values.windows(2).all(|pair| pair[1] > pair[0]));
    }
    #[test]
    fn bootstrap_hook_preserves_first_handler_wins_start_action() {
        let rig = Rig::new(false);
        let signaller: TestSignaller = glib::Object::new();
        let other: TestSignaller = glib::Object::new();
        let signal = glib::subclass::SignalId::lookup("start", signaller.type_()).unwrap();
        rig.capture
            .observe_discovery(signaller.upcast_ref(), signal)
            .unwrap();
        let after = Arc::new(AtomicUsize::new(0));
        let count = after.clone();
        signaller.connect("start", true, move |_| {
            count.fetch_add(1, Ordering::SeqCst);
            Some(true.to_value())
        });
        assert!(!other.emit_by_name::<bool>("start", &[]));
        assert!(!rig.capture.0.state.lock().unwrap().discovered);
        assert!(!signaller.emit_by_name::<bool>("start", &[]));
        rig.wait(|s| s.discovered);
        assert_eq!(signaller.imp().starts.load(Ordering::SeqCst), 1);
        assert_eq!(after.load(Ordering::SeqCst), 0);
        let _lease = rig.capture.acquire();
        assert!(rig.capture.ready());
    }
}
impl State {
    fn wanted(&self) -> bool {
        !self.peers.is_empty() || self.readers != 0
    }
}
struct Shared {
    state: Mutex<State>,
    changed: Condvar,
    events: mpsc::Sender<Event>,
    bootstrap_hook: Mutex<Option<EmissionHook>>,
}
enum Event {
    Discovered,
    Demand,
}
#[derive(Clone)]
pub struct Capture(Arc<Shared>);
pub struct Lease(Capture);
impl Drop for Lease {
    fn drop(&mut self) {
        if let Ok(mut state) = self.0.0.state.lock() {
            state.readers = state.readers.saturating_sub(1);
        }
        let _ = self.0.0.events.send(Event::Demand);
    }
}

// The pinned signaller uses a first-handler-wins accumulator. A normal before handler would
// suppress its action; an after handler never runs. An emission hook observes without either.
struct EmissionHook {
    signal: u32,
    hook: libc::c_ulong,
}
impl Drop for EmissionHook {
    fn drop(&mut self) {
        unsafe {
            glib::gobject_ffi::g_signal_remove_emission_hook(self.signal, self.hook);
        }
    }
}
struct HookData {
    signaller: glib::WeakRef<glib::Object>,
    capture: Weak<Shared>,
}
unsafe extern "C" fn observe_start(
    _: *mut glib::gobject_ffi::GSignalInvocationHint,
    count: u32,
    values: *const glib::gobject_ffi::GValue,
    data: glib::ffi::gpointer,
) -> glib::ffi::gboolean {
    let data = unsafe { &*(data as *const HookData) };
    if count != 0 && !values.is_null() {
        if let Some(expected) = data.signaller.upgrade() {
            let actual = unsafe { glib::gobject_ffi::g_value_get_object(values) };
            if actual == expected.as_ptr() {
                if let Some(capture) = data.capture.upgrade() {
                    let _ = capture.events.send(Event::Discovered);
                }
            }
        }
    }
    1
}
unsafe extern "C" fn destroy_hook(data: glib::ffi::gpointer) {
    drop(unsafe { Box::from_raw(data as *mut HookData) });
}

impl Capture {
    pub fn install(
        pipeline: &gst::Pipeline,
        source: &gst::Element,
        caps: &gst::Caps,
        sink: &gst::Element,
    ) -> Result<(Self, gst::Element)> {
        let signaller = sink.property::<glib::Object>("signaller");
        let signal = glib::subclass::SignalId::lookup("start", signaller.type_())
            .context("camera demand needs the signaller start signal")?;
        if signal.query().flags().contains(glib::SignalFlags::NO_HOOKS) {
            bail!("the signaller start signal cannot be observed without changing its action");
        }
        if glib::subclass::SignalId::lookup("consumer-removed", sink.type_()).is_none() {
            bail!("camera demand needs webrtcsink consumer-removed");
        }
        let (capture, selector) = Self::build(pipeline, source, caps)?;
        capture.observe_discovery(&signaller, signal)?;
        Ok((capture, selector))
    }

    fn observe_discovery(
        &self,
        signaller: &glib::Object,
        signal: glib::subclass::SignalId,
    ) -> Result<()> {
        let data = Box::into_raw(Box::new(HookData {
            signaller: signaller.downgrade(),
            capture: Arc::downgrade(&self.0),
        }));
        let signal = signal.into_glib();
        let hook = unsafe {
            glib::gobject_ffi::g_signal_add_emission_hook(
                signal,
                0,
                Some(observe_start),
                data.cast(),
                Some(destroy_hook),
            )
        };
        if hook == 0 {
            unsafe {
                destroy_hook(data.cast());
            }
            bail!("could not observe signaller start");
        }
        *self.0.bootstrap_hook.lock().expect("capture hook") = Some(EmissionHook { signal, hook });
        Ok(())
    }

    fn build(
        pipeline: &gst::Pipeline,
        source: &gst::Element,
        caps: &gst::Caps,
    ) -> Result<(Self, gst::Element)> {
        let selector = gst::ElementFactory::make("input-selector")
            .property("sync-streams", false)
            .build()?;
        let seed = gst::ElementFactory::make("videotestsrc")
            .property("is-live", true)
            .property_from_str("pattern", "black")
            .build()?;
        let seed_caps = gst::ElementFactory::make("capsfilter")
            .property("caps", caps)
            .build()?;
        pipeline.add_many([&selector, &seed, &seed_caps])?;
        seed.link(&seed_caps)?;
        let camera_pad = selector
            .request_pad_simple("sink_%u")
            .context("camera selector pad")?;
        let seed_pad = selector
            .request_pad_simple("sink_%u")
            .context("discovery selector pad")?;
        source
            .static_pad("src")
            .context("camera source pad")?
            .link(&camera_pad)?;
        seed_caps
            .static_pad("src")
            .context("discovery source pad")?
            .link(&seed_pad)?;
        selector.set_property("active-pad", &seed_pad);
        // No real sensor frames are needed to discover the codec and register the producer.
        source.set_locked_state(true);
        let (events, receiver) = mpsc::channel();
        let capture = Self(Arc::new(Shared {
            state: Mutex::new(State::default()),
            changed: Condvar::new(),
            events,
            bootstrap_hook: Mutex::new(None),
        }));
        capture.publish();
        let weak = Arc::downgrade(&capture.0);
        let source = source.clone();
        let selected = selector.clone();
        std::thread::Builder::new()
            .name("camera-demand".into())
            .spawn(move || {
                let mut discovered = false;
                while let Ok(event) = receiver.recv() {
                    let Some(shared) = weak.upgrade() else {
                        break;
                    };
                    if matches!(event, Event::Discovered) && !discovered {
                        seed.set_locked_state(true);
                        if let Err(error) = seed.set_state(gst::State::Null) {
                            tracing::warn!(%error, "could not stop codec discovery source");
                        }
                        discovered = true;
                        if let Ok(mut state) = shared.state.lock() {
                            state.discovered = true;
                        }
                        shared.changed.notify_all();
                    }
                    if !discovered {
                        continue;
                    }
                    let (wanted, active) = match shared.state.lock() {
                        Ok(state) => (state.wanted(), state.active),
                        Err(_) => break,
                    };
                    if wanted == active {
                        continue;
                    }
                    let result = if wanted {
                        selected.set_property("active-pad", &camera_pad);
                        if let Some(base_time) = selected.base_time() {
                            source.set_base_time(base_time);
                        }
                        let _ = source.set_clock(selected.clock().as_ref());
                        source
                            .sync_state_with_parent()
                            .map_err(|error| error.to_string())
                    } else {
                        // Select the dormant branch before v4l2's flush so signalling stays online.
                        selected.set_property("active-pad", &seed_pad);
                        source
                            .set_state(gst::State::Null)
                            .map(|_| ())
                            .map_err(|error| error.to_string())
                    };
                    if let Ok(mut state) = shared.state.lock() {
                        match result {
                            Ok(()) => {
                                state.active = wanted;
                                state.error = None;
                            }
                            Err(error) => {
                                state.error = Some(error);
                            }
                        }
                    }
                    shared.changed.notify_all();
                    let capture = Capture(shared);
                    capture.publish();
                    tracing::info!(active = wanted, "camera demand transition");
                }
                let _ = source.set_state(gst::State::Null);
                let _ = seed.set_state(gst::State::Null);
            })
            .context("could not start camera demand owner")?;
        Ok((capture, selector))
    }

    fn publish(&self) {
        let Ok(state) = self.0.state.lock() else {
            return;
        };
        let payload = serde_json::json!({"active":state.active,
            "status": if state.error.is_some() {"error"} else if state.active {"active"} else {"asleep"},
            "error":state.error});
        let path = std::path::Path::new("/run/mediad/capture.json");
        let temporary = path.with_extension("json.tmp");
        if let Ok(bytes) = serde_json::to_vec(&payload) {
            let _ =
                std::fs::write(&temporary, bytes).and_then(|_| std::fs::rename(&temporary, path));
        }
    }

    pub fn peer(&self, peer: &str, present: bool) {
        let changed = if let Ok(mut state) = self.0.state.lock() {
            let changed = if present {
                state.peers.insert(peer.into())
            } else {
                state.peers.remove(peer)
            };
            if changed && present && !state.active {
                state.error = None;
            }
            changed
        } else {
            false
        };
        if changed {
            let _ = self.0.events.send(Event::Demand);
        }
    }
    pub fn acquire(&self) -> Lease {
        if let Ok(mut state) = self.0.state.lock() {
            state.readers += 1;
            if !state.active {
                state.error = None;
            }
        }
        let _ = self.0.events.send(Event::Demand);
        Lease(self.clone())
    }
    pub fn ready(&self) -> bool {
        let Ok(state) = self.0.state.lock() else {
            return false;
        };
        self.0
            .changed
            .wait_timeout_while(state, Duration::from_secs(2), |state| {
                !state.active && state.error.is_none()
            })
            .map(|(state, _)| state.active)
            .unwrap_or(false)
    }
    /// AE and detection are passive: parked without a timer until somebody needs the camera.
    pub fn wait_active(&self) {
        if let Ok(state) = self.0.state.lock() {
            drop(self.0.changed.wait_while(state, |state| !state.active));
        }
    }
}
