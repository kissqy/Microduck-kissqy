import {actionSlots,supportsFeature} from './service-builds.js';
import {showFeedback} from './feedback.js';
import {AdvancedParameters} from './advanced-parameters.js';
import {jointExecutionProfile,jointProfileSummary} from './execution-profile.js';

const ACTIONS=actionSlots.map(row=>[row.slot,row.label]);
function recoveryText(catalog){
  const recovery=catalog?.manual_recovery,model=recovery?.model;
  if(!recovery)return 'LB 起身：未绑定';
  return `LB 起身：${model?.name||recovery.path} · ${model?.id||''} · 基础系数 ${Number(recovery.action_scale).toFixed(2)} · ${model?.available?'已绑定（按 LB 运行）':`不可用：${model?.error||'模型文件缺失'}`}`;
}

// Fixed HAT service recovery and policy management share the existing job channel.
export class ServiceManagement {
  constructor(panel){
    this.panel=panel;this.cfg=panel.cfg;this.catalog=null;this.catalogError='';this.catalogRequest=null;this.loading=false;this.uploading=false;this.retryAfter=0;this.lastJob='';this.connection=null;this.connectionLoading=false;this.connectionAfter=0;this.selectedSlot='walk';
    this.root=document.createElement('section');this.root.className='service-management';this.root.id='service-models';
    this.root.innerHTML=`
      <div class="management-model-actions"><div id="management-model" class="model-buttons" role="group" aria-label="官方动作模型"></div><button class="button accent" id="management-import">导入模型</button><input id="management-file" type="file" accept=".zip" aria-label="导入所选动作模型 ZIP" hidden></div><span id="management-target" class="tiny muted" role="status"></span><div id="management-recovery" class="tiny muted" role="status"></div>
      <div id="management-status" class="panel-note service-job" role="status"></div>`;
    document.querySelector('#control-panel .model-management-anchor').append(this.root);
    this.advanced=new AdvancedParameters(this);
    this.hat=document.createElement('section');this.hat.className='service-hat';this.hat.id='service-hat';
    this.hat.innerHTML=`<div class="service-action-row"><button class="button" id="management-reconnect">重启固件</button><span id="management-connection" class="tiny muted">等待反馈</span></div><p id="management-health" class="tiny muted"></p><div id="management-hat-status" class="panel-note service-job" role="status"></div>`;
    panel.$('service-mode-switch').querySelector('.service-mode-body').append(this.hat);
    this.$=id=>document.getElementById('management-'+id);
    this.$('reconnect').onclick=()=>this.recover('reconnect-service');
    this.$('import').onclick=()=>{if(!this.importBlocked)this.$('file').click();};
    this.$('file').onchange=()=>this.upload();
    this.$('model').onclick=e=>{const b=e.target.closest('[data-slot]');if(b&&!b.disabled){this.selectedSlot=b.dataset.slot;this.$('file').value='';this.paint();}};
  }
  invalidate(){
    // A response started before an install/reconnect belongs to the old service.
    this.catalogRequest?.abort();this.catalogRequest=null;this.loading=false;
    this.catalog=null;this.catalogError='';this.retryAfter=0;
    this.connection=null;this.connectionAfter=0;
  }
  async refresh(silent=false){
    if(this.loading||this.uploading||!this.supported)return;
    const request=new AbortController();this.catalogRequest=request;
    const timer=setTimeout(()=>request.abort(new DOMException('配置读取超时','TimeoutError')),25000);
    this.loading=true;this.catalogError='';this.paint();
    if(!silent)showFeedback(this.$('status'),'正在读取模型列表…','running');
    try{
      const response=await fetch('/api/service/models',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},body:'{}',signal:request.signal});
      const data=await response.json();if(!response.ok)throw Error(data.error||'模型列表读取失败');
      if(this.catalogRequest!==request)return;
      if(!Array.isArray(data?.models))throw Error(data?.error||data?.message||'模型及高级参数回执不完整');
      const buttons=ACTIONS.map(([slot,label])=>{
        const info=data.slots?.find(row=>row.slot===slot),current=info?.model||data.models.find(row=>row.slot===slot&&row.active),stored=data.models.find(row=>row.slot===slot&&row.available);
        const button=document.createElement('button');button.className='button action-slot'+(current?' configured':' empty');button.dataset.slot=slot;
        button.textContent=label;button.title=`${label} · ${slot} · ${current?current.name+' · '+current.sha256:slot==='stand'?'自动 Stand 未绑定':stored?'已存入 '+stored.name+'，尚未绑定':info?.import_supported===false?info.support_message:'未配置模型；可以选择后导入'}${slot==='stand'?'；'+recoveryText(data):''}`;
        return button;
      });
      this.catalog=data;this.retryAfter=0;this.$('model').replaceChildren(...buttons);
      if(!silent)showFeedback(this.$('status'),`模型列表已刷新 · ${data.models.length} 项`,'completed');
    }catch(error){
      if(this.catalogRequest!==request)return;
      this.catalog=null;this.catalogError=error.message;this.retryAfter=Date.now()+30000;
      showFeedback(this.$('status'),error.message,'error');
    }finally{
      clearTimeout(timer);
      if(this.catalogRequest===request){this.catalogRequest=null;this.loading=false;this.paint();}
    }
  }
  async command(command){
    const password=this.panel.$('service-sudo-password').value;
    await this.panel.post({...command,...(password?{sudo_password:password}:{})});
  }
  async recover(action){
    if(this.recoveryBlocked)return;
    await this.command({action,supported:true});
  }
  async refreshConnection(){
    if(this.connectionLoading)return;
    this.connectionLoading=true;this.connectionAfter=Date.now()+5000;
    try{
      const response=await fetch('/api/service/connection',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},body:'{}',signal:AbortSignal.timeout(15000)});
      const data=await response.json();
      if(!response.ok||!data.management_revision)throw Error('当前服务未提供进程核对信息。');
      this.connection=data;this.connectionAfter=Infinity;this.connectionError='';this.supported ||= data.management_revision==='R17';
      if(this.supported&&!this.catalog&&!this.loading&&!this.recoveryBlocked)this.refresh(true);
    }catch(error){this.connection=null;this.connectionError=error.message;this.connectionAfter=Date.now()+15000;}
    finally{this.connectionLoading=false;this.paint();}
  }
  async upload(){
    if(this.importBlocked)return;const file=this.$('file').files[0],slot=this.selectedSlot,label=ACTIONS.find(row=>row[0]===slot)?.[1];
    if(!file||!file.name.toLowerCase().endsWith('.zip'))return showFeedback(this.$('status'),'请选择训练台导出的完整 .zip 模型包。','warning');
    if(!file.size||file.size>64*1024*1024)return showFeedback(this.$('status'),'模型大小须在 1 字节到 64 MiB 之间','warning');
    if(!confirm(`将“${file.name}”导入并替换“${label}”？\n合同必须与所选动作一致；确认机身有支撑，应用会卸力、重启并确认实际模型，完成后重新 HOME。`)){this.$('file').value='';return;}
    this.uploading=true;this.paint();showFeedback(this.$('status'),`正在导入并替换 ${label}…`,'running');
    const password=this.panel.$('service-sudo-password').value;
    try{
      const headers={'Content-Type':'application/octet-stream','X-Control-Token':this.cfg.control_token,'X-Model-Name':encodeURIComponent(file.name),'X-Model-Slot':slot};
      if(password)headers['X-Sudo-Password']=encodeURIComponent(password);
      this.panel.$('service-sudo-password').value='';
      const response=await fetch('/api/service/models/upload',{method:'POST',headers,body:file,signal:AbortSignal.timeout(180000)});
      const data=await response.json();if(!response.ok)throw Error(data.error||'模型导入失败');
      showFeedback(this.$('status'),`已替换 ${label} · ${data.message||data.name||file.name}`,'completed');
      this.uploading=false;await this.refresh(true);
    }catch(error){showFeedback(this.$('status'),error.message,'error');}
    finally{this.uploading=false;this.$('file').value='';this.paint();}
  }
  render(snapshot,options){
    this.s=snapshot;this.options=options;this.supported=supportsFeature(snapshot.bus,'management')||this.connection?.management_revision==='R17';
    const identity=snapshot.bus?.build&&snapshot.bus?.mode?`${snapshot.bus.build}/${snapshot.bus.mode}`:null;
    if(identity&&identity!==this.lastIdentity){if(this.lastIdentity)this.invalidate();this.lastIdentity=identity;}
    const job=snapshot.service_control?.job;
    const key=job?`${job.at}:${job.status}`:'';
    if(key!==this.lastJob){
      this.lastJob=key;
      if(['switch-mode','reconnect-service','upgrade-service','set-action-scale','import-model','resume-connection'].includes(job?.action)){
        this.invalidate();
      }
    }
    if(Date.now()>this.retryAfter&&this.supported&&!this.catalog&&!this.loading&&!this.uploading&&!snapshot.service_control?.busy&&!snapshot.service_control?.stopping&&!options.replay&&!options.paused&&!options.offline)this.refresh(true);
    if(Date.now()>this.connectionAfter&&!snapshot.service_control?.busy&&!snapshot.service_control?.stopping&&!options.replay&&!options.paused&&!options.offline)this.refreshConnection();
    this.paint();
  }
  paint(){
    const s=this.s||{},job=s.service_control||{},options=this.options||{};
    this.blocked=!this.supported||!s.service_sample_fresh||job.busy||job.stopping||this.loading||this.uploading||this.panel.posting||options.replay||options.paused||options.offline;
    this.recoveryBlocked=job.busy||job.stopping||this.uploading||this.panel.posting||options.replay||options.paused||options.offline;
    const c=this.connection,problem=s.bus?.error||s.bus?.last_cycle_error;
    const mismatch=c&&(c.process_matches!==true||c.actual_port!=='/dev/ttyS2');
    this.$('connection').textContent=`HAT · /dev/ttyS2 · ${mismatch?'进程待恢复':s.service_sample_fresh?'已连接':'等待总线'}`;
    this.$('connection').classList.toggle('connection-error',!!(mismatch||problem));
    this.$('health').textContent=job.busy?'正在执行服务操作…':c&&c.management_revision!=='R17'?`当前服务 ${c.management_revision}；请在“09 固件与电源”中升级统一版本。`:mismatch?`实际进程${c.running?'使用 '+(c.actual_port||'未知串口'):'未运行'}；点击“重启固件”。`:problem?'R17 服务报告异常，详情见“逐设备通信”及服务操作回执。':c?`服务 R17 · HD1910 自训配置 · PID ${c.pid} · ${s.service_sample_fresh?'正在采集':'等待设备反馈'}`:this.connectionError||'正在读取服务状态…';
    this.$('health').classList.toggle('connection-error',!!(mismatch||problem));
    for(const el of this.root.querySelectorAll('button,input'))el.disabled=!!this.blocked;
    for(const button of this.$('model').querySelectorAll('[data-slot]')){
      button.classList.toggle('selected',button.dataset.slot===this.selectedSlot);button.setAttribute('aria-pressed',String(button.dataset.slot===this.selectedSlot));button.disabled=!!this.recoveryBlocked||this.loading;
    }
    const slotInfo=this.catalog?.slots?.find(row=>row.slot===this.selectedSlot),current=slotInfo?.model||this.catalog?.models.find(row=>row.active&&row.slot===this.selectedSlot);
    const selectedLabel=ACTIONS.find(row=>row[0]===this.selectedSlot)?.[1];
    this.importBlocked=!!(this.recoveryBlocked||this.loading||!this.supported||!this.catalog||slotInfo?.import_supported===false);
    this.$('import').disabled=this.importBlocked;this.$('file').disabled=this.importBlocked;
    this.$('import').title=slotInfo?.import_supported===false?slotInfo.support_message:`导入并替换 ${selectedLabel}`;
    const stored=this.catalog?.models.find(row=>row.slot===this.selectedSlot&&row.available);
    const executionProfile=jointExecutionProfile(current);
    this.$('target').textContent=`已选：${selectedLabel} · ${current?'当前模型 '+current.name:this.selectedSlot==='stand'?'自动 Stand 未绑定':stored?'已存入 '+stored.name+'，尚未绑定':slotInfo?.import_supported===false?slotInfo.support_message:'未配置，可导入'}${this.selectedSlot==='stand'?'；导入替换自动 Stand 槽，LB 命名技能绑定见下方':''}${executionProfile?'；联合模型统一输出参数：'+jointProfileSummary(executionProfile)+'。实际倍率与滤波见机器人回读。':''}`;
    this.$('recovery').textContent=this.catalog?recoveryText(this.catalog):this.catalogError?'LB 起身：列表读取失败':'LB 起身：等待读取';
    this.advanced.paint(s,options);
    this.$('reconnect').disabled=!!this.recoveryBlocked||c?.management_revision!=='R17';
  }
}
