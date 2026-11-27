/* Duck 遥控 — 局域网 PWA 前端。
 *
 * 没有依赖、没有构建步骤：板子只发静态文件，手机直接跑这一份 JS。
 * 唯一的数据来源是 /ws：桥把 robotd 的 20 Hz 状态流裁成 ~300 B 推下来，
 * 页面把摇杆与按钮变成 drive / cmd 消息。
 *
 * 设计说明见 microduck-hd1910/firmware/docs/design/lan-phone-remote.md（kissqy 仓库）。
 */
(() => {
  'use strict';

  const SPEEDS = { '0.1': { vx: 0.10, yaw: 0.45 }, '0.2': { vx: 0.20, yaw: 0.75 }, '0.3': { vx: 0.30, yaw: 1.00 } };
  // 值来自 robotd 的 RobotState::policy（见 duck-ipc-proto）。`homing` 是 R17 fork
  // 在回 HOME 斜坡期间的取值——不翻译的话顶栏会直接显示英文。
  const POLICY = {
    walk: '行走', stand: '待命', held: '待命', homing: '回 HOME',
    limp: '卸力', sit: '坐着', sitstand: '起坐', ground_pick: '捡拾',
  };
  const BACKOFF = [1000, 2000, 4000, 8000, 15000];
  const OFFLINE_AFTER = 5;
  const RELAX_HOLD_MS = 1500;
  const STICK_R = 80;
  // 比手柄默认 0.5 rad 更明显；robotd 仍会按策略/关节限位处理。
  const HEAD_MAX = 0.8;
  const HEAD_REFRESH_MS = 60;
  const SOUND_TAGS = ['chirp', 'greet', 'inquire', 'coo', 'alarm', 'peck', 'wheee'];
  // Mirrors actions.py; the bridge is the source of truth for the actual frames.
  const PRESETS = {
    look_up:     { label: '抬头',   dur: 1.2 },
    look_around: { label: '左右看', dur: 1.6 },
    circle:      { label: '画圈',   dur: 3.9 },
    quack:       { label: '张嘴',   dur: 2.1 },
  };
  const TOKEN_KEY = 'duck.token';
  const SPEED_KEY = 'duck.speed';
  const NAME_KEY = 'duck.name';
  const LAST_KEY = 'duck.last';
  const POLICY_REFRESH_MS = 20000;
  // Mirrors audio_settings.py; used before the bridge sends its config and for
  // the "restore defaults" button. The bridge remains the source of truth.
  const AUDIO_DEFAULTS = {
    idle: { after_s: 30, repeat_s: 300, max_per_hour: 12, gesture: true,
            library: ['look_up', 'look_around', 'circle', 'quack'] },
    fall: { repeat_s: 5, max_repeats: 6, tail_s: 60 },
    tilt: { deg: 30, repeat_s: 10 },
    actions: { takeover: true, handback: true, skill_start: true, skill_end: true,
               enable: true, refusal: true },
    alerts: { fall: true, tilt: true, battery: true, motor: true, cpu: true,
              loop: true, bus: true },
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);

  // ── 状态 ───────────────────────────────────────────────────────────────
  const S = {
    link: 'connecting',      // connecting | online | down
    role: 'readonly',
    policy: 'held',
    limp: true,
    fallen: false,
    req: [0, 0, 0],        // 本机摇杆的意图，界面以它为准
    robotReq: [0, 0, 0],   // robotd 收到的请求，只用于"请求 vs 实际"的证据
    applied: [0, 0, 0],
    stickMode: 'drive',    // drive | head
    headReq: { yaw: 0, pitch: 0 },
    head: [0, 0, 0, 0],    // robotd 回传的头部意图 [neck, pitch, yaw, roll]
    sound: { volume: null, mute: false, prev: 60, wheee: false },
    dyn: false,            // 桥接层动态声音总开关；接管后默认开
    audio: null,           // 桥接层动态声音配置；hello/audioConfig 下发
    act: null,             // 正在播放的预设动作名
    actIdle: false,        // 是否空闲自动触发
    actStarted: 0,
    actDur: 0,
    limited: [],
    hz: 0,
    missed: 0,
    tilt: 0,
    batt: { p: null, v: null },
    temp: null,
    cpu: null,
    padd: false,
    paddCanStop: false,
    ro: false,          // robotd 处于标定模式：能连、能看，不能动
    roReason: '',
    lastInputAt: 0,     // 最后一次非零摇杆请求的时间；deadman 要靠它才显示
    primed: false,      // 第一帧只是"现在长这样"，不是事件
    robotd: '',
    speed: '0.2',
    driverName: '',
    events: [],
    eventSeq: 0,
    offline: false,
    policies: null,     // 策略条目录（桥给的），null = 还没拿到
    policiesAt: 0,
  };

  const el = {
    app: $('#app'),
    topbar: $('#topbar'),
    statusBtn: $('#statusBtn'),
    dot: $('#connDot'),
    policyBar: $('#policyBar'), policyChips: $('#policyChips'),
    policyToggle: $('#policyToggle'), policyPanel: $('#policyPanel'), policyKey: $('.pb-key'),
    policyChip: $('#policyChip'),
    policyText: $('#policyText'),
    battMetric: $('#battMetric'),
    battFill: $('#battFill'),
    battPct: $('#battPct'),
    hzMetric: $('#hzMetric'),
    hzVal: $('#hzVal'),
    tempMetric: $('#tempMetric'),
    tempVal: $('#tempVal'),
    cpuMetric: $('#cpuMetric'),
    cpuVal: $('#cpuVal'),
    alarmChip: $('#alarmChip'),
    alarmCount: $('#alarmCount'),
    btnFull: $('#btnFull'),

    banner: $('#banner'),
    bannerText: $('#bannerText'),
    bannerAction: $('#bannerAction'),

    stickZone: $('#stickZone'),
    stickBase: $('#stickBase'),
    knob: $('#stickKnob'),
    stickGuide: $('#stickGuide'),
    roVx: $('#roVx'),
    roYaw: $('#roYaw'),
    barReq: $('#barReq'),
    barApp: $('#barApp'),
    roLimit: $('#roLimit'),
    stickMode: $('#stickMode'),
    roHeadReq: $('#roHeadReq'),
    roHeadApp: $('#roHeadApp'),
    btnHeadReset: $('#btnHeadReset'),

    btnStand: $('#btnStand'),
    btnEnable: $('#btnEnable'),
    enableLabel: $('#enableLabel'), enableSub: $('#enableSub'),
    btnStop: $('#btnStop'),
    btnRelax: $('#btnRelax'),

    speedSeg: $('#speedSeg'),
    tiltBubble: $('#tiltBubble'),
    tiltDot: $('#tiltDot'),
    tiltVal: $('#tiltVal'),
    btnActions: $('#btnActions'), actionsSheet: $('#actionsSheet'), actGrid: $('#actGrid'),
    actHint: $('#actHint'), actReadonly: $('#actReadonly'),
    btnActStop: $('#btnActStop'), btnActClose: $('#btnActClose'),
    idlePool: $('#idlePool'),
    btnSound: $('#btnSound'),
    btnMaint: $('#btnMaint'),

    toasts: $('#toasts'),

    readonly: $('#readonly'),
    readonlyWho: $('#readonlyWho'),
    btnTakeover: $('#btnTakeover'),
    btnReadonlyClose: $('#btnReadonlyClose'),

    offline: $('#offline'),
    offlineLast: $('#offlineLast'),
    btnRetry: $('#btnRetry'),
    btnHelp: $('#btnHelp'),


    status: $('#status'),
    stConn: $('#stConn'),
    stIp: $('#stIp'),
    stConnCard: $('#stConnCard'),
    stPolicy: $('#stPolicy'),
    stPolicyD: $('#stPolicyD'),
    stPolicyCard: $('#stPolicyCard'),
    stHz: $('#stHz'),
    stMissed: $('#stMissed'),
    stHzCard: $('#stHzCard'),
    stBatt: $('#stBatt'),
    stBattD: $('#stBattD'),
    stBattCard: $('#stBattCard'),
    stMotor: $('#stMotor'),
    stCpu: $('#stCpu'),
    stTempCard: $('#stTempCard'),
    stInput: $('#stInput'),
    stInputD: $('#stInputD'),
    stInputCard: $('#stInputCard'),
    statusAlarms: $('#statusAlarms'),
    stVersion: $('#stVersion'),
    btnStatusClose: $('#btnStatusClose'),
    btnStatusClose2: $('#btnStatusClose2'),

    alert: $('#alert'),
    alertIco: $('#alertIco'),
    alertKicker: $('#alertKicker'),
    alertTitle: $('#alertTitle'),
    alertBody: $('#alertBody'),
    alertEv: $('#alertEv'),
    alertPadd: $('#alertPadd'),
    alertCopy: $('#alertCopy'),
    alertStand: $('#alertStand'),
    alertOk: $('#alertOk'),
    alertBack: $('#alertBack'),
    msgList: $('#msgList'),
    msgCount: $('#msgCount'),

    sound: $('#sound'),
    soundGrid: $('#soundGrid'),
    volRange: $('#volRange'),
    volPct: $('#volPct'),
    btnMute: $('#btnMute'),
    btnDynSound: $('#btnDynSound'),
    dynState: $('#dynState'),
    dynNote: $('#dynNote'),
    btnDynSettings: $('#btnDynSettings'),
    btnSoundClose: $('#btnSoundClose'),

    settings: $('#settings'),
    setIdleFirst: $('#setIdleFirst'), setIdleRepeat: $('#setIdleRepeat'), setIdleMax: $('#setIdleMax'),
    setFallRepeat: $('#setFallRepeat'), setFallMax: $('#setFallMax'), setFallTail: $('#setFallTail'),
    setTiltDeg: $('#setTiltDeg'), setTiltRepeat: $('#setTiltRepeat'),
    setHint: $('#setHint'), setReadonly: $('#setReadonly'),
    btnSettingsReset: $('#btnSettingsReset'), btnSettingsClose: $('#btnSettingsClose'),
    btnSettingsSave: $('#btnSettingsSave'),

    maint: $('#maint'),
    btnReboot: $('#btnReboot'),
    btnShutdown: $('#btnShutdown'),
    btnInputDetail: $('#btnInputDetail'),
    paddState: $('#paddState'),
    maintHz: $('#maintHz'),
    maintTemp: $('#maintTemp'),
    maintVersion: $('#maintVersion'),
    btnMaintClose: $('#btnMaintClose'),

    romode: $('#romode'),
    roReason: $('#roReason'),
    roRetry: $('#roRetry'),
    roStatus: $('#roStatus'),

    swUpdate: $('#swUpdate'),
    swReload: $('#swReload'),
  };

  // ── WebSocket ──────────────────────────────────────────────────────────
  let sock = null;
  let attempt = 0;
  let retryTimer = 0;
  let helloDone = false;
  let cmdSeq = 0;
  const pending = new Map();
  // 页面不再问配对码；服务端若仍开着校验，可以用 ?token=123456 带进来。
  const urlToken = new URLSearchParams(location.search).get('token');
  let token = urlToken || localStorage.getItem(TOKEN_KEY) || '';
  const clientName = localStorage.getItem(NAME_KEY) || guessName();

  function guessName() {
    const ua = navigator.userAgent;
    if (/Mate\s*40/i.test(ua)) return 'Mate 40 Pro';
    if (/Android/i.test(ua)) return 'Android 手机';
    if (/iPhone|iPad/i.test(ua)) return 'iPhone';
    return '浏览器';
  }

  function wsURL() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${location.host}/ws`;
  }

  // 一条页面只能有一条 socket。开第二条会变成"自己是只读、另一条自己在驾驶"——
  // 点「重试连接」时旧的退避定时器还在跑，就正好会撞上这个。
  function connect() {
    clearTimeout(retryTimer);
    retryTimer = 0;
    if (sock && (sock.readyState === WebSocket.OPEN || sock.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setLink('connecting');
    let ws;
    try {
      ws = new WebSocket(wsURL());
    } catch (_) {
      scheduleRetry();
      return;
    }
    sock = ws;

    ws.addEventListener('open', () => {
      if (sock !== ws) return;      // 被更新的连接取代了，这条不算
      attempt = 0;
      helloDone = false;
      sendHello();
    });

    ws.addEventListener('message', (ev) => {
      if (sock !== ws) return;
      let msg;
      try { msg = JSON.parse(ev.data); } catch (_) { return; }
      if (msg && typeof msg === 'object') handle(msg);
    });

    ws.addEventListener('close', () => {
      if (sock !== ws) return;      // 旧的 socket 关掉不该影响当前这条
      sock = null;
      helloDone = false;
      failPending('连接断开');
      setLink('down');
      scheduleRetry();
    });

    ws.addEventListener('error', () => { /* close 会跟着来 */ });
  }

  function dropSocket() {
    const ws = sock;
    sock = null;
    if (ws) {
      try { ws.close(); } catch (_) {}
    }
  }

  function scheduleRetry() {
    if (retryTimer) return;
    attempt += 1;
    if (attempt >= OFFLINE_AFTER) showOffline();
    const wait = BACKOFF[Math.min(attempt - 1, BACKOFF.length - 1)];
    retryTimer = setTimeout(() => { retryTimer = 0; connect(); }, wait);
  }

  function escapeText(v) {
    return String(v == null ? '' : v).replace(/[&<>]/g, (c) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]);
  }
  function escapeAttr(v) {
    return escapeText(v).replace(/"/g, '&quot;');
  }

  function wsSend(payload) {
    if (!sock || sock.readyState !== WebSocket.OPEN) return false;
    try {
      sock.send(JSON.stringify(payload));
      return true;
    } catch (_) {
      return false;
    }
  }

  function sendHello() {
    wsSend({ t: 'hello', token, name: clientName });
  }

  // 1 Hz 应用层心跳：桥在 5 s 没有任何消息时会判会话死亡。
  // 它也是页面知道自己"还连着"的唯一依据——WS 本身可能半开。
  setInterval(() => {
    if (!helloDone) return;
    wsSend({ t: 'ping' });
  }, 1000);

  function failPending(reason) {
    for (const [, entry] of pending) entry.resolve({ ok: false, reason });
    pending.clear();
  }

  // ── 消息处理 ───────────────────────────────────────────────────────────
  function handle(msg) {
    switch (msg.t) {
      case 'hello': return onHello(msg);
      case 'state': return onState(msg);
      case 'policies': return onPolicies(msg);
      case 'audioConfig': return onAudioConfig(msg);
      case 'ack': return onAck(msg);
      case 'session': return onSession(msg);
      case 'pong': return;
      case 'error': return;
      default: return;
    }
  }

  function onPolicies(msg) {
    if (msg.ok) {
      S.policies = msg;
      S.policiesAt = Date.now();
    } else {
      S.policies = { ok: false, chips: [], reason: msg.reason || '' };
    }
    renderPolicyBar();
  }

  function onAudioConfig(msg) {
    if (msg && msg.config) S.audio = msg.config;
    updateDynUI();
    if (!el.settings.classList.contains('hidden')) fillSettingsForm(audioCfg());
  }

  function onHello(msg) {
    if (!msg.ok) {
      // 页面已经不收配对码了。到这个分支只可能是服务端仍带着 --auth，
      // 那是运维配置问题，值得直接说清楚，而不是显示一个没人能填的表单。
      if (msg.reason === 'locked') toast('尝试过多，请稍后再试', 'err', 4000);
      else if (msg.reason === 'need_token' || msg.reason === 'bad_token') {
        toast('服务端开了配对码校验：请用 --auth 关闭，或在地址后加 ?token=xxxxxx', 'err', 6000);
      }
      return;
    }
    helloDone = true;
    if (token) localStorage.setItem(TOKEN_KEY, token);
    S.role = msg.role;
    S.driverName = msg.driver || '';
    S.paddCanStop = !!msg.paddCanStop;
    if (msg.audio) S.audio = msg.audio;
    setLink('online');
    hideOffline();
    if (msg.role === 'readonly') showReadonly(msg.driver);
    else hideReadonly();
    pushEvent('link', 'ok', '已连接', msg.role === 'driver' ? '本机在驾驶' : '只读模式');
    requestPolicies(true);
    if (!el.settings.classList.contains('hidden')) fillSettingsForm(audioCfg());
    render();
  }

  function onState(msg) {
    const wasPolicy = S.policy;
    const wasLimped = S.limp;

    S.policy = msg.pol || 'held';
    S.limp = !!msg.limp;
    S.fallen = !!msg.fall;
    S.robotReq = Array.isArray(msg.mv) ? msg.mv : [0, 0, 0];
    S.applied = Array.isArray(msg.ap) ? msg.ap : [0, 0, 0];
    S.head = Array.isArray(msg.head) ? msg.head.slice(0, 4) : [0, 0, 0, 0];
    S.limited = Array.isArray(msg.lim) ? msg.lim : [];
    S.hz = Number(msg.hz) || 0;
    S.missed = Number(msg.missed) || 0;
    S.tilt = Number(msg.tilt) || 0;
    S.padd = !!msg.padd;
    if (typeof msg.dyn === 'boolean') S.dyn = msg.dyn;
    const wasAct = S.act;
    S.act = typeof msg.act === 'string' && msg.act ? msg.act : null;
    S.actIdle = !!msg.actIdle;
    if (S.act && S.act !== wasAct) {
      S.actStarted = performance.now();
      S.actDur = PRESETS[S.act]?.dur || 0;
    } else if (!S.act) {
      S.actStarted = 0;
      S.actDur = 0;
    }
    if (typeof msg.paddCanStop === 'boolean') S.paddCanStop = msg.paddCanStop;
    if (msg.robotd) S.robotd = msg.robotd;
    const wasRo = S.ro;
    S.ro = !!msg.ro;
    S.roReason = msg.roReason || '';
    if (S.ro !== wasRo) {
      if (S.ro) {
        stopStick();
        pushEvent('romode', 'warn', '机器人处于标定模式', S.roReason || 'robotd --commissioning');
        toast('机器人处于标定模式，暂不能驾驶', 'warn', 3600);
      } else {
        hideOffline();
        toast('机器人已恢复可驾驶');
        pushEvent('romode', 'ok', '标定模式已结束', '可以站立/接管');
      }
      renderRomode();
    } else if (S.ro) {
      renderRomode();
    }
    if (Array.isArray(msg.bat)) S.batt = { v: msg.bat[0], p: msg.bat[1] };
    else if (msg.bat === null) S.batt = { p: null, v: null };
    S.temp = msg.temp === null || msg.temp === undefined ? null : Number(msg.temp);
    S.cpu = msg.cpu === null || msg.cpu === undefined ? null : Number(msg.cpu);
    if (msg.ok === false && S.link === 'online') {
      // robotd 掉线但桥还在：保持页面，只是不能动
      setLink('down');
    } else if (msg.ok && S.link !== 'online') {
      setLink('online');
    }

    // 头部意图是绝对量，robotd 不会因为策略退出而自动归零；一旦离开行走
    // 就主动回正，避免"交还策略后头还歪着"。
    if ((S.headReq.yaw || S.headReq.pitch) && (S.policy !== 'walk' || S.limp || S.fallen)) {
      stopStick();
    }

    if (!S.primed) S.primed = true;
    else {
      if (wasPolicy !== S.policy) {
        const text = { walk: '已接管行走策略', stand: '策略待命', held: '已交还策略' }[S.policy];
        if (text) pushEvent('policy', 'ok', text, `policy=${S.policy}`);
      }
      if (!wasLimped && S.limp) pushEvent('relax', 'warn', '舵机已卸力', '需要重新站立');
    }

    trackAlarms();
    render();
  }

  function onAck(msg) {
    const entry = pending.get(msg.id);
    if (entry) {
      pending.delete(msg.id);
      entry.resolve({
        ok: !!msg.ok, reason: msg.reason || '', policies: msg.policies,
        volume: msg.volume, muted: msg.muted, saved: msg.saved, message: msg.message,
        enabled: msg.enabled, config: msg.config,
        action: msg.action, sound: msg.sound,
      });
    }
    if (typeof msg.padd === 'boolean') S.padd = msg.padd;
    render();
  }

  function onSession(msg) {
    S.role = msg.role;
    if (msg.role === 'driver') {
      S.driverName = clientName;
      hideReadonly();
      toast('已接管，现在由这台设备驾驶');
      pushEvent('takeover', 'ok', '已接管驾驶', clientName);
    } else {
      S.driverName = msg.driver || '';
      stopStick();
      stopWheee();
      showReadonly(msg.driver);
      toast(msg.reason || '已被另一台设备接管', 'warn', 3200);
      pushEvent('takeover', 'warn', '已被另一台设备接管', msg.driver || '');
    }
    if (!el.settings.classList.contains('hidden')) fillSettingsForm(audioCfg());
    render();
  }

  function renderRomode() {
    const show = S.ro && S.link === 'online' && S.role === 'driver'
      && el.readonly.classList.contains('hidden')
      && el.offline.classList.contains('hidden');
    el.romode.classList.toggle('hidden', !show);
    if (show) el.roReason.textContent = S.roReason || 'robotd is read-only';
  }

  function setLink(state) {
    S.link = state;
    el.app.dataset.link = state === 'online' ? 'up' : 'down';
    if (state !== 'online') {
      S.req = [0, 0, 0];
      S.robotReq = [0, 0, 0];
      S.applied = [0, 0, 0];
      S.headReq = { yaw: 0, pitch: 0 };
      stopWheee();
    }
    render();
  }

  // ── 告警 ───────────────────────────────────────────────────────────────
  function alarmState() {
    const a = { batt: null, cpu: null, motor: null, loop: null };
    const p = S.batt.p;
    const v = S.batt.v;
    if (p !== null && v !== null) {
      if (p < 15 || v < 7.0) a.batt = 'bad';
      else if (p < 25 || v < 7.3) a.batt = 'warn';
    }
    if (S.cpu !== null) {
      if (S.cpu >= 85) a.cpu = 'bad';
      else if (S.cpu >= 70) a.cpu = 'warn';
    }
    if (S.temp !== null) {
      if (S.temp >= 60) a.motor = 'bad';
      else if (S.temp >= 50) a.motor = 'warn';
    }
    if (S.hz > 0) {
      if (S.hz < 45) a.loop = 'bad';
      else if (S.hz < 48) a.loop = 'warn';
    }
    // 固件的 fallen 要到 60° 才置位（fall_gravity_z = -0.5），而 30–60° 这段
    // 已经很危险了：真机上机器人就是在这个区间里倒下去的，页面却一片安静。
    if (S.tilt >= 60) a.tilt = 'bad';
    else if (S.tilt >= 30) a.tilt = 'warn';
    return a;
  }

  let alarmSeen = new Set();

  function trackAlarms() {
    const list = activeAlarms();
    const now = new Set(list.map((x) => x.kind));
    for (const item of list) {
      if (!alarmSeen.has(item.kind) && item.sev !== 'ok') {
        pushEvent(item.kind, item.sev, alarmTitle(item.kind), item.summary || item.text);
      }
    }
    alarmSeen = now;
  }

  function alarmTitle(kind) {
    return {
      batt: '电量告警', motor: '电机温度偏高', cpu: '主控温度偏高',
      loop: '控制环频率偏低', padd: '手柄服务运行中', limit: '指令未执行', fallen: '检测到倒地',
      tilt: '机身倾斜过大',
    }[kind] || kind;
  }

  function activeAlarms() {
    const a = alarmState();
    const out = [];
    if (a.batt) {
      const v = S.batt.v === null ? '—' : S.batt.v.toFixed(2);
      out.push({ kind: 'batt', sev: a.batt, text: `电量 ${Math.round(S.batt.p)}% · ${v}V`, summary: `${a.batt === 'bad' ? '危险' : '偏低'} · ${Math.round(S.batt.p)}% · ${v} V` });
    }
    if (a.motor) out.push({ kind: 'motor', sev: a.motor, text: `电机 ${Math.round(S.temp)}°C`, summary: `最热舵机 ${Math.round(S.temp)}°C` });
    if (a.cpu) out.push({ kind: 'cpu', sev: a.cpu, text: `主控 ${Math.round(S.cpu)}°C`, summary: `主控 ${Math.round(S.cpu)}°C` });
    if (a.loop) out.push({ kind: 'loop', sev: a.loop, text: `控制环 ${S.hz.toFixed(1)} Hz`, summary: `${S.hz.toFixed(1)} Hz · missed ${S.missed}` });
    if (S.fallen) out.push({ kind: 'fallen', sev: 'bad', text: '检测到倒地', summary: `倾角 ${S.tilt.toFixed(1)}°` });
    else if (a.tilt) out.push({ kind: 'tilt', sev: a.tilt, text: `倾斜 ${S.tilt.toFixed(0)}°`, summary: `机身倾斜 ${S.tilt.toFixed(0)}°（倒地门限 60°）` });
    if (S.padd) out.push({ kind: 'padd', sev: 'warn', text: '手柄服务运行中', summary: 'padd 会覆盖手机指令' });
    if (limitIsReal()) {
      out.push({
        kind: 'limit', sev: 'warn', text: '指令未执行',
        summary: S.limited.map(limitZh).join(' / '),
      });
    }
    return out;
  }

  // 机器人静止时 `limited_by` 常年是 ["deadman"]——那是"没有新指令"，不是故障。
  // 只有"刚给过非零请求，却被归零了"才值得显示（设计稿 §5.3）。
  const INPUT_WINDOW_MS = 500;

  function limitIsReal() {
    if (!S.limited.length) return false;
    const onlyDeadman = S.limited.every((x) => x === 'deadman');
    if (!onlyDeadman) return true;
    return performance.now() - S.lastInputAt < INPUT_WINDOW_MS;
  }

  function worstSev(...sevs) {
    if (sevs.includes('bad')) return 'bad';
    if (sevs.includes('warn')) return 'warn';
    return null;
  }

  // ── 渲染 ───────────────────────────────────────────────────────────────
  function pct(v) { return v === null || v === undefined || Number.isNaN(v) ? '—' : `${Math.round(v)}%`; }
  function deg(v) { return v === null || v === undefined || Number.isNaN(v) ? '—' : `${Math.round(v)}°`; }
  function radDeg(v) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
    const d = Math.round(Number(v) * 180 / Math.PI);
    return `${d >= 0 ? '+' : '−'}${Math.abs(d)}°`;
  }

  function render() {
    updateTopbar();
    updateStatus();
    updateStatusPage();
    updateBanner();
    updateActions();
    updateMaintenance();
    updateStickModeUI();
    renderPolicyBar();
    updateDynUI();
    updateActUI();
  }

  function updateTopbar() {
    const a = alarmState();
    const list = activeAlarms();
    const online = S.link === 'online';
    const readonly = online && S.role !== 'driver';

    const ro = online && S.ro;
    el.dot.className = 'dot' + (!online ? ' offline' : (readonly || ro) ? ' readonly' : '');
    el.statusBtn.dataset.conn = !online ? 'offline' : (readonly || ro) ? 'readonly' : 'online';
    // `policy` 一直是 "held"，卸力体现在 `safety.limp` 上——只看 policy 会在卸力后
    // 仍然显示"待命"，与红色的 pill 自相矛盾。
    el.policyText.textContent = S.limp ? '卸力' : (POLICY[S.policy] || S.policy);
    el.policyChip.className = 's-pill policy ' + (
      S.limp || S.policy === 'limp' ? 'limp'
        : S.policy === 'walk' ? 'walk'
          : (S.policy === 'homing' || S.policy === 'stand') ? 'home'
            : 'home');

    el.battPct.textContent = pct(S.batt.p);
    el.battFill.style.setProperty('--level', `${clamp(S.batt.p || 0, 0, 100)}%`);
    el.battMetric.className = 's-item batt' + (a.batt === 'bad' ? ' low' : a.batt === 'warn' ? ' warn' : '');

    el.hzVal.textContent = S.hz > 0 ? `${Math.round(S.hz)}` : '—';
    el.hzMetric.className = 's-item hz' + (a.loop === 'bad' ? ' bad' : a.loop === 'warn' ? ' warn' : '');

    el.tempVal.textContent = deg(S.temp);
    el.tempMetric.className = 's-item temp' + (a.motor === 'bad' ? ' bad' : a.motor === 'warn' ? ' warn' : '');

    el.cpuVal.textContent = deg(S.cpu);
    el.cpuMetric.className = 's-item cpu' + (a.cpu === 'bad' ? ' bad' : a.cpu === 'warn' ? ' warn' : '');

    el.alarmChip.classList.toggle('hidden', list.length === 0);
    el.alarmChip.classList.toggle('danger', list.some((x) => x.sev === 'bad'));
    el.alarmCount.textContent = String(list.length);
  }

  function updateStatus() {
    el.roVx.textContent = (S.req[0] >= 0 ? '+' : '') + S.req[0].toFixed(2);
    el.roYaw.textContent = (S.req[2] >= 0 ? '+' : '') + S.req[2].toFixed(2);
    el.barReq.style.width = `${clamp(Math.abs(S.req[0]) / 0.3 * 100, 0, 100)}%`;
    el.barApp.style.width = `${clamp(Math.abs(S.applied[0]) / 0.3 * 100, 0, 100)}%`;
    // pitch 在关节/协议里负值是抬头；界面上反过来显示，向上才是正数。
    el.roHeadReq.textContent = `${radDeg(S.headReq.yaw)} / ${radDeg(-S.headReq.pitch)}`;
    el.roHeadApp.textContent = `${radDeg(S.head[2])} / ${radDeg(-S.head[1])}`;
    const limited = limitIsReal();
    el.roLimit.classList.toggle('hidden', !limited);
    el.roLimit.textContent = limited ? `已限幅 · ${S.limited.map(limitZh).join(' / ')}` : '';

    const deg_ = S.tilt;
    el.tiltVal.textContent = `${deg_.toFixed(1)}°`;
    const ratio = clamp(deg_ / 30, 0, 1);
    const x = clamp(S.applied[1] * 26, -12, 12);
    const y = clamp(S.applied[0] * 18, -12, 12);
    el.tiltDot.style.transform = `translate(${x}px,${y}px)`;
    el.tiltBubble.className = 'bubble' + (S.fallen || ratio > 0.8 ? ' bad' : ratio > 0.5 ? ' warn' : '');

  }

  function updateStatusPage() {
    const online = S.link === 'online';
    const a = alarmState();
    const list = activeAlarms();
    const readonly = online && S.role !== 'driver';

    const ro = online && S.ro;
    el.stConn.textContent = !online ? '未连接' : ro ? '只读模式' : readonly ? '只读（他人在驾驶）' : '已连接';
    el.stIp.textContent = online ? (location.host || '—') : '—';
    el.stPolicy.textContent = POLICY[S.policy] || S.policy;
    el.stPolicyD.textContent = `policy=${S.policy} · limp=${S.limp} · fallen=${S.fallen}`;
    el.stHz.textContent = S.hz > 0 ? `${S.hz.toFixed(1)} Hz` : '—';
    el.stMissed.textContent = `missed ${S.missed}` + (a.loop ? ' · 阈值 48/45 Hz' : '');
    el.stBatt.textContent = pct(S.batt.p);
    el.stBattD.textContent = (S.batt.v === null ? '—' : `${S.batt.v.toFixed(2)} V`) + (a.batt ? ' · 阈值 7.3/7.0 V' : '');
    el.stMotor.textContent = S.temp === null ? '—' : `${Math.round(S.temp)}°C`;
    el.stCpu.textContent = S.cpu === null ? '—' : `${Math.round(S.cpu)}°C`;
    el.stInput.textContent = S.padd ? 'padd 运行中' : '仅手机';
    el.stInputD.textContent = S.padd ? '会覆盖手机指令 · 点此查看' : '无输入冲突';
    el.stVersion.textContent = `robotd ${S.robotd || '—'} · duckphone`;

    const setCard = (node, sev) => {
      if (node) node.className = 's-card' + (sev === 'bad' ? ' bad' : sev === 'warn' ? ' warn' : '');
    };
    setCard(el.stConnCard, online ? ((readonly || ro) ? 'warn' : null) : 'bad');
    setCard(el.stPolicyCard, S.fallen ? 'bad' : null);
    setCard(el.stHzCard, a.loop);
    setCard(el.stBattCard, a.batt);
    setCard(el.stTempCard, worstSev(a.motor, a.cpu));
    el.stInputCard.className = 's-card' + (S.padd ? ' warn' : '');

    if (ro) {
      el.statusAlarms.textContent = `⚠ 标定模式（robotd --commissioning）：能看状态，不能驾驶`;
      el.statusAlarms.className = 'status-alarms';
      return;
    }
    if (list.length) {
      el.statusAlarms.textContent = `⚠ ${list.length} 项告警 · ${list.map((x) => x.text).join(' / ')}`;
      el.statusAlarms.className = 'status-alarms' + (list.some((x) => x.sev === 'bad') ? ' danger' : '');
    } else {
      el.statusAlarms.className = 'status-alarms hidden';
    }
  }

  function updateMaintenance() {
    el.paddState.textContent = S.padd ? '运行中' : '未运行';
    el.paddState.className = 'v ' + (S.padd ? 'warn' : 'ok');
    el.maintHz.textContent = S.hz > 0 ? `${S.hz.toFixed(1)} Hz` : '—';
    el.maintTemp.textContent = `${S.cpu === null ? '—' : Math.round(S.cpu) + '°C'} / ${S.temp === null ? '—' : Math.round(S.temp) + '°C'}`;
    if (el.maintVersion) el.maintVersion.textContent = `robotd ${S.robotd || '—'} · 控制环 ${S.hz > 0 ? Math.round(S.hz) : '—'} Hz`;
    el.btnReboot.disabled = S.role !== 'driver' || S.link !== 'online';
    el.btnShutdown.disabled = S.role !== 'driver' || S.link !== 'online';
  }

  function updateBanner() {
    const a = currentAlert();
    if (!a) {
      el.banner.classList.add('hidden');
      return;
    }
    el.bannerText.textContent = a.banner || a.title;
    el.banner.classList.remove('hidden');
    el.banner.classList.toggle('danger', !!a.danger);
  }

  function canAct() {
    return S.link === 'online' && S.role === 'driver' && !S.ro;
  }

  function canDrive() {
    // 只有 walk 网络在驱动时才接受速度指令。跑技能时（roulade / kick_left…）
    // robotd 的优先级链是 skill > walk，推摇杆也不会动，所以这里直接禁用。
    return canAct() && !S.limp && !S.fallen && S.policy === 'walk';
  }

  // ── 预设动作 ───────────────────────────────────────────────────────────
  function canPresetAct() {
    return canAct() && !S.limp && !S.fallen && S.policy === 'walk'
      && !S.padd && !S.act && !(S.req[0] || S.req[2]);
  }

  function presetBlockedReason() {
    if (S.link !== 'online') return '未连接';
    if (S.role !== 'driver') return '只读会话不能播放';
    if (S.ro) return '机器人处于标定模式';
    if (S.limp) return '机器人已卸力，先站立';
    if (S.fallen) return '机器人倒地，先站起';
    if (S.policy !== 'walk') return '先站立并接管行走策略';
    if (S.padd) return '手柄服务正在运行，先停止它';
    if (S.req[0] || S.req[2]) return '机器人正在移动，先松开摇杆';
    if (S.act) return `还有动作在播放：${PRESETS[S.act]?.label || S.act}`;
    return '';
  }

  function updateActUI() {
    if (!el.actionsSheet) return;
    const readonly = S.link === 'online' && S.role !== 'driver';
    el.btnActions.disabled = S.link !== 'online';
    el.btnActions.classList.toggle('active', !el.actionsSheet.classList.contains('hidden'));
    if (el.actReadonly) el.actReadonly.classList.toggle('hidden', !readonly);

    if (el.actHint) {
      if (S.act) {
        el.actHint.textContent = `${S.actIdle ? '空闲动作' : '正在播放'}：${PRESETS[S.act]?.label || S.act}`;
      } else if (readonly) {
        el.actHint.textContent = '只读 · 可以看，不能播放';
      } else if (!canPresetAct()) {
        el.actHint.textContent = presetBlockedReason() || '现在不能播放';
      } else {
        el.actHint.textContent = '站立或静止时可播放；播放中一碰摇杆就停。';
      }
    }

    const p = S.act && S.actDur
      ? clamp((performance.now() - S.actStarted) / (S.actDur * 1000), 0, 1)
      : 0;
    for (const b of el.actGrid.querySelectorAll('.preset')) {
      const name = b.dataset.act;
      const playing = S.act === name;
      b.disabled = !playing && (!canPresetAct() || readonly);
      b.classList.toggle('playing', playing);
      const bar = b.querySelector('.p-bar i');
      if (bar) bar.style.width = playing ? `${Math.round(p * 100)}%` : '0';
      let badge = b.querySelector('.p-badge');
      if (playing && S.actIdle) {
        if (!badge) {
          badge = document.createElement('span');
          badge.className = 'p-badge';
          badge.textContent = '空闲动作';
          b.appendChild(badge);
        }
      } else if (badge) {
        badge.remove();
      }
    }
    if (el.btnActStop) el.btnActStop.disabled = !S.act;
  }

  function openActions() {
    hideSheets();
    stopStick();
    render();
    el.actionsSheet.classList.remove('hidden');
    el.btnActions.classList.add('active');
    pushSheet();
  }

  function closeActions() {
    el.actionsSheet.classList.add('hidden');
    el.btnActions.classList.remove('active');
    dropSheet();
  }

  async function startAction(name) {
    if (!PRESETS[name]) return;
    if (!canPresetAct()) { toast(presetBlockedReason() || '现在不能播放', 'warn'); return; }
    const res = await cmd('action', { action: name });
    if (!res.ok) { toast(res.reason || '动作被拒绝', 'err'); return; }
    S.act = name;
    S.actIdle = false;
    S.actStarted = performance.now();
    S.actDur = PRESETS[name].dur;
    if (res.sound === false) toast('动作已开始，但机器人没有发声', 'warn', 3200);
    else toast(`播放 ${PRESETS[name].label} · ${PRESETS[name].dur.toFixed(1)} s`);
    pushEvent('action', 'ok', `播放预设：${PRESETS[name].label}`, `${name} · ${PRESETS[name].dur.toFixed(1)} s`);
    render();
  }

  async function cancelAction() {
    if (!S.act) return;
    const name = S.act;
    S.act = null;
    S.actIdle = false;
    S.actStarted = 0;
    S.actDur = 0;
    render();
    const res = await cmd('cancelAction');
    if (!res.ok) toast(res.reason || '停止动作失败', 'err');
    else toast(`已停止 ${PRESETS[name]?.label || name}`);
  }

  function tickAction() {
    if (!S.act) return;
    if (S.actDur && performance.now() - S.actStarted > S.actDur * 1000 + 800) {
      S.act = null;
      S.actIdle = false;
      S.actStarted = 0;
      S.actDur = 0;
      render();
      return;
    }
    updateActUI();
  }

  function readPool() {
    if (!el.idlePool) return [];
    return [...el.idlePool.querySelectorAll('.pool-chip')]
      .filter((b) => b.classList.contains('on')).map((b) => b.dataset.pool);
  }

  function fillPool(pool) {
    if (!el.idlePool) return;
    const set = new Set(Array.isArray(pool) && pool.length ? pool : AUDIO_DEFAULTS.idle.library);
    for (const b of el.idlePool.querySelectorAll('.pool-chip')) {
      const on = set.has(b.dataset.pool);
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', String(on));
      b.disabled = !settingsCanEdit();
    }
  }

  let stickModeSig = '';
  function updateStickModeUI() {
    if (S.stickMode === stickModeSig) return;
    stickModeSig = S.stickMode;
    el.stickZone.dataset.mode = S.stickMode;
    el.stickGuide.innerHTML = S.stickMode === 'head'
      ? '<b>左右转头</b> · 上下抬头 · 松手回正'
      : '<b>按住拖动</b> · 松手即停';
    $$('#stickMode button').forEach((b) => {
      const on = b.dataset.stick === S.stickMode;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', String(on));
    });
  }

  function setStickMode(mode) {
    if (mode !== 'drive' && mode !== 'head') return;
    if (S.stickMode === mode) return;
    const hadHead = S.headReq.yaw !== 0 || S.headReq.pitch !== 0;
    S.stickMode = mode;
    S.req = [0, 0, 0];
    S.headReq = { yaw: 0, pitch: 0 };
    restStick();
    if (canAct()) {
      sendDrive();               // 切模式时把上一个模式的速度归零
      if (hadHead) sendHeadZero();
    }
    render();
    if (mode === 'head' && !canDrive()) {
      toast(S.policy === 'walk' ? '先接管行走策略' : '接管行走策略后才能控制头部', 'warn', 2600);
    }
  }

  function updateActions() {
    const drive = canDrive();
    el.stickZone.classList.toggle('disabled', !drive);
    el.btnStand.disabled = !canAct();
    el.btnEnable.disabled = !canAct();
    el.btnStop.disabled = !canAct();
    el.btnRelax.disabled = !canAct() || S.limp;
    el.btnMaint.disabled = false;
    // Read-only sessions may open the sound drawer to view the switch and the
    // settings, but must not play sounds or change volume.
    el.btnSound.disabled = S.link !== 'online';
    el.volRange.disabled = !canAct();
    el.btnMute.disabled = !canAct();
    for (const b of el.soundGrid.querySelectorAll('.snd')) b.disabled = !canAct();

    const walking = S.policy !== 'held' && !S.limp;
    el.enableLabel.textContent = walking ? '交还' : '接管';
    el.enableSub.textContent = walking ? '策略待命' : '让策略驱动';
    el.btnEnable.classList.toggle('enabled', walking);
    el.btnEnable.setAttribute('aria-label', walking ? '交还策略' : '接管策略');
  }

  function limitZh(x) {
    return ({ deadman: '指令超时', joint_range: '关节限位', not_finite: '数值非法' })[x] || x;
  }

  // ── 策略条 ─────────────────────────────────────────────────────────────
  // 目录（哪些槽位、叫什么、跑完去哪）来自桥的 `policies`；"现在在跑什么"
  // 直接用 state 里的 pol，不另做计时器 —— 界面和后端说的是同一个事实。
  function policyChips() {
    return (S.policies && Array.isArray(S.policies.chips)) ? S.policies.chips : [];
  }

  function policyState(chip) {
    if (!chip.ready) return 'missing';
    if (chip.kind === 'walk') return S.policy === 'walk' ? 'active' : 'idle';
    // walk 之外的槽位：robotd 报什么名字就是什么在跑
    return S.policy === chip.slot || S.policy === chip.skill ? 'active' : 'idle';
  }

  function policyGateOpen() {
    // 没接管（held）或没连上时不能执行策略：robot.do 会被拒，硬发只会留一堆错误
    return canAct() && !S.limp && S.policy !== 'held';
  }

  let policySig = '';

  function maybeRefreshPolicies() {
    if (S.link !== 'online') return;
    if (!S.policiesAt || Date.now() - S.policiesAt > POLICY_REFRESH_MS) requestPolicies(false);
  }

  function renderPolicyBar(force) {
    // 每次 state（20 Hz）都会走到这里，重建 innerHTML 是白烧 CPU 且会吃掉点击。
    // 只有"内容真的变了"才重画。
    const sig = JSON.stringify([
      S.policy, S.limp, S.policies, policyGateOpen(), el.policyBar.dataset.open,
    ]);
    if (!force && sig === policySig) return;
    policySig = sig;

    const chips = policyChips();
    if (!chips.length) {
      el.policyChips.innerHTML = '<span class="chip" data-state="missing">策略不可用</span>';
      el.policyBar.dataset.locked = 'true';
      return;
    }
    const open = policyGateOpen();
    el.policyBar.dataset.locked = open ? 'false' : 'true';
    el.policyKey.textContent = open ? '策略' : '策略（需接管）';
    el.policyChips.innerHTML = chips.map((c) => {
      const st = policyState(c);
      const dis = !open || st === 'missing' || st === 'active' && c.kind === 'walk';
      return `<button class="chip" type="button" data-slot="${c.slot}" data-state="${st}"` +
             ` title="${escapeAttr(c.name)}"${dis ? ' disabled' : ''}>` +
             `${escapeText(c.short)}</button>`;
    }).join('');
    if (el.policyBar.dataset.open === 'true') renderPolicyPanel();
  }

  function renderPolicyPanel() {
    const chips = policyChips();
    const open = policyGateOpen();
    el.policyPanel.innerHTML = chips.map((c) => {
      const st = policyState(c);
      const badge = st === 'active' ? '在用' : st === 'missing' ? '未配置' : '';
      const sub = st === 'missing'
        ? `${c.slot} · ${c.error || '缺少 policy.onnx'}`
        : `${c.slot} · ${c.label}`;
      const dis = !open || st === 'missing' || st === 'active' && c.kind === 'walk';
      return `<button class="pp" type="button" role="option" data-slot="${c.slot}" data-state="${st}"` +
             `${dis ? ' disabled' : ''}>` +
             '<span class="pp-dot"></span>' +
             '<span class="pp-txt">' +
             `<span class="pp-name">${escapeText(c.name)}</span>` +
             `<span class="pp-sub">${escapeText(sub)}</span>` +
             '</span>' +
             (badge ? `<span class="pp-badge">${badge}</span>` : '') +
             '</button>';
    }).join('') +
      `<div class="pp-note">${open
        ? '点一次执行一次：前滚翻 1 s、踢球 0.5 s、拾取 2.8 s，跑完自动回到「行走」；坐下/站起是开关。只有「行走」时方向盘能驱动运动。'
        : '现在没有策略在驱动，不能执行 —— 先点「接管」让策略跑起来。'}</div>`;
  }

  function setPolicyOpen(open) {
    el.policyBar.dataset.open = open ? 'true' : 'false';
    el.policyToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    el.policyPanel.classList.toggle('hidden', !open);
    if (open) {
      renderPolicyPanel();
      requestPolicies(false);
    }
  }

  function requestPolicies(fresh) {
    if (S.link !== 'online') return;
    wsSend({ t: 'cmd', id: ++cmdSeq, name: 'policies', fresh: !!fresh });
  }

  async function runPolicy(slot) {
    const chip = policyChips().find((c) => c.slot === slot);
    if (!chip) return;
    if (!policyGateOpen()) { toast('先点「接管」让策略驱动', 'warn'); return; }
    if (!chip.ready) { toast(chip.error || '这个策略没有可执行的文件', 'warn'); return; }
    if (chip.kind === 'walk') { toast('已经是行走策略'); return; }
    stopStick();
    setPolicyOpen(false);
    const res = await cmd('policyDo', { skill: chip.skill });
    if (!res.ok) { toast(res.reason || '策略被拒绝', 'err', 3600); return; }
    if (res.policies) { S.policies = res.policies; S.policiesAt = Date.now(); renderPolicyBar(); }
    pushEvent('policy', 'ok', '执行策略', `${chip.slot} · ${chip.name}`);
    toast(`已切换至${chip.short}策略`);
  }

  el.policyChips.addEventListener('click', (e) => {
    const b = e.target.closest('.chip');
    if (b) runPolicy(b.dataset.slot);
  });
  el.policyPanel.addEventListener('click', (e) => {
    const b = e.target.closest('.pp');
    if (b) runPolicy(b.dataset.slot);
  });
  el.policyToggle.addEventListener('click', () => {
    setPolicyOpen(el.policyBar.dataset.open !== 'true');
  });
  document.addEventListener('pointerdown', (e) => {
    if (el.policyBar.dataset.open !== 'true') return;
    if (e.target.closest('#policyBar')) return;
    setPolicyOpen(false);
  }, true);

  // ── 事件记录 ───────────────────────────────────────────────────────────
  function fmtTime(ts) {
    const d = new Date(ts);
    const p = (n) => String(n).padStart(2, '0');
    return `${p(d.getHours())}:${p(d.getMinutes())}`;
  }

  function pushEvent(kind, sev, title, summary) {
    S.eventSeq += 1;
    S.events.unshift({ id: `e${S.eventSeq}`, t: Date.now(), kind, sev, title, summary: summary || '' });
    if (S.events.length > 10) S.events.length = 10;
    if (!el.alert.classList.contains('hidden')) renderMsgList();
  }

  // ── 提示 / 告警详情 ────────────────────────────────────────────────────
  function currentAlert() {
    if (S.link !== 'online') return null;
    const a = alarmState();
    const order = [];
    if (S.fallen) order.push('fallen');
    if (a.tilt === 'bad') order.push('tilt');
    if (a.batt === 'bad') order.push('batt');
    if (a.motor === 'bad') order.push('motor');
    if (a.cpu === 'bad') order.push('cpu');
    // 机身正在倒，比"手柄服务在跑"要紧得多
    if (a.tilt === 'warn') order.push('tilt');
    if (S.padd) order.push('padd');
    if (limitIsReal()) order.push('limit');
    if (a.batt === 'warn') order.push('batt');
    if (a.motor === 'warn') order.push('motor');
    if (a.cpu === 'warn') order.push('cpu');
    if (a.loop) order.push('loop');
    if (!order.length) return null;
    const detail = buildAlert(order[0]);
    if (detail) detail.kind = order[0];
    return detail;
  }

  function buildAlert(kind) {
    const reason = S.limited.map(limitZh).join(' / ');
    const reqTxt = `${S.robotReq[0].toFixed(2)} m/s · ${S.robotReq[2].toFixed(2)} rad/s`;
    const appTxt = `${S.applied[0].toFixed(2)} m/s · ${S.applied[2].toFixed(2)} rad/s`;

    if (kind === 'padd') {
      return {
        danger: false, kicker: '输入源 · 手柄',
        title: '手柄服务正在运行',
        banner: '手柄服务 (padd) 在运行，会覆盖手机指令',
        body: 'padd 在收到过摇杆输入后，会每 100 ms 重发一次速度帧，覆盖手机 20 Hz 的驾驶指令。联调前先停掉它；停掉后手柄不能再用。',
        ev: `<div class="ev-row"><span>状态</span><b>运行中</b></div>
             <div class="ev-row"><span>影响</span><b>手机与手柄互相覆盖</b></div>
             <div class="ev-row"><span>停止命令</span><code>sudo systemctl stop padd</code></div>`,
      };
    }
    if (kind === 'limit') {
      return {
        danger: false, kicker: '未执行 · 安全层',
        title: '指令没有被执行',
        banner: `未执行：${reason || '安全层限幅'}`,
        body: '机器人收到了速度请求，但安全层把它归零了。下面是原因和建议。',
        ev: `<div class="ev-row"><span>请求</span><b>${reqTxt}</b></div>
             <div class="ev-row"><span>实际</span><b>${appTxt}</b></div>
             <div class="ev-row"><span>原因</span><b>${reason || '—'}</b></div>
             <div class="ev-row"><span>建议</span><b>${suggestionForLimit()}</b></div>`,
      };
    }
    if (kind === 'batt') {
      return {
        danger: alarmState().batt === 'bad', kicker: '电量',
        title: '电量偏低',
        banner: `电量低：${pct(S.batt.p)} · ${(S.batt.v || 0).toFixed(2)} V`,
        body: '走路峰值电流会让电压瞬间下塌，可能出现掉力矩或板子重启。建议先充电再走。',
        ev: `<div class="ev-row"><span>当前</span><b>${pct(S.batt.p)} · ${(S.batt.v || 0).toFixed(2)} V</b></div>
             <div class="ev-row"><span>阈值</span><b>25% / 7.3 V 预警 · 15% / 7.0 V 危险</b></div>
             <div class="ev-row"><span>建议</span><b>充电到 7.8 V 以上</b></div>`,
      };
    }
    if (kind === 'fallen') {
      return {
        danger: true, kicker: '姿态',
        title: '检测到倒地',
        banner: '已检测到倒地；仍可站立/卸力',
        body: '机器人报告 fallen。它仍然可以站立、卸力或重启舵机；先把周围清空，确认是吊架还是地面。',
        ev: `<div class="ev-row"><span>倾角</span><b>${S.tilt.toFixed(1)}°</b></div>
             <div class="ev-row"><span>建议</span><b>${S.limp ? '先点“站立”重新上力' : '点“站立”回 HOME，或长按卸力'}</b></div>`,
        stand: true,
      };
    }
    if (kind === 'tilt') {
      const sev = alarmState().tilt;
      return {
        danger: sev === 'bad', kicker: '姿态',
        title: '机身倾斜过大',
        banner: `机身倾斜 ${S.tilt.toFixed(0)}°：机器人可能正在倒`,
        body: '机身已经明显偏离直立。固件要到 60° 才判"倒地"，这之前它不会自己停下——先松开摇杆，扶住或准备接住它。',
        ev: `<div class="ev-row"><span>当前倾角</span><b>${S.tilt.toFixed(1)}°</b></div>
             <div class="ev-row"><span>阈值</span><b>30° 预警 · 60° 判为倒地</b></div>
             <div class="ev-row"><span>建议</span><b>松手让它自己稳，或长按卸力</b></div>`,
      };
    }
    if (kind === 'motor') {
      return {
        danger: alarmState().motor === 'bad', kicker: '温度 · 电机',
        title: '电机温度偏高',
        banner: `电机温度偏高：${S.temp === null ? '—' : Math.round(S.temp) + '°C'}`,
        body: '最热舵机接近或超过建议上限。继续走路可能触发热保护或掉力矩。',
        ev: `<div class="ev-row"><span>最热舵机</span><b>${S.temp === null ? '—' : Math.round(S.temp) + '°C'}</b></div>
             <div class="ev-row"><span>阈值</span><b>50°C 预警 · 60°C 危险</b></div>
             <div class="ev-row"><span>建议</span><b>停下散热，检查是否卡住</b></div>`,
      };
    }
    if (kind === 'cpu') {
      return {
        danger: alarmState().cpu === 'bad', kicker: '温度 · 主控',
        title: '主控温度偏高',
        banner: `主控温度偏高：${S.cpu === null ? '—' : Math.round(S.cpu) + '°C'}`,
        body: 'SoC 温度接近或超过降频阈值。控制环可能掉频，先降低负载或停机散热。',
        ev: `<div class="ev-row"><span>主控</span><b>${S.cpu === null ? '—' : Math.round(S.cpu) + '°C'}</b></div>
             <div class="ev-row"><span>阈值</span><b>70°C 预警 · 85°C 危险</b></div>
             <div class="ev-row"><span>建议</span><b>停止驾驶，检查散热/环境温度</b></div>`,
      };
    }
    if (kind === 'loop') {
      return {
        danger: alarmState().loop === 'bad', kicker: '控制环',
        title: '控制环频率偏低',
        banner: `控制环频率偏低：${S.hz.toFixed(1)} Hz`,
        body: '50 Hz 控制环没有跑满，可能是 CPU 负载、总线超时或散热降频。走路会变得不稳。',
        ev: `<div class="ev-row"><span>当前</span><b>${S.hz.toFixed(1)} Hz</b></div>
             <div class="ev-row"><span>丢步</span><b>missed ${S.missed}</b></div>
             <div class="ev-row"><span>阈值</span><b>48 Hz 预警 · 45 Hz 危险</b></div>`,
      };
    }
    return null;
  }

  function suggestionForLimit() {
    if (S.limited.includes('deadman')) return '摇杆保持按住；检查 Wi-Fi';
    if (S.limited.includes('joint_range')) return '降低速度/角度；检查关节是否卡住';
    if (S.limited.includes('not_finite')) return '松开摇杆重试；持续出现就看日志';
    return '松开摇杆重试';
  }

  let currentAlertDetail = null;
  let currentAlertEventId = null;
  let currentAlertAt = 0;
  let viewingEventId = null;

  function renderAlertView(a, isCurrent) {
    el.alertIco.className = 'alert-ico' + (a.danger ? ' danger' : '');
    el.alertKicker.textContent = a.kicker || '提示';
    el.alertTitle.textContent = a.title || '';
    el.alertBody.textContent = a.body || '';
    el.alertEv.innerHTML = a.ev || '';
    const isPadd = a.kind === 'padd';
    const canStop = isCurrent && isPadd && S.paddCanStop;
    el.alertPadd.classList.toggle('hidden', !canStop);
    el.alertCopy.classList.toggle('hidden', !(isCurrent && isPadd));
    // 不能一键停时，"复制命令"就是主按钮
    el.alertCopy.classList.toggle('primary', !canStop);
    el.alertCopy.classList.toggle('ghost', canStop);
    el.alertStand.classList.toggle('hidden', !(isCurrent && a.stand));
    el.alertBack.classList.toggle('hidden', isCurrent || !currentAlertDetail);
  }

  function renderMsgList() {
    const items = S.events.slice();
    if (currentAlertDetail && !currentAlertEventId) {
      items.unshift({
        id: '__current', t: currentAlertAt, kind: currentAlertDetail.kind,
        sev: currentAlertDetail.danger ? 'bad' : 'warn',
        title: currentAlertDetail.title, summary: currentAlertDetail.banner || '',
      });
    }
    el.msgCount.textContent = `${items.length} 条`;
    if (!items.length) {
      el.msgList.innerHTML = '<div class="msg-empty">还没有消息</div>';
      return;
    }
    el.msgList.innerHTML = items.map((e) => {
      const dot = e.sev === 'bad' ? 'bad' : e.sev === 'warn' ? 'warn' : 'ok';
      return `<button class="msg${e.id === viewingEventId ? ' on' : ''}" data-id="${e.id}" type="button">
        <span class="msg-dot ${dot}"></span>
        <span class="msg-time">${fmtTime(e.t)}</span>
        <span class="msg-txt"><b>${escapeHtml(e.title)}</b><small>${escapeHtml(e.summary || '')}</small></span>
        <span class="msg-chev">›</span>
      </button>`;
    }).join('');
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function eventDetail(e) {
    if (e.id === '__current') return currentAlertDetail;
    if (e.detail) return e.detail;
    if (['padd', 'limit', 'motor', 'cpu', 'loop', 'batt', 'fallen', 'tilt'].includes(e.kind)) {
      const built = buildAlert(e.kind);
      if (built) return built;
    }
    return {
      danger: e.sev === 'bad', kicker: '记录', title: e.title,
      body: e.summary || '—',
      ev: `<div class="ev-row"><span>时间</span><b>${fmtTime(e.t)}</b></div>
           <div class="ev-row"><span>结果</span><b>${escapeHtml(e.summary || '—')}</b></div>`,
    };
  }

  function showEvent(id) {
    if (id === '__current') { backToCurrent(); return; }
    const e = S.events.find((x) => x.id === id);
    if (!e) return;
    viewingEventId = id;
    renderAlertView(eventDetail(e), false);
    renderMsgList();
  }

  function backToCurrent() {
    if (!currentAlertDetail) return;
    viewingEventId = currentAlertEventId || '__current';
    renderAlertView(currentAlertDetail, true);
    renderMsgList();
  }

  function openAlert(kind) {
    const detail = kind ? buildAlert(kind) : currentAlert();
    if (!detail) { toast('当前没有需要处理的提示'); return; }
    if (kind) detail.kind = kind;
    hideSheets();
    stopStick();
    currentAlertDetail = detail;
    currentAlertAt = Date.now();
    const match = S.events.find((e) => e.kind === detail.kind);
    currentAlertEventId = match ? match.id : null;
    viewingEventId = currentAlertEventId || '__current';
    renderAlertView(detail, true);
    renderMsgList();
    el.alert.classList.remove('hidden');
  }

  function closeAlert() { el.alert.classList.add('hidden'); }

  // ── 覆盖层 ─────────────────────────────────────────────────────────────
  // 一次 pushState 覆盖所有弹层：系统返回手势先关弹层，再退页面。
  let sheetOpen = false;

  function pushSheet() {
    if (sheetOpen) return;
    sheetOpen = true;
    try { history.pushState({ sheet: true }, ''); } catch (_) { sheetOpen = false; }
  }

  function dropSheet() {
    if (!sheetOpen) return;
    sheetOpen = false;
    try { history.back(); } catch (_) {}
  }

  function hideSheets() {
    stopWheee();
    el.alert.classList.add('hidden');
    el.status.classList.add('hidden');
    el.maint.classList.add('hidden');
    el.sound.classList.add('hidden');
    el.settings.classList.add('hidden');
    el.actionsSheet.classList.add('hidden');
    el.btnSound.classList.remove('active');
    el.btnActions.classList.remove('active');
  }

  function dismissSheets() {
    hideSheets();
    dropSheet();
  }

  function showReadonly(name) {
    el.readonlyWho.textContent = name || '另一台设备';
    el.readonly.classList.remove('hidden');
  }
  function hideReadonly() { el.readonly.classList.add('hidden'); }

  function showOffline() {
    S.offline = true;
    try {
      const last = JSON.parse(localStorage.getItem(LAST_KEY) || 'null');
      el.offlineLast.innerHTML = last
        ? `上次连接 <b>${last.time}</b> · ${last.policy} · ${last.pct}`
        : '还没有成功连接过';
    } catch (_) {
      el.offlineLast.textContent = '还没有成功连接过';
    }
    el.offline.classList.remove('hidden');
  }
  function hideOffline() {
    S.offline = false;
    el.offline.classList.add('hidden');
  }

  el.roRetry.addEventListener('click', () => {
    // 只重新发 hello：桥每 2 s 自己会重试 subscribe，重开 socket 反而会丢掉驾驶权。
    el.romode.classList.add('hidden');
    toast('正在重新检测…');
    if (sock && sock.readyState === WebSocket.OPEN) sendHello();
    else { attempt = 0; clearTimeout(retryTimer); retryTimer = 0; connect(); }
  });
  el.roStatus.addEventListener('click', () => { el.romode.classList.add('hidden'); openStatus(); });

  function openStatus() { hideSheets(); render(); el.status.classList.remove('hidden'); pushSheet(); }
  function openMaint() { hideSheets(); stopStick(); render(); el.maint.classList.remove('hidden'); pushSheet(); }

  // ── 声音 ───────────────────────────────────────────────────────────────
  function applyVolume(value, muted) {
    const level = clamp(Math.round(Number(value) || 0), 0, 100);
    S.sound.volume = level;
    S.sound.mute = !!muted || level === 0;
    if (level > 0) S.sound.prev = level;
    el.volRange.value = String(level);
    el.volPct.textContent = `${level}%`;
    const off = S.sound.mute || level === 0;
    el.btnMute.classList.toggle('on', off);
    el.btnMute.textContent = off ? '取消静音' : '静音';
  }

  async function refreshVolume() {
    if (!canAct()) {
      el.volPct.textContent = '—';
      return;
    }
    const res = await cmd('volume');
    if (res.ok && typeof res.volume === 'number') applyVolume(res.volume, res.muted);
    else el.volPct.textContent = '—';
  }

  async function setVolume(level) {
    const previous = S.sound.volume;
    const target = clamp(Math.round(Number(level) || 0), 0, 100);
    const res = await cmd('volume', { level: target });
    if (!res.ok) {
      if (previous !== null) applyVolume(previous, S.sound.mute);
      toast(res.reason || '音量设置失败', 'err', 3600);
      return;
    }
    applyVolume(res.volume, res.muted);
    if (res.message) toast(res.message, 'warn', 3600);
    else toast(`音量 ${S.sound.volume}%`);
  }

  function audioCfg() {
    const raw = S.audio || {};
    const out = {};
    for (const key of Object.keys(AUDIO_DEFAULTS)) {
      out[key] = { ...AUDIO_DEFAULTS[key], ...(raw[key] || {}) };
    }
    return out;
  }

  function audioNoteText() {
    const idle = audioCfg().idle;
    const rep = idle.repeat_s % 60 === 0 && idle.repeat_s >= 60
      ? `${idle.repeat_s / 60} 分钟` : `${idle.repeat_s} 秒`;
    const pool = Array.isArray(idle.library) ? idle.library.length : 0;
    return `接管后默认开启；首次空闲 ${idle.after_s} s、之后每 ${rep}`
      + `${idle.gesture && pool ? `，从 ${pool} 个动作里随机` : ''}。`;
  }

  function updateDynUI() {
    if (!el.btnDynSound) return;
    const online = S.link === 'online';
    const can = online && S.role === 'driver' && !S.ro;
    const on = can && !!S.dyn;
    el.btnDynSound.setAttribute('aria-checked', String(on));
    el.btnDynSound.disabled = !can;
    if (!can) {
      el.dynState.textContent = !online ? '离线 · 不生效' : S.ro ? '标定模式 · 不生效' : '接管后可开启';
      el.dynNote.textContent = '动态声音只在手机接管驾驶后生效。';
    } else if (on) {
      el.dynState.textContent = '已开启 · 动作/告警/空闲会自动叫';
      el.dynNote.textContent = audioNoteText();
    } else {
      el.dynState.textContent = '已关闭 · 只响应手动点播';
      el.dynNote.textContent = '已关闭；下次接管会重新默认开启。';
    }
  }

  function settingsCanEdit() {
    return S.link === 'online' && S.role === 'driver' && !S.ro;
  }

  function fillSettingsForm(cfg) {
    const set = (ref, value) => { if (ref) ref.value = value; };
    set(el.setIdleFirst, cfg.idle.after_s);
    set(el.setIdleRepeat, cfg.idle.repeat_s);
    set(el.setIdleMax, cfg.idle.max_per_hour);
    set(el.setFallRepeat, cfg.fall.repeat_s);
    set(el.setFallMax, cfg.fall.max_repeats);
    set(el.setFallTail, cfg.fall.tail_s);
    set(el.setTiltDeg, cfg.tilt.deg);
    set(el.setTiltRepeat, cfg.tilt.repeat_s);
    const state = {
      gesture: cfg.idle.gesture,
      takeover: cfg.actions.takeover && cfg.actions.handback,
      skill: cfg.actions.skill_start && cfg.actions.skill_end,
      enable: cfg.actions.enable,
      refusal: cfg.actions.refusal,
      ...cfg.alerts,
    };
    for (const b of $$('[data-set-toggle]')) {
      b.setAttribute('aria-checked', String(state[b.dataset.setToggle] === true));
    }
    fillPool(cfg.idle.library);
    const can = settingsCanEdit();
    for (const input of el.settings.querySelectorAll('input')) input.disabled = !can;
    for (const b of $$('[data-set-toggle]')) b.disabled = !can;
    for (const b of el.idlePool?.querySelectorAll('.pool-chip') || []) b.disabled = !can;
    el.btnSettingsSave.disabled = !can;
    el.btnSettingsReset.disabled = !can;
    el.setHint.textContent = can
      ? '保存后立即生效；写入 /etc/duckphone/audio.json。总开关仍在声音抽屉。'
      : '只读会话只能查看；接管后才能保存。';
    el.setReadonly.textContent = can
      ? '恢复默认只改本页；点保存才写入。'
      : '动态声音设置与手机、调试台共用。';
  }

  function readSetToggle(name) {
    const b = $(`[data-set-toggle="${name}"]`);
    return b?.getAttribute('aria-checked') === 'true';
  }

  async function saveSettings() {
    if (!settingsCanEdit()) { toast('接管后才能保存设置', 'warn', 3000); return; }
    const num = (ref, fallback, lo, hi) => clamp(Number(ref?.value) || fallback, lo, hi);
    const first = num(el.setIdleFirst, 30, 5, 3600);
    let repeat = num(el.setIdleRepeat, 300, 5, 3600);
    if (repeat < first) repeat = first;
    const patch = {
      idle: {
        after_s: first,
        repeat_s: repeat,
        max_per_hour: num(el.setIdleMax, 12, 1, 60),
        gesture: readSetToggle('gesture'),
        library: readPool().length ? readPool() : AUDIO_DEFAULTS.idle.library,
      },
      fall: {
        repeat_s: num(el.setFallRepeat, 5, 2, 30),
        max_repeats: num(el.setFallMax, 6, 1, 20),
        tail_s: num(el.setFallTail, 60, 10, 600),
      },
      tilt: {
        deg: num(el.setTiltDeg, 30, 10, 60),
        repeat_s: num(el.setTiltRepeat, 10, 5, 120),
      },
      actions: {
        takeover: readSetToggle('takeover'),
        handback: readSetToggle('takeover'),
        skill_start: readSetToggle('skill'),
        skill_end: readSetToggle('skill'),
        enable: readSetToggle('enable'),
        refusal: readSetToggle('refusal'),
      },
      alerts: {
        fall: readSetToggle('fall'),
        tilt: readSetToggle('tilt'),
        battery: readSetToggle('battery'),
        motor: readSetToggle('motor'),
        cpu: readSetToggle('cpu'),
        loop: readSetToggle('loop'),
        bus: readSetToggle('bus'),
      },
    };
    el.btnSettingsSave.disabled = true;
    const res = await cmd('setAudioConfig', { patch });
    el.btnSettingsSave.disabled = false;
    if (!res.ok) { toast(res.reason || '保存失败', 'err', 3600); return; }
    if (res.config) S.audio = res.config;
    fillSettingsForm(audioCfg());
    updateDynUI();
    el.setHint.textContent = '已保存 · 设置立即生效';
    toast('动态声音设置已保存', 'ok', 3600);
    pushEvent('dyn', 'ok', '动态声音设置已更新', '节奏 / 动作反馈 / 告警类别');
  }

  function resetSettings() {
    fillSettingsForm(AUDIO_DEFAULTS);
    toast('已恢复默认，点保存才写入', 'warn', 2600);
  }

  function openSettings() {
    hideSheets();
    stopStick();
    render();
    fillSettingsForm(audioCfg());
    el.settings.classList.remove('hidden');
    pushSheet();
  }

  function closeSettings() {
    el.settings.classList.add('hidden');
    dropSheet();
  }


  function openSound() {
    hideSheets();
    stopStick();
    render();
    el.sound.classList.remove('hidden');
    el.btnSound.classList.add('active');
    pushSheet();
    refreshVolume();
  }

  function flashSound(btn, ms) {
    if (!btn) return;
    btn.classList.add('playing');
    clearTimeout(btn._t);
    btn._t = setTimeout(() => btn.classList.remove('playing'), ms);
  }

  async function playSound(tag, label) {
    if (!canAct()) { toast(blockedReason(), 'warn'); return; }
    const btn = el.soundGrid.querySelector(`[data-tag="${tag}"]`);
    flashSound(btn, 700);
    const res = await cmd('sound', { tag });
    if (!res.ok) { toast(res.reason || '播放被拒绝', 'err', 3600); return; }
    pushEvent('sound', 'ok', `播放${label}`, `${tag} · 单次播放`);
    toast(`播放 ${label} · ${tag}`);
  }

  // robotd 把 wheee 当成"电平"：只发一次 hold:true 会在约 300 ms 后自然衰减并落地，
  // 所以按住期间必须像手柄一样持续重发，松开才发 hold:false。
  let wheeeTimer = 0;
  function startWheeeRepeat() {
    clearInterval(wheeeTimer);
    wheeeTimer = setInterval(() => {
      if (!S.sound.wheee) return;
      wsSend({ t: 'cmd', id: ++cmdSeq, name: 'sound', tag: 'wheee', hold: true });
    }, 100);
  }

  function stopWheee() {
    clearInterval(wheeeTimer);
    wheeeTimer = 0;
    if (!S.sound.wheee) return;
    S.sound.wheee = false;
    const b = el.soundGrid.querySelector('[data-tag="wheee"]');
    if (b) b.classList.remove('playing');
    if (canAct()) cmd('sound', { tag: 'wheee', hold: false });
  }

  el.btnActions.addEventListener('click', openActions);
  el.btnActClose.addEventListener('click', closeActions);
  el.actionsSheet.addEventListener('click', (e) => {
    if (e.target === el.actionsSheet) closeActions();
  });
  el.actGrid.addEventListener('click', (e) => {
    const b = e.target.closest('.preset');
    if (!b || b.disabled) return;
    startAction(b.dataset.act);
  });
  el.btnActStop.addEventListener('click', () => cancelAction());
  el.idlePool.addEventListener('click', (e) => {
    const b = e.target.closest('.pool-chip');
    if (!b || b.disabled) return;
    const on = !b.classList.contains('on');
    if (!on && readPool().length <= 1) { toast('随机池至少保留一个动作', 'warn'); return; }
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', String(on));
  });

  el.btnSound.addEventListener('click', openSound);
  el.btnSoundClose.addEventListener('click', dismissSheets);
  el.sound.addEventListener('click', (e) => { if (e.target === el.sound) dismissSheets(); });

  el.btnDynSound.addEventListener('click', async () => {
    if (!canAct()) { toast(blockedReason(), 'warn'); return; }
    const want = !S.dyn;
    el.btnDynSound.disabled = true;
    const res = await cmd('dynamicSound', { on: want });
    el.btnDynSound.disabled = false;
    if (!res.ok) { toast(res.reason || '动态声音切换失败', 'err', 3600); return; }
    S.dyn = typeof res.enabled === 'boolean' ? res.enabled : want;
    render();
    toast(S.dyn ? '动态声音已开启' : '动态声音已关闭 · 只响应手动点播', S.dyn ? 'ok' : 'warn');
    pushEvent('dyn', 'ok', S.dyn ? '动态声音已开启' : '动态声音已关闭', '手机与调试台共用');
  });
  el.btnDynSettings.addEventListener('click', openSettings);
  el.btnSettingsClose.addEventListener('click', closeSettings);
  el.btnSettingsSave.addEventListener('click', saveSettings);
  el.btnSettingsReset.addEventListener('click', resetSettings);
  el.settings.addEventListener('click', (e) => { if (e.target === el.settings) closeSettings(); });
  for (const b of $$('[data-set-toggle]')) {
    b.addEventListener('click', () => {
      b.setAttribute('aria-checked', b.getAttribute('aria-checked') === 'true' ? 'false' : 'true');
    });
  }

  el.soundGrid.addEventListener('click', (e) => {
    const b = e.target.closest('.snd');
    if (!b || b.dataset.tag === 'wheee') return;
    if (!SOUND_TAGS.includes(b.dataset.tag)) return;
    playSound(b.dataset.tag, b.dataset.label);
  });

  const wheeeBtn = el.soundGrid.querySelector('[data-tag="wheee"]');
  wheeeBtn.addEventListener('pointerdown', (e) => {
    if (!canAct()) { toast(blockedReason(), 'warn'); return; }
    e.preventDefault();
    e.stopPropagation();
    S.sound.wheee = true;
    wheeeBtn.classList.add('playing');
    cmd('sound', { tag: 'wheee', hold: true }).then((res) => {
      if (!res.ok) {
        stopWheee();
        toast(res.reason || '长叫被拒绝', 'err', 3600);
      }
    });
    startWheeeRepeat();
    pushEvent('sound', 'ok', '长叫开始', 'wheee · 按住持续');
    vibrate(10);
  });
  ['pointerup', 'pointercancel', 'pointerleave'].forEach((ev) =>
    wheeeBtn.addEventListener(ev, stopWheee));
  window.addEventListener('blur', stopWheee);

  el.volRange.addEventListener('input', () => {
    const level = clamp(Math.round(Number(el.volRange.value) || 0), 0, 100);
    el.volPct.textContent = `${level}%`;
    el.btnMute.classList.toggle('on', level === 0);
    el.btnMute.textContent = level === 0 ? '取消静音' : '静音';
  });
  el.volRange.addEventListener('change', () => { setVolume(el.volRange.value); });
  el.btnMute.addEventListener('click', () => {
    const current = Number(el.volRange.value) || 0;
    const target = current > 0 ? 0 : (S.sound.prev > 0 ? S.sound.prev : 60);
    setVolume(target);
  });

  // ── 摇杆 ───────────────────────────────────────────────────────────────

  // ── 自适应尺寸 ─────────────────────────────────────────────────────────
  // 手机浏览器带地址栏时，`100vh` 是"地址栏收起后"的大视口，底部按钮会被裁掉；
  // `dvh` 在华为浏览器不生效。所以用 innerHeight 实测，写进 --app-h 让布局跟着走。
  // 摇杆直径同理：不写死 px，按摇杆区实际大小算，屏幕大小变化时自动缩放。
  function syncAppHeight() {
    const vv = window.visualViewport;
    const h = Math.round((vv && vv.height) || window.innerHeight || 0);
    if (h > 0) document.documentElement.style.setProperty('--app-h', `${h}px`);
    sizeStick();
  }

  function sizeStick() {
    const zone = el.stickZone;
    if (!zone) return;
    const w = zone.clientWidth || 0;
    const h = zone.clientHeight || 0;
    if (w < 40 || h < 40) return;
    // 直径取"短边的 0.62"，再夹到 84–248：小屏不至于溢出轨杆区，大屏不至于空
    const d = Math.round(Math.max(84, Math.min(248, Math.min(w, h) * 0.62)));
    document.documentElement.style.setProperty('--stick-d', `${d}px`);
    try {
      if (!stick.active) restStick();
    } catch (_) { /* 初始化早于 stick 声明，首帧由 init 收尾 */ }
  }

  window.addEventListener('resize', syncAppHeight);
  window.addEventListener('orientationchange', () => setTimeout(syncAppHeight, 120));
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', syncAppHeight);
  }
  if (window.ResizeObserver) {
    new ResizeObserver(() => sizeStick()).observe(el.stickZone);
  }

  const stick = { active: false, id: null, cx: 0, cy: 0 };

  function showStickBase(x, y) {
    el.stickBase.style.left = `${x}px`;
    el.stickBase.style.top = `${y}px`;
    el.stickBase.classList.add('on');
  }
  function moveKnob(dx, dy) { el.knob.style.transform = `translate(${dx}px,${dy}px)`; }
  function restStick() {
    el.stickBase.style.left = '50%';
    el.stickBase.style.top = '50%';
    el.stickBase.classList.remove('on');
    moveKnob(0, 0);
  }

  function setStickFromPoint(px, py) {
    let dx = px - stick.cx;
    let dy = py - stick.cy;
    const len = Math.hypot(dx, dy);
    if (len > STICK_R) { dx = (dx / len) * STICK_R; dy = (dy / len) * STICK_R; }
    const nx = dx / STICK_R;
    const ny = dy / STICK_R;
    const dead = Math.hypot(nx, ny) < 0.12;

    if (S.stickMode === 'head') {
      // 与 padd 一致：左右 → head_yaw，上下 → head_pitch。
      // 真机约定是 head_pitch 负值抬头（推上去 ny<0 → 负值），之前符号反了。
      S.headReq = dead
        ? { yaw: 0, pitch: 0 }
        : {
          yaw: clamp(-nx * HEAD_MAX, -HEAD_MAX, HEAD_MAX),
          pitch: clamp(ny * HEAD_MAX, -HEAD_MAX, HEAD_MAX),
        };
      moveKnob(dx, dy);
      sendHead();
      render();
      return;
    }

    if (dead) {
      S.req = [0, 0, 0];
    } else {
      const lim = SPEEDS[S.speed] || SPEEDS['0.2'];
      const vx = clamp(-ny * lim.vx, -lim.vx * 0.6, lim.vx);
      const vyaw = clamp(-nx * lim.yaw, -lim.yaw, lim.yaw);
      S.req = [vx, 0, vyaw];
    }
    moveKnob(dx, dy);
    sendDrive();
    render();
  }

  function sendDrive() {
    if (S.req[0] || S.req[2]) S.lastInputAt = performance.now();
    wsSend({ t: 'drive', vx: S.req[0], vyaw: S.req[2] });
  }

  let lastHeadAt = 0;
  function sendHead(force = false) {
    if (!canAct()) return;
    const now = performance.now();
    if (!force && now - lastHeadAt < 1000 / 50) return;
    lastHeadAt = now;
    wsSend({
      t: 'head', neck_pitch: 0, head_pitch: S.headReq.pitch,
      head_yaw: S.headReq.yaw, head_roll: 0,
    });
  }

  function sendHeadZero() {
    lastHeadAt = performance.now();
    wsSend({ t: 'head', neck_pitch: 0, head_pitch: 0, head_yaw: 0, head_roll: 0 });
  }

  function stopStick() {
    stick.active = false;
    stick.id = null;
    S.req = [0, 0, 0];
    const wasHead = S.headReq.yaw !== 0 || S.headReq.pitch !== 0;
    S.headReq = { yaw: 0, pitch: 0 };
    restStick();
    if (canAct()) {
      sendDrive();
      if (wasHead || S.stickMode === 'head') sendHeadZero();
    }
    render();
  }

  el.stickZone.addEventListener('pointerdown', (e) => {
    if (!canDrive()) return;
    if (e.target.closest('button')) return;
    const rect = el.stickZone.getBoundingClientRect();
    stick.active = true;
    stick.id = e.pointerId;
    stick.cx = e.clientX - rect.left;
    stick.cy = e.clientY - rect.top;
    showStickBase(stick.cx, stick.cy);
    moveKnob(0, 0);
    try { el.stickZone.setPointerCapture(e.pointerId); } catch (_) {}
    e.preventDefault();
  });

  el.stickZone.addEventListener('pointermove', (e) => {
    if (!stick.active || e.pointerId !== stick.id) return;
    const rect = el.stickZone.getBoundingClientRect();
    setStickFromPoint(e.clientX - rect.left, e.clientY - rect.top);
  });

  ['pointerup', 'pointercancel', 'lostpointercapture', 'pointerleave'].forEach((ev) =>
    el.stickZone.addEventListener(ev, () => { if (stick.active) stopStick(); }));
  window.addEventListener('blur', () => { if (stick.active) stopStick(); });

  el.stickMode.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-stick]');
    if (b) setStickMode(b.dataset.stick);
  });
  el.btnHeadReset.addEventListener('click', () => {
    S.headReq = { yaw: 0, pitch: 0 };
    if (canAct()) sendHeadZero();
    render();
    toast('头部已回正');
  });

  // 20 Hz 心跳：桥的看门狗是 250 ms，按住不动也要续命。
  // 头部意图也在这里重发——robotd 对 head 没有 deadman，桥靠新鲜度回正。
  setInterval(() => {
    if (S.stickMode === 'head' && (stick.active || S.headReq.yaw !== 0 || S.headReq.pitch !== 0)) {
      sendHead(true);
      return;
    }
    if (!stick.active) return;
    if (S.req[0] || S.req[2]) sendDrive();
    else wsSend({ t: 'drive', vx: 0, vyaw: 0 });
  }, HEAD_REFRESH_MS);

  // 键盘演示（电脑上评审用）
  const keys = new Set();
  window.addEventListener('keydown', (e) => {
    if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) return;
    if (!canDrive()) return;
    e.preventDefault();
    keys.add(e.key);
    if (S.stickMode === 'head') {
      S.headReq = {
        yaw: (keys.has('ArrowLeft') ? HEAD_MAX : 0) + (keys.has('ArrowRight') ? -HEAD_MAX : 0),
        pitch: (keys.has('ArrowUp') ? -HEAD_MAX : 0) + (keys.has('ArrowDown') ? HEAD_MAX : 0),
      };
      sendHead(true);
      render();
      return;
    }
    const lim = SPEEDS[S.speed] || SPEEDS['0.2'];
    const vx = (keys.has('ArrowUp') ? lim.vx : 0) + (keys.has('ArrowDown') ? -lim.vx * 0.6 : 0);
    const vyaw = (keys.has('ArrowLeft') ? lim.yaw : 0) + (keys.has('ArrowRight') ? -lim.yaw : 0);
    S.req = [vx, 0, vyaw];
    sendDrive();
    render();
  });
  window.addEventListener('keyup', (e) => {
    if (!keys.delete(e.key)) return;
    if (!keys.size) {
      S.req = [0, 0, 0];
      S.headReq = { yaw: 0, pitch: 0 };
      if (canAct()) {
        sendDrive();
        if (S.stickMode === 'head') sendHeadZero();
      }
      render();
    }
  });

  // ── 动作 ───────────────────────────────────────────────────────────────
  function blockedReason() {
    if (S.link !== 'online') return '还没连上';
    if (S.role !== 'driver') return '另一台设备在驾驶';
    if (S.ro) return '机器人处于标定模式，不能发运动指令';
    return '现在不能操作';
  }

  // 只要求"这台设备有控制权"，不要求 robotd 接受运动指令。
  // 停 padd 是主机侧动作，标定模式下同样应该能停——那正是最该停的时候。
  function canHost() {
    return S.link === 'online' && S.role === 'driver';
  }

  function hostCmd(name, extra = {}) {
    if (!canHost()) {
      return Promise.resolve({ ok: false, reason: blockedReason() });
    }
    return sendCmd(name, extra);
  }

  function cmd(name, extra = {}) {
    if (!canAct()) {
      return Promise.resolve({ ok: false, reason: blockedReason() });
    }
    return sendCmd(name, extra);
  }

  function sendCmd(name, extra = {}) {
    const id = ++cmdSeq;
    wsSend({ t: 'cmd', id, name, ...extra });
    return new Promise((resolve) => {
      pending.set(id, { resolve });
      setTimeout(() => {
        if (pending.delete(id)) resolve({ ok: false, reason: '超时' });
      }, 8000);
    });
  }

  el.btnStand.addEventListener('click', async () => {
    if (!canAct()) { toast(blockedReason(), 'warn'); return; }
    const res = await cmd('init');
    if (!res.ok) { toast(res.reason || '站立被拒绝', 'err'); return; }
    toast('站立中…（约 2 秒）', 'warn');
    pushEvent('home', 'ok', '开始站立', '回 HOME');
    setTimeout(() => { if (canAct()) toast('已回 HOME，请扶稳'); }, 2100);
  });

  el.btnEnable.addEventListener('click', async () => {
    if (!canAct()) { toast(blockedReason(), 'warn'); return; }
    const walking = S.policy !== 'held' && !S.limp;
    const res = await cmd('enable', { on: !walking });
    if (!res.ok) { toast(res.reason || '策略切换被拒绝', 'err'); return; }
    if (walking) toast('已交还策略，机器人待命');
    else toast('已接管行走策略');
  });

  el.btnStop.addEventListener('click', async () => {
    if (!canAct()) { toast(blockedReason(), 'warn'); return; }
    stopStick();
    vibrate(40);
    const res = await cmd('stop');
    if (!res.ok) { toast(res.reason || '停止失败', 'err'); return; }
    toast('已停止 · 仍站立');
    pushEvent('stop', 'ok', '已停止', '指令已归零');
  });

  function bindHold(btn, ms, onDone) {
    let start = 0;
    let timer = 0;
    let active = false;
    const stopTimer = () => { if (timer) { clearInterval(timer); timer = 0; } };
    const reset = () => { btn.classList.remove('holding'); btn.style.setProperty('--hold', 0); };
    const cancel = () => { if (!active) return; active = false; stopTimer(); reset(); };

    btn.addEventListener('pointerdown', (e) => {
      if (btn.disabled) return;
      e.preventDefault();
      e.stopPropagation();
      active = true;
      start = performance.now();
      btn.classList.add('holding');
      btn.style.setProperty('--hold', 0.001);
      try { btn.setPointerCapture(e.pointerId); } catch (_) {}
      stopTimer();
      timer = setInterval(() => {
        if (!active) return;
        const p = clamp((performance.now() - start) / ms, 0, 1);
        btn.style.setProperty('--hold', p);
        if (p >= 1) {
          active = false;
          stopTimer();
          reset();
          onDone();
        }
      }, 30);
    });
    ['pointerup', 'pointercancel', 'lostpointercapture', 'pointerleave'].forEach((ev) =>
      btn.addEventListener(ev, cancel));
    return cancel;
  }

  // 长按 1.5 s 直接卸力，不再弹二次确认：按钮本身就是那道闸
  bindHold(el.btnRelax, RELAX_HOLD_MS, async () => {
    stopStick();
    vibrate(60);
    const res = await cmd('relax', { confirm: 'RELAX' });
    if (!res.ok) { toast(res.reason || '卸力被拒绝', 'err'); return; }
    S.req = [0, 0, 0];
    pushEvent('relax', 'warn', '已卸力', '机器人会瘫倒，需要重新站立');
    render();
    toast('已卸力 · 机器人会瘫倒', 'warn', 3200);
  });

  // 重启舵机：两次确认
  let rebootArmed = false;
  let rebootTimer = 0;
  el.btnReboot.addEventListener('click', async () => {
    if (!rebootArmed) {
      rebootArmed = true;
      el.btnReboot.textContent = '再点一次确认';
      rebootTimer = setTimeout(() => { rebootArmed = false; el.btnReboot.textContent = '重启舵机'; }, 3000);
      return;
    }
    clearTimeout(rebootTimer);
    rebootArmed = false;
    el.btnReboot.textContent = '重启舵机';
    const res = await cmd('rebootMotors');
    if (!res.ok) { toast(res.reason || '重启被拒绝', 'err'); return; }
    pushEvent('reboot', 'warn', '舵机重启中', '会先切力矩');
    toast('舵机重启中…', 'warn');
    setTimeout(() => {
      pushEvent('reboot', 'ok', '舵机已重启', '请重新站立');
      toast('舵机已重启，请重新站立', 'warn', 3200);
    }, 1600);
  });

  // 关机：两步确认后才发。robotd 先坐下再断电，之后只能手动上电
  let shutdownArmed = false;
  let shutdownTimer = 0;
  el.btnShutdown.addEventListener('click', async () => {
    if (!shutdownArmed) {
      shutdownArmed = true;
      el.btnShutdown.textContent = '再点一次关机';
      shutdownTimer = setTimeout(() => {
        shutdownArmed = false;
        el.btnShutdown.textContent = '关机';
      }, 4000);
      return;
    }
    clearTimeout(shutdownTimer);
    shutdownArmed = false;
    el.btnShutdown.textContent = '关机';
    stopStick();
    const res = await cmd('shutdown', { confirm: 'SHUTDOWN' });
    if (!res.ok) { toast(res.reason || '关机被拒绝', 'err'); return; }
    pushEvent('shutdown', 'warn', '正在关机', '先坐下，然后断电；之后需要手动上电');
    toast('正在关机 · 会先坐下再断电', 'warn', 4000);
    dismissSheets();
  });

  // ── 速度档 ─────────────────────────────────────────────────────────────
  function setSpeed(v) {
    if (!SPEEDS[v]) return;
    S.speed = v;
    localStorage.setItem(SPEED_KEY, v);
    $$('#speedSeg button').forEach((b) => b.classList.toggle('on', b.dataset.speed === v));
  }
  $$('#speedSeg button').forEach((b) => b.addEventListener('click', () => setSpeed(b.dataset.speed)));

  // ── 顶栏 / 详情入口 ────────────────────────────────────────────────────
  el.statusBtn.addEventListener('click', openStatus);
  el.btnStatusClose.addEventListener('click', dismissSheets);
  el.btnStatusClose2.addEventListener('click', dismissSheets);
  el.status.addEventListener('click', (e) => { if (e.target === el.status) dismissSheets(); });
  el.stInputCard.addEventListener('click', () => openAlert('padd'));
  el.stInputCard.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openAlert('padd'); }
  });

  el.bannerAction.addEventListener('click', () => openAlert(null));
  el.btnMaint.addEventListener('click', openMaint);
  el.btnMaintClose.addEventListener('click', dismissSheets);
  el.maint.addEventListener('click', (e) => { if (e.target === el.maint) dismissSheets(); });
  el.btnInputDetail.addEventListener('click', () => openAlert('padd'));

  el.alertOk.addEventListener('click', dismissSheets);
  el.alertBack.addEventListener('click', backToCurrent);
  el.msgList.addEventListener('click', (e) => {
    const b = e.target.closest('.msg');
    if (b && b.dataset.id) showEvent(b.dataset.id);
  });
  el.alertStand.addEventListener('click', () => {
    dismissSheets();
    if (el.btnStand.disabled) { toast('当前不能站立，请先看维护面板', 'warn'); return; }
    el.btnStand.click();
  });
  el.alertCopy.addEventListener('click', async () => {
    const text = 'sudo systemctl stop padd';
    try {
      await navigator.clipboard.writeText(text);
      toast('命令已复制');
    } catch (_) {
      toast(`请手动复制：${text}`, 'warn', 4200);
    }
  });
  el.alertPadd.addEventListener('click', async () => {
    el.alertPadd.disabled = true;
    const res = await hostCmd('padd', { action: 'stop' });
    el.alertPadd.disabled = false;
    if (!res.ok) {
      toast(res.reason || '停不掉，请复制命令手动执行', 'err', 4200);
      return;
    }
    toast('手柄服务已停止');
    pushEvent('padd', 'ok', '手柄服务已停止', '手机可以独占控制');
  });

  // 只读
  el.btnTakeover.addEventListener('click', () => {
    wsSend({ t: 'takeover' });
    el.btnTakeover.disabled = true;
    setTimeout(() => { el.btnTakeover.disabled = false; }, 1500);
  });
  el.btnReadonlyClose.addEventListener('click', () => {
    hideReadonly();
    toast('只看状态 · 不能驾驶', 'warn');
  });

  // 离线
  el.btnRetry.addEventListener('click', () => {
    attempt = 0;
    clearTimeout(retryTimer);
    retryTimer = 0;
    hideOffline();
    dropSocket();
    connect();
  });
  el.btnHelp.addEventListener('click', () => window.open('/help.html', '_blank'));

  // 全屏（只做竖屏，全屏后不锁方向）
  el.btnFull.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch (_) {
      toast('这个浏览器不支持全屏', 'warn');
    }
  });

  // ── 停止路径 ───────────────────────────────────────────────────────────
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      S.req = [0, 0, 0];
      S.headReq = { yaw: 0, pitch: 0 };
      S.act = null;
      S.actIdle = false;
      S.actStarted = 0;
      S.actDur = 0;
      sendDrive();
      if (canAct()) sendHeadZero();
      stopWheee();
      try { navigator.sendBeacon('/stop', '{}'); } catch (_) {}
    } else {
      requestWakeLock();
      if (!sock) connect();
    }
  });

  window.addEventListener('pagehide', () => {
    S.req = [0, 0, 0];
    S.headReq = { yaw: 0, pitch: 0 };
    S.act = null;
    S.actIdle = false;
    S.actStarted = 0;
    S.actDur = 0;
    if (canAct()) sendHeadZero();
    stopWheee();
    try { navigator.sendBeacon('/stop', '{}'); } catch (_) {}
  });

  document.addEventListener('contextmenu', (e) => e.preventDefault());

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') dismissSheets();
  });
  window.addEventListener('popstate', () => {
    if (!sheetOpen) return;
    sheetOpen = false;
    hideSheets();
  });

  // ── 屏幕常亮 ───────────────────────────────────────────────────────────
  let wakeLock = null;

  async function requestWakeLock() {
    if (!('wakeLock' in navigator) || document.visibilityState !== 'visible') return;
    try {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release', () => { wakeLock = null; });
    } catch (_) { /* 华为浏览器可能拒绝，失败就让它黑屏，停止路径仍然成立 */ }
  }

  function vibrate(ms) {
    if (navigator.vibrate) { try { navigator.vibrate(ms); } catch (_) {} }
  }

  // ── Toast ──────────────────────────────────────────────────────────────
  function toast(msg, kind = 'ok', ms = 2400) {
    const d = document.createElement('div');
    d.className = `toast ${kind}`;
    d.textContent = msg;
    el.toasts.appendChild(d);
    while (el.toasts.children.length > 3) el.toasts.removeChild(el.toasts.firstChild);
    setTimeout(() => { d.style.opacity = '0'; d.style.transition = 'opacity .2s'; }, ms);
    setTimeout(() => d.remove(), ms + 240);
    vibrate(kind === 'err' ? 40 : 10);
  }

  // ── 上次状态 ───────────────────────────────────────────────────────────
  function rememberLast() {
    if (S.link !== 'online') return;
    const d = new Date();
    const p = (n) => String(n).padStart(2, '0');
    localStorage.setItem(LAST_KEY, JSON.stringify({
      time: `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`,
      policy: S.policy,
      pct: pct(S.batt.p),
    }));
  }
  setInterval(rememberLast, 5000);
  setInterval(maybeRefreshPolicies, 5000);
  setInterval(tickAction, 100);

  // ── Service Worker ─────────────────────────────────────────────────────
  let swReg = null;
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').then((reg) => {
        swReg = reg;
        if (reg.waiting) showUpdate();
        reg.addEventListener('updatefound', () => {
          const nw = reg.installing;
          if (!nw) return;
          nw.addEventListener('statechange', () => {
            if (nw.state === 'installed' && navigator.serviceWorker.controller) showUpdate();
          });
        });
        setInterval(() => reg.update(), 5 * 60 * 1000);
      }).catch(() => { /* 离线壳不可用也不影响局域网驾驶 */ });
    });
    navigator.serviceWorker.addEventListener('controllerchange', () => location.reload());
  }

  function showUpdate() { el.swUpdate.classList.remove('hidden'); }
  el.swReload.addEventListener('click', () => {
    if (swReg && swReg.waiting) swReg.waiting.postMessage({ t: 'skip-waiting' });
    else location.reload();
  });

  // ── 启动 ───────────────────────────────────────────────────────────────
  setSpeed(localStorage.getItem(SPEED_KEY) || '0.2');
  syncAppHeight();          // 第一帧就把可见高度和摇杆尺寸算准
  restStick();
  render();
  requestWakeLock();
  document.addEventListener('pointerdown', requestWakeLock, { once: true });
  connect();
})();
