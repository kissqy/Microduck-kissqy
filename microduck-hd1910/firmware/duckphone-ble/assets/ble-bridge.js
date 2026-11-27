/*
 * duckphone-ble · 页面桥
 *
 * 这段脚本在页面任何脚本之前注入（MainActivity 用 DOCUMENT_START_SCRIPT），把
 * `new WebSocket()` 换成本地实现，于是**原网页版与页面副本都不需要改**：
 *
 *   页面  ──{t:'drive'|'head'|'cmd'|…}──►  本桥  ──JSON-RPC──►  DuckNative(BLE)
 *   页面  ◄──{t:'state'|'policies'|'ack'|…}── 本桥  ◄──机器人帧──
 *
 * 为什么翻译放在 JS 而不是 Kotlin：页面协议属于 UI，跟传输无关；放在这里可以脱离
 * Android 单测，也方便以后换 WebRTC。
 *
 * 需要配置机器人与 PIN。三种来源，优先级从高到低：
 *   1. `window.duckBle.connect(address, pin)`
 *   2. URL 查询参数 `?bleAddress=..&blePin=..`
 *   3. localStorage 的 `duckble.address` / `duckble.pin`
 * 没有配置时，连接失败并给出可读原因——M2 的扫描/配对页会把第 1 条接上。
 */
