//! One bounded, operator-started intent clip. No torque, policy or mode changes.
//! Capture observes successful IPC writes; playback is advanced by padd's loop.
use duck_ipc_proto as proto;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    cell::RefCell,
    fs,
    io::{BufRead, BufReader, Read, Write},
    os::unix::net::UnixStream,
    path::{Path, PathBuf},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    thread,
    time::{Duration, Instant},
};

const MAX_NS: u64 = 120_000_000_000;
const MAX_BYTES: usize = 4 * 1024 * 1024;
const MAX_EVENTS: usize = 30_000;
const CLICK_WINDOW: Duration = Duration::from_millis(350);
const MAX_LATE: Duration = Duration::from_millis(100);
pub const EMOTIONS: [&str; 13] = [
    "sad",
    "devastated",
    "curious",
    "mmh",
    "yes",
    "yes_fast",
    "no",
    "angry",
    "excited",
    "laugh",
    "mock",
    "defiant",
    "impatient",
];

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Intent {
    pub method: String,
    pub params: Value,
    pub request: bool,
}
impl Intent {
    fn from_call(call: &proto::Call, request: bool) -> Self {
        let wire = proto::Request::notify(call);
        Self {
            method: wire.method,
            params: wire.params.unwrap_or(json!({})),
            request,
        }
    }
    pub fn call(&self) -> Result<proto::Call, String> {
        let wire: proto::Request = serde_json::from_value(
            json!({"jsonrpc":"2.0","method":self.method,"params":self.params}),
        )
        .map_err(|e| e.to_string())?;
        wire.as_call().map_err(|e| e.to_string())
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Frame {
    pub at_ns: u64,
    pub intents: Vec<Intent>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Clip {
    schema: String,
    pub duration_ns: u64,
    start_sitting: bool,
    identity: Value,
    skills: Vec<String>,
    pub frames: Vec<Frame>,
}
fn allowed(call: &proto::Call, request: bool, skills: &[String]) -> bool {
    fn range(v: f64, a: f64, b: f64) -> bool {
        v.is_finite() && v >= a && v <= b
    }
    match call {
        proto::Call::RobotMove(p) => {
            !request && range(p.vx, -0.6, 0.6) && range(p.vy, -0.3, 0.3) && range(p.vyaw, -1.5, 1.5)
        }
        proto::Call::RobotHead(p) => {
            !request
                && [p.neck_pitch, p.head_pitch, p.head_yaw, p.head_roll]
                    .into_iter()
                    .all(|v| range(v, -3.2, 3.2))
        }
        proto::Call::RobotPose(p) => {
            !request
                && range(p.z, -0.025, 0.01)
                && range(p.pitch, -0.2618, 0.2618)
                && range(p.roll, -0.2618, 0.2618)
        }
        proto::Call::RobotMouth(p) => !request && range(p.open, 0., 1.),
        proto::Call::RobotSound(p) => {
            !request && matches!(p.tag, proto::SoundTag::Chirp | proto::SoundTag::Wheee)
        }
        proto::Call::RobotDo(p) => {
            request
                && !management(call)
                && p.skill != "emotion_next"
                && !p.skill.starts_with("emotion_cancel_")
                && p.skill != "emotion_status"
                && skills.contains(&p.skill)
        }
        _ => false,
    }
}
fn management(call: &proto::Call) -> bool {
    matches!(
        call,
        proto::Call::RobotInit
            | proto::Call::RobotEnable(_)
            | proto::Call::RobotRelax
            | proto::Call::RobotShutdown
            | proto::Call::RobotRebootMotors(_)
            | proto::Call::RobotSetMode(_)
    ) || matches!(call,proto::Call::RobotDo(p) if ["stand_test","roller_stand","home","init","enable","relax","shutdown","reboot","reboot_motors"].contains(&p.skill.as_str()))
}
fn validate(clip: &Clip) -> Result<(), String> {
    if clip.schema != "microduck-pad-clip/v1"
        || clip.duration_ns == 0
        || clip.duration_ns > MAX_NS
        || clip.frames.is_empty()
        || clip.frames.len() > MAX_EVENTS
        || !clip.identity.is_object()
        || clip.skills.len() > 128
        || clip.identity["skills"] != json!(clip.skills)
    {
        return Err("录制文件格式或时长无效".into());
    }
    let mut previous = None;
    let mut events = 0;
    for frame in &clip.frames {
        if frame.at_ns > clip.duration_ns
            || previous.is_some_and(|at| frame.at_ns <= at)
            || frame.intents.is_empty()
            || frame.intents.len() > 8
        {
            return Err("录制时间顺序或帧无效".into());
        }
        previous = Some(frame.at_ns);
        events += frame.intents.len();
        if events > MAX_EVENTS {
            return Err("录制事件过多".into());
        }
        for intent in &frame.intents {
            if !allowed(&intent.call()?, intent.request, &clip.skills) {
                return Err("录制含不允许的指令或超范围参数".into());
            }
        }
    }
    if serde_json::to_vec(clip).map_err(|e| e.to_string())?.len() > MAX_BYTES {
        return Err("录制超过4MiB".into());
    }
    Ok(())
}
fn load(path: &Path) -> Result<Clip, String> {
    let f = fs::File::open(path).map_err(|e| e.to_string())?;
    if f.metadata().map_err(|e| e.to_string())?.len() > MAX_BYTES as u64 {
        return Err("录制超过4MiB".into());
    }
    let mut bytes = Vec::new();
    f.take(MAX_BYTES as u64 + 1)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() > MAX_BYTES {
        return Err("录制超过4MiB".into());
    }
    let clip = serde_json::from_slice(&bytes).map_err(|e| format!("录制文件损坏：{e}"))?;
    validate(&clip)?;
    Ok(clip)
}
fn save(path: &Path, clip: &Clip, cancel: &AtomicBool) -> Result<(), String> {
    validate(clip)?;
    let parent = path.parent().ok_or("没有保存目录")?;
    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    let tmp = path.with_extension(format!("{}.tmp", std::process::id()));
    let result = (|| {
        let mut file = fs::File::create(&tmp).map_err(|e| e.to_string())?;
        serde_json::to_writer(&mut file, clip).map_err(|e| e.to_string())?;
        file.flush()
            .and_then(|_| file.sync_all())
            .map_err(|e| e.to_string())?;
        drop(file);
        if cancel.load(Ordering::Acquire) {
            return Err("本次保存已取消，保留上次录制".into());
        }
        fs::rename(&tmp, path).map_err(|e| e.to_string())?;
        // Rename is the commit point. A directory-sync failure cannot honestly
        // be reported as though the previous file still existed.
        if let Ok(dir) = fs::File::open(parent) {
            let _ = dir.sync_all();
        }
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(tmp);
    }
    result
}

struct Capture {
    started: Instant,
    clip: Clip,
    bytes: usize,
    events: usize,
    last_do: Option<(Instant, String, Option<u64>)>,
    seen_skill: bool,
    next_emotion: usize,
}
#[derive(Default)]
struct CaptureSlot {
    capture: Option<Capture>,
    error: Option<String>,
}
thread_local! { static CAPTURE:RefCell<CaptureSlot> = RefCell::new(CaptureSlot::default()); }
pub fn recording() -> bool {
    CAPTURE.with(|c| c.borrow().capture.is_some())
}
pub fn next_emotion() -> String {
    CAPTURE.with(|c| {
        let c = c.borrow();
        format!(
            "emotion_{}",
            EMOTIONS[c.capture.as_ref().map_or(0, |s| s.next_emotion) % 13]
        )
    })
}
pub fn emotion_accepted() {
    CAPTURE.with(|c| {
        if let Some(s) = c.borrow_mut().capture.as_mut() {
            s.next_emotion = (s.next_emotion + 1) % 13;
        }
    });
}
pub fn before_send(call: &proto::Call) {
    // Management is a boundary even when robotd later refuses it.
    if management(call) {
        CAPTURE.with(|s| {
            let mut s = s.borrow_mut();
            if s.capture.take().is_some() {
                s.error = Some("管理操作已取消本次录制，保留上次文件".into());
            }
        });
    }
}
pub fn observe(calls: &[proto::Call], request: bool, written: Instant) {
    CAPTURE.with(|cell| {
        let mut slot = cell.borrow_mut();
        if slot.capture.is_none() {
            return;
        }
        if calls.iter().any(management) {
            slot.capture = None;
            slot.error = Some("管理操作已取消本次录制，保留上次文件".into());
            return;
        }
        let s = slot.capture.as_mut().unwrap();
        let mut intents = Vec::new();
        for call in calls {
            // Read-only traffic and unacknowledged one-shot notifications do not
            // become movement events. Only the recording X path asks for ACKs.
            if matches!(call, proto::Call::RobotDo(_)) && !request {
                continue;
            }
            if allowed(call, request, &s.clip.skills) {
                if let proto::Call::RobotDo(p) = call {
                    s.last_do = Some((written, p.skill.clone(), None));
                    s.seen_skill = false;
                }
                intents.push(Intent::from_call(call, request));
            } else if matches!(
                call,
                proto::Call::RobotMove(_)
                    | proto::Call::RobotHead(_)
                    | proto::Call::RobotPose(_)
                    | proto::Call::RobotMouth(_)
                    | proto::Call::RobotSound(_)
                    | proto::Call::RobotDo(_)
            ) {
                slot.capture = None;
                slot.error = Some("遇到不支持或超范围指令，保留上次录制".into());
                return;
            }
        }
        if intents.is_empty() {
            return;
        }
        let elapsed = written
            .saturating_duration_since(s.started)
            .as_nanos()
            .min(u64::MAX as u128) as u64;
        let at_ns = elapsed.max(
            s.clip
                .frames
                .last()
                .map_or(0, |f| f.at_ns.saturating_add(1)),
        );
        let frame = Frame { at_ns, intents };
        s.bytes += serde_json::to_vec(&frame).map_or(MAX_BYTES, |b| b.len());
        s.events += frame.intents.len();
        if at_ns >= MAX_NS || s.bytes > MAX_BYTES - 4096 || s.events > MAX_EVENTS {
            slot.capture = None;
            slot.error = Some("达到120秒/4MiB/事件上限，本次未覆盖上次录制".into());
            return;
        }
        s.clip.frames.push(frame);
    });
}

pub fn observe_request(call: &proto::Call, written: Instant, result: Option<&Value>) {
    observe(std::slice::from_ref(call), true, written);
    CAPTURE.with(|s| {
        if let Some(c) = s.borrow_mut().capture.as_mut() {
            if let Some((_, _, generation)) = c.last_do.as_mut() {
                if matches!(call,proto::Call::RobotDo(p) if p.skill.starts_with("emotion_")) {
                    *generation = result.and_then(|v| v["request_id"].as_u64());
                }
            }
        }
    });
}

#[derive(Clone)]
struct Snapshot {
    state: Value,
    policies: Value,
    health: Value,
    skills: Vec<String>,
    expressions: Vec<String>,
    received: Instant,
    probed: Instant,
    emotion: Value,
    emotion_at: Instant,
}
impl Snapshot {
    fn fresh(&self, now: Instant) -> bool {
        self.fresh_at(now, proto::clock::monotonic_ns())
    }
    fn fresh_at(&self, now: Instant, ns: u64) -> bool {
        let t = self.state["t_ns"].as_u64().unwrap_or(0);
        now.duration_since(self.received) < Duration::from_millis(350)
            && now.duration_since(self.probed) < Duration::from_millis(350)
            && t > 0
            && ns >= t
            && ns - t < 350_000_000
            && self.health["healthy"] == true
            && self.health["imu"]["ready"] == true
            && self.health["imu"]["consecutive_stale_blocks"]
                .as_u64()
                .unwrap_or(0)
                < proto::ImuHealth::FROZEN_RUN as u64
            && self.policies["homed"] == true
            && self.policies["enabled"] == true
            && self.state["safety"]["limp"] == false
            && !matches!(
                self.state["policy"].as_str(),
                None | Some("" | "held" | "home" | "off")
            )
    }
    fn idle(&self) -> bool {
        matches!(
            self.state["policy"].as_str(),
            Some("walk" | "stand" | "sit")
        ) && !matches!(self.emotion["phase"].as_str(), Some("pending" | "playing"))
    }
    fn sitting(&self) -> Option<bool> {
        self.policies["sitting"].as_bool()
    }
    fn identity(&self) -> Value {
        let slots = self.policies["slots"]
            .as_array()
            .map(|slots| {
                slots
                    .iter()
                    .map(|s| json!({"slot":s["slot"],"path":s["path"]}))
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default();
        json!({"mode":self.policies["mode"],"slots":slots,"skills":self.skills})
    }
}
struct Monitor {
    value: Arc<Mutex<Option<Snapshot>>>,
    stop: Arc<AtomicBool>,
}
impl Monitor {
    fn start(socket: PathBuf) -> Self {
        let value = Arc::new(Mutex::new(None));
        let stop = Arc::new(AtomicBool::new(false));
        let v = value.clone();
        let end = stop.clone();
        thread::spawn(move || {
            let _ = monitor(socket, v.clone(), end);
            *v.lock().unwrap() = None;
        });
        Self { value, stop }
    }
    #[cfg(test)]
    fn from_stream(stream: UnixStream) -> Self {
        let value = Arc::new(Mutex::new(None));
        let stop = Arc::new(AtomicBool::new(false));
        let v = value.clone();
        let end = stop.clone();
        thread::spawn(move || {
            let _ = monitor_stream(stream, v.clone(), end);
            *v.lock().unwrap() = None;
        });
        Self { value, stop }
    }
    fn get(&self) -> Option<Snapshot> {
        self.value.lock().unwrap().clone()
    }
}
impl Drop for Monitor {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Release);
    }
}
struct Reader {
    reader: BufReader<UnixStream>,
    id: u64,
    latest: Option<(Value, Instant)>,
}
impl Reader {
    fn line(&mut self) -> Result<Value, String> {
        let mut l = String::new();
        if self.reader.read_line(&mut l).map_err(|e| e.to_string())? == 0 {
            return Err("状态连接关闭".into());
        }
        let v: Value = serde_json::from_str(&l).map_err(|e| e.to_string())?;
        if v["method"] == "robot.state" {
            let state = v["params"].clone();
            if self
                .latest
                .as_ref()
                .is_none_or(|(old, _)| state["t_ns"].as_u64() > old["t_ns"].as_u64())
            {
                self.latest = Some((state, Instant::now()));
            }
        }
        Ok(v)
    }
    fn call(&mut self, call: proto::Call) -> Result<Value, String> {
        self.id += 1;
        let id = self.id;
        serde_json::to_writer(
            self.reader.get_mut(),
            &proto::Request::call(proto::Id::Number(id), &call),
        )
        .map_err(|e| e.to_string())?;
        self.reader
            .get_mut()
            .write_all(b"\n")
            .map_err(|e| e.to_string())?;
        let until = Instant::now() + Duration::from_millis(250);
        while Instant::now() < until {
            let v = self.line()?;
            if v["id"] == id {
                if !v["error"].is_null() {
                    return Err("状态查询被拒绝".into());
                }
                return Ok(v["result"].clone());
            }
        }
        Err("状态查询超时".into())
    }
}
fn monitor(
    socket: PathBuf,
    value: Arc<Mutex<Option<Snapshot>>>,
    stop: Arc<AtomicBool>,
) -> Result<(), String> {
    let stream = UnixStream::connect(socket).map_err(|e| e.to_string())?;
    monitor_stream(stream, value, stop)
}
fn monitor_stream(
    stream: UnixStream,
    value: Arc<Mutex<Option<Snapshot>>>,
    stop: Arc<AtomicBool>,
) -> Result<(), String> {
    stream
        .set_read_timeout(Some(Duration::from_millis(250)))
        .map_err(|e| e.to_string())?;
    stream
        .set_write_timeout(Some(Duration::from_millis(250)))
        .map_err(|e| e.to_string())?;
    let mut r = Reader {
        reader: BufReader::new(stream),
        id: 0,
        latest: None,
    };
    let catalog = r.call(proto::Call::RobotSkills)?;
    let mut skills: Vec<String> = catalog["skills"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|s| s["name"].as_str().map(str::to_owned))
        .collect();
    skills.extend(
        catalog["built_in"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(|s| s.as_str().map(str::to_owned)),
    );
    let expressions: Vec<String> = catalog["expressions"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|e| {
            e["name"]
                .as_str()
                .filter(|n| EMOTIONS.contains(n))
                .map(|n| format!("emotion_{n}"))
        })
        .collect();
    skills.extend(expressions.iter().cloned());
    skills.sort();
    skills.dedup();
    r.call(proto::Call::RobotSubscribe(proto::SubscribeParams {
        hz: Some(10),
    }))?;
    while !stop.load(Ordering::Acquire) {
        let policies = r.call(proto::Call::RobotPolicies)?;
        let health = r.call(proto::Call::RobotHealth)?;
        let emotion = r.call(proto::Call::RobotDo(proto::DoParams {
            skill: "emotion_status".into(),
        }))?;
        let probed = Instant::now();
        let prior = r
            .latest
            .as_ref()
            .and_then(|(s, _)| s["t_ns"].as_u64())
            .unwrap_or(0);
        while r
            .latest
            .as_ref()
            .is_none_or(|(s, _)| s["t_ns"].as_u64().unwrap_or(0) <= prior)
        {
            r.line()?;
            if stop.load(Ordering::Acquire) {
                return Ok(());
            }
        }
        let (state, received) = r.latest.clone().unwrap();
        *value.lock().unwrap() = Some(Snapshot {
            state,
            policies,
            health,
            skills: skills.clone(),
            expressions: expressions.clone(),
            received,
            probed,
            emotion,
            emotion_at: probed,
        });
    }
    Ok(())
}

enum Job {
    Load(u64),
    Save(u64, Clip, Arc<AtomicBool>),
    Report(Value),
}
enum Reply {
    Loaded(u64, Result<Clip, String>),
    Saved(u64, Result<Clip, String>),
}
struct Worker {
    jobs: mpsc::SyncSender<Job>,
    replies: mpsc::Receiver<Reply>,
}
impl Worker {
    fn start(path: PathBuf, report: PathBuf) -> Self {
        let (jobs, rx) = mpsc::sync_channel(4);
        let (tx, replies) = mpsc::channel();
        thread::spawn(move || {
            while let Ok(job) = rx.recv() {
                match job {
                    Job::Load(id) => {
                        let _ = tx.send(Reply::Loaded(id, load(&path)));
                    }
                    Job::Save(id, clip, cancel) => {
                        let result = save(&path, &clip, &cancel).map(|_| clip);
                        let _ = tx.send(Reply::Saved(id, result));
                    }
                    Job::Report(v) => {
                        if let Some(parent) = report.parent() {
                            let _ = fs::create_dir_all(parent);
                        }
                        let tmp = report.with_extension("json.tmp");
                        if let Ok(bytes) = serde_json::to_vec(&v) {
                            if fs::write(&tmp, bytes).is_ok() {
                                let _ = fs::rename(&tmp, &report);
                            }
                        }
                    }
                }
            }
        });
        Self { jobs, replies }
    }
}
#[derive(Clone, Copy, PartialEq)]
enum Phase {
    Idle,
    Pending,
    Recording,
    Saving,
    Playing,
    Error,
}
impl Phase {
    fn name(self) -> &'static str {
        match self {
            Self::Idle => "idle",
            Self::Pending => "pending",
            Self::Recording => "recording",
            Self::Saving => "saving",
            Self::Playing => "playing",
            Self::Error => "error",
        }
    }
}
#[derive(Clone, Copy)]
enum Goal {
    Record,
    Play,
}
#[derive(Default)]
struct Click {
    down: Option<Instant>,
    first: Option<Instant>,
}
impl Click {
    fn press(&mut self, now: Instant) {
        self.down.get_or_insert(now);
    }
    fn release(&mut self, now: Instant) -> Option<Goal> {
        let down = self.down.take()?;
        if now.duration_since(down) > Duration::from_millis(600) {
            self.first = None;
            return None;
        }
        if self
            .first
            .is_some_and(|first| now.duration_since(first) <= CLICK_WINDOW)
        {
            self.first = None;
            Some(Goal::Play)
        } else {
            self.first = Some(now);
            None
        }
    }
    fn single(&mut self, now: Instant) -> bool {
        if self.down.is_none()
            && self
                .first
                .is_some_and(|first| now.duration_since(first) >= CLICK_WINDOW)
        {
            self.first = None;
            true
        } else {
            false
        }
    }
}
struct Player {
    clip: Clip,
    began: Instant,
    index: usize,
}
impl Player {
    fn due(&mut self, now: Instant) -> Result<Vec<Frame>, String> {
        let elapsed = now.duration_since(self.began);
        let ns = elapsed.as_nanos() as u64;
        let mut out = Vec::new();
        while let Some(frame) = self.clip.frames.get(self.index) {
            if frame.at_ns > ns {
                break;
            }
            if ns - frame.at_ns >= MAX_LATE.as_nanos() as u64 {
                return Err("回放调度落后100ms，已停止".into());
            }
            out.push(frame.clone());
            self.index += 1;
        }
        Ok(out)
    }
    fn done(&self, now: Instant) -> bool {
        self.index == self.clip.frames.len()
            && now.duration_since(self.began).as_nanos() >= self.clip.duration_ns as u128
    }
}
pub struct Recorder {
    socket: PathBuf,
    phase: Phase,
    reason: String,
    monitor: Option<Monitor>,
    worker: Worker,
    last: Option<Clip>,
    player: Option<Player>,
    click: Click,
    pending: Option<(Goal, Instant)>,
    generation: u64,
    io_pending: bool,
    save_cancel: Option<Arc<AtomicBool>>,
    cleanup: bool,
    changed: bool,
    last_report: Instant,
    started: Instant,
    expression_request: Option<u64>,
    cancel_expression: bool,
    saving_duration_ms: Option<u64>,
}
impl Recorder {
    pub fn new(socket: PathBuf) -> Self {
        Self::with_paths(
            socket,
            "/var/lib/padd/last.json".into(),
            "/run/padd/recorder.json".into(),
        )
    }
    pub(super) fn with_paths(socket: PathBuf, path: PathBuf, report: PathBuf) -> Self {
        let worker = Worker::start(path, report);
        let _ = worker.jobs.try_send(Job::Load(0));
        Self {
            socket,
            phase: Phase::Idle,
            reason: "尚未开始录制".into(),
            monitor: None,
            worker,
            last: None,
            player: None,
            click: Click::default(),
            pending: None,
            generation: 0,
            io_pending: false,
            save_cancel: None,
            cleanup: false,
            changed: true,
            last_report: Instant::now(),
            started: Instant::now(),
            expression_request: None,
            cancel_expression: false,
            saving_duration_ms: None,
        }
    }
    pub fn busy(&self) -> bool {
        matches!(
            self.phase,
            Phase::Pending | Phase::Recording | Phase::Saving | Phase::Playing
        )
    }
    pub fn playing(&self) -> bool {
        self.phase == Phase::Playing
    }
    pub fn handoff_pending(&self) -> bool {
        self.cleanup
    }
    #[cfg(test)]
    pub fn is_recording(&self) -> bool {
        self.phase == Phase::Recording
    }
    fn set(&mut self, phase: Phase, reason: impl Into<String>) {
        self.phase = phase;
        self.reason = reason.into();
        self.changed = true;
    }
    fn ensure_monitor(&mut self) {
        if self.monitor.is_none() {
            self.monitor = Some(Monitor::start(self.socket.clone()));
        }
    }
    pub fn logo_press(&mut self, now: Instant) {
        if self.phase != Phase::Saving {
            self.click.press(now);
        }
    }
    pub fn logo_release(&mut self, now: Instant, neutral: bool) {
        if self.phase == Phase::Playing {
            self.click = Click::default();
            self.abort("已取消回放");
            return;
        }
        if self.phase == Phase::Saving {
            return;
        }
        if self.phase == Phase::Recording {
            if self.click.down.take().is_some_and(|down| {
                now.saturating_duration_since(down) <= Duration::from_millis(600)
            }) {
                self.stop_recording(now, neutral);
            }
            return;
        }
        if matches!(self.click.release(now), Some(Goal::Play)) {
            self.generation += 1;
            self.pending = Some((Goal::Play, now));
            self.io_pending = true;
            if self
                .worker
                .jobs
                .try_send(Job::Load(self.generation))
                .is_err()
            {
                self.abort("文件工作队列忙，未开始回放");
                return;
            }
            self.ensure_monitor();
            self.set(Phase::Pending, "正在检查上次录制与机器人状态");
        } else if self.click.first.is_some() {
            self.ensure_monitor();
            self.set(Phase::Pending, "等待350ms单/双击判定");
        } else if self.phase == Phase::Pending && self.pending.is_none() {
            self.monitor = None;
            self.set(Phase::Idle, "Logo长按已忽略");
        }
    }
    fn stop_recording(&mut self, now: Instant, neutral: bool) {
        let snap = self.monitor.as_ref().and_then(Monitor::get);
        let stopped = CAPTURE.with(|slot| {
            let mut slot = slot.borrow_mut();
            let s = slot.capture.as_mut().ok_or("录制状态丢失")?;
            let snap = snap
                .as_ref()
                .filter(|s| s.fresh(now))
                .ok_or("等待新的机器人反馈后再按保存")?;
            if !neutral || !snap.idle() || s.last_do.is_some() {
                return Err("请松开摇杆并等动作/表情结束后，再按保存");
            }
            let mut capture = slot.capture.take().unwrap();
            capture.clip.duration_ns = now.duration_since(capture.started).as_nanos() as u64;
            Ok(capture.clip)
        });
        match stopped {
            Err(reason) => {
                self.reason = reason.into();
                self.changed = true;
            }
            Ok(clip) => {
                if let Err(e) = validate(&clip) {
                    self.abort(&e);
                    return;
                }
                self.generation += 1;
                self.saving_duration_ms = Some(clip.duration_ns / 1_000_000);
                let cancel = Arc::new(AtomicBool::new(false));
                self.save_cancel = Some(cancel.clone());
                if self
                    .worker
                    .jobs
                    .try_send(Job::Save(self.generation, clip, cancel))
                    .is_err()
                {
                    self.abort("文件工作队列忙，本次未覆盖上次录制");
                    return;
                }
                self.monitor = None;
                self.set(Phase::Saving, "正在保存，成功后覆盖上次录制");
            }
        }
    }
    pub fn abort(&mut self, reason: &str) {
        // Saving is already authorized and has no control ownership. Do not race
        // its atomic commit with a manual safety operation or drop its reply.
        if self.phase == Phase::Saving {
            return;
        }
        if self.phase == Phase::Playing {
            self.cleanup = true;
            self.cancel_expression = true;
        }
        if let Some(cancel) = self.save_cancel.take() {
            cancel.store(true, Ordering::Release);
        }
        self.generation += 1;
        self.io_pending = false;
        self.player = None;
        self.pending = None;
        self.click = Click::default();
        self.monitor = None;
        CAPTURE.with(|s| {
            let mut s = s.borrow_mut();
            s.capture = None;
            s.error = None;
        });
        self.set(Phase::Error, reason);
    }
    pub fn take_cleanup(&mut self) -> bool {
        std::mem::take(&mut self.cleanup)
    }
    pub fn replay_failed(&mut self, reason: &str) {
        self.abort(reason);
    }
    pub fn frame_late(&self, at_ns: u64, now: Instant) -> bool {
        now.saturating_duration_since(self.started)
            .as_nanos()
            .saturating_sub(at_ns as u128)
            >= MAX_LATE.as_nanos()
    }
    pub fn replay_accepted(&mut self, call: &proto::Call, answer: Option<&proto::Response>) {
        if matches!(call,proto::Call::RobotDo(p) if p.skill.starts_with("emotion_")) {
            self.expression_request = answer
                .and_then(|a| a.result.as_ref())
                .and_then(|v| v["request_id"].as_u64());
        }
    }
    pub fn take_expression_cancel(&mut self) -> Option<u64> {
        if std::mem::take(&mut self.cancel_expression) {
            self.expression_request.take()
        } else {
            self.expression_request = None;
            None
        }
    }
    pub fn tick(
        &mut self,
        now: Instant,
        manual_ready: bool,
        ai_active: bool,
        mouth_active: bool,
    ) -> Vec<Frame> {
        while let Ok(reply) = self.worker.replies.try_recv() {
            match reply {
                Reply::Loaded(0, result) => {
                    if let Ok(clip) = result {
                        self.last = Some(clip);
                        self.changed = true;
                    }
                }
                Reply::Loaded(id, result) if id == self.generation => {
                    self.io_pending = false;
                    match result {
                        Ok(clip) => self.last = Some(clip),
                        Err(e) => self.abort(&format!("无法回放：{e}")),
                    }
                }
                Reply::Saved(id, result) if id == self.generation => {
                    self.save_cancel = None;
                    self.saving_duration_ms = None;
                    match result {
                        Ok(clip) => {
                            self.last = Some(clip);
                            self.set(Phase::Idle, "上次录制已覆盖保存");
                        }
                        Err(e) => {
                            self.io_pending = false;
                            self.monitor = None;
                            self.set(Phase::Error, format!("保存失败，保留上次录制：{e}"));
                        }
                    }
                }
                _ => {}
            }
        }
        if self.phase == Phase::Pending && self.pending.is_none() && self.click.single(now) {
            self.pending = Some((Goal::Record, now));
        }
        let snap = self.monitor.as_ref().and_then(Monitor::get);
        if let Some((goal, since)) = self.pending {
            if ai_active || mouth_active {
                self.abort("AI动作或语音正在占用，未开始录放");
            } else if let Some(s) = snap.as_ref().filter(|s| s.fresh(now)) {
                if !manual_ready
                    || !s.idle()
                    || s.sitting().is_none()
                    || s.state["safety"]["fallen"] == true
                {
                    self.abort("请先人工HOME并保持，切普通手柄模式、回中，再录放");
                } else if !self.io_pending {
                    match goal {
                        Goal::Record => {
                            let clip = Clip {
                                schema: "microduck-pad-clip/v1".into(),
                                duration_ns: 0,
                                start_sitting: s.sitting().unwrap(),
                                identity: s.identity(),
                                skills: s.skills.clone(),
                                frames: Vec::new(),
                            };
                            CAPTURE.with(|slot| {
                                let mut slot = slot.borrow_mut();
                                slot.error = None;
                                slot.capture = Some(Capture {
                                    started: now,
                                    clip,
                                    bytes: 0,
                                    events: 0,
                                    last_do: None,
                                    seen_skill: false,
                                    next_emotion: 0,
                                });
                            });
                            self.pending = None;
                            self.started = now;
                            self.set(Phase::Recording, "正在录制；再单击Logo保存");
                        }
                        Goal::Play => {
                            let clip = self.last.as_ref().unwrap();
                            if clip.start_sitting != s.sitting().unwrap()
                                || clip.identity != s.identity()
                                || validate(clip).is_err()
                            {
                                self.abort("起始坐姿或运动模型已变化，本次不回放");
                            } else {
                                self.player = Some(Player {
                                    clip: clip.clone(),
                                    began: now,
                                    index: 0,
                                });
                                self.pending = None;
                                self.started = now;
                                self.set(Phase::Playing, "正在回放；操作手柄可中止");
                            }
                        }
                    }
                }
            } else if now.duration_since(since) > Duration::from_millis(1500) {
                self.abort("没有新鲜的运动/IMU反馈，未开始录放");
            }
        }
        if matches!(self.phase, Phase::Recording | Phase::Playing) {
            let ready = snap.as_ref().is_some_and(|s| {
                s.fresh(now)
                    && !(s.idle() && s.state["safety"]["fallen"] == true)
                    && if self.phase == Phase::Playing {
                        self.player
                            .as_ref()
                            .is_some_and(|p| p.clip.identity == s.identity())
                    } else {
                        CAPTURE.with(|slot| {
                            slot.borrow()
                                .capture
                                .as_ref()
                                .is_some_and(|c| c.clip.identity == s.identity())
                        })
                    }
            });
            if !ready || ai_active || mouth_active {
                self.abort("反馈过期、卸力或AI占用，已停止录放");
            }
        }
        if self.phase == Phase::Recording {
            CAPTURE.with(|slot| {
                let mut slot = slot.borrow_mut();
                if let (Some(s), Some(snap)) = (slot.capture.as_mut(), snap.as_ref()) {
                    if let Some((sent, name, generation)) = s.last_do.as_ref() {
                        if name.starts_with("emotion_") {
                            if snap.emotion_at > *sent
                                && matches!(
                                    snap.emotion["phase"].as_str(),
                                    Some("pending" | "playing")
                                )
                            {
                                s.seen_skill = true;
                            }
                            let matching_terminal = generation
                                .is_some_and(|id| snap.emotion["request_id"].as_u64() == Some(id))
                                && matches!(
                                    snap.emotion["phase"].as_str(),
                                    Some("completed" | "cancelled")
                                );
                            if snap.emotion_at > *sent
                                && (matching_terminal
                                    || s.seen_skill
                                        && !matches!(
                                            snap.emotion["phase"].as_str(),
                                            Some("pending" | "playing")
                                        ))
                            {
                                s.last_do = None;
                            }
                        } else {
                            let policy = snap.state["policy"].as_str().unwrap_or("");
                            if snap.received > *sent
                                && (policy == name
                                    || policy.starts_with(&(name.clone() + ":"))
                                    || name == "sit_toggle" && matches!(policy, "sit" | "rise"))
                            {
                                s.seen_skill = true;
                            }
                            if s.seen_skill && snap.received > *sent && snap.idle() {
                                s.last_do = None;
                            }
                        }
                    }
                    if now.duration_since(s.started).as_nanos() >= MAX_NS as u128 {
                        slot.capture = None;
                        slot.error = Some("录制达到120秒，本次未覆盖上次文件".into());
                    }
                }
            });
            let error = CAPTURE.with(|s| s.borrow_mut().error.take());
            if let Some(e) = error {
                self.abort(&e);
            }
        }
        let mut frames = Vec::new();
        if self.phase == Phase::Playing {
            match self.player.as_mut().unwrap().due(now) {
                Ok(due) => frames = due,
                Err(e) => self.abort(&e),
            }
            if self.phase == Phase::Playing && self.player.as_ref().unwrap().done(now) {
                self.cleanup = true;
                self.player = None;
                self.monitor = None;
                self.set(Phase::Idle, "回放已结束");
            }
        }
        self.publish(now);
        frames
    }
    pub fn supports_recording_emotion(&self, name: &str) -> bool {
        self.monitor
            .as_ref()
            .and_then(Monitor::get)
            .is_some_and(|s| s.expressions.iter().any(|e| e == name))
    }
    fn publish(&mut self, now: Instant) {
        if !self.changed && now.duration_since(self.last_report) < Duration::from_secs(1) {
            return;
        }
        self.last_report = now;
        self.changed = false;
        let duration = self
            .saving_duration_ms
            .or_else(|| self.player.as_ref().map(|p| p.clip.duration_ns / 1_000_000))
            .or_else(|| self.last.as_ref().map(|p| p.duration_ns / 1_000_000))
            .unwrap_or(0);
        let elapsed = if matches!(self.phase, Phase::Recording | Phase::Playing) {
            now.duration_since(self.started).as_millis() as u64
        } else {
            0
        };
        let _=self.worker.jobs.try_send(Job::Report(json!({"pid":std::process::id(),"t_ms":monotonic_ms(),"phase":self.phase.name(),"elapsed_ms":elapsed,"duration_ms":duration,"has_last":self.last.is_some(),"reason":self.reason})));
    }
}
fn monotonic_ms() -> u64 {
    let mut t = libc::timespec {
        tv_sec: 0,
        tv_nsec: 0,
    };
    if unsafe { libc::clock_gettime(libc::CLOCK_MONOTONIC, &mut t) } != 0 {
        return 0;
    }
    (t.tv_sec as u64) * 1000 + t.tv_nsec as u64 / 1_000_000
}

#[cfg(test)]
mod tests {
    use super::*;
    fn clip() -> Clip {
        Clip {
            schema: "microduck-pad-clip/v1".into(),
            duration_ns: 2_000_000_000,
            start_sitting: false,
            identity: json!({"mode":"walk","slots":[],"skills":["sit_toggle","emotion_yes"]}),
            skills: vec!["sit_toggle".into(), "emotion_yes".into()],
            frames: vec![
                Frame {
                    at_ns: 0,
                    intents: vec![Intent::from_call(
                        &proto::Call::RobotMove(proto::MoveParams {
                            vx: 0.2,
                            ..Default::default()
                        }),
                        false,
                    )],
                },
                Frame {
                    at_ns: 1_000_000_000,
                    intents: vec![Intent::from_call(
                        &proto::Call::RobotMove(Default::default()),
                        false,
                    )],
                },
            ],
        }
    }
    #[test]
    fn clip_rejects_management_unknown_and_bad_ranges() {
        for call in [
            proto::Call::RobotInit,
            proto::Call::RobotEnable(proto::EnableParams {
                on: true,
                toggle: false,
            }),
            proto::Call::RobotRelax,
            proto::Call::RobotShutdown,
            proto::Call::RobotMove(proto::MoveParams {
                vx: 3.,
                ..Default::default()
            }),
        ] {
            let mut c = clip();
            c.frames[0].intents[0] = Intent::from_call(&call, false);
            assert!(validate(&c).is_err());
        }
    }
    #[test]
    fn clip_rejects_bad_timing_and_preserves_tail() {
        let mut c = clip();
        assert!(validate(&c).is_ok());
        assert_eq!(c.duration_ns, 2_000_000_000);
        c.frames[1].at_ns = 0;
        assert!(validate(&c).is_err());
        c.frames[1].at_ns = 3_000_000_000;
        assert!(validate(&c).is_err());
    }
    #[test]
    fn one_shot_must_be_explicit_and_acknowledged() {
        let mut c = clip();
        c.frames[0].intents[0] = Intent::from_call(
            &proto::Call::RobotDo(proto::DoParams {
                skill: "emotion_next".into(),
            }),
            true,
        );
        assert!(validate(&c).is_err());
        c.frames[0].intents[0] = Intent::from_call(
            &proto::Call::RobotDo(proto::DoParams {
                skill: "emotion_yes".into(),
            }),
            false,
        );
        assert!(validate(&c).is_err());
        c.frames[0].intents[0].request = true;
        assert!(validate(&c).is_ok());
    }
    #[test]
    fn double_click_never_starts_a_recording() {
        let mut c = Click::default();
        let t = Instant::now();
        c.press(t);
        assert!(c.release(t + Duration::from_millis(20)).is_none());
        assert!(!c.single(t + Duration::from_millis(300)));
        c.press(t + Duration::from_millis(200));
        assert!(matches!(
            c.release(t + Duration::from_millis(220)),
            Some(Goal::Play)
        ));
        assert!(!c.single(t + Duration::from_secs(1)));
    }
    #[test]
    fn single_and_long_press_are_distinct() {
        let mut c = Click::default();
        let t = Instant::now();
        c.press(t);
        c.release(t + Duration::from_millis(10));
        assert!(c.single(t + Duration::from_millis(360)));
        c.press(t);
        assert!(c.release(t + Duration::from_secs(2)).is_none());
        assert!(!c.single(t + Duration::from_secs(3)));
    }
    #[test]
    fn player_keeps_absolute_time_and_tail() {
        let t = Instant::now();
        let mut p = Player {
            clip: clip(),
            began: t,
            index: 0,
        };
        assert_eq!(p.due(t).unwrap().len(), 1);
        assert!(p.due(t + Duration::from_millis(900)).unwrap().is_empty());
        assert_eq!(p.due(t + Duration::from_secs(1)).unwrap().len(), 1);
        assert!(!p.done(t + Duration::from_millis(1500)));
        assert!(p.done(t + Duration::from_secs(2)));
    }
    #[test]
    fn late_movement_is_aborted_not_bursted() {
        let t = Instant::now();
        let mut p = Player {
            clip: clip(),
            began: t,
            index: 0,
        };
        assert!(p.due(t + Duration::from_millis(101)).is_err());
        assert_eq!(p.index, 0);
    }
    #[test]
    fn cancelled_or_failed_save_keeps_previous_file() {
        let d = tempfile::tempdir().unwrap();
        let p = d.path().join("last.json");
        fs::write(&p, b"previous").unwrap();
        assert!(save(&p, &clip(), &AtomicBool::new(true)).is_err());
        assert_eq!(fs::read(&p).unwrap(), b"previous");
    }
    #[test]
    fn atomic_save_load_is_validated() {
        let d = tempfile::tempdir().unwrap();
        let p = d.path().join("last.json");
        save(&p, &clip(), &AtomicBool::new(false)).unwrap();
        assert_eq!(load(&p).unwrap().duration_ns, 2_000_000_000);
        fs::write(&p, b"broken").unwrap();
        assert!(load(&p).is_err());
    }
    #[test]
    fn capture_only_actual_allowed_frames_and_request_times() {
        CAPTURE.with(|s| {
            let mut c = clip();
            c.frames.clear();
            s.borrow_mut().capture = Some(Capture {
                started: Instant::now(),
                clip: c,
                bytes: 0,
                events: 0,
                last_do: None,
                seen_skill: false,
                next_emotion: 0,
            });
        });
        let sent = Instant::now();
        observe(&[proto::Call::RobotMove(Default::default())], false, sent);
        observe(
            &[proto::Call::RobotDo(proto::DoParams {
                skill: "sit_toggle".into(),
            })],
            true,
            sent + Duration::from_millis(5),
        );
        CAPTURE.with(|s| {
            let mut s = s.borrow_mut();
            let c = s.capture.take().unwrap();
            assert_eq!(c.clip.frames.len(), 2);
            assert_eq!(c.clip.frames[1].at_ns - c.clip.frames[0].at_ns, 5_000_000);
        });
    }
    #[test]
    fn recording_management_discards_buffer() {
        CAPTURE.with(|s| {
            let mut c = clip();
            c.frames.clear();
            s.borrow_mut().capture = Some(Capture {
                started: Instant::now(),
                clip: c,
                bytes: 0,
                events: 0,
                last_do: None,
                seen_skill: false,
                next_emotion: 0,
            });
        });
        observe(&[proto::Call::RobotInit], true, Instant::now());
        assert!(!recording());
        CAPTURE.with(|s| {
            s.borrow_mut().error = None;
        });
    }
    fn snapshot(now: Instant) -> Snapshot {
        Snapshot {
            state: json!({"t_ns":proto::clock::monotonic_ns(),"policy":"walk","safety":{"limp":false,"fallen":false}}),
            policies: json!({"homed":true,"enabled":true,"sitting":false,"mode":"walk","slots":[]}),
            health: json!({"healthy":true,"imu":{"ready":true,"consecutive_stale_blocks":1}}),
            skills: vec!["sit_toggle".into(), "emotion_yes".into()],
            expressions: vec!["emotion_yes".into()],
            received: now,
            probed: now,
            emotion: json!({"phase":"completed"}),
            emotion_at: now,
        }
    }
    #[test]
    fn fresh_sample_inside_current_millisecond_keeps_nanosecond_precision() {
        let now = Instant::now();
        let mut s = snapshot(now);
        let sampled = 12_345_678_901u64;
        let current = 12_345_678_999u64;
        s.state["t_ns"] = json!(sampled);
        // Flooring current to milliseconds would incorrectly make this fresh
        // sample appear to come from the future.
        assert!(sampled > current / 1_000_000 * 1_000_000);
        assert!(s.fresh_at(now, current));
        assert!(!s.fresh_at(now, sampled - 1));
        assert!(!s.fresh_at(now, sampled + 350_000_000));
    }
    #[test]
    fn freshness_allows_occasional_imu_repeat_but_not_frozen_or_held() {
        let now = Instant::now();
        let mut s = snapshot(now);
        assert!(s.fresh(now));
        s.health["imu"]["consecutive_stale_blocks"] = json!(25);
        assert!(!s.fresh(now));
        s.health["imu"]["consecutive_stale_blocks"] = json!(0);
        s.state["policy"] = json!("held");
        assert!(!s.fresh(now));
        s.state["policy"] = json!("walk");
        assert!(!s.fresh(now + Duration::from_millis(351)));
    }
    #[test]
    fn save_io_failure_leaves_saving_and_preserves_previous_clip() {
        let dir = tempfile::tempdir().unwrap();
        let blocked = dir.path().join("blocked");
        fs::write(&blocked, b"not a directory").unwrap();
        let mut r = Recorder::with_paths(
            "unused".into(),
            blocked.join("last.json"),
            dir.path().join("status.json"),
        );
        r.last = Some(clip());
        r.generation = 1;
        r.phase = Phase::Saving;
        r.worker
            .jobs
            .try_send(Job::Save(1, clip(), Arc::new(AtomicBool::new(false))))
            .unwrap();
        let until = Instant::now() + Duration::from_secs(1);
        while r.phase == Phase::Saving && Instant::now() < until {
            r.tick(Instant::now(), true, false, false);
            thread::sleep(Duration::from_millis(2));
        }
        assert!(r.phase == Phase::Error);
        assert!(!r.busy());
        assert_eq!(r.last.unwrap().duration_ns, 2_000_000_000);
    }
    #[test]
    fn named_management_rejected_even_if_catalog_includes_it() {
        let mut c = clip();
        c.skills.push("stand_test".into());
        c.identity["skills"] = json!(c.skills);
        c.frames[0].intents[0] = Intent::from_call(
            &proto::Call::RobotDo(proto::DoParams {
                skill: "stand_test".into(),
            }),
            true,
        );
        assert!(validate(&c).is_err());
        CAPTURE.with(|s| {
            s.borrow_mut().capture = Some(Capture {
                started: Instant::now(),
                clip: c,
                bytes: 0,
                events: 0,
                last_do: None,
                seen_skill: false,
                next_emotion: 0,
            })
        });
        before_send(&proto::Call::RobotDo(proto::DoParams {
            skill: "stand_test".into(),
        }));
        assert!(!recording());
        CAPTURE.with(|s| s.borrow_mut().error = None);
    }
    #[test]
    fn manual_safety_during_saving_does_not_discard_authorized_commit() {
        let dir = tempfile::tempdir().unwrap();
        let mut r = Recorder::with_paths(
            "unused".into(),
            dir.path().join("last.json"),
            dir.path().join("status.json"),
        );
        r.phase = Phase::Saving;
        let generation = r.generation;
        r.abort("manual select");
        assert!(r.phase == Phase::Saving);
        assert_eq!(r.generation, generation);
    }
    #[test]
    fn recording_r3_starts_at_first_name_and_advances_only_accepted() {
        let c = clip();
        CAPTURE.with(|s| {
            s.borrow_mut().capture = Some(Capture {
                started: Instant::now(),
                clip: c,
                bytes: 0,
                events: 0,
                last_do: None,
                seen_skill: false,
                next_emotion: 0,
            })
        });
        assert_eq!(next_emotion(), "emotion_sad");
        assert_eq!(next_emotion(), "emotion_sad");
        emotion_accepted();
        assert_eq!(next_emotion(), "emotion_devastated");
        CAPTURE.with(|s| s.borrow_mut().capture = None);
    }
    // This exercises the real monitor wire reader (responses interleaved with
    // robot.state), actual successful capture writes, the asynchronous atomic
    // save, disk reload, same-socket playback and a latched-sit ending.
    #[test]
    fn real_socket_capture_save_reload_and_sit_ending_replay() {
        let dir = tempfile::tempdir().unwrap();
        let socket = dir.path().join("unused.sock");
        let stop = Arc::new(AtomicBool::new(false));
        let sitting = Arc::new(AtomicBool::new(false));
        let calls = Arc::new(Mutex::new(Vec::<Value>::new()));
        let mut clients = Vec::new();
        fn peer(
            stream: UnixStream,
            e: Arc<AtomicBool>,
            s: Arc<AtomicBool>,
            c: Arc<Mutex<Vec<Value>>>,
        ) -> thread::JoinHandle<()> {
            thread::spawn(move || {
                stream
                    .set_read_timeout(Some(Duration::from_millis(10)))
                    .unwrap();
                let mut reader = BufReader::new(stream.try_clone().unwrap());
                let mut writer = stream;
                let mut subscribed = false;
                let mut last = Instant::now() - Duration::from_secs(1);
                while !e.load(Ordering::Acquire) {
                    let mut line = String::new();
                    match reader.read_line(&mut line) {
                        Ok(0) => break,
                        Ok(_) => {
                            let v: Value = serde_json::from_str(&line).unwrap();
                            let method = v["method"].as_str().unwrap();
                            if method == "robot.move"
                                || method == "robot.do" && v["params"]["skill"] != "emotion_status"
                            {
                                c.lock().unwrap().push(v.clone());
                            }
                            let result = match method {
                                "robot.skills" => {
                                    json!({"skills":[],"built_in":["sit_toggle"],"expressions":EMOTIONS.map(|name|json!({"name":name}))})
                                }
                                "robot.subscribe" => {
                                    subscribed = true;
                                    json!({"hz":10})
                                }
                                "robot.policies" => {
                                    json!({"homed":true,"enabled":true,"sitting":s.load(Ordering::Acquire),"mode":"walk","slots":[]})
                                }
                                "robot.health" => {
                                    json!({"healthy":true,"imu":{"ready":true,"consecutive_stale_blocks":1}})
                                }
                                "robot.do" if v["params"]["skill"] == "emotion_status" => {
                                    json!({"phase":"completed","request_id":0})
                                }
                                "robot.do" => {
                                    s.fetch_xor(true, Ordering::AcqRel);
                                    json!({"accepted":true})
                                }
                                _ => json!({"accepted":true}),
                            };
                            if !v["id"].is_null() {
                                writeln!(
                                    writer,
                                    "{}",
                                    json!({"jsonrpc":"2.0","id":v["id"],"result":result})
                                )
                                .unwrap();
                            }
                        }
                        Err(e)
                            if matches!(
                                e.kind(),
                                std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut
                            ) => {}
                        Err(_) => break,
                    }
                    if subscribed && last.elapsed() >= Duration::from_millis(40) {
                        last = Instant::now();
                        let state = json!({"t_ns":proto::clock::monotonic_ns(),"policy":if s.load(Ordering::Acquire){"sit"}else{"walk"},"safety":{"fallen":false,"limp":false}});
                        if writeln!(
                            writer,
                            "{}",
                            json!({"jsonrpc":"2.0","method":"robot.state","params":state})
                        )
                        .is_err()
                        {
                            break;
                        }
                    }
                }
            })
        }
        let (mut stream, other) = UnixStream::pair().unwrap();
        clients.push(peer(other, stop.clone(), sitting.clone(), calls.clone()));
        let mut new_monitor = || {
            let (a, b) = UnixStream::pair().unwrap();
            clients.push(peer(b, stop.clone(), sitting.clone(), calls.clone()));
            Monitor::from_stream(a)
        };
        let path = dir.path().join("last.json");
        let mut r = Recorder::with_paths(
            socket.clone(),
            path.clone(),
            dir.path().join("recorder.json"),
        );
        let mut id = 1;
        let mut continuous = crate::Continuous::default();
        let first = Instant::now() - Duration::from_millis(400);
        r.logo_press(first);
        r.logo_release(first + Duration::from_millis(10), true);
        r.monitor = Some(new_monitor());
        let until = Instant::now() + Duration::from_secs(2);
        while !r.is_recording() && Instant::now() < until {
            r.tick(Instant::now(), true, false, false);
            thread::sleep(Duration::from_millis(10));
        }
        assert!(r.is_recording(), "{}", r.reason);
        crate::notify(
            &mut stream,
            &proto::Call::RobotMove(proto::MoveParams {
                vx: 0.2,
                ..Default::default()
            }),
        )
        .unwrap();
        let answer = crate::request(
            &mut stream,
            &mut id,
            &proto::Call::RobotDo(proto::DoParams {
                skill: "sit_toggle".into(),
            }),
        )
        .unwrap();
        assert!(crate::intent_accepted(answer.as_ref()));
        crate::notify(&mut stream, &proto::Call::RobotMove(Default::default())).unwrap();
        let until = Instant::now() + Duration::from_secs(1);
        loop {
            r.tick(Instant::now(), true, false, false);
            let finished = CAPTURE.with(|s| {
                s.borrow()
                    .capture
                    .as_ref()
                    .is_some_and(|c| c.last_do.is_none())
            });
            if finished {
                break;
            }
            assert!(Instant::now() < until, "sit tail did not become savable");
            thread::sleep(Duration::from_millis(10));
        }
        let now = Instant::now();
        r.logo_press(now);
        r.logo_release(now + Duration::from_millis(1), true);
        assert!(r.phase == Phase::Saving, "{}", r.reason);
        let until = Instant::now() + Duration::from_secs(1);
        while r.phase == Phase::Saving && Instant::now() < until {
            r.tick(Instant::now(), true, false, false);
            thread::sleep(Duration::from_millis(5));
        }
        assert!(r.phase == Phase::Idle, "{}", r.reason);
        let saved = load(&path).unwrap();
        assert!(!saved.start_sitting);
        assert_eq!(saved.frames.len(), 3);
        assert!(saved.duration_ns >= saved.frames.last().unwrap().at_ns);
        // Replay must refuse the current sitting=true because this clip began standing.
        let first = Instant::now() - Duration::from_millis(200);
        r.logo_press(first);
        r.logo_release(first + Duration::from_millis(10), true);
        r.logo_press(Instant::now());
        r.logo_release(Instant::now(), true);
        r.monitor = Some(new_monitor());
        let until = Instant::now() + Duration::from_secs(1);
        while r.phase == Phase::Pending && Instant::now() < until {
            r.tick(Instant::now(), true, false, false);
            thread::sleep(Duration::from_millis(10));
        }
        assert!(r.phase == Phase::Error);
        assert!(!r.handoff_pending());
        sitting.store(false, Ordering::Release);
        let first = Instant::now() - Duration::from_millis(200);
        r.logo_press(first);
        r.logo_release(first + Duration::from_millis(10), true);
        r.logo_press(Instant::now());
        r.logo_release(Instant::now(), true);
        r.monitor = Some(new_monitor());
        let until = Instant::now() + Duration::from_secs(2);
        let mut played = false;
        loop {
            let now = Instant::now();
            let due = r.tick(now, true, false, false);
            played |= r.playing() || !due.is_empty();
            crate::replay_frames(&mut stream, &mut continuous, &mut id, &mut r, due, now).unwrap();
            if r.take_cleanup() {
                crate::finish_recorder(
                    &mut stream,
                    &mut continuous,
                    &mut id,
                    &mut r,
                    false,
                    false,
                    now,
                )
                .unwrap();
            }
            if played && !r.busy() {
                break;
            }
            assert!(Instant::now() < until, "{}", r.reason);
            thread::sleep(Duration::from_millis(10));
        }
        assert!(r.phase == Phase::Idle, "{}", r.reason);
        assert!(sitting.load(Ordering::Acquire));
        let seen = calls.lock().unwrap();
        assert_eq!(
            seen.iter()
                .filter(|v| v["params"]["skill"] == "sit_toggle")
                .count(),
            2
        );
        assert_eq!(
            seen.iter()
                .filter(|v| v["method"] == "robot.move" && v["params"]["vx"] == 0.2)
                .count(),
            2
        );
        drop(seen);
        drop(r);
        drop(stream);
        stop.store(true, Ordering::Release);
        for c in clients {
            c.join().unwrap();
        }
    }
    #[test]
    fn second_press_across_deadline_or_long_hold_cannot_start_recording() {
        let t = Instant::now();
        let mut c = Click::default();
        c.press(t);
        c.release(t + Duration::from_millis(10));
        c.press(t + Duration::from_millis(200));
        assert!(!c.single(t + Duration::from_millis(400)));
        assert!(c.release(t + Duration::from_secs(1)).is_none());
        assert!(!c.single(t + Duration::from_secs(2)));
    }
    #[test]
    fn same_generation_terminal_status_ends_expression_even_if_monitor_missed_playing() {
        let dir = tempfile::tempdir().unwrap();
        let mut r = Recorder::with_paths(
            "unused".into(),
            dir.path().join("last.json"),
            dir.path().join("status.json"),
        );
        let now = Instant::now();
        let mut snap = snapshot(now);
        snap.emotion = json!({"request_id":8,"phase":"completed"});
        let mut c = clip();
        c.identity = snap.identity();
        let sent = now - Duration::from_millis(20);
        CAPTURE.with(|s| {
            let mut s = s.borrow_mut();
            s.error = None;
            s.capture = Some(Capture {
                started: sent,
                clip: c,
                bytes: 0,
                events: 0,
                last_do: Some((sent, "emotion_yes".into(), Some(7))),
                seen_skill: false,
                next_emotion: 0,
            });
        });
        r.phase = Phase::Recording;
        r.monitor = Some(Monitor {
            value: Arc::new(Mutex::new(Some(snap))),
            stop: Arc::new(AtomicBool::new(false)),
        });
        r.tick(now, true, false, false);
        assert!(
            CAPTURE.with(|s| s.borrow().capture.as_ref().unwrap().last_do.is_some()),
            "previous generation must not clear pending action"
        );
        r.monitor
            .as_ref()
            .unwrap()
            .value
            .lock()
            .unwrap()
            .as_mut()
            .unwrap()
            .emotion = json!({"request_id":7,"phase":"cancelled"});
        r.tick(Instant::now(), true, false, false);
        assert!(CAPTURE.with(|s| s.borrow().capture.as_ref().unwrap().last_do.is_none()));
        r.abort("test done");
    }
    #[test]
    fn slow_accepted_request_never_replays_the_following_stale_move() {
        let dir = tempfile::tempdir().unwrap();
        let mut r = Recorder::with_paths(
            "unused".into(),
            dir.path().join("last.json"),
            dir.path().join("status.json"),
        );
        r.phase = Phase::Playing;
        r.started = Instant::now();
        let (mut ours, mut peer) = UnixStream::pair().unwrap();
        let server = thread::spawn(move || {
            let mut line = String::new();
            BufReader::new(peer.try_clone().unwrap())
                .read_line(&mut line)
                .unwrap();
            let req: Value = serde_json::from_str(&line).unwrap();
            assert_eq!(req["method"], "robot.do");
            thread::sleep(Duration::from_millis(110));
            writeln!(
                peer,
                "{}",
                json!({"jsonrpc":"2.0","id":req["id"],"result":{"accepted":true}})
            )
            .unwrap();
            peer
        });
        let frames = vec![Frame {
            at_ns: 0,
            intents: vec![
                Intent::from_call(
                    &proto::Call::RobotDo(proto::DoParams {
                        skill: "sit_toggle".into(),
                    }),
                    true,
                ),
                Intent::from_call(
                    &proto::Call::RobotMove(proto::MoveParams {
                        vx: 0.2,
                        ..Default::default()
                    }),
                    false,
                ),
            ],
        }];
        crate::replay_frames(
            &mut ours,
            &mut crate::Continuous::default(),
            &mut 1,
            &mut r,
            frames,
            Instant::now(),
        )
        .unwrap();
        assert!(r.phase == Phase::Error);
        assert!(r.take_cleanup());
        let mut peer = server.join().unwrap();
        peer.set_nonblocking(true).unwrap();
        let mut bytes = [0; 1024];
        assert!(
            peer.read(&mut bytes)
                .is_err_and(|e| e.kind() == std::io::ErrorKind::WouldBlock)
        );
    }
    #[test]
    fn manual_safety_cleanup_stops_first_and_respects_the_pcm_mouth_lease() {
        let dir = tempfile::tempdir().unwrap();
        let mut r = Recorder::with_paths(
            "unused".into(),
            dir.path().join("last.json"),
            dir.path().join("status.json"),
        );
        r.phase = Phase::Playing;
        r.expression_request = Some(99);
        r.abort("manual Select");
        let (mut ours, mut peer) = UnixStream::pair().unwrap();
        crate::finish_recorder(
            &mut ours,
            &mut crate::Continuous::default(),
            &mut 1,
            &mut r,
            true,
            true,
            Instant::now(),
        )
        .unwrap();
        peer.set_nonblocking(true).unwrap();
        let mut bytes = [0; 2048];
        let n = peer.read(&mut bytes).unwrap();
        let lines: Vec<Value> = std::str::from_utf8(&bytes[..n])
            .unwrap()
            .lines()
            .map(|s| serde_json::from_str(s).unwrap())
            .collect();
        assert_eq!(lines.len(), 3);
        assert_eq!(lines[0]["method"], "robot.move");
        assert_eq!(lines[0]["params"]["vx"], 0.0);
        assert_eq!(lines[1]["method"], "robot.pose");
        assert_eq!(lines[1]["params"]["active"], false);
        assert_eq!(lines[2]["method"], "robot.sound");
        assert!(
            lines
                .iter()
                .all(|v| v["method"] != "robot.mouth" && v["method"] != "robot.do")
        );
    }
}
