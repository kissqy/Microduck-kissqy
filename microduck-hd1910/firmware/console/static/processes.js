// Present the watched robot services: what is running, whether the hardware each
// one needs is fitted, and whether it starts at boot. The three are kept apart on
// purpose — `tofd` running while the ToF is silent and `mediad` running while the
// camera node is missing are both worse than the unit being down, and a single
// green light would hide exactly that.
const STATE_ZH={active:'运行',reloading:'重载',activating:'启动中',deactivating:'停止中',
  inactive:'停止',failed:'失败'};
const SUB_ZH={running:'运行中',exited:'已退出',dead:'未启动',failed:'失败',waiting:'等待',
  'auto-restart':'自动重启',start:'启动中'};

const finite=v=>typeof v==='number'&&Number.isFinite(v);

export function unitState(row){
  const active=row?.active||'unknown';
  const label=STATE_ZH[active]||active;
  if(active==='failed')return {tone:'bad',label};
  if(active==='active')return {tone:'live',label:SUB_ZH[row?.sub]&&row.sub!=='running'?'运行 · '+SUB_ZH[row.sub]:label};
  if(active==='activating'||active==='reloading'||active==='deactivating')return {tone:'warn',label};
  if(row?.load==='not-found')return {tone:'neutral',label:'未安装'};
  return {tone:'neutral',label};
}

export function autostartState(row){
  const state=row?.enabled||'';
  // Masked with no unit file behind the mask: nothing to enable, and unmasking
  // it would only fail later and leave the board changed.
  if(row?.installed===false)return {tone:'warn',label:'已屏蔽 · 未安装'};
  if(row?.load==='not-found')return {tone:'neutral',label:'—'};
  if(state==='enabled')return {tone:'live',label:'开机自启'};
  if(state==='disabled')return {tone:'neutral',label:'不自启'};
  if(state==='masked')return {tone:'warn',label:'已屏蔽'};
  if(state==='static')return {tone:'neutral',label:'内建'};
  return {tone:'neutral',label:state||'未知'};
}

// null is "not verified", never "absent": the console will not claim the ToF is
// missing just because nobody has asked the bus yet.
export function hardwareChip(id,reading,meta){
  const label=meta?.label||id;
  const present=reading?.present;
  if(present===true)return {tone:'live',symbol:'●',label,detail:reading?.detail||''};
  if(present===false)return {tone:'bad',symbol:'○',label,detail:reading?.detail||'未检测到'};
  return {tone:'neutral',symbol:'◌',label,detail:reading?.detail||'未验证'};
}

// The servos are the one piece of hardware the console cannot see on its own:
// they are behind robotd, so the count comes from the live bus sample. Zero
// live joints while robotd runs is the case worth showing red.
export function servoChip(count,total=15){
  const label='HD-1910 舵机';
  if(!Number.isInteger(count))return {tone:'neutral',symbol:'◌',label,detail:'等待 robotd 反馈'};
  if(count===0)return {tone:'bad',symbol:'○',label,detail:'没有关节反馈'};
  return {tone:count===total?'live':'warn',symbol:count===total?'●':'◐',label,
          detail:`${count}/${total} 有反馈`};
}

// A ToF that is producing frames is present however it was last probed.
export function tofChip(reading,streaming){
  const meta={label:'VL53L5CX 测距'};
  if(streaming)return {tone:'live',symbol:'●',label:meta.label,detail:'正在出帧'};
  return hardwareChip('tof',reading,meta);
}

export function memoryText(bytes){
  if(!finite(bytes)||bytes<=0)return '—';
  if(bytes>=1024**3)return (bytes/1024**3).toFixed(1)+' GiB';
  return Math.max(1,Math.round(bytes/1024/1024))+' MiB';
}

export function autostartCommand(row,meta,enabled){
  if(!meta?.autostart)return null;
  if(!row||row.load==='not-found'||row.enabled==='static')return null;
  if(row.installed===false)return null;
  if(row.enabled==='masked'&&!enabled)return null;
  return {action:'unit-autostart',unit:meta.unit,enabled,supported:true};
}

export function autostartLabel(row,meta){
  if(!meta?.autostart)return '只读';
  if(!row||row.load==='not-found')return '不可用';
  if(row.installed===false)return '未安装';
  if(row.enabled==='static')return '内建 unit';
  if(row.enabled==='enabled')return '取消开机自启';
  if(row.enabled==='masked')return '开启开机自启（会先解除屏蔽）';
  return '设为开机自启';
}

export function autostartReason(row,meta){
  if(!meta?.autostart)return '该服务只能查看，不能从中控修改开机自启';
  if(!row)return '等待服务状态';
  if(row.installed===false)return '本机没有安装 '+meta.unit+'（只有屏蔽用的空壳），先部署该组件';
  if(row.load==='not-found')return '本机未安装 '+meta.unit;
  if(row.enabled==='static')return '内建 unit，不能改自启';
  return '';
}

