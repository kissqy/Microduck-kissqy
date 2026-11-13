import {actionSlots,supportsFeature} from './service-builds.js';
import {showFeedback} from './feedback.js';
import {AdvancedParameters} from './advanced-parameters.js';
import {jointExecutionProfile,jointProfileSummary} from './execution-profile.js';

const ACTIONS=actionSlots.map(row=>[row.slot,row.label]);
const ROLLER_NAMES={swizzle:'滑轮对称滑 / Swizzle',crouch:'滑轮蹲下 / Crouch',spin:'滑轮原地转 / Spin',standup:'滑轮倒地起身 / Stand up'};
// Fixed HAT service recovery and policy management share the existing job channel.
export class ServiceManagement {
  constructor(panel){
    this.panel=panel;this.cfg=panel.cfg;this.catalog=null;this.catalogError='';this.catalogRequest=null;this.loading=false;this.retryAfter=0;this.lastJob='';this.connection=null;this.connectionLoading=false;this.connectionAfter=0;this.connectionRequest=null;
    this.root=document.createElement('section');this.root.className='service-management';this.root.id='service-models';
    this.root.innerHTML=`
      <div class="management-model-actions"><div id="management-model" class="model-status-list" role="list" aria-label="内置动作模型状态"></div></div>
      <div id="management-status" class="panel-note service-job" role="status"></div>`;
    document.querySelector('#control-panel .model-management-anchor').append(this.root);
    this.advanced=new AdvancedParameters(this);
    this.hat=document.createElement('section');this.hat.className='service-hat';this.hat.id='service-hat';
    this.hat.innerHTML=`<div class="service-action-row"><button class="button" id="management-reconnect">重启固件</button><button class="button" id="management-diagnostic">导出启动诊断</button><span id="management-connection" class="tiny muted">等待反馈</span></div><p id="management-health" class="tiny muted"></p><div id="management-hat-status" class="panel-note service-job" role="status"></div>`;
    panel.$('service-mode-switch').querySelector('.service-mode-body').append(this.hat);
    this.$=id=>document.getElementById('management-'+id);
    this.$('reconnect').onclick=()=>this.recover('reconnect-service');
    this.$('diagnostic').onclick=()=>this.diagnose();
  }
  invalidate(){
    // A response started before an install/reconnect belongs to the old service.
    this.catalogRequest?.abort();this.catalogRequest=null;this.loading=false;
    this.catalog=null;this.catalogError='';this.retryAfter=0;
    this.connectionRequest?.abort();this.connectionRequest=null;this.connectionLoading=false;
    this.connection=null;this.connectionAfter=0;
  }
  async refresh(silent=false){
    if(this.loading||!this.supported)return;
    const request=new AbortController();this.catalogRequest=request;
    const timer=setTimeout(()=>request.abort(new DOMException('配置读取超时','TimeoutError')),25000);
    this.loading=true;this.catalogError='';this.paint();
    if(!silent)showFeedback(this.$('status'),'正在读取模型列表…','running');
    try{
      const response=await fetch('/api/service/models',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},body:'{}',signal:request.signal});
      const data=await response.json();if(!response.ok)throw Error(data.error||'模型列表读取失败');
      if(this.catalogRequest!==request)return;
      if(!Array.isArray(data?.models))throw Error(data?.error||data?.message||'模型及高级参数回执不完整');
      const models=ACTIONS.map(([slot,label])=>{
        const info=data.slots?.find(row=>row.slot===slot),current=info?.model||data.models.find(row=>row.slot===slot&&row.active),stored=data.models.find(row=>row.slot===slot&&row.available);
        const item=document.createElement('span');item.className='model-slot'+(current?' configured':' empty');item.setAttribute('role','listitem');
        const name=document.createElement('strong');name.textContent=label;
        const status=document.createElement('span');status.className='model-slot-name';status.textContent=current?current.name:stored?'已存入，尚未绑定':'未配置';
        const profile=jointExecutionProfile(current);
        item.title=`${label} · ${slot} · ${current?current.name+' · '+current.sha256:stored?'已存入 '+stored.name+'，尚未绑定':'尚未安装配套模型'}${profile?' · '+jointProfileSummary(profile):''}`;
        item.append(name,status);return item;
      });
      const rollers=(data.roller_models||[]).map(row=>{
        const item=document.createElement('span');item.className='model-slot'+(row.available?' configured':' empty');item.setAttribute('role','listitem');
        const name=document.createElement('strong');name.textContent=ROLLER_NAMES[row.id]||row.name;
        const status=document.createElement('span');status.className='model-slot-name';
        status.textContent=row.name+' · '+(row.available?(row.trigger_bound===false?'已安装 · 未绑定触发':'已安装 · 实体手柄切换'):'未安装');
        item.title=row.available?`${row.name} · ${row.sha256} · 缩放 ${row.action_scale} / 头部 ${row.head_lowpass} / 腿部 ${row.legs_lowpass}`:row.error||'尚未安装滑轮模型';
        item.append(name,status);return item;
      });
      this.catalog=data;this.retryAfter=0;this.$('model').replaceChildren(...models,...rollers);
      if(!silent)showFeedback(this.$('status'),`模型列表已刷新 · ${data.models.length+(data.roller_models||[]).length} 项`,'completed');
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
  async diagnose(){
    if(this.recoveryBlocked||this.diagnosticBusy)return;
    this.diagnosticBusy=true;this.paint();
    showFeedback(this.$('hat-status'),'正在收集本次与上次启动、UART 和网络日志…','running');
    const password=this.panel.$('service-sudo-password').value;
    this.panel.$('service-sudo-password').value='';
    try{
      const response=await fetch('/api/service/diagnostic',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},
        body:JSON.stringify(password?{sudo_password:password}:{}),signal:AbortSignal.timeout(90000)});
      const data=await response.json();if(!response.ok||!data.diagnostic)throw Error(data.error||'未取得启动诊断');
      const url=URL.createObjectURL(new Blob([JSON.stringify(data.diagnostic,null,2)],{type:'application/json'}));
      const link=document.createElement('a');link.href=url;link.download='Microduck-startup-diagnostic-'+new Date().toISOString().replace(/[:.]/g,'-')+'.json';
      document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
      showFeedback(this.$('hat-status'),data.message,'completed');
    }catch(error){showFeedback(this.$('hat-status'),error.message,'error');}
    finally{this.diagnosticBusy=false;this.paint();}
  }
  async recover(action){
    if(this.recoveryBlocked)return;
    await this.command({action,supported:true});
  }
  async refreshConnection(){
    if(this.connectionLoading)return;
    const request=new AbortController();this.connectionRequest=request;
    const timer=setTimeout(()=>request.abort(),15000);
    this.connectionLoading=true;this.connectionAfter=Date.now()+5000;
    try{
      const response=await fetch('/api/service/connection',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},body:'{}',signal:request.signal});
      const data=await response.json();
      if(this.connectionRequest!==request)return;
      if(!response.ok||!data.management_revision)throw Error('当前服务未提供进程核对信息。');
      this.connection=data;this.connectionAfter=Infinity;this.connectionError='';this.supported ||= data.management_revision==='R17';
      if(this.supported&&!this.catalog&&!this.loading&&!this.recoveryBlocked)this.refresh(true);
    }catch(error){if(this.connectionRequest!==request)return;this.connection=null;this.connectionError=error.message;this.connectionAfter=Date.now()+15000;}
    finally{clearTimeout(timer);if(this.connectionRequest===request){this.connectionRequest=null;this.connectionLoading=false;this.paint();}}
  }
  render(snapshot,options){
    this.s=snapshot;this.options=options;this.supported=supportsFeature(snapshot.bus,'management')||this.connection?.management_revision==='R17';
    const identity=snapshot.bus?.build&&snapshot.bus?.mode?`${snapshot.bus.build}/${snapshot.bus.mode}`:null;
    if(identity&&identity!==this.lastIdentity){if(this.lastIdentity)this.invalidate();this.lastIdentity=identity;}
    const job=snapshot.service_control?.job;
    const key=job?`${job.at}:${job.status}`:'';
    if(key!==this.lastJob){
      this.lastJob=key;
      if(['switch-mode','reconnect-service','upgrade-service','set-action-scale','resume-connection'].includes(job?.action)){
        this.invalidate();
      }
    }
    const coreReady=[1,2,3,4].every(n=>snapshot.startup?.steps?.[n]?.status==='success');
    if(coreReady&&Date.now()>this.retryAfter&&this.supported&&!this.catalog&&!this.loading&&!snapshot.service_control?.busy&&!snapshot.service_control?.stopping&&!options.replay&&!options.offline)this.refresh(true);
    if(coreReady&&Date.now()>this.connectionAfter&&!snapshot.service_control?.busy&&!snapshot.service_control?.stopping&&!options.replay&&!options.offline)this.refreshConnection();
    this.paint();
  }
  paint(){
    const s=this.s||{},job=s.service_control||{},options=this.options||{};
    this.blocked=!this.supported||!s.service_sample_fresh||job.busy||job.stopping||this.loading||this.panel.posting||options.replay||options.offline;
    this.recoveryBlocked=job.busy||job.stopping||this.panel.posting||options.replay||options.offline;
    const c=this.connection,problem=s.bus?.error||s.bus?.last_cycle_error;
    const mismatch=c&&(c.process_matches!==true||c.actual_port!=='/dev/ttyS2');
    this.$('connection').textContent=`HAT · /dev/ttyS2 · ${mismatch?'进程待恢复':s.service_sample_fresh?'已连接':'等待总线'}`;
    this.$('connection').classList.toggle('connection-error',!!(mismatch||problem));
    this.$('health').textContent=job.busy?'正在执行服务操作…':c&&c.management_revision!=='R17'?`当前服务 ${c.management_revision}；请在“09 固件与电源”中升级统一版本。`:mismatch?`实际进程${c.running?'使用 '+(c.actual_port||'未知串口'):'未运行'}；点击“重启固件”。`:problem?'R17 服务报告异常，详情见“逐设备通信”及服务操作回执。':c?`服务 R17 · HD1910 自训配置 · PID ${c.pid} · ${s.service_sample_fresh?'正在采集':'等待设备反馈'}`:this.connectionError||'正在读取服务状态…';
    this.$('health').classList.toggle('connection-error',!!(mismatch||problem));
    for(const el of this.root.querySelectorAll('button,input'))el.disabled=!!this.blocked;
    this.advanced.paint(s,options);
    this.$('reconnect').disabled=!!this.recoveryBlocked;
    this.$('diagnostic').disabled=!!this.recoveryBlocked||!!this.diagnosticBusy;
  }
}
