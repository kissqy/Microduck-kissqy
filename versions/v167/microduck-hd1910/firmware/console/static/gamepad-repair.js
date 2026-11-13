import {showFeedback} from './feedback.js';

export class GamepadRepair {
  constructor(panel){
    this.panel=panel;this.open=false;
    const head=document.querySelector('#control-panel .panel-head');
    this.button=document.createElement('button');this.button.type='button';this.button.className='button';
    this.button.id='gamepad-repair-open';this.button.textContent='手柄连接修复';
    head.append(this.button);
    this.root=document.createElement('section');this.root.className='gamepad-repair';this.root.hidden=true;
    this.root.setAttribute('aria-label','GameSir 手柄连接修复');
    this.root.innerHTML=`<div class="gamepad-repair-heading"><strong>手柄连接 / 修复</strong><button type="button" class="text-button" id="gamepad-repair-close">收起</button></div>
      <p>打开 Nova 2 Lite，保持 <b>A+HOME</b> 模式，松开摇杆和按键。正常连接保留原配对，按层恢复缺失的输入服务；已连接时直接返回。</p>
      <div class="gamepad-repair-fields"><label>手柄 MAC（可留空自动识别）<input id="gamepad-repair-address" type="text" maxlength="17" placeholder="例如 53:81:7F:20:AE:AB" autocomplete="off" spellcheck="false"></label>
      <label class="service-check"><input id="gamepad-repair-supported" type="checkbox">首次／重新配对：手柄已进入配对模式，机身有支撑；允许卸力，并删除所选手柄已有的配对</label></div>
      <p class="tiny muted">仅首次／重新配对会暂停实体输入并卸力。慢闪时按住 HOME+截图键 2–3 秒进入配对；手机连接服务只恢复原状态。</p>
      <div class="service-action-row"><button type="button" class="button accent" id="gamepad-repair-start" disabled>连接／修复</button><span class="tiny muted">执行一次，不自动重试或重启 Zero</span></div>
      <div id="gamepad-repair-status" class="panel-note service-job" role="status" aria-live="polite">先连接 Zero 的 SSH，再开始修复。</div>
      <div id="gamepad-repair-steps" class="tiny muted"></div>
      <div id="gamepad-repair-evidence" class="tiny muted"></div>`;
    head.after(this.root);
    this.$=id=>this.root.querySelector('#gamepad-repair-'+id);
    this.button.onclick=()=>{this.open=!this.open;this.root.hidden=!this.open;this.render();};
    this.$('close').onclick=()=>{this.open=false;this.root.hidden=true;};
    this.$('supported').onchange=()=>this.render();
    this.$('start').onclick=()=>this.start();
  }
  async start(){
    if(this.blocked)return;
    const address=this.$('address').value.trim().toUpperCase();
    if(address&&!/^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$/.test(address)){
      showFeedback(this.$('status'),'MAC 格式应为 AA:BB:CC:DD:EE:FF；只有一只手柄时可留空。','warning');return;
    }
    await this.panel.post({action:'repair-gamepad',supported:true,address,operation:this.$('supported').checked?'pair':'repair'});
  }
  render(){
    const s=this.panel.s,options=this.panel.options||{},job=s?.service_control?.job;
    this.blocked=!s||!!(options.replay||options.offline||s.connection?.active===false||s.connection_paused||s.service_control?.busy||s.service_control?.stopping||s.service_operation||this.panel.posting);
    this.button.disabled=!!(options.replay||options.offline);
    this.$('start').disabled=this.blocked;
    for(const id of ['address','supported'])this.$(id).disabled=this.blocked;
    this.$('start').textContent=job?.action==='repair-gamepad'&&job.status==='running'?'正在处理…':this.$('supported').checked?'开始配对':'连接／修复';
    const bus=s?.bus||{},pad=s?.control?.webpad;
    const robot=!s?.service_sample_fresh?'等待实时反馈':bus.mode!=='motion'?'标定模式':!bus.homed?'未 HOME':!bus.policy_enabled?'HOME':s.control?.balance_active?'保持／运动':'策略已启用';
    const result=job?.action==='repair-gamepad'?(job.result||job.pad_evidence):null;
    const yes=v=>v===true?'已确认':v===false?'未就绪':'未核对';
    const current=pad?.event_authoritative?` · 当前手柄输入 ${pad.real_connected?'已接入':'已断开'}`:'';
    this.$('evidence').textContent=result?`${job.status==='running'?'本次核对':'上次核对'}：${result.address||'目标手柄'} · 蓝牙 ${yes(result.bluetooth_connected)} · 实体输入 ${yes(result.physical)} · Xbox 桥接 ${yes(result.virtual&&result.bridge_active)} · padd 打开 Xbox ${yes(result.padd_open)}${current} · 机器人 ${robot}`:`尚未执行连接核对${current} · 机器人 ${robot}`;
    if(job?.action!=='repair-gamepad')return;
    const key=JSON.stringify([job.at,job.status,job.phase,job.message,job.error,job.result,job.pad_steps]);
    if(key===this.lastKey)return;this.lastKey=key;
    showFeedback(this.$('status'),job.error||job.result?.message||job.message||'正在提交修复…',job.result?.phase==='pair_required'||job.result?.warnings?.length?'warning':job.status);
    const names={checking:'目标核对',pause_input:'暂停输入',forget:'删除目标旧配对',adapter:'蓝牙适配器',scanning:'发现手柄',pairing:'配对与信任',bluetooth:'蓝牙连接',physical:'实体输入',bridge:'Xbox 桥接',padd:'padd 接入',phone_pause:'暂停手机连接服务',phone_restore:'恢复手机连接服务',connect_failed:'蓝牙连接',physical_unready:'实体输入',bridge_unready:'Xbox 桥接',padd_unready:'padd 接入',adapter_failed:'蓝牙适配器',scan_busy:'发现手柄',scan_failed:'发现手柄',not_found:'发现手柄',missing_service:'目标核对',wrong_device:'目标核对',choose_device:'目标核对',busy:'目标核对',relax_unconfirmed:'停止并松开',bridge_service:'恢复桥接服务',padd_service:'恢复 padd 服务',connection_changed:'结束核对'};
    this.$('steps').textContent=Object.entries(job.pad_steps||{}).filter(([,v])=>v.status!=='waiting').map(([phase,v])=>`${names[phase]||'操作结果'} · ${v.status==='success'?'成功':v.status==='failed'?'失败':'提示'} · ${v.message}`).join('\n');
    if(job.status==='completed'&&job.result?.phase==='ready'&&this.$('supported').checked){this.$('supported').checked=false;this.$('start').textContent='连接／修复';}
  }
}