export function summary(rows){
  if(!rows.length)return '';
  const total=rows.length;
  const running=rows.filter(r=>r.active==='active').length;
  const failed=rows.filter(r=>r.active==='failed').length;
  const masked=rows.filter(r=>r.enabled==='masked').length;
  const missing=rows.filter(r=>r.load==='not-found').length;
  const parts=[`${running}/${total} 运行`];
  if(failed)parts.push(`${failed} 失败`);
  if(masked)parts.push(`${masked} 已屏蔽`);
  if(missing)parts.push(`${missing} 未安装`);
  return parts.join(' · ');
}

export class ProcessPanel{
  constructor(cfg){
    this.cfg=cfg;this.rows=[];this.hardware={};this.posting=false;this.offline=false;
    this.meta=new Map((cfg.units||[]).map(row=>[row.unit,row]));
    this.hardwareMeta=new Map((cfg.hardware||[]).map(row=>[row.id,row]));
    this.root=document.getElementById('process-panel');
    if(!this.root)return;
    this.$=id=>document.getElementById(id);
    this.$('process-list').addEventListener('click',e=>{
      const button=e.target.closest('button[data-unit]');
      if(button)this.toggle(button.dataset.unit,button.dataset.enabled==='true');
    });
  }

  async post(command){
    if(this.posting||this.offline)return;
    this.posting=true;this.paint();
    try{
      const response=await fetch('/api/service',{method:'POST',
        headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},
        body:JSON.stringify({client:this.client(),seq:this.nextSeq(),command}),
        signal:AbortSignal.timeout(30000)});
      const data=await response.json();
      if(!response.ok||data.accepted!==true)throw Error(data.error||'服务未接收指令');
      // The ack only says the job was queued; the answer lands when it finishes.
      // Jobs carry their own timestamp, so remember where the log stood.
      // Console clock and browser clock are the same machine; a job with no
      // predecessor still needs a floor, or nothing would ever look "newer".
      this.baseJobAt=Math.max(this.s?.service_control?.job?.at||0,Date.now()/1000-1);
      this.feedback(data.message||'已提交','running');
    }catch(e){
      this.feedback(e.message,'error');
    }finally{this.posting=false;this.paint();}
  }

  client(){
    // One stable client id per page, so the service-side sequence window can
    // reject a replayed request from this tab.
    this.owner=this.owner||crypto.randomUUID().replaceAll('-','');
    return this.owner;
  }
  nextSeq(){this.seq=(this.seq||0)+1;return this.seq;}

  toggle(unit,enabled){
    const meta=this.meta.get(unit);if(!meta)return;
    this.post({action:'unit-autostart',unit,enabled,supported:true});
  }

  feedback(message,tone){
    const el=this.$('process-feedback');if(!el)return;
    el.textContent=message;el.className='panel-note service-job '+(tone||'');
  }

  render(s,options={}){
    if(!this.root)return;
    this.s=s;
    this.offline=!!options.replay||!!options.offline;
    // A dedicated channel: in --feetech mode `system` is robotd's own
    // telemetry and carries none of this.
    const units=s?.units||{};
    this.rows=Array.isArray(units.units)?units.units:[];
    // The probe belongs to the ToF row, and tofd's own state decides whether the
    // bus is free — not whichever row is being drawn.
    const tofd=this.rows.find(row=>row.unit==='tofd.service');
    this.tofdActive=tofd?.active==='active';
    this.hardware=units.hardware||{};
    this.error=units.error||'';
    const servos=Array.isArray(s?.servos)?s.servos:[];
    const live=servos.filter(row=>row.status==='live').length;
    this.servoCount=servos.length?live:null;
    this.tofStreaming=s?.channels?.tof?.status==='live';
    this.paint();
    this.watchJob(s);
  }

  // Report the finished job, not the submission ack: "found 0x29" and
  // "回读 enabled" are the answers the operator is waiting for.
  watchJob(s){
    const job=s?.service_control?.job;
    if(!job||this.baseJobAt===undefined)return;
    if(!['unit-autostart','tof-probe'].includes(job.action))return;
    // Only a job newer than the one already on screen belongs to this click.
    if(job.at<=this.baseJobAt)return;
    if(job.status==='running'||job.at===this.shownJobAt)return;
    this.shownJobAt=job.at;
    if(job.status==='error'){
      this.feedback(job.error||'操作失败','error');
      return;
    }
    const result=job.result||{};
    const message=job.action==='tof-probe'
      ?(result.message||'探测完成')
      :(result.message||'完成');
    this.feedback(message,'completed');
  }

  chip(id){
    if(id==='servos')return servoChip(this.servoCount);
    if(id==='tof')return tofChip(this.hardware.tof,this.tofStreaming);
    return hardwareChip(id,this.hardware[id],this.hardwareMeta.get(id)||{id,label:id});
  }

  paint(){
    if(!this.root)return;
    const list=this.$('process-list');if(!list)return;
    this.nodes=this.nodes||new Map();
    const seen=new Set();
    this.rows.forEach((row,index)=>{
      const meta=this.meta.get(row.unit)||{unit:row.unit,label:row.unit,hardware:[],autostart:false};
      seen.add(row.unit);
      // Rows are reused, not re-created: a snapshot every two seconds must not
      // pull the button out from under a click or drop keyboard focus.
      let node=this.nodes.get(row.unit);
      if(!node){node=this.buildRow(row,meta);this.nodes.set(row.unit,node);}
      this.updateRow(node,row,meta);
      const expected=list.children[index];
      if(expected!==node.row)list.insertBefore(node.row,expected||null);
    });
    for(const [unit,node] of this.nodes){
      if(seen.has(unit))continue;
      node.row.remove();this.nodes.delete(unit);
    }
    if(!this.rows.length&&!list.children.length)
      list.innerHTML='<p class="tiny muted">等待 Zero 上的 systemd 状态（每 2 秒一次；若中控刚重启，请刷新页面）。</p>';
    const empty=list.querySelector('p');
    if(empty)empty.hidden=this.rows.length>0;
    this.$('process-summary').textContent=this.rows.length?summary(this.rows):'等待服务状态';
    this.$('process-error').textContent=this.error||'';
    this.$('process-error').hidden=!this.error;
  }

  buildRow(row,meta){
    const el=(tag,cls)=>{const node=document.createElement(tag);if(cls)node.className=cls;return node;};
    const row_=el('div','process-row');row_.dataset.unit=row.unit;
    const name=el('div','process-name'),dot=el('span','status-dot'),
      strong=el('strong'),code=el('code');
    code.textContent=row.unit.replace('.service','');
    name.append(dot,strong,code);
    const badges=el('div','process-badges'),state=el('span','badge'),boot=el('span','badge');
    badges.append(state,boot);
    const hardware=el('div','process-hardware'),detail=el('div','process-detail'),actions=el('div','process-actions');
    const toggle=el('button','button'),probe=el('button','button');
    probe.type='button';probe.textContent='探测 0x29';
    probe.title='用 i2cdetect -y -r 3 读一次 I²C3';
    probe.onclick=()=>this.post({action:'tof-probe',supported:true});
    toggle.type='button';
    toggle.onclick=()=>{if(toggle.dataset.unit)this.toggle(toggle.dataset.unit,toggle.dataset.enabled!=='false');};
    if(meta.autostart)toggle.dataset.unit=row.unit;
    actions.append(toggle,probe);
    row_.append(name,badges,hardware,detail,actions);
    return {row:row_,dot,strong,state,boot,hardware,detail,toggle,probe};
  }

  updateRow(node,row,meta){
    const state=unitState(row),boot=autostartState(row);
    node.dot.className='status-dot '+state.tone;
    node.strong.textContent=meta.label;
    node.state.className='badge '+badgeTone(state.tone);
    node.state.textContent=state.label;
    node.boot.className='badge '+badgeTone(boot.tone);
    node.boot.textContent=boot.label;
    const chips=(meta.hardware||[]).map(id=>this.chip(id));
    node.hardware.replaceChildren(...(chips.length?chips.map(chip=>{
      const span=document.createElement('span');
      span.className='hw-chip '+chip.tone;span.title=chip.detail||'';
      span.append(document.createTextNode(chip.symbol+' '+chip.label));
      if(chip.detail){const small=document.createElement('small');small.textContent=chip.detail;span.append(small);}
      return span;
    }):[(()=>{const span=document.createElement('span');span.className='hw-chip neutral';span.textContent='无专属硬件';return span;})()]));
    node.detail.textContent=[finite(row.pid)?`PID ${row.pid}`:null,`内存 ${memoryText(row.memory)}`,
      finite(row.restarts)&&row.restarts>0?`重启 ${row.restarts} 次`:null,
      row.executable_present===false?'可执行文件缺失':null].filter(Boolean).join(' · ');
    const command=this.posting||this.offline?null:autostartCommand(row,meta,row.enabled!=='enabled');
    const reason=this.posting?'正在提交…':this.offline?'回放或离线时不修改服务':autostartReason(row,meta);
    node.toggle.disabled=!command;
    node.toggle.textContent=meta.autostart?autostartLabel(row,meta):'只读';
    node.toggle.title=reason||autostartLabel(row,meta);
    if(meta.autostart){node.toggle.dataset.unit=row.unit;node.toggle.dataset.enabled=String(row.enabled!=='enabled');}
    else{delete node.toggle.dataset.unit;delete node.toggle.dataset.enabled;}
    // Only the ToF row owns a bus probe, and only while tofd is not using the
    // bus. `hidden` is not enough: `.button` sets a display value, which wins
    // over the attribute's UA rule.
    const needsProbe=meta.hardware.includes('tof');
    node.probe.style.display=needsProbe?'':'none';
    const tofdBusy=this.tofdActive===true;
    node.probe.disabled=this.posting||this.offline||tofdBusy;
    node.probe.title=tofdBusy?'tofd 正在使用 I²C3；停掉它才能探测'
      :this.offline?'回放或离线时不探测总线':'用 i2cdetect -y -r 3 读一次 I²C3';
  }
}

function badgeTone(tone){
  return tone==='bad'?'bad':tone==='warn'?'warn':tone==='live'?'':'neutral';
}
