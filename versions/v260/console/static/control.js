import {PadControls} from './webpad-controls.js';
import {ControlSocket} from './control-socket.js';
import {ConnectionRetry} from './connection-retry.js';
import {showFeedback} from './feedback.js';
import {formatError} from './messages.js';
import {actionSlots,supportsFeature} from './service-builds.js';
import {jointExecutionProfile,jointProfileSummary,jointExecutionNotice} from './execution-profile.js';
export function skillReady(s,slot){
  const b=s?.bus||{},n=b.native||{};
  return s?.service_sample_fresh===true&&b.mode==='motion'&&b.phase==='control'&&b.homed===true&&b.policy_enabled===true&&n.imu_ready===true&&n.torque_state_confirmed===true&&!b.torque_off_pending&&typeof b.loaded_models?.[slot]?.sha256==='string'&&(slot==='ground_pick'||slot==='sitstand'?typeof s.capabilities?.[slot]==='string':s.capabilities?.skills?.includes(slot)===true);
}
export function recorderLabel(record,fresh=true){
  if(!fresh||!record)return '录放：等待回读';
  if(record.available!==true)return '录放：'+(formatError(record.reason)||'状态尚未就绪');
  const seconds=ms=>(ms/1000).toFixed(1).replace(/\.0$/,'')+'秒';
  const phase=record.phase;
  if(!Number.isSafeInteger(record.elapsed_ms)||record.elapsed_ms<0||!Number.isSafeInteger(record.duration_ms)||record.duration_ms<0||typeof record.has_last!=='boolean')return '录放：状态无效';
  if(phase==='recording')return '录放：录制中 '+seconds(record.elapsed_ms)+(record.reason?' · '+record.reason:'');
  if(phase==='saving')return '录放：保存中 '+seconds(record.duration_ms);
  if(phase==='playing')return '录放：播放中 '+seconds(record.elapsed_ms)+' / '+seconds(record.duration_ms);
  if(phase==='pending')return '录放：'+(record.reason||'等待按键判定');
  if(phase==='error')return '录放：'+(formatError(record.reason)||'操作未完成');
  if(phase==='idle')return record.has_last?'录放：已保存 '+seconds(record.duration_ms):'录放：尚未录制';
  return '录放：状态无效';
}
export class ControlPanel {
  constructor(cfg,root){
    this.cfg=cfg;this.root=root;this.client=crypto.randomUUID().replaceAll('-','');this.seq=0;this.connected=false;this.connecting=false;
    this.disabled=true;this.armed=false;this.epoch=0;this.real=false;this.s=null;this.options={};this.frames=[];this.sending=false;
    this.feedback=root.querySelector('#control-feedback');this.pad=new PadControls(this);this.retry=0;this.reconnect=new ConnectionRetry();this.linkEpoch=0;this.sessionUsed=false;
    this.socket=new ControlSocket(cfg.control_token,message=>{this.suspend();this.connectionFailed(message);},status=>{this.state={...this.state,...status};this.real=!!status.real_connected;if(this.real||status.available===false)this.suspend();this.paint();});
    this.volumeDirty=false;this.volumeBusy=false;this.mouthDirty=false;
    const volume=root.querySelector('#control-volume'),mouth=root.querySelector('#control-mouth');
    volume.addEventListener('input',()=>{this.volumeDirty=true;root.querySelector('#control-volume-value').textContent=volume.value+'%';});
    volume.addEventListener('change',()=>this.applyVolume());
    mouth.addEventListener('input',()=>{this.mouthDirty=true;root.querySelector('#control-mouth-value').textContent=Number(mouth.value).toFixed(0)+'%';});
    mouth.addEventListener('change',()=>this.applyPadSettings());
    for(const button of root.querySelectorAll('[data-head-amplitude]'))button.onclick=()=>{this.headRad=Number(button.dataset.headAmplitude);this.mouthDirty=true;this.applyPadSettings();};
    this.timer=setInterval(()=>this.tick(),100);
    for(const event of ['blur','pagehide'])window.addEventListener(event,()=>this.suspend());
    window.addEventListener('pagehide',()=>this.socket.close());
    document.addEventListener('visibilitychange',()=>{if(document.hidden)this.suspend();});
  }
  async post(command){
    const epoch=this.epoch,queuedAt=performance.now();
    const run=async()=>{
      if(command.action==='webpad_state'&&(!this.armed||epoch!==this.epoch))return {accepted:true,cancelled:true};
      if(command.action==='webpad_state'&&performance.now()-queuedAt>400)throw Error('输入已过期，已暂停网页动作');
      const payload={...command,client:this.client,seq:++this.seq};let result;
      if(['webpad_state','webpad_close'].includes(command.action)){
        result=await this.socket.request(payload);this.inputRtt=result.browser_rtt_ms;
      }else{
        const response=await fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},body:JSON.stringify(payload),signal:AbortSignal.timeout(command.action==='connect'?20000:12000)});
        result=await response.json();if(!response.ok)throw Error(result.error||'控制请求失败');
      }
      if(result.real_connected!==undefined)this.real=result.real_connected;
      if(result.accepted!==true)throw Error(result.error||result.reason||'手柄输入未确认');
      if(result.audio)this.audio=result.audio;
      if(command.action!=='set_volume')this.state=result;this.paint();return result;
    };
    try{return await run();}
    catch(e){
      if(e.name==='TimeoutError'||e.name==='AbortError')throw Error(command.action==='set_volume'?'音量请求超时；未确认成功，请查看系统日志':command.action==='connect'?'手柄接口连接超时，请查看系统日志':'手柄回执超时；动作未重发');
      throw e;
    }
  }
  applyPadSettings(){
    window.dispatchEvent(new CustomEvent('r17-pad-settings',{detail:{mouth_percent:Number(this.root.querySelector('#control-mouth').value),head_rad:this.headRad??this.state?.settings?.head_rad??this.s?.control?.webpad?.settings?.head_rad}}));
  }
  async applyVolume(){
    if(this.volumeBusy)return;
    const value=Number(this.root.querySelector('#control-volume').value);let resend=false;
    this.volumeBusy=true;this.paint();
    try{const result=await this.post({action:'set_volume',volume:value});this.audio=result.audio;resend=Number(this.root.querySelector('#control-volume').value)!==value;this.volumeDirty=resend;showFeedback(this.feedback,`音量 ${result.volume}% 已回读确认并保存，重启后恢复`,'completed');}
    catch(e){showFeedback(this.feedback,e.message,'error');}
    finally{this.volumeBusy=false;this.paint();if(resend)this.applyVolume();}
  }
  async connect(){
    if(this.connecting||!this.reconnect.ready||this.servicePaused())return;this.connecting=true;const linkEpoch=this.linkEpoch;
    try{if(this.sessionUsed){this.client=crypto.randomUUID().replaceAll('-','');this.seq=0;this.sessionUsed=false;}if(!(this.s?.control?.connected===true&&this.s?.control?.webpad?.available===true))await this.post({action:'connect'});if(linkEpoch!==this.linkEpoch||this.servicePaused())return;await this.socket.open();this.sessionUsed=true;if(linkEpoch!==this.linkEpoch||this.servicePaused())return;this.connected=true;this.reconnect.connected();this.localPadError=false;showFeedback(this.feedback,'手柄长连接已就绪 · Start 回 HOME；启用策略后 RB 右脚踢球','completed');}
    catch(e){if(linkEpoch===this.linkEpoch&&!this.servicePaused())this.connectionFailed(e.message);}
    finally{this.connecting=false;this.paint();}
  }
  bindStartButton(button){
    this.startAlias=button;this.pad.bindButton(button);this.paint();
  }
  bindRelaxButton(button){
    if(this.relaxAlias===button)return;
    this.relaxAlias=button;this.pad.boundButtons.add(button);
    button.addEventListener('keydown',e=>{if(e.repeat&&['Enter','Space'].includes(e.code))e.preventDefault();});
    button.addEventListener('click',()=>{
      if(button.disabled||this.disabled)return;
      // One bounded Select tap; this alias never holds Select for shutdown.
      this.releaseStartOwnerOnIdle=true;
      this.pad.applyButton(button,true);this.pad.applyButton(button,false);
    });
    this.paint();
  }
  connectionFailed(message){
    this.connected=false;this.resetRecorderReadback();this.socket.close();
    if(!this.servicePaused())showFeedback(this.feedback,message+'；'+this.reconnect.failed(),'error');
  }
  change(arm=true){
    if(this.disabled)return;if(arm)this.armed=true;if(!this.armed)return;
    if(this.frames.length>=32){this.suspend();showFeedback(this.feedback,'输入回执延迟过大，已暂停网页输入','error');return;}
    const frame=this.pad.frame(),key=JSON.stringify([frame.buttons.slice().sort(),frame.axes.dx,frame.axes.dy,...['lt','rt'].map(k=>[frame.axes[k]>0,frame.axes[k]>=.3])]);
    const next={frame,key,at:performance.now()},last=this.frames.at(-1);
    if(last?.key===key)this.frames[this.frames.length-1]=next;else this.frames.push(next);
    this.sendFrames();
  }
  async sendFrames(){
    if(this.sending)return;this.sending=true;const linkEpoch=this.linkEpoch;
    try{while(this.frames.length&&this.armed&&linkEpoch===this.linkEpoch){const next=this.frames.shift();if(performance.now()-next.at>400)throw Error('输入已过期，已暂停网页动作');await this.post({action:'webpad_state',frame:next.frame});if(!this.frames.length&&!this.pad.active())this.armed=false;}}
    catch(e){if(linkEpoch===this.linkEpoch){this.suspend();if(e.status!==409){if(this.connected)this.connectionFailed(e.message);}else if(!this.servicePaused())showFeedback(this.feedback,e.message,'warning');}}
    finally{
      this.sending=false;
      if(this.releaseStartOwnerOnIdle&&!this.armed&&!this.frames.length&&!this.pad.active()){
        this.releaseStartOwnerOnIdle=false;
        if(linkEpoch===this.linkEpoch&&this.connected)this.post({action:'webpad_close'}).catch(e=>showFeedback(this.feedback,'AI 控制按钮已发送，但网页控制权未释放：'+e.message,'error'));
      }
    }
  }
  tick(){
    if(document.hidden||this.options.replay||this.options.offline||this.servicePaused())return;
    if(!this.connected){if(supportsFeature(this.s?.bus,'webpad'))this.connect();return;}
    if(this.armed&&!this.disabled&&!this.sending&&!this.frames.length)this.change(false);
  }
  suspend(){
    const active=this.armed;this.armed=false;this.epoch++;this.frames=[];this.pad.reset();
    if(active&&this.connected)this.post({action:'webpad_close'}).catch(()=>{});
  }
  servicePaused(){
    const job=this.s?.service_control;
    return !!(this.s?.service_operation||this.s?.connection_paused||job?.stopping||job?.busy&&!['set-pad-settings'].includes(job?.job?.action)||job?.job?.result?.input?.status==='recovering');
  }
  recoveringLink(){return this.recovering&&Date.now()<this.recoveryUntil&&this.s?.service_control?.job?.status!=='error';}
  linkFeedback(message,status){this.linkMessage=message;showFeedback(this.feedback,message,status);}
  resetConnectionRetry(){this.reconnect=new ConnectionRetry();}
  resetRecorderReadback(){
    this.recorderReport=undefined;this.recorderChecked=undefined;this.recorderReceived=undefined;
    this.recorderPid=undefined;this.recorderStamp=undefined;this.recorderEpoch=this.linkEpoch;
  }
  recorderReadback(drive,live){
    if(!live||this.recorderEpoch!==this.linkEpoch)this.resetRecorderReadback();
    if(!live)return {fresh:false};
    const report=drive?.recorder,checked=report?.checked_ms;
    if(!report||!Number.isSafeInteger(checked))return {report,fresh:false};
    // Input events, command replies and telemetry snapshots can arrive out of
    // order. Keep only this display's newest receipt, without changing input state.
    const native=report.available===true&&Number.isSafeInteger(report.pid)&&Number.isSafeInteger(report.t_ms);
    if((this.recorderChecked===undefined||checked>this.recorderChecked)&&
       !(native&&report.pid===this.recorderPid&&report.t_ms<this.recorderStamp)){
      this.recorderReport={...report};this.recorderChecked=checked;this.recorderReceived=performance.now();
      if(native){this.recorderPid=report.pid;this.recorderStamp=report.t_ms;}
    }
    return {report:this.recorderReport,fresh:Number.isFinite(this.recorderReceived)&&performance.now()-this.recorderReceived<=3500};
  }
  render(s,options={}){
    // A command receipt is useful immediately; the next snapshot owns state.
    this.audio=s.control?.audio;
    this.s=s;this.options=options;const previousAvailable=this.state?.available,pad=s.control?.webpad;if(pad){this.state={...this.state,...pad};if(pad.real_connected!==undefined)this.real=pad.real_connected;}
    const maintenance=this.servicePaused();
    if(maintenance&&!this.maintenance){this.suspend();this.recovering=false;this.localPadError=false;this.linkFeedback(s.connection_paused?'Zero 关机已提交，手柄连接已暂停':'服务操作进行中，手柄输入已暂停；长连接保持开启','running');}
    if(!maintenance&&this.maintenance){this.retry=0;this.recovering=true;this.recoveryUntil=Date.now()+8000;this.linkFeedback('服务操作结束，正在恢复手柄连接…','running');}
    this.maintenance=maintenance;
    if(s.connection_paused){this.suspend();this.connected=false;this.socket.close();}
    if(s.control?.connected===false&&this.connected){this.suspend();this.connectionFailed('手柄连接已断开');}
    const recovering=this.recoveringLink();
    if(pad?.available===false&&this.connected&&!maintenance){this.suspend();this.connectionFailed(pad.reason||pad.error||'手柄 SSH 已断开');}
    if(pad?.available===false&&!maintenance&&!recovering&&!this.localPadError){this.localPadError=true;this.suspend();this.linkFeedback('手柄本地接口不可用：'+(pad.reason||pad.error||'等待恢复'),'error');}
    if(pad?.available===true&&!maintenance){
      if(this.recovering&&previousAvailable!==true&&!this.connected)this.retry=0;
      if((this.localPadError||this.recovering&&this.connected)&&this.feedback.textContent===this.linkMessage)this.linkFeedback('手柄本地接口已恢复，无需刷新页面','completed');
      this.localPadError=false;if(this.connected)this.recovering=false;
    }
    if(this.real||options.replay||options.offline||maintenance)this.suspend();this.paint();
  }
  paint(){
    this.real=!!(this.state?.event_authoritative?this.state.real_connected:this.s?.control?.webpad?.real_connected??this.state?.real_connected);
    const bus=this.s?.bus||{},loaded=bus.policy_enabled?bus.active_model??bus.loaded_models?.walk:bus.loaded_models?.walk;
    const profile=jointExecutionProfile(loaded),joint=!!profile;
    const uniformApplied=joint&&bus.policy_enabled&&bus.scale_use==='joint_uniform'&&Number.isFinite(bus.active_action_scale);
    this.disabled=!this.connected||this.real||!this.cfg.service_enabled||!supportsFeature(bus,'webpad')||bus.mode!=='motion'||bus.phase!=='control'||this.state?.available===false||this.servicePaused()||this.options.replay||this.options.offline;
    const audio=this.audio||this.s?.control?.audio,volume=this.root.querySelector('#control-volume');
    if(!this.volumeDirty&&Number.isInteger(audio?.volume)){volume.value=audio.volume;this.root.querySelector('#control-volume-value').textContent=audio.volume+'%';}
    if(!Number.isInteger(audio?.volume))this.root.querySelector('#control-volume-value').textContent='—';
    volume.disabled=!this.connected||this.volumeBusy||!Number.isInteger(audio?.volume)||this.options.replay||this.options.offline||!!this.s?.service_operation;
    const mouth=this.root.querySelector('#control-mouth'),settings=this.state?.settings||this.s?.control?.webpad?.settings;
    const settingJob=this.s?.service_control?.job;
    if(settingJob?.action==='set-pad-settings'&&settingJob.status==='completed'&&this.settingJob!==settingJob.at&&settings?.mouth_percent===settingJob.command.mouth_percent&&settings?.head_rad===settingJob.command.head_rad){this.settingJob=settingJob.at;this.mouthDirty=false;this.headRad=undefined;}
    if(!this.mouthDirty&&settings){mouth.value=settings.mouth_percent;this.headRad=settings.head_rad;this.root.querySelector('#control-mouth-value').textContent=settings.mouth_percent.toFixed(0)+'%';}
    if(!settings){this.root.querySelector('#control-mouth-value').textContent='—';if(!this.mouthDirty)this.headRad=undefined;}
    const settingsDisabled=!settings||!supportsFeature(bus,'live_pad_settings')||!!this.s?.service_control?.busy||!!this.s?.service_operation||this.options.replay||this.options.offline;
    mouth.disabled=settingsDisabled;
    const drive=this.state?.drive_speed??this.s?.control?.webpad?.drive_speed;
    const recorderLive=this.connected&&this.s?.control?.connected!==false&&this.state?.available!==false&&this.s?.control?.webpad?.available!==false&&!this.options.replay&&!this.options.offline&&!this.servicePaused();
    const recorder=this.recorderReadback(drive,recorderLive);
    this.root.querySelector('#control-recorder').textContent=recorderLive&&drive&&!drive.recorder?'录放：安装配套更新后支持录放':recorderLabel(recorder.report,recorderLive&&recorder.fresh);

    for(const button of this.root.querySelectorAll('[data-head-amplitude]')){button.disabled=settingsDisabled;const selected=Number(button.dataset.headAmplitude)===(this.headRad??settings?.head_rad);button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));}
    this.root.querySelector('#control-audio-status').textContent=Number.isInteger(audio?.volume)?'嘴巴限制与头部幅度对网页、真实手柄共同生效；运行中更新，不卸力。':'音量等待配置 · 幅度保存到 Zero，重启后保留。';
    this.root.querySelector('[data-button="start"] small').textContent=bus.policy_enabled?'关闭策略 / 回 HOME':!bus.homed?'回 HOME':'启用 Walk / 保持';
    if(this.startAlias){
      this.startAlias.textContent=bus.policy_enabled?'Start · 回 HOME':bus.homed?'Start · 进入保持':'Start · 回 HOME';
      this.startAlias.title=bus.policy_enabled?'与手柄 Start 相同：关闭策略并回 HOME':bus.homed?'与手柄 Start 相同：本次点击启用策略，零速度保持':'与手柄 Start 相同：本次点击只回 HOME；回位完成后再点进入保持';
    }
    for(const button of this.root.querySelectorAll('[data-requires-slot]')){const slot=button.dataset.requiresSlot,available=skillReady(this.s,slot);button.dataset.unavailable=String(!available);button.title=slot==='kick_right'?(available?'RB：右脚踢球；HOME 后启用策略，按一次执行':'先回 HOME 并启用保持，等待右脚踢球就绪'):slot==='roulade'?(available?'X：前滚翻 / Roulade；基准 1.00，按住连续翻滚':'先回 HOME 并启用保持，等待前滚翻就绪'):(available?'A：地面捡取 / Ground pick；策略启用后按一次':'先回 HOME 并启用保持，等待捡物动作就绪');}
    const sit=this.root.querySelector('[data-dpad="dy:1"]');if(sit){sit.dataset.unavailable=String(!skillReady(this.s,'sitstand'));sit.title=sit.dataset.unavailable==='true'?'先回 HOME 并启用保持，等待起坐模型就绪':'方向键下：起坐';}
    this.pad.paint();this.root.querySelector('#control-status').textContent=this.servicePaused()?'服务操作中':this.real?'真实手柄已接管':this.disabled?'等待运动服务':this.armed?'网页手柄输入中':'网页手柄就绪';
    const startHint=bus.policy_enabled?'Walk 已启用：摇杆回中＝原地保持，推摇杆＝行走':!bus.homed?'首次 Start 回 HOME；回位过程结束后，再按 Start 启用 Walk':'按 Start 启用 Walk；躺着也可启用，无需先扶正';
    this.root.querySelector('#control-reason').textContent=(this.real?'真实手柄接管 · 网页动作输入暂停；':'')+startHint;
    this.root.querySelector('#control-link-latency').textContent=this.connected?`WebSocket 长连接 · ${Number.isFinite(this.inputRtt)?'输入回执 '+Math.round(this.inputRtt)+' ms':'等待首次输入回执'}`:'手柄长连接未就绪';
    if(bus.last_enable_refusal&&bus.last_enable_refusal!==this.lastEnableRefusal){this.lastEnableRefusal=bus.last_enable_refusal;showFeedback(this.feedback,bus.last_enable_refusal,'error');}
    if(!bus.last_enable_refusal)this.lastEnableRefusal=null;
    const model=this.root.querySelector('#control-model');
    const task=loaded?.task,modelLabel=task?.startsWith('Mjlab-VelStand-')?'联合行走／起身 / Walk':actionSlots.find(row=>row.task_prefixes.some(prefix=>task?.startsWith('Mjlab-'+prefix+'-')))?.label||'自训模型';
    const inference=bus.policy_enabled?joint?uniformApplied?'统一输出参数 · 推理中':'统一参数已加载，实际值待回读':'正在推理':joint?'统一输出参数 · 策略未启用':'策略未启用';
    model.textContent=loaded?`${modelLabel} · ${loaded.sha256.slice(0,12)} · ${inference}`:'尚未确认运行模型';model.title=[task,loaded?.sha256,profile&&jointProfileSummary(profile)].filter(Boolean).join(' · ');
    const fresh=this.s?.service_sample_fresh===true;
    const set=(id,value)=>this.root.querySelector('#parameter-'+id).textContent=value;
    const number=value=>typeof value==='number'&&Number.isFinite(value);
    const fmt=value=>number(value)?value.toFixed(2):'—';
    set('status',fresh?uniformApplied?'机器人回读 · 联合模型统一输出':'机器人实际回读':'等待机器人新鲜反馈');
    set('action-label',joint?'联合基础缩放':'官方动作缩放');
    set('action',fresh?fmt(profile?.action_scale??bus.action_scale):'—');set('sit',fresh?'1.00':'—');
    if(joint)set('action-default','联合模型 · 默认 1.00');
    for(const [label,key] of [['head','head_lowpass'],['legs','legs_lowpass']]){
      const a=fresh?(bus.policy_enabled?bus.active_target_filters?.[key]??(joint?null:bus[key]):profile?null:bus[key]):null;set(label,fmt(a));
      set(label+'-desc',number(a)?a===1?'直通，不做低通平滑':`本帧 ${Math.round(a*100)}% + 上帧 ${Math.round((1-a)*100)}%`:'等待实际滤波参数');
    }
    set('voltage',fresh?fmt(bus.voltage_scale_mult)+' 倍':'—');
    set('voltage-desc',fresh&&typeof bus.voltage_adapt==='boolean'?(bus.voltage_adapt?`已开启 · 参考 ${bus.nominal_voltage??'—'} V`:'已关闭 · 不作电压补偿'):'等待实际电压补偿参数');
    set('actual',fresh&&bus.policy_enabled?number(bus.active_action_scale)?bus.active_action_scale.toFixed(3):'未推理':'—');
    set('actual-desc',fresh&&bus.policy_enabled?joint?`联合模型 · 基础 ${fmt(profile.action_scale)} × 电压补偿`:({walking:'行走',hold:'零速度保持',sitstand:'起坐',ground_pick:'低头捡物',roulade:'前滚翻',kick_right:'右脚踢球'}[bus.scale_use]||'当前模型')+' · 基础倍率 × 电压补偿':'启用策略后显示实际推理倍率');
    this.root.querySelector('#control-readback').textContent=joint?`${fresh?uniformApplied?'实际倍率与滤波由机器人回读；':bus.policy_enabled?'等待实际推理参数；':'配置已加载，策略未启用；':'等待新鲜反馈；'}${jointProfileSummary(profile)}。${jointExecutionNotice}`:'头、腿滤波及电压补偿沿用官方配置；中控仅调整动作缩放。';
  }
}
