// Display-only guide for the public, guarded demo. No robot requests or input.
(() => {
  if (!window.MicroduckDemo) return;
  const entries = [
    ['connect', '#ssh-form', '先找到 IP，再连接', '刷入 R2 镜像后未连接已保存 Wi-Fi 时，先连 Microduck-kissqy 热点完成配网，再到家庭路由器的在线设备列表查机器人 IP。这里填 radxa@实际IP 和自己设置的系统登录密码；127.0.0.1 是电脑中控，10.42.0.1 是热点配网入口。演示页不能连接实机。'],
    ['overview', '.metrics', '先看反馈是否就绪', '这里查看控制频率、15 个关节反馈、电压与温度。演示数值是模拟数据；实机应等待启动和反馈完成。'],
    ['reference', '.twin-panel', '用 3D 参考核对方向', '「实测」看反馈；「零位 0°」「HOME 站姿」「0 → +10°」只改变屏幕模型。左右按鸭子自身判断。'],
    ['calibration', '#service-editor', '在工作台保存本机关节标定', '切到标定模式，逐个选择关节，核对已知角度、方向、实际限位，勾选后保存。「全部顺序回到 2048」仅用于未装配舵机。'],
    ['imu', '.service-imu', '核对 IMU 安装方向', 'X 向前、Y 向左、Z 向上。按实物安装填写 w x y z，核对实际倾斜方向后保存安装确认。显示视角归零不会校准 IMU。'],
    ['control', '#control-panel', 'HOME 之后再启用策略', '实体手柄首次 Start 回 HOME，之后 Start 开关策略。左杆行走，右杆转向；Select 短按松开卸力。实体手柄接入时网页输入暂停。'],
    ['ai', '#ai-agent-panel', '体验 V260 的 AI 对话与动作', '演示中可查看音色、13 个官方表情及身体动作，点击示例体验对话与工具调用日志。实机版通过豆包语音服务接收 HAT 麦克风输入；在线演示无需密钥。'],
    ['camera', '#camera-panel', '按需打开摄像头', '实机点击「连接摄像头」后开始采集，可查看帧率与丢包。最后一个视频使用者退出后休眠。演示页不连接摄像头。'],
    ['firmware', '#service-firmware', '维护、升级与诊断', '在这里查看实际运行版本、选择配套固件、等待校验并升级。系统维护区可导出启动诊断。完整教程还包含关机与常见问题。']
  ];
  let index = 0, active = null, returnFocus = null, initialized = false;
  const card = document.createElement('section');
  card.id = 'console-tour'; card.hidden = true;
  card.setAttribute('role', 'region'); card.setAttribute('aria-label', '中控使用导览');
  card.innerHTML = `<div class="tour-heading"><span id="tour-count"></span><button type="button" id="tour-close" aria-label="关闭使用导览">×</button></div><h2 id="tour-title" tabindex="-1"></h2><p id="tour-copy"></p><div class="tour-actions"><a href="./console-guide.html#network" id="tour-ip-help">不知道 IP？先看配网与查找 →</a><button type="button" id="tour-back">上一步</button><button type="button" id="tour-next">下一步 →</button></div>`;
  function stop() {
    active?.classList.remove('console-tour-target'); active = null; card.hidden = true;
    document.body.classList.remove('console-tour-open');
    const url = new URL(location.href); url.searchParams.delete('tutorial'); history.replaceState(null, '', url);
    if (returnFocus?.isConnected) returnFocus.focus();
  }
  function show() {
    active?.classList.remove('console-tour-target');
    const [key, selector, title, copy] = entries[index];
    active = document.querySelector(selector);
    document.getElementById('tour-count').textContent = `界面导览 ${index + 1} / ${entries.length}`;
    document.getElementById('tour-title').textContent = title;
    document.getElementById('tour-copy').textContent = copy + (active ? '' : ' 当前页面尚未载入该区域，可先查看完整图文教程。');
    document.getElementById('tour-back').disabled = index === 0;
    document.getElementById('tour-next').textContent = index === entries.length - 1 ? '完成导览 ✓' : '下一步 →';
    card.hidden = false; document.body.classList.add('console-tour-open');
    active?.classList.add('console-tour-target');
    active?.scrollIntoView({behavior: 'instant', block: 'start'});
    document.getElementById('tour-title').focus({preventScroll: true});
    const url = new URL(location.href); url.searchParams.set('tutorial', key); history.replaceState(null, '', url);
  }
  function start(key) {
    returnFocus = document.activeElement;
    index = Math.max(0, entries.findIndex(row => row[0] === key)); show();
  }
  function init() {
    if (initialized) return; initialized = true;
    document.body.append(card);
    document.getElementById('tour-close').onclick = stop;
    document.getElementById('tour-back').onclick = () => { if (index > 0) { index--; show(); } };
    document.getElementById('tour-next').onclick = () => { if (index === entries.length - 1) stop(); else { index++; show(); } };
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && !card.hidden) stop(); });
    document.getElementById('start-console-tour')?.addEventListener('click', () => start('connect'));
    const key = new URL(location.href).searchParams.get('tutorial'); if (key) start(key);
  }
  // Service panels are constructed asynchronously by app.js.
  if (document.getElementById('service-firmware')) init();
  else {
    const observer = new MutationObserver(() => {
      if (document.getElementById('service-firmware')) { observer.disconnect(); init(); }
    });
    observer.observe(document.body, {childList: true, subtree: true});
    setTimeout(() => { observer.disconnect(); init(); }, 12000);
  }
})();