(function () {
  if (window.__duckBleBridgeInstalled) return;
  window.__duckBleBridgeInstalled = true;

  // ── 配置 ───────────────────────────────────────────────────────────────
  // localStorage 在 file:// 或隐私模式下会抛异常；配置读不到就退回 URL 参数。
  function lsGet(key) { try { return localStorage.getItem(key) || ''; } catch (_) { return ''; } }
  function lsSet(key, value) { try { localStorage.setItem(key, value); } catch (_) {} }

  // 页面之间（连接页 / 驾驶页 / 网络页）是整页导航，JS 状态全丢；但同一个 WebView 里
  // sessionStorage 会保留，进程被杀才清空。用它存一份「最近一次可用状态」，新页面
  // 先按它渲染，等原生回报后再覆盖——切换页面时不会先闪一下「未连接」。
  function ssGet(key) { try { return sessionStorage.getItem(key) || ''; } catch (_) { return ''; } }
  function ssSet(key, value) { try { sessionStorage.setItem(key, value); } catch (_) {} }
  function ssRemove(key) { try { sessionStorage.removeItem(key); } catch (_) {} }

  var params = new URLSearchParams(location.search);
  var config = {
    address: lsGet('duckble.address') || params.get('bleAddress') || '',
    pin: lsGet('duckble.pin') || params.get('blePin') || '',
    // 广播名（`duck-dillon`）。只有扫描结果里有，连过之后记下来，离线浮层要显示它。
    name: lsGet('duckble.name') || '',
  };
  if (params.get('bleAddress')) lsSet('duckble.address', params.get('bleAddress'));
  if (params.get('blePin')) lsSet('duckble.pin', params.get('blePin'));

  var VX_MIN = -0.25, VX_MAX = 0.35, VYAW_MAX = 0.8;
  var PADDLESS = false;

  // ── 到原生的调用 ───────────────────────────────────────────────────────
  var native = window.DuckNative || null;
  var pendingCalls = Object.create(null);

  // 真机调试用：console.* 由 MainActivity 的 WebChromeClient 转到 logcat（tag DuckWeb）。
  // 页面本身不写日志，所以这里只记几条关键状态迁移，出问题时 `adb logcat -s DuckWeb` 够看。
  function logEvent() {
    try {
      console.log('[duckble] ' + Array.prototype.join.call(arguments, ' '));
    } catch (_) { /* 没有 console 就算了 */ }
  }
  function available() { return !!(window.DuckNative && window.DuckNative.call); }

  function rpc(method, params, timeoutMs) {
    return new Promise(function (resolve, reject) {
      if (!available()) { reject(new Error('原生桥不可用')); return; }
      // id 必须用**原生返回的那个**：JSON-RPC 的 id 由 Kotlin 的 RobotLink 分配，回答也带着
      // 它回来。早先这里是 JS 自己 `++callSeq`，翻页之后两边编号错开，回答就被当成"未知
      // 请求"丢掉了——表现正是认证成功后一直"连接中…"、订阅永远不返回。
      var id = window.DuckNative.call(method, JSON.stringify(params || {}), timeoutMs || 0);
      pendingCalls[id] = { resolve: resolve, reject: reject };
      logEvent('rpc→', id, method);
    });
  }

  function notify(method, params) {
    if (!available()) return;
    window.DuckNative.notify(method, JSON.stringify(params || {}));
  }

  // ── 页面状态（从精简帧 + 1 Hz 健康/手柄）───────────────────────────────
  var link = {
    state: 'down',        // down | scanning | connecting | authenticating | ready
    detail: '',
    /** 最近一次断开的原因。`detail` 会被 `connecting <地址>` 覆盖，不能拿来当原因。 */
    downReason: '',
    apiVersion: 0,
    mtu: 0,
    frame: null,
    health: null,
    padd: false,
    wifi: null,           // net.status 的最近一次回答
    socket: null,
    scanning: false,
    scanSeen: Object.create(null),
    lastDriveAt: 0,
    lastTwist: [0, 0],
    /** 自己主动断开的回声：随后的原生 `down` 不该盖掉已经给出的失败原因。 */
    localDown: false,
    /** 页面是否真的握过手（收到过 hello）。断链再连时用它判断浮层要不要兜底。 */
    pageBound: false,
    /** 首帧用的是上次会话的快照；原生回报 ready 后置回 false。 */
    cached: false,
    cachedState: 'ready',
    /** 页面正在 App 内跳转：这时关掉替身 socket 不该把底层 GATT 也断掉。 */
    navigating: false,
  };

  // ── 跨页面快照 ─────────────────────────────────────────────────────────
  // 整页导航会丢掉 JS 状态，但 GATT 仍在 Activity 里活着。新页面先用 sessionStorage
  // 里的上一份快照渲染（30 秒内有效），原生 `ready` 一到就被真实数据覆盖。
  var SNAP_TTL = 30000;
  var snap = null;
  try { snap = JSON.parse(ssGet('duckble.live') || 'null'); } catch (_) { snap = null; }
  if (snap && snap.at && (Date.now() - snap.at) < SNAP_TTL) {
    link.cached = true;
    link.cachedState = snap.state || 'ready';
    link.apiVersion = Number(snap.api) || 0;
    link.mtu = Number(snap.mtu) || 0;
    link.wifi = snap.wifi || null;
    link.health = snap.health || null;
    link.frame = snap.frame || null;
    link.padd = !!snap.padd;
  }

  function saveSnap() {
    if (link.state !== 'ready') return;
    ssSet('duckble.live', JSON.stringify({
      at: Date.now(),
      state: 'ready',
      api: link.apiVersion,
      mtu: link.mtu,
      wifi: link.wifi,
      health: link.health,
      frame: link.frame,
      padd: link.padd,
    }));
  }

  /** 界面用的状态：刚切页、还没收到原生回报时先显示上次快照。 */
  function shownState() {
    if (link.state === 'down' && link.cached) return link.cachedState;
    return link.state;
  }


  function emitState() {
    if (!link.socket || link.socket.readyState !== 1) return;
    var f = link.frame || {};
    var move = f.move || {};
    var safety = f.safety || {};
    var loop = f.loop || {};
    var gravity = safety.gravity || [0, 0, -1];
    var gz = Math.max(-1, Math.min(1, -Number(gravity[2] || -1)));
    var tilt = Math.acos(gz) * 180 / Math.PI;
    var health = link.health || {};
    // 页面按 `[volts, percent]` 取值（app.js 里 `S.batt = { v: msg.bat[0], p: msg.bat[1] }`），
    // 顺序反过来会把 7.9 V 显示成 "8%"，把 75% 显示成 "75.00 V"。
    var bat = health.battery ? [health.battery.volts, health.battery.percent] : null;
    var message = {
      t: 'state',
      ok: true,
      pol: f.policy || 'held',
      limp: !!safety.limp,
      fall: !!safety.fallen,
      mv: move.requested || [0, 0, 0],
      ap: move.applied || [0, 0, 0],
      head: f.head || [0, 0, 0, 0],
      lim: move.limited_by || [],
      hz: Number(loop.hz) || 0,
      missed: Number(loop.missed) || 0,
      tilt: tilt,
      padd: !!link.padd,
      paddCanStop: !PADDLESS,
      ro: false,
    };
    if (bat) message.bat = bat;
    if (health.motors && typeof health.motors.max_c === 'number') message.temp = health.motors.max_c;
    if (typeof health.cpu_temp_c === 'number') message.cpu = health.cpu_temp_c;
    // 正在播放的预设动作由 robotd 回传；没有就不发，省掉两帧空字段。
    if (f.act) {
      message.act = f.act;
      message.actIdle = !!f.actIdle;
    }
    link.socket.emit(message);
  }

  // 连续多少次健康检查超时就判定 GATT 已经假连接（对端 btd 重启、走远、适配器卡住）。
  // 假连接的表现是：页面仍显示「已连接」，但所有 RPC 都超时；不主动断开就永远回不来。
  var HEALTH_MISS_LIMIT = 5;
  var healthMisses = 0;

  function refreshHealth() {
    rpc('robot.health', {}).then(function (health) {
      healthMisses = 0;
      link.health = health || null;
      saveSnap();
      emitState();
    }).catch(function () {
      if (link.state !== 'ready') { healthMisses = 0; return; }
      healthMisses += 1;
      if (healthMisses < HEALTH_MISS_LIMIT) return;
      healthMisses = 0;
      logEvent('健康检查连续超时，判定链路无响应，强制重连');
      setLink('down', '链路无响应，正在重连');
      if (window.duckBle.onLink) window.duckBle.onLink('down', '链路无响应，正在重连');
      link.localDown = true;
      if (window.DuckNative) window.DuckNative.disconnect();
      startSession();
    });
    rpc('pad.status', {}).then(function (pad) {
      var driver = pad && pad.driver ? String(pad.driver) : '';
      link.padd = driver === 'active' || driver === 'activating' || driver === 'reloading';
      emitState();
    }).catch(function () { /* 没有 padd 时按“未运行”显示 */ });
  }

  /** 机器人自己的 Wi-Fi——与手机蓝牙是两条链路，所以必须分开显示。 */
  function refreshWifi() {
    rpc('net.status', {}).then(function (status) {
      link.wifi = status || null;
      saveSnap();
      renderLinkStrip();
    }).catch(function () {
      link.wifi = { state: 'unavailable' };
      renderLinkStrip();
    });
  }

  // ── 驾驶页顶栏下的双链路条 ────────────────────────────────────────────
  var strip = null;

  function mountLinkStrip() {
    // 驾驶页才有顶栏；`?strip=1` 是给无头测试用的，让它在任意页面上装一次。
    if (params.get('strip') !== '1' && location.pathname.indexOf('/duckphone/') < 0) return;
    if (document.getElementById('bleLinkStrip')) return;
    var topbar = document.getElementById('topbar');
    if (!topbar) return;
    strip = document.createElement('div');
    strip.id = 'bleLinkStrip';
    strip.style.cssText =
      'display:flex;gap:8px;align-items:center;padding:4px 12px 6px;' +
      'font-size:11px;color:#8b95a5;border-bottom:1px solid #2a303a;background:#15171b;';
    strip.innerHTML =
      '<span id="bleChip" style="display:inline-flex;align-items:center;gap:5px">' +
      '<i style="width:6px;height:6px;border-radius:50%;background:#8b95a5"></i>' +
      '<span>手机蓝牙</span></span>' +
      '<span style="color:#3a414d">|</span>' +
      '<span id="wifiChip" role="button" style="display:inline-flex;align-items:center;gap:5px">' +
      '<i style="width:6px;height:6px;border-radius:50%;background:#8b95a5"></i>' +
      '<span>机器人 Wi-Fi</span><span style="color:#5b6472">›</span></span>';
    topbar.parentNode.insertBefore(strip, topbar.nextSibling);
    // 点 Wi-Fi 这条去配网；机器人自己的网络与手机蓝牙无关。
    var wifiChip = document.getElementById('wifiChip');
    if (wifiChip) {
      wifiChip.addEventListener('click', function () {
        location.href = '../ble-network.html';
      });
    }
    renderLinkStrip();
  }

  /** 值没变就别碰 DOM：页面 10 Hz 更新时会触发这里的重写，避免无谓的重排/闪烁。 */
  function setText(el, text) {
    if (el && el.textContent !== text) el.textContent = text;
  }

  function chip(id, ok, warn, text) {
    var chipEl = document.getElementById(id);
    if (!chipEl) return;
    var dot = chipEl.getElementsByTagName('i')[0];
    var label = chipEl.getElementsByTagName('span')[0];
    var color = ok ? '#4ade80' : warn ? '#ffc53d' : '#6b7280';
    dot.style.background = color;
    setText(label, text);
  }

  function renderLinkStrip() {
    if (!strip && !document.getElementById('stConn')) return;
    var s = shownState();
    var bleText =
      s === 'ready' ? '手机蓝牙 已连接'
        : (s === 'connecting' || s === 'authenticating') ? '手机蓝牙 连接中…'
        : '手机蓝牙 未连接';
    var wifi = link.wifi || {};
    var state = String(wifi.state || '');

    if (strip) {
      chip('bleChip', s === 'ready',
        s === 'connecting' || s === 'authenticating', bleText);
      var wifiText = !link.wifi ? '机器人 Wi-Fi —'
        : state === 'connected' ? '机器人 Wi-Fi ' + (wifi.ssid || '已连接')
        : state === 'connecting' ? '机器人 Wi-Fi 连接中…'
        : state === 'unavailable' ? '机器人 Wi-Fi 无接口'
        : '机器人 Wi-Fi 未连接';
      chip('wifiChip', state === 'connected', state === 'connecting', wifiText);
    }

    // 页面自己的「连接」卡：原文是 WebSocket + location.host，在 App 里两者都不对，
    // 所以改写为两条真实链路。没有这个卡（连接页）时什么也不做。
    var connEl = document.getElementById('stConn');
    var ipEl = document.getElementById('stIp');
    if (connEl) setText(connEl, bleText);
    if (ipEl) {
      var where = state === 'connected' ? (wifi.ip4 || wifi.ssid || '已联网') : '机器人未联网';
      setText(ipEl, where +
        ' · api ' + (link.apiVersion || '—') +
        ' · MTU ' + (link.mtu || '—'));
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountLinkStrip);
  } else {
    mountLinkStrip();
  }

  // ── 精简帧缓存（Kotlin 通知转来的 robot.state）────────────────────────
  function onRobotFrame(frame) {
    link.frame = frame || null;
    emitState();
  }

  // ── 页面命令 → JSON-RPC ────────────────────────────────────────────────
  function clamp(value, lo, hi) {
    var v = Number(value);
    if (!isFinite(v)) return 0;
    return v < lo ? lo : v > hi ? hi : v;
  }

  function sendDrive(vx, vyaw) {
    // 双保险：robotd 也会限幅并回报 limited_by，这里保证抖动不会进 20 Hz 流。
    var twist = [clamp(vx, VX_MIN, VX_MAX), clamp(vyaw, -VYAW_MAX, VYAW_MAX)];
    link.lastTwist = twist;
    link.lastDriveAt = Date.now();
    notify('robot.move', { vx: twist[0], vy: 0, vyaw: twist[1] });
  }

  function sendHead(message) {
    notify('robot.head', {
      neck_pitch: Number(message.neck_pitch) || 0,
      head_pitch: Number(message.head_pitch) || 0,
      head_yaw: Number(message.head_yaw) || 0,
      head_roll: Number(message.head_roll) || 0,
    });
  }

  function ack(socket, id, payload) {
    var message = { t: 'ack', id: id, ok: !!payload.ok };
    ['reason', 'volume', 'muted', 'saved', 'message', 'enabled', 'action', 'sound'].forEach(function (key) {
      if (payload[key] !== undefined) message[key] = payload[key];
    });
    socket.emit(message);
  }

  function policyBar(report) {
    // 与 duckphone/server.py 的 POLICY_SLOTS 同步；槽位顺序是产品顺序。
    var slots = [
      { slot: 'walk', short: '行走', label: '行走／保持', kind: 'walk', skill: null, dur: 0 },
      { slot: 'sitstand', short: '坐下/站起', label: '坐下／站起', kind: 'latch', skill: 'sit_toggle', dur: 0 },
      { slot: 'ground_pick', short: '拾取', label: '地面捡取', kind: 'oneshot', skill: 'ground_pick', dur: 2.8 },
      { slot: 'kick_left', short: '左脚踢', label: '左脚踢球', kind: 'oneshot', skill: 'kick_left', dur: 0.5 },
      { slot: 'kick_right', short: '右脚踢', label: '右脚踢球', kind: 'oneshot', skill: 'kick_right', dur: 0.5 },
      { slot: 'roulade', short: '前滚翻', label: '前滚翻', kind: 'oneshot', skill: 'roulade', dur: 1.0 },
    ];
    // 没有自己槽位的技能（robotd 的 slots 是固定的，policy.skill 装的只出现在 skills 里）。
    // 新装的策略不用改代码：robot.reloadPolicies 之后刷新页面就多一个按钮。
    var extra = {
      crouch: { short: '深蹲', label: '深蹲', kind: 'oneshot', dur: 4.5 },
    };
    var byName = {};
    (report.slots || []).forEach(function (row) {
      if (row && typeof row.slot === 'string') byName[row.slot] = row;
    });
    var out = [];
    var covered = {};
    slots.forEach(function (meta) {
      if (meta.skill) covered[meta.skill] = true;
      var row = byName[meta.slot];
      if (!row) return;
      var path = typeof row.path === 'string' ? row.path : '';
      out.push({
        slot: meta.slot, short: meta.short, label: meta.label, kind: meta.kind,
        skill: meta.skill, dur: meta.dur,
        ready: meta.kind === 'walk' ? true : !!path,
        name: meta.label,
        desc: '',
        error: typeof row.error === 'string' ? row.error : null,
      });
    });
    (report.skills || []).forEach(function (skill) {
      if (typeof skill !== 'string' || covered[skill]) return;
      var meta = extra[skill] || {};
      var label = meta.label || skill;
      out.push({
        slot: skill, short: meta.short || label, label: label,
        kind: meta.kind || 'oneshot', skill: skill, dur: meta.dur || 0,
        ready: true, name: label, desc: '', error: null,
      });
    });
    return out;
  }

  function handleCommand(socket, message) {
    var name = message.name;
    var id = message.id;
    function done(result, extra) {
      var payload = extra || {};
      payload.ok = !!(result && result.accepted !== undefined ? result.accepted : result);
      if (result && result.reason) payload.reason = result.reason;
      ack(socket, id, payload);
    }
    switch (name) {
      case 'policies':
        return rpc('robot.policies', {}).then(function (report) {
          socket.emit({
            t: 'policies', ok: true, mode: report.mode || '',
            homed: report.homed, sitting: report.sitting,
            chips: policyBar(report || {}),
          });
          return { accepted: true };
        }).then(function (result) { done(result); })
          .catch(function (error) {
            socket.emit({ t: 'policies', ok: false, chips: [], reason: error.message });
            ack(socket, id, { ok: false, reason: error.message });
          });
      case 'policyDo':
        return rpc('robot.do', { skill: message.skill })
          .then(done).catch(function (e) { ack(socket, id, { ok: false, reason: e.message }); });
      case 'init':
        return rpc('robot.init', {})
          .then(done).catch(function (e) { ack(socket, id, { ok: false, reason: e.message }); });
      case 'enable':
        return rpc('robot.enable', { on: !!message.on })
          .then(done).catch(function (e) { ack(socket, id, { ok: false, reason: e.message }); });
      case 'stop':
        return rpc('robot.stop', {})
          .then(done).catch(function (e) { ack(socket, id, { ok: false, reason: e.message }); });
      case 'relax':
        return rpc('robot.relax', {})
          .then(done).catch(function (e) { ack(socket, id, { ok: false, reason: e.message }); });
      case 'rebootMotors':
        return rpc('robot.rebootMotors', { ids: [] })
          .then(done).catch(function (e) { ack(socket, id, { ok: false, reason: e.message }); });
      // 关机：robotd 先坐下再断电。桥不主动断开，等 btd 随系统一起消失，
      // 离线浮层由现有的断链逻辑接管。
      case 'shutdown':
        return rpc('robot.shutdown', {})
          .then(done).catch(function (e) { ack(socket, id, { ok: false, reason: e.message }); });
      case 'sound':
        return rpc('robot.sound', { tag: message.tag, hold: message.hold })
          .then(done).catch(function (e) { ack(socket, id, { ok: false, reason: e.message }); });
      // 预设动作由 robotd 播放（API 42），与网页版是同一份实现。
      case 'action':
        return rpc('robot.action', {
          action: message.action, idle: false, sound: true,
        }).then(function (result) {
          done(result, { action: message.action, sound: !!(result && result.sound) });
        }).catch(function (e) { ack(socket, id, { ok: false, reason: e.message }); });
      case 'cancelAction':
        return rpc('robot.action', {})
          .then(done).catch(function (e) { ack(socket, id, { ok: false, reason: e.message }); });
      case 'volume':
        return (message.level === undefined
          ? rpc('robot.volume', {})
          : rpc('robot.volume', { percent: Number(message.level) }))
          .then(function (result) {
            ack(socket, id, {
              ok: true, volume: result.percent, muted: result.muted, saved: true,
            });
          })
          .catch(function (e) { ack(socket, id, { ok: false, reason: e.message }); });
      case 'dynamicSound':
        // 动态声音是 duckphone 主机侧的开关，BLE 版没有对应方法；如实说明。
        ack(socket, id, { ok: false, reason: '蓝牙版暂不支持动态声音（网页版仍在）' });
        return;
      default:
        ack(socket, id, { ok: false, reason: '蓝牙版暂不支持：' + name });
    }
  }

  // ── 会话建立与重连 ─────────────────────────────────────────────────────
  function setLink(state, detail) {
    link.state = state;
    link.detail = detail || '';
    if (state === 'down') link.downReason = link.detail || '连接已断开';
    logEvent('link', state, link.detail);
    renderLinkStrip();
    if (link.socket) link.socket.emitLink();
  }

  function authenticate() {
    if (!config.pin) return Promise.reject(new Error('还没有配对 PIN'));
    return rpc('system.authenticate', { pin: config.pin }).then(function (result) {
      if (!result || !result.authenticated) {
        throw new Error('PIN 不正确（剩余 ' + (result && result.attempts_remaining) + ' 次）');
      }
      return result;
    });
  }

  function startSession() {
    if (!config.address) {
      setLink('down', '还没有机器人地址');
      return;
    }
    setLink('connecting', config.address);
    window.DuckNative.connect(config.address);
  }

  /**
   * 会话真的可用了才通知页面。
   *
   * 原生的 `ready` 只说明 GATT 连上了，认证、版本检查、状态订阅都还没做；连接页如果
   * 一见 `ready` 就跳到驾驶页，固件太旧这类错误就只会闪一下，用户看到的是驾驶页里
   * 一句含糊的「未连接」。
   */
  function announceReady() {
    var detail = 'api=' + link.apiVersion + ' mtu=' + link.mtu;
    if (window.duckBle.onLink) window.duckBle.onLink('ready', detail);
  }

  function onReady() {
    logEvent('ready: api', link.apiVersion, 'mtu', link.mtu);
    link.cached = false;
    authenticate()
      .then(function (authResult) {
        logEvent('authed', JSON.stringify(authResult));
        if (link.apiVersion < 42) {
          throw new Error(link.apiVersion
            ? '机器人固件是 API ' + link.apiVersion + '，需要 42；等新固件部署后再连'
            : '读不到机器人的 API 版本；断开后重新连接一次');
        }
        // 系统页（网络/维护）只需要一条已认证的会话，不订阅状态——那 10 Hz 的帧是
        // 驾驶页要的。没有 WebSocket 就说明当前不是驾驶页。
        if (!link.socket) {
          setLink('ready', 'api=' + link.apiVersion);
          saveSnap();
          announceReady();
          return null;
        }
        setLink('authenticating', '');
        return rpc('robot.subscribe', { hz: 10, profile: 'phone' });
      })
      .then(function (ackResult) {
        if (ackResult === null) return;
        logEvent('subscribed', JSON.stringify(ackResult));
        if (!ackResult || !ackResult.accepted) throw new Error('状态订阅被拒绝');
        setLink('ready', 'api=' + link.apiVersion);
        saveSnap();
        announceReady();
        refreshHealth();
        refreshWifi();
        // 页面已经握过手（切页快照分支会在认证前就 open）时，不要再把 pageBound 清掉
        // 等第二次 open——那次 open 不会再发生，4 s 后就会误判成「没握手」整页重载，
        // 表现就是驾驶页每 4 秒闪一下。只有 socket 还关着、即将由我们 open 时才需要验证。
        var sock = link.socket;
        if (sock && sock.readyState === 1) {
          link.pageBound = true;
        } else {
          link.pageBound = false;
          if (sock) sock._open();
          // 兜底：重连后页面一直没握手（app.js 的退避重连在多次断链后可能不再新建 socket），
          // 4 s 后还在「未连接」就整页重载一次——已在静止状态，重载只会更快回到驾驶页。
          setTimeout(function () {
            if (!link.pageBound && link.socket && link.state === 'ready'
                && location.protocol.indexOf('http') === 0) {
              logEvent('页面没有完成握手，重载页面');
              location.reload();
            }
          }, 4000);
        }
      })
      .catch(function (error) {
        var reason = (error && error.message) ? error.message : String(error);
        logEvent('error', reason);
        setLink('down', reason);
        // 紧接着的断开是我们自己发的，它的回调只会说「已断开」；别让它覆盖原因，
        // 所以这里直接把真正的原因交给页面。
        link.localDown = true;
        if (window.duckBle.onLink) window.duckBle.onLink('down', reason);
        if (window.DuckNative) window.DuckNative.disconnect();
      });
  }

  // ── WebSocket 替身 ─────────────────────────────────────────────────────
  function FakeSocket(url) {
    this.url = url || '';
    this.readyState = FakeSocket.CONNECTING;
    this._listeners = Object.create(null);
    this._opened = false;
    if (link.socket && link.socket !== this) {
      try { link.socket.close(); } catch (_) {}
    }
    link.socket = this;
    if (link.state === 'ready') {
      // 页面在 `new WebSocket()` 之后才挂 `open` 监听；同步发 open 会丢，
      // 页面就永远收不到握手，只能停在「重试连接」。推到下一个 tick。
      var self = this;
      setTimeout(function () { self._open(); }, 0);
    } else if (link.cached) {
      // 刚从另一个页面切过来：GATT 通常还活着。先用快照把页面点亮（open + 上一帧
      // 状态），同时向原生核对一次——原生 ready 后会照常认证/订阅，真的断了则由
      // `onLink down` 撤掉页面、清掉快照。
      var cachedSocket = this;
      setTimeout(function () {
        cachedSocket._open();
        emitState();
      }, 0);
      if (window.DuckNative) window.DuckNative.connect(config.address);
    } else {
      startSession();
    }
  }

  FakeSocket.CONNECTING = 0;
  FakeSocket.OPEN = 1;
  FakeSocket.CLOSING = 2;
  FakeSocket.CLOSED = 3;

  FakeSocket.prototype.addEventListener = function (type, handler) {
    (this._listeners[type] = this._listeners[type] || []).push(handler);
  };
  FakeSocket.prototype.removeEventListener = function (type, handler) {
    var list = this._listeners[type] || [];
    var index = list.indexOf(handler);
    if (index >= 0) list.splice(index, 1);
  };
  FakeSocket.prototype.emit = function (data) {
    var event = { data: JSON.stringify(data) };
    (this._listeners.message || []).forEach(function (handler) { handler(event); });
    return event;
  };
  FakeSocket.prototype.emitLink = function () {
    if (this.readyState !== 1) return;
    // 页面的 link 状态来自 hello/state；这里只把原生链路细节目放进 window.duckBle。
    if (window.duckBle) window.duckBle.detail = link.detail;
  };
  FakeSocket.prototype._open = function () {
    // 断线重连后要能再发一次 open：页面收到 close 会切到「未连接」浮层，
    // 只在第一次 open 的话，重连成功也不会自动回到驾驶页。
    if (this.readyState === 1) return;
    this._opened = true;
    this.readyState = 1;
    (this._listeners.open || []).forEach(function (handler) { handler({}); });
  };
  FakeSocket.prototype._close = function () {
    if (this.readyState === 3) return;
    this.readyState = 3;
    (this._listeners.close || []).forEach(function (handler) { handler({}); });
  };
  FakeSocket.prototype.send = function (text) {
    if (this.readyState !== 1) return;
    var message;
    try { message = JSON.parse(text); } catch (_) { return; }
    if (!message || typeof message !== 'object') return;
    switch (message.t) {
      case 'hello':
        link.pageBound = true;
        this.emit({ t: 'hello', ok: true, role: 'driver', driver: 'phone', paddCanStop: !PADDLESS });
        return;
      case 'ping':
        this.emit({ t: 'pong' });
        return;
      case 'drive':
        sendDrive(message.vx, message.vyaw);
        return;
      case 'head':
        sendHead(message);
        return;
      case 'takeover':
        rpc('robot.enable', { on: true }).then(function (result) {
          this.emit({ t: 'session', role: 'driver' });
          if (!result || !result.accepted) {
            this.emit({ t: 'error', reason: (result && result.reason) || '接管被拒绝' });
          }
        }.bind(this)).catch(function () { /* 断开时页面自会显示离线 */ });
        return;
      case 'cmd':
        handleCommand(this, message);
        return;
      default:
        return;
    }
  };
  FakeSocket.prototype.close = function () {
    this.readyState = 2;
    // App 内导航（驾驶页 ↔ 网络页）时把 GATT 留给下一个页面，不要断；只有页面自己
    // 主动关连接（重连、退出）才真的 disconnect。
    if (window.DuckNative && !link.navigating) window.DuckNative.disconnect();
    this._close();
  };

  window.WebSocket = FakeSocket;

  // ── 看门狗：页面停了也要零速 ───────────────────────────────────────────
  setInterval(function () {
    if (!link.socket || link.socket.readyState !== 1) return;
    if (!link.lastDriveAt) return;
    if (Date.now() - link.lastDriveAt < 250) return;
    if (link.lastTwist[0] === 0 && link.lastTwist[1] === 0) return;
    sendDrive(0, 0);
  }, 100);

  // ── 页面补丁（App 专用，不写回原网页版）─────────────────────────────────
  // `assets/duckphone/` 由 `tools/sync-web.sh` 单向生成，改副本会在下次同步时被覆盖，
  // 所以 BLE 专属的差异都在这里补：
  //   1) 注入 `ble-page.css`，修状态抽屉两列被长串挤扁；
  //   2) 离线浮层的「同一 Wi-Fi」换成蓝牙说法，并补上上次的设备与断开原因；
  //   3) 状态抽屉「连接」里的 `appassets.androidplatform.net`（App 内的资源域名，
  //      对用户没有意义）换成蓝牙设备名与地址。
  function escapeHtml(text) {
    return String(text == null ? '' : text).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function deviceLabel() {
    if (config.name && config.address) return config.name + ' · ' + config.address;
    return config.name || config.address || '';
  }

  // 页面把 `S.policy` 的英文 id 原样存进 `duck.last`（网页版也这样），
  // 离线摘要里得先翻译，否则会出现「上次连接 · held · 85%」。
  var POLICY_NAMES = {
    walk: '行走', stand: '待命', held: '待命', homing: '回 HOME',
    limp: '卸力', sit: '坐着', sitstand: '起坐', ground_pick: '捡拾',
  };

  function policyLabel(id) {
    return POLICY_NAMES[id] || id || '';
  }

  function reasonLabel() {
    if (link.downReason && link.downReason !== '已断开') return link.downReason;
    return '蓝牙连接中断（机器人断电、超出范围或蓝牙服务停了）';
  }

  function offlineDetailHtml() {
    var rows = [];
    var device = deviceLabel();
    if (device) rows.push('设备 <b>' + escapeHtml(device) + '</b>');
    var last = null;
    try { last = JSON.parse(lsGet('duck.last') || 'null'); } catch (_) { last = null; }
    if (last && last.time) {
      rows.push('上次连接 <b>' + escapeHtml(last.time) + '</b> · ' +
        escapeHtml(policyLabel(last.policy)) + ' · ' + escapeHtml(last.pct || ''));
    } else if (!device) {
      rows.push('还没有成功连接过');
    }
    rows.push('断开原因：' + escapeHtml(reasonLabel()));
    return rows.join('<br>');
  }

  function patchPage() {
    var css = document.createElement('link');
    css.id = 'duckble-patch-css';
    css.rel = 'stylesheet';
    css.href = '/assets/ble-page.css';
    (document.head || document.documentElement).appendChild(css);

    var offline = document.getElementById('offline');
    if (offline) {
      var lead = offline.querySelector('p');
      if (lead) lead.textContent = '蓝牙连接已断开。靠近机器人后点「重试连接」；要换设备就返回连接页。';
      // 页面每次 `showOffline()` 都会重写这段摘要，所以写完再盯着，改回来。
      var refreshOffline = function () {
        var node = document.getElementById('offlineLast');
        if (!node) return;
        var html = offlineDetailHtml();
        if (node.innerHTML !== html) node.innerHTML = html;
      };
      refreshOffline();
      new MutationObserver(refreshOffline).observe(offline, {
        childList: true, subtree: true, characterData: true,
      });
    }

    // 「连接」卡：页面写的是 `location.host`（App 里是资源域名）与「已连接」，
    // 都跟 BLE 无关。检测到页面覆盖回来就重写成两条真实链路。
    var connEl = document.getElementById('stConn');
    var ipEl = document.getElementById('stIp');
    var pageWording = { '已连接': 1, '未连接': 1, '只读模式': 1, '只读（他人在驾驶）': 1 };
    var keepBridgeText = function () {
      var conn = connEl ? (connEl.textContent || '') : '';
      var ip = ipEl ? (ipEl.textContent || '') : '';
      var connIsPage = connEl && pageWording[conn];
      var ipIsPage = ipEl && ip && ip !== '—' && ip.indexOf(' · api ') < 0;
      if (connIsPage || ipIsPage) renderLinkStrip();
    };
    if (connEl || ipEl) {
      keepBridgeText();
      var observer = new MutationObserver(keepBridgeText);
      if (connEl) observer.observe(connEl, { childList: true, characterData: true, subtree: true });
      if (ipEl) observer.observe(ipEl, { childList: true, characterData: true, subtree: true });
    }

    // 维护页的「排障」一行写的是网页版的 8001 与同一 Wi-Fi，App 里没有意义。
    var notes = document.querySelectorAll('.d');
    for (var i = 0; i < notes.length; i += 1) {
      if ((notes[i].textContent || '').indexOf('8001') >= 0) {
        notes[i].textContent = '连不上机器人：确认已上电、App 有蓝牙权限，靠近后点「重试连接」。';
      }
    }

    // 页面用 `window.open('/help.html')` 打开排障页，那一页整篇讲 Wi-Fi、8001 与
    // 配对码。App 里没有多窗口，直接在当前 WebView 打开蓝牙版排障页（返回键可用）。
    if (!window.__duckHelpPatched) {
      window.__duckHelpPatched = true;
      var realOpen = window.open;
      window.open = function (url) {
        if (typeof url === 'string' && url.indexOf('help.html') >= 0) {
          location.href = '/assets/ble-help.html';
          return null;
        }
        return realOpen.apply(window, arguments);
      };
      // 兜底：页面里如果有 `<a href="/help.html">` 之类的链接，也改走蓝牙版。
      document.addEventListener('click', function (event) {
        var node = event.target;
        while (node && node !== document) {
          if (node.tagName === 'A' && node.getAttribute) {
            var href = node.getAttribute('href') || '';
            if (href.indexOf('help.html') >= 0) {
              event.preventDefault();
              location.href = '/assets/ble-help.html';
              return;
            }
          }
          node = node.parentNode;
        }
      }, true);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', patchPage);
  } else {
    patchPage();
  }

  // ── 给 M2 的扫描/配网页用的接口 ────────────────────────────────────────
  window.duckBle = {
    detail: '',
    onScan: null,
    onLink: null,
    /** 系统页用的直接调用；驾驶页走 WebSocket 替身。 */
    call: function (method, params, timeoutMs) { return rpc(method, params, timeoutMs); },
    scan: function (seconds) {
      if (!window.DuckNative) return false;
      link.scanSeen = Object.create(null);
      link.scanning = true;
      window.DuckNative.scan();
      return true;
    },
    connect: function (address, pin, name) {
      if (address) { config.address = address; lsSet('duckble.address', address); }
      if (name) { config.name = String(name); lsSet('duckble.name', config.name); }
      if (pin !== undefined) { config.pin = pin; lsSet('duckble.pin', pin); }
      // 重试时把上一条会话彻底关掉再开，否则 `startSession` 会被旧的 socket 挡住。
      if (link.socket) {
        try { link.socket.close(); } catch (_) {}
        link.socket = null;
      }
      startSession();
    },
    disconnect: function () {
      if (link.socket) link.socket.close();
      else if (window.DuckNative) window.DuckNative.disconnect();
    },
    config: function () {
      return { address: config.address, name: config.name, pinSet: !!config.pin };
    },
    setPaddControl: function (enabled) { PADDLESS = !enabled; },
    state: function () {
      return {
        link: link.state, detail: link.detail, apiVersion: link.apiVersion, mtu: link.mtu,
        frame: link.frame, health: link.health, padd: link.padd, wifi: link.wifi,
        // `shownLink` 会先返回上次快照里的「已连接」，用于首帧渲染；判断能否发 RPC
        // 仍然只看 `link`。
        shownLink: shownState(), cached: link.cached,
      };
    },
  };

  // ── 原生 → 页面 ────────────────────────────────────────────────────────
  window.DuckNativeBridge = {
    onResult: function (id, ok, payload) {
      var entry = pendingCalls[id];
      if (!entry) { logEvent('回答没有对应的请求', id); return; }
      delete pendingCalls[id];
      if (ok) {
        entry.resolve(payload ? JSON.parse(payload) : null);
      } else {
        var error = payload ? JSON.parse(payload) : {};
        entry.reject(new Error((error && error.message) || '调用失败'));
      }
    },
    onNotify: function (line) {
      var message;
      try { message = JSON.parse(line); } catch (_) { return; }
      if (!message || !message.method) return;
      if (message.method === 'robot.state') onRobotFrame(message.params);
    },
    onScan: function (payload) {
      var robot = JSON.parse(payload);
      link.scanSeen = link.scanSeen || {};
      link.scanSeen[robot.address] = robot;
      // 记住目标设备的广播名：离线浮层与状态卡要用「duck-dillon · CC:C8:…」而不是地址。
      if (robot.address && robot.address === config.address && robot.name) {
        config.name = String(robot.name);
        lsSet('duckble.name', config.name);
      }
      if (window.duckBle.onScan) window.duckBle.onScan(robot);
      if (window.duckBle._onScan) window.duckBle._onScan(robot);
    },
    onLink: function (state, detail) {
      link.detail = detail || '';
      if (state === 'down') link.state = 'down';
      else if (state === 'connecting' || state === 'connected') link.state = 'connecting';
      // 自己主动断开的回声只说「已断开」，真正的原因已经由 setLink(down, reason) 记下了。
      if (state === 'down' && !link.localDown) link.downReason = link.detail || '连接已断开';
      renderLinkStrip();
      if (state === 'ready') {
        // 原生的 ready 只是 GATT 连上；认证/版本/订阅走完才算真的可用，
        // 由 `announceReady()` 再通知页面。
        var info = {};
        try {
          info = window.DuckNative && window.DuckNative.info
            ? JSON.parse(window.DuckNative.info()) : {};
        } catch (_) { info = {}; }
        link.apiVersion = Number(info.apiVersion) || 0;
        link.mtu = Number(info.mtu) || 0;
        onReady();
        return;
      }
      if (state === 'down' && link.localDown) {
        link.localDown = false;   // 自己断开的回声，页面已经拿到真正的原因
      } else if (window.duckBle.onLink) {
        window.duckBle.onLink(state, detail || '');
      }
      if (state === 'down') {
        pendingCalls = Object.create(null);
        link.frame = null;
        // 真的断了：快照作废，否则下次进页面会先显示「已连接」再打脸。
        link.cached = false;
        ssRemove('duckble.live');
        if (link.socket) link.socket._close();
      }
    },
    onPermission: function (granted) {
      if (!granted && window.duckBle.onLink) window.duckBle.onLink('down', '缺少蓝牙权限');
    },
  };

  // 1 Hz 健康与手柄状态；只有驾驶页（有替身 socket）才需要，网络/维护页省掉这些流量。
  setInterval(function () {
    if (link.state === 'ready' && link.socket) refreshHealth();
  }, 1000);

  // 机器人自己的 Wi-Fi 变化慢，5 秒一次就够，也省一条 BLE 请求。
  setInterval(function () {
    if (link.state === 'ready') refreshWifi();
  }, 5000);

  // 页面要走了（返回连接页、刷新、关闭 WebView）：只关页面这一侧的 socket。
  // Activity 与 GATT 都还在，下一个页面会直接接管；真的退出时 Activity.onPause
  // 会归零并断开。`navigating` 让页面自己的 `ws.close()` 也别误伤底层连接。
  function markNavigating() {
    link.navigating = true;
    if (link.socket) {
      try { link.socket._close(); } catch (_) {}
      link.socket = null;
    }
  }
  window.addEventListener('pagehide', markNavigating);
  window.addEventListener('beforeunload', markNavigating);
  window.addEventListener('pageshow', function () { link.navigating = false; });
})();
