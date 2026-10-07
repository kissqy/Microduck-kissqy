import {modelJointLimits,referenceAngle} from './joint-reference.js';
import {supportsFeature} from './service-builds.js';
import {ServiceManagement} from './service-management.js';
import {showFeedback} from './feedback.js';
import {DeviceInspection} from './inspection.js';
import {FirmwarePanel} from './firmware.js';

const finite=v=>typeof v==='number'&&Number.isFinite(v);
const fmt=(v,n=1)=>finite(v)?v.toFixed(n):'—';
const phases={power_pending:'Zero 电源操作已提交',ready:'服务就绪',control:'运动循环',sensor_or_fall_stop:'传感器或跌倒停止',moving:'关节运动中',read_error:'本轮读取异常',stop_unconfirmed:'停扭矩未确认',configuring_uart:'总线初始化中',waiting_for_bus:'等待总线',configuration_error:'配置异常'};
const actions={'set-pad-settings':'手柄幅度设置',move:'关节移动',center:'整组顺序居中',capture:'关节标定',init:'Home 站姿','switch-mode':'服务模式切换','reconnect-service':'重新连接 HAT','upgrade-service':'升级 R17 / 0.15.1','set-action-scale':'高级参数应用','import-model':'导入模型',relax:'停止并松开', 'verify-imu':'IMU 安装方向',reboot:'重启 Zero',shutdown:'关闭 Zero','resume-connection':'恢复连接'};
const feedbackTargets={'set-pad-settings':'control-feedback',move:'service-job',center:'service-job',capture:'service-job',init:'control-feedback',
  'switch-mode':'service-mode-job','forget-sudo-password':'service-mode-job','verify-imu':'service-imu-job',
  relax:'service-power-job',reboot:'service-power-job',shutdown:'service-power-job','resume-connection':'service-power-job',
  'set-action-scale':'management-status','import-model':'management-status',
  
  'reconnect-service':'management-hat-status','upgrade-service':'firmware-status'};

function setModeText(panel,mode,s,torqueOff){
  const job=s.service_control?.job;
  const known=s.channels?.bus?.status==='live'||panel.management?.connection?.process_matches===true;
  const modeName=known?(mode==='motion'?'运动模式':mode==='commissioning'?'标定模式':'待确认'):'待确认';
  const modeClass='service-mode-indicator '+(modeName==='待确认'?'unknown':mode==='motion'?'motion':'calibration');
  panel.$('service-current-mode').textContent=`当前模式：${modeName}`;
  panel.$('service-current-mode').className=modeClass;
  panel.$('service-mode-label').textContent=modeName;
  panel.$('service-mode-indicator').className=modeClass;
  panel.$('service-mode-check').textContent=job?.action==='switch-mode'&&job.status==='running'
    ?'正在切换并等待机器人服务校验，请勿断开 Zero 电源。'
    :job?.action==='switch-mode'&&job.status==='error'?job.error
    :job?.action==='switch-mode'&&job.status==='completed'&&job.command.target!==mode?'切换脚本已完成，等待新模式的实时反馈。'
    :!s.service_sample_fresh?'等待服务实时反馈。'
    :!torqueOff?'确认机身有支撑；点击切换后会先释放全部扭矩。'
    :mode==='motion'?'运动模式可回 Home 或运行策略；修改零位或限位时切到标定模式。'
    :mode==='commissioning'?'完成 15 关节与 IMU 标定后可切到运动模式。':'等待服务模式确认。';
}

export class ServicePanel {
  constructor(cfg,choose){
    this.cfg=cfg;this.id=20;this.seq=0;this.client=crypto.randomUUID().replaceAll('-','');
    this.lastJob='';this.mountDirty=false;this.calibrationDirty=false;
    window.addEventListener('r17-pad-settings',e=>this.post({action:'set-pad-settings',...e.detail,supported:true}));
    this.s=null;this.options={};this.dirty=false;this.ownsMotion=false;this.posting=false;this.lastSample=0;
    this.root=document.createElement('section');this.root.id='service-panel';this.root.className='service-console';this.root.hidden=!cfg.service_enabled;
    document.querySelector('main footer').before(this.root);
    this.root.innerHTML=`
      <div class="service-status">
        <h2 id="service-heading">正式机器人服务</h2><strong id="service-mode-indicator" class="service-mode-indicator unknown">当前模式：<span id="service-mode-label">待确认</span></strong><span id="service-phase" class="badge neutral">等待服务</span>
        <span>扭矩 <b id="service-torque">未知</b></span><span id="service-message" role="status">等待正式服务</span>
      </div>
      <div class="service-gait-preflight"><strong>行走预检</strong><span id="service-gait-status" role="status">等待策略和健康状态反馈</span><button class="button" id="service-gait-export" type="button">导出实时记录</button></div>
      <section class="panel service-mode-switch" id="service-mode-switch">
        <div class="panel-head"><div><h2>机器人服务模式</h2></div><strong id="service-current-mode" class="service-mode-indicator unknown">当前模式：待确认</strong></div>
        <div class="service-mode-body">
          <p id="service-mode-check" role="status">等待机器人实时状态</p>
          <div class="service-action-row"><button class="button" id="service-mode-calibrate" disabled>切到标定模式</button><button class="button accent" id="service-mode-motion" disabled>切到运动模式</button></div>
        </div><div id="service-mode-job" class="panel-note service-job" role="status" aria-live="polite"></div>
      </section>
      <div class="service-hero" id="service-hero">
        <div class="service-view-side" id="service-view-side"></div>
      </div>
      <div class="service-joint-row" id="service-joint-row">
        <div class="service-observation" id="service-observation"></div>
        <div class="service-workbench-stack" id="service-workbench-stack">
        <section class="panel service-editor" id="service-editor">
          <div class="panel-head"><div><h2>关节工作台</h2></div><span id="service-count" class="muted tiny">0 / 15 已标定</span></div>
          <div class="service-editor-body">
            <div class="service-selection">
              <label class="field">选择关节<select id="service-joint-select"></select></label>
              <div class="service-value"><span>当前位置 / counts</span><strong id="service-raw">—</strong></div>
              <div class="service-value"><span>已标定角度 / °</span><strong id="service-angle">—</strong></div>
            </div>
            <div id="service-feedback-values" class="service-feedback-values"></div>
            <div class="service-movement">
              <div class="service-target-row">
                <label class="field">目标 / counts<input id="service-position" type="number" min="0" max="4095" step="1" placeholder="等待反馈"></label>
                <input id="service-slider" aria-label="所选关节目标位置" type="range" min="0" max="4095" step="1" value="2048">
                <label class="field">移动时长<select id="service-duration"><option value="2000">2 秒</option><option value="4000">4 秒</option><option value="1000">1 秒</option></select></label>
              </div>
              <div class="service-action-row"><button class="button" id="service-minus" title="当前位置减 57 counts，约 5°">−57 counts</button><button class="button accent" id="service-move">移动到目标</button><button class="button" id="service-plus" title="当前位置加 57 counts，约 5°">+57 counts</button></div>
            </div>
            <div class="service-calibration">
              <h3>实际关节标定</h3>
              <p id="service-calibration-mode" class="tiny muted" role="status"></p>
              <div class="service-fields">
                <label class="field">已知角度 / °<input id="service-known-angle" type="number" step="0.1" value="0"></label>
                <label class="field">编码器正方向<select id="service-direction"><option value="1">同向 +1</option><option value="-1">反向 −1</option></select></label>
                <label class="field">实际最小角 / °<input id="service-min" type="number" step="0.1" placeholder="实物限位"><small class="service-limit-reference" id="service-model-min" title="官方模型参考，不是实物机械限位">模型参考 —</small></label>
                <label class="field">实际最大角 / °<input id="service-max" type="number" step="0.1" placeholder="实物限位"><small class="service-limit-reference" id="service-model-max" title="官方模型参考，不是实物机械限位">模型参考 —</small></label>
              </div>
              <div class="service-confirm-row"><label class="service-check"><input id="service-known" type="checkbox">已核对实际角度、方向与机械限位</label><button class="button accent" id="service-capture">保存当前关节</button></div>
              <p id="service-calibration-detail" class="tiny muted"></p>
            </div>
            <div class="service-center">
              <div class="service-confirm-row"><h3>未装配居中</h3><label class="service-check"><input id="service-unassembled" type="checkbox">15 颗舵机未装到骨架，空间无遮挡</label><button class="button" id="service-center">全部顺序回到 2048</button></div>
              <p id="service-center-progress" class="tiny muted" role="status"></p>
              <p class="tiny muted">2048 是编码器中心，不是装配零位。</p>
            </div>
          </div>
          <div class="panel-note service-job" id="service-job" role="status" aria-live="polite"></div>
        </section>
        </div>
      </div>
      <section class="panel service-inspection" id="service-inspection">
        <div class="panel-head"><div><h2>逐设备通信</h2><span id="inspection-source" class="badge neutral">待检测</span><span id="inspection-status" class="tiny muted" role="status">未检测</span></div><div class="service-action-row"><button class="button accent" id="inspection-start">开始检测</button><button class="button" id="inspection-stop" disabled>停止检测</button></div></div>
        <div id="inspection-devices" class="inspection-devices"></div>
        <p class="tiny muted">各设备互斥统计：到截止仍未收到有效回包记“超时未回”，不再计缺包；提前因读取错误结束且缺有效回包记“非超时缺包”。完整回包超时只计整轮。超时不能证明永久丢包；旧版未分类累计值会明确标注。恢复或刷新网页不清零，固件重启开始新一轮。</p>
        <div id="inspection-feedback" class="panel-note service-job" role="status" aria-live="polite"></div>
      </section>
      <div class="service-setup-row" id="service-setup-row">
        <section class="panel service-imu">
          <div class="panel-head"><div><h2>IMU 安装核对</h2><span id="service-imu-state" class="badge neutral">尚未确认</span></div></div>
          <div class="service-setup-body">
            <label class="field">安装四元数 / w x y z<input id="service-mount" placeholder="等待服务配置" spellcheck="false" title="按实际安装方向填写；直立时重力约为 [0, 0, −1]"></label>
            <label class="service-check"><input id="service-mount-confirmed" type="checkbox">已固定并核对坐标轴与倾斜方向</label>
            <button class="button" id="service-verify-imu">保存安装确认</button>
          </div><div id="service-imu-job" class="panel-note service-job" role="status" aria-live="polite"></div>
        </section>
        <section class="panel service-power">
          <div class="panel-head"><div><h2>Zero 电源</h2></div></div>
          <div class="service-setup-body"><div id="service-power-actions" class="service-power-actions"><div class="service-action-row"><button class="button" id="service-reboot">重启 Zero</button><button class="button" id="service-shutdown">关闭 Zero</button><button class="button" id="service-resume">恢复连接</button></div></div><p id="service-power-state" role="status" class="tiny muted"></p></div>
          <div id="service-power-job" class="panel-note service-job" role="status" aria-live="polite"></div>
        </section>
      </div>`;
    this.$=id=>document.getElementById(id);
    this.inspection=new DeviceInspection(cfg,this.$('service-inspection'));
    if(cfg.service_enabled){
      const stop=document.createElement('button');stop.className='button service-relax';stop.textContent='■ 停止并松开';stop.id='service-quick-stop';
      stop.onclick=()=>this.post({action:'relax'});this.$('service-power-actions').prepend(stop);
      document.body.classList.add('service-mode');
      const hero=document.querySelector('.hero-grid');hero.before(this.root);
      const twin=document.querySelector('.twin-panel');
      const stage=this.$('service-hero');stage.classList.add('r17-three-columns');
      stage.replaceChildren(twin,this.$('control-panel'),this.$('camera-panel'));hero.remove();
      this.$('service-mount').addEventListener('input',()=>{this.mountDirty=true;});
      this.root.querySelector('.service-calibration').addEventListener('input',()=>{this.calibrationDirty=true;});
      this.management=new ServiceManagement(this);
      this.firmware=new FirmwarePanel(this);
      this.$('reset-view').textContent='↺ 整机视角';
      const chart=document.querySelector('.motor-detail');chart.classList.add('panel','service-joint-chart');
      chart.querySelector('.eyebrow').textContent='关节曲线';
      chart.querySelector('#joint-extra').hidden=true;
      document.querySelector('#control-panel .mode-management-anchor').append(this.$('service-mode-switch'));
      this.$('service-observation').append(chart);
      this.$('service-editor').querySelector('.service-target-row').append(this.$('service-move').closest('.service-action-row'));
      const bottom=document.createElement('div');bottom.className='service-workbench-bottom';
      bottom.setAttribute('aria-label','标定保存、未装配居中与 IMU 安装');
      const saved=document.createElement('div');saved.className='service-saved-controls';
      saved.append(this.root.querySelector('.service-calibration .service-confirm-row'),this.$('service-calibration-detail'));
      bottom.append(saved,this.root.querySelector('.service-center'),this.$('service-setup-row').querySelector('.service-imu'));
      this.$('service-editor').querySelector('.service-editor-body').append(bottom);
      this.$('service-setup-row').remove();
      this.$('service-hero').after(this.$('motors'));
      document.querySelector('#motors h2').textContent='全部关节反馈';
      // Merge raw readback into the workbench. Current position is already here.
      this.$('service-feedback-values').append(this.$('joint-registers'));
      document.querySelector('#motors .register-details').remove();
      const navMotors=document.querySelector('nav a[href="#motors"]');if(navMotors)navMotors.title='全部关节反馈';

    }

    for(let i=0;i<cfg.ids.length;i++){
      const option=document.createElement('option');option.value=cfg.ids[i];option.textContent=`${cfg.ids[i]} · ${cfg.labels[i]}`;
      this.$('service-joint-select').append(option);
    }
    this.$('service-joint-select').onchange=e=>choose(Number(e.target.value));
    this.$('service-position').addEventListener('input',()=>{this.dirty=true;this.$('service-slider').value=this.$('service-position').value;});
    this.$('service-slider').addEventListener('input',()=>{this.dirty=true;this.$('service-position').value=this.$('service-slider').value;});
    for(const action of ['reboot','shutdown'])this.$('service-'+action).onclick=()=>this.post({action});;
    this.$('service-resume').onclick=()=>this.post({action:'resume-connection'});
    this.$('service-move').onclick=()=>this.move();
    this.$('service-minus').onclick=()=>this.move(-57);this.$('service-plus').onclick=()=>this.move(57);
    this.$('service-center').onclick=()=>this.post({action:'center',unassembled:this.$('service-unassembled').checked,duration_ms:Number(this.$('service-duration').value)});
    this.$('service-capture').onclick=()=>{
      if(!this.$('service-known').checked)return this.feedback('capture','请先确认当前实际关节角度、方向和限位','warning');
      const values=['service-known-angle','service-min','service-max'].map(id=>this.$(id).value.trim());
      if(values.some(x=>!x||!finite(Number(x))))return this.feedback('capture','请填写已知角度和两个实际限位','warning');
      this.post({action:'capture',id:this.id,angle_deg:Number(values[0]),direction:Number(this.$('service-direction').value),min_deg:Number(values[1]),max_deg:Number(values[2])});
    };
    this.$('service-mode-calibrate').onclick=()=>this.switchMode('commissioning');
    this.$('service-mode-motion').onclick=()=>this.switchMode('motion');
    this.$('service-sudo-forget').onclick=()=>{this.$('service-sudo-password').value='';this.post({action:'forget-sudo-password'});};
    this.$('service-gait-export').onclick=()=>document.getElementById('export').click();
    this.$('service-verify-imu').onclick=()=>{
      if(!this.$('service-mount-confirmed').checked)return this.feedback('verify-imu','请先固定 IMU 并核对安装方向','warning');
      const q=this.$('service-mount').value.trim().split(/[ ,，]+/).map(Number);
      this.post({action:'verify-imu',confirmed:true,mount_wxyz:q});
    };
    if(cfg.service_enabled){
      const nav=document.querySelector('nav a[href="#control-panel"]');
      const calibrationNav=nav.cloneNode(true);calibrationNav.href='#service-editor';calibrationNav.childNodes[1].textContent='关节标定';nav.after(calibrationNav);
      document.querySelector('#motors .badge').textContent='舵机';
      const heads=document.querySelectorAll('#motors thead th');heads[5].textContent='速度 raw';heads[6].textContent='电流 raw';heads[9].remove();heads[10].remove();heads[11].textContent='扭矩';
      heads[2].insertAdjacentHTML('beforebegin','<th>当前位置 / counts</th>');
      heads[2].insertAdjacentHTML('afterend','<th title="官方默认站立姿态；仅供对照，非当前标定值">官方站立 °</th><th class="model-limit" title="官方模型参考；并非已验证的实物机械限位">模型最小 °</th><th class="model-limit" title="官方模型参考；并非已验证的实物机械限位">模型最大 °</th><th class="saved-limit" title="从关节标定读取，未保存时显示横线">已保存最小 °</th><th class="saved-limit" title="从关节标定读取，未保存时显示横线">已保存最大 °</th>');
      heads[3].classList.add('target-angle');
      this.$('plot-field').insertAdjacentHTML('afterbegin','<option value="raw">编码器位置 / 目标 counts</option>');this.$('plot-field').value='angle';
      this.$('plot-field').querySelector('[value="current"]').textContent='电流 raw';
      this.$('plot-field').querySelector('[value="velocity"]').textContent='速度 raw';
      document.querySelector('#motors .panel-note.important').remove();
    }
    window.addEventListener('pagehide',()=>this.suspend());window.addEventListener('blur',()=>this.suspend());
    document.addEventListener('visibilitychange',()=>{if(document.hidden)this.suspend();});
  }
  feedback(action,message,status='info',output=''){
    showFeedback(this.$(feedbackTargets[action]),message,status);
    if(action==='reconnect-service')showFeedback(this.$('management-hat-status'),message+(output?'\n'+output:''),status);
  }
  select(id){
    if(this.id!==id){this.id=id;this.dirty=false;this.$('service-known').checked=false;this.calKey=null;this.calibrationDirty=false;}
    this.paint();
  }
  move(delta){
    const row=this.s?.servos.find(r=>r.id===this.id),value=delta===undefined?this.$('service-position').value.trim():null;
    const position=delta===undefined?(value===''?NaN:Number(value)):row?.position_raw+delta;
    if(!Number.isInteger(position)||position<0||position>4095)return this.feedback('move','目标超出 0～4095，不能跨编码器端点移动','warning');
    this.post({action:'move',id:this.id,position,duration_ms:Number(this.$('service-duration').value)});
  }
  async post(command,keepalive=false){
    if(!this.cfg.service_enabled||(this.options.replay&&command.action!=='relax'))return;
    const special={
      'switch-mode':command.target==='motion'?'service-mode-motion':'service-mode-calibrate',
      'reconnect-service':'management-reconnect','upgrade-service':'firmware-flash',
      'set-pad-settings':'control-mouth','set-action-scale':'management-scale-apply'};
    const configurationAction=['switch-mode','reconnect-service','upgrade-service','set-action-scale'].includes(command.action);
    if(!['relax','reboot','shutdown','resume-connection','forget-sudo-password'].includes(command.action)&&((special[command.action]?this.$(special[command.action]).disabled:this.blocked)||this.posting||document.hidden||!configurationAction&&performance.now()-this.lastSample>2000))return;
    if(command.action==='center'&&!command.unassembled)return this.feedback('center','整组居中只适用于未装配舵机，请先确认','warning');
    if(command.action!=='relax')this.posting=true;
    if(['move','center','init'].includes(command.action))this.ownsMotion=true;
    try{
      const privileged=['switch-mode','reconnect-service','upgrade-service','set-pad-settings','set-action-scale','reboot','shutdown'].includes(command.action);
      const password=privileged?this.$('service-sudo-password').value:'';
      if(password)command.sudo_password=password;
      const body=JSON.stringify({client:this.client,seq:++this.seq,command});
      delete command.sudo_password;
      const response=await fetch('/api/service',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},body,keepalive,signal:keepalive?undefined:AbortSignal.timeout(5000)});
      const data=await response.json();if(!response.ok||!data.accepted)throw Error(data.error||'服务未接收指令');
      if(['relax','reboot','shutdown'].includes(command.action))this.ownsMotion=false;
      this.feedback(command.action,data.message,['forget-sudo-password','resume-connection'].includes(command.action)?'completed':'running');
      if(command.action==='capture')this.$('service-known').checked=false;
    }catch(e){this.feedback(command.action,e.message,'error');}
    finally{this.posting=false;this.paint();}
  }
  suspend(){if(this.ownsMotion){this.ownsMotion=false;this.post({action:'relax'},true);}}
  switchMode(target){
    const password=this.$('service-sudo-password').value;
    if(!confirm(`切到${target==='motion'?'运动':'标定'}模式？请确认机身有支撑；切换会先释放扭矩，完成后不自动 HOME 或启动策略。`))return;
    this.post({action:'switch-mode',target,supported:true,
      ...(password?{sudo_password:password}:{})});
  }
  render(s,options={}){this.s=s;this.options=options;this.lastSample=performance.now();if(options.replay||options.paused||options.offline)this.suspend();if(s.service_control?.job?.status&&s.service_control.job.status!=='running')this.ownsMotion=false;this.paint();this.management?.render(s,options);this.firmware?.render(s,options);}
  paint(){
    this.$('service-gait-status').title='目标角度超出已保存机械限位时，在发送前截回边界；这是关节指令累计次数，非实测越界次数。服务重启清零，持续增加需核对模型与标定。';
    if(!this.cfg.service_enabled||!this.s)return;
    const s=this.s,b=s.bus||{},live=s.channels.bus?.status==='live',fresh=s.service_sample_fresh,job=s.service_control?.job;
    this.blocked=!fresh||!s.service_compatible||b.mode!=='commissioning'||b.phase!=='ready'||b.torque_state!=='off'||!!s.service_control?.busy||!!s.service_control?.stopping||this.options.replay||this.options.paused||this.options.offline;
    const native=b.native||{},gravity=s.imu?.gravity;
    const mode=s.channels?.bus?.status==='live'?b.mode:this.management?.connection?.actual_mode,torqueOff=mode==='motion'?native.torque_state_confirmed===false:b.torque_state==='off';
    const managed=supportsFeature(b,'management')||this.management?.connection?.management_revision==='R17';
    const switchReady=!!((managed||fresh&&supportsFeature(b,'motion')&&torqueOff&&!b.torque_off_pending)
      &&!s.service_control?.busy&&!s.service_control?.stopping&&!this.posting&&!document.hidden
      &&!this.options.replay&&!this.options.paused&&!this.options.offline);
    setModeText(this,mode,s,torqueOff);
    const credential=s.service_control||{},remembered=credential.sudo_password_saved===true;
    this.$('service-sudo-status').textContent=remembered?(credential.sudo_password_scope==='windows-user'?'已记住密码':'本次运行已记住密码'):'登录和维护共用此密码';
    this.$('service-sudo-forget').disabled=!remembered||!!credential.busy||this.posting;
    this.$('service-mode-calibrate').disabled=!switchReady||mode==='commissioning';
    this.$('service-mode-motion').disabled=!switchReady||mode==='motion';
    const readiness=this.management?.connection;
    if(mode==='commissioning'&&readiness?.motion_ready===false&&!s.service_control?.busy&&job?.status!=='error')
      this.$('service-mode-check').textContent='运动预检：'+readiness.motion_readiness_message+'；切换时由本机再次核验。';
    const set=(id,v)=>this.$(id).textContent=v;
    set('service-heading','正式机器人服务');
    set('service-phase',!live?'服务未连接':this.options.replay?'历史记录':phases[b.phase]||b.mode||'等待反馈');
    this.$('service-phase').className='badge '+(fresh?'':live?'warn':'bad');
    set('service-torque',!live?'未知':b.mode==='motion'?(native.torque_state_confirmed===false?'已确认 OFF':native.torque_state_confirmed===true?'ON':'尚未确认'):({off:'已确认 OFF',single_joint_enabled:'单关节 ON',unknown:'尚未确认'})[b.torque_state]||'见服务状态');
    set('service-message',!live?'等待正式服务，详情见逐设备通信':!s.service_compatible?'请升级配套服务':!fresh?'等待新鲜反馈，详情见逐设备通信':`关节 ${s.servos.filter(r=>r.status==='live').length}/15 · IMU ${s.imu?.status==='live'?'在线':'等待就绪'}`);
    const gaitStatus=!fresh?'等待机器人新鲜反馈':b.mode!=='motion'?'先切到运动模式，行走策略在该模式下显示':
      s.channels?.capabilities?.status==='live'&&s.capabilities?.unavailable?`行走策略加载失败：${s.capabilities.unavailable}`:
      s.channels?.health?.status!=='live'?'等待健康状态':!s.health?.healthy?`健康检查未通过：${s.health?.reason||'查看原始记录'}`:
      s.channels?.capabilities?.status!=='live'?'等待策略能力列表':
      !s.capabilities?.walk?'当前服务未加载行走策略；请导出记录':
      !b.homed||native.torque_state_confirmed!==true?'先完成 Home 并确认扭矩 ON':
      b.policy_enabled?`策略正在驱动 · ${s.capabilities.walk} · 摇杆回中进入同一走路模型的零速度保持；Start 关闭策略回 HOME。目标限位截断累计 ${native.command_clamps_total??'—'}（逐帧 / 逐关节计数）`:
      `策略已加载：${s.capabilities.walk} · Start 启用策略后用摇杆行走。目标限位截断累计 ${native.command_clamps_total??'—'}（逐帧 / 逐关节计数）`;
    set('service-gait-status',gaitStatus);
    this.inspection.render(s,this.options);
    const m=b.motion,centerJob=job?.action==='center',center=m?.action==='center',centerDone=center?m.completed_ids?.length:job?.result?.completed_ids?.length;
    set('service-center-progress',center?`归中 ${centerDone??0}/15 · 当前 ID ${m.id}`:centerJob&&job.status==='completed'?`归中完成 ${centerDone??'—'}/15 · 已松开`:centerJob&&job.status==='error'?`归中未完成 · ${job.error}`:'');
    for(const action of ['reboot','shutdown'])this.$('service-'+action).disabled=!!(s.service_control?.job?.status==='running'&&['reboot','shutdown'].includes(s.service_control?.job?.action));
    this.$('service-resume').disabled=!s.connection_paused||!!(s.service_control?.busy||job?.status==='running'||this.options.replay||this.options.paused);
    const power=job&&['reboot','shutdown'].includes(job.action);
    set('service-power-state',power?(job.status==='completed'?(job.result?.reconnected?'Zero 已重新上线。':job.action==='reboot'?'重启请求已提交；等待 Zero 启动后自动重连。':'已提交关机；自动连接已暂停。Zero 再次上电后点击“恢复连接”。'):job.status==='error'?job.error:'正在提交系统电源指令…'):'关机 / 重启直接执行系统指令。');
    set('service-count',`${s.saved_calibrated_count??s.calibrated_count??0} / 15 已保存标定`);
    this.$('service-joint-select').value=this.id;
    const limits=modelJointLimits[this.id];
    set('service-model-min',`模型参考 ${referenceAngle(limits?.[0])}°`);
    set('service-model-max',`模型参考 ${referenceAngle(limits?.[1])}°`);
    const row=s.servos.find(r=>r.id===this.id),cal=row?.calibration;
    if(row){set('service-raw',row.status==='live'?row.position_raw:'—');set('service-angle',row.calibrated&&row.status==='live'?fmt(row.angle_deg,2):row.calibrated?'—':'未标定');
      if(!this.dirty&&row.status==='live'){this.$('service-position').value=row.position_raw;this.$('service-slider').value=row.position_raw;}
      const key=JSON.stringify([row.id,cal?.zero_raw,cal?.direction,cal?.min_rad,cal?.max_rad,cal?.calibrated]);
      const captureKey=job?.action==='capture'&&job.status==='completed'?`${job.at}:${job.status}`:null;
      if(captureKey&&this.captureJob!==captureKey){this.calibrationDirty=false;this.captureJob=captureKey;}
      if(this.calKey!==key&&!this.calibrationDirty&&!this.root.querySelector('.service-calibration')?.contains(document.activeElement)){
        this.calKey=key;this.$('service-direction').value=cal?.direction??'';this.$('service-min').value=finite(cal?.min_rad)?(cal.min_rad*180/Math.PI).toFixed(2):'';this.$('service-max').value=finite(cal?.max_rad)?(cal.max_rad*180/Math.PI).toFixed(2):'';
      }
    set('service-calibration-detail',cal?.calibrated?`已保存零位 ${cal.zero_raw} counts · 方向 ${cal.direction} · ${s.calibration?.calibration_path||'等待保存路径'}`:'未保存实际零位');
    }
    set('service-calibration-mode',b.mode==='motion'?'当前为运动模式；支撑机身，停止并松开后点上方“切到标定模式”。':b.mode==='commissioning'?'标定模式：确认扭矩 OFF 后可调整并保存。':'等待服务模式反馈。');
    const saved=s.calibration?.calibration,q=saved?.imu_mount_quat,imuKey=JSON.stringify([q,saved?.imu_mount_verified]);
    const imuJob=job?.action==='verify-imu'&&job.status==='completed'?`${job.at}:${job.status}`:null;
    if(imuJob&&this.imuJob!==imuJob){this.mountDirty=false;this.imuJob=imuJob;}
    if(Array.isArray(q)&&this.imuKey!==imuKey&&!this.mountDirty&&document.activeElement!==this.$('service-mount')){this.$('service-mount').value=q.join(' ');this.imuKey=imuKey;}
    set('service-imu-state',saved?.imu_mount_verified===true?'已保存确认':saved?'尚未保存确认':'等待标定回读');
    for(const id of ['service-center','service-move','service-minus','service-plus','service-capture','service-verify-imu'])this.$(id).disabled=!!(this.blocked||this.posting);
    this.$('service-center').disabled ||= !!(s.saved_calibrated_count??s.calibrated_count);
    if(this.$('service-quick-stop'))this.$('service-quick-stop').disabled=!!this.options.replay;
    const key=job?`${job.at}:${job.action}:${job.status}:${job.error||''}:${job.result?.reconnected||''}:${job.result?.input?.status||''}:${job.action==='init'?job.phase+':'+job.message:''}`:'';
    if(job&&key!==this.lastJob){
      this.lastJob=key;
      const message=job.action==='init'?`Home 站姿 · ${{running:'执行中',completed:'已确认到位',error:'未完成'}[job.status]||job.status} · ${job.error||job.result?.message||job.message||'等待执行反馈'}`:
        job.status==='completed'&&['delete-model'].includes(job.action)?job.result?.message||'模型已删除，官方模型保留':
        job.action==='import-model'&&job.status==='completed'?`已替换 ${job.result?.name||'模型'}；所选动作绑定已确认。`:
        `${actions[job.action]||job.action} · ${{running:'执行中，等待反馈',completed:'服务已完成',error:'未完成'}[job.status]||job.status}${job.error?' · '+job.error:''}`;
      const input=job.result?.input,inputNote=input?.status==='recovering'?'手柄连接恢复中':input?.status==='error'?`手柄暂不可用：${input.error}`:input?.status==='ready'?'手柄连接已恢复':'';
      this.feedback(job.action,message+(inputNote?' · '+inputNote:''),job.status,job.result?.message||'');
    }
  }
}
