import {showFeedback} from './feedback.js';

export class FirmwarePanel {
  constructor(panel){
    this.panel=panel;this.cfg=panel.cfg;this.info=null;this.prepared=null;this.loading=false;this.localLoading=false;this.source='bundled';
    this.root=document.createElement('section');this.root.className='panel firmware-card';this.root.id='service-firmware';
    this.root.innerHTML=`<div class="panel-head"><div><span class="section-index">09</span><h2>系统维护</h2></div><span class="badge neutral">R17 · 官方 0.15.1</span></div>
      <div class="firmware-body"><p id="firmware-runtime" class="tiny muted">实际运行版本：等待机器人回读</p>
      <div class="firmware-toolbar"><button class="button" id="firmware-bundled">随包固件 · control.18</button>
      <div class="firmware-upload"><input id="firmware-file" type="file" accept=".zip" aria-label="本地固件 ZIP" hidden><button class="button" id="firmware-choose">选择 ZIP 文件</button><span id="firmware-filename" class="tiny muted">尚未选择文件</span></div><div class="service-action-row firmware-install-actions"><button class="button accent" id="firmware-flash" disabled>升级所选固件</button></div></div>
      <p class="tiny muted">升级保留本机标定、已导入模型及参数；首次安装使用随包四个自训模型。安装后不自动回 HOME 或启动策略。</p>
      <p id="firmware-verification" class="tiny muted" role="status">正在校验随包固件…</p>
      <div id="firmware-status" class="panel-note service-job" role="status" aria-live="polite"></div>
      <div class="firmware-power"></div></div>`;
    document.getElementById('diagnostics').append(this.root);this.$=id=>document.getElementById('firmware-'+id);
    const old=panel.$('service-power-actions').closest('.service-power'),power=this.root.querySelector('.firmware-power');
    this.root.querySelector('#firmware-flash').parentElement.append(panel.$('management-reconnect'));
    power.append(panel.$('service-hat'),panel.$('service-power-actions'),panel.$('service-power-state'),panel.$('service-power-job'));old.remove();
    this.$('bundled').onclick=()=>{this.source='bundled';this.paint();};this.$('file').onchange=()=>this.prepare();
    this.$('choose').onclick=()=>this.$('file').click();
    this.$('flash').onclick=()=>this.flash();
    this.root.querySelector('.firmware-body').append(document.getElementById('maintenance-events'));
    this.verify();
  }
  async verify(){
    this.loading=true;this.paint();
    try{
      const response=await fetch('/api/service/firmware',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},body:'{}',signal:AbortSignal.timeout(15000)});
      const data=await response.json();if(!response.ok||!data.verified)throw Error(data.error||'固件校验未通过');this.info=data;this.error='';
    }catch(e){this.error=e.message;}finally{this.loading=false;this.paint();}
  }
  async prepare(){
    const file=this.$('file').files[0];this.prepared=null;this.$('filename').textContent=file?.name||'尚未选择文件';if(!file){this.paint();return;}
    this.source='local';
    if(!file.name.toLowerCase().endsWith('.zip')||!file.size||file.size>64*1024*1024){this.error='请选择不超过 64 MiB 的本版固件 ZIP';this.paint();return;}
    this.localLoading=true;this.error='';this.paint();
    try{
      const response=await fetch('/api/service/firmware/upload',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Control-Token':this.cfg.control_token,'X-Firmware-Name':encodeURIComponent(file.name),'X-Firmware-Client':this.panel.client},body:file,signal:AbortSignal.timeout(90000)});
      const data=await response.json();if(!response.ok||!data.verified)throw Error(data.error||'本地固件校验失败');this.prepared=data;
    }catch(e){this.error=e.message;}finally{this.localLoading=false;this.paint();}
  }
  flash(){
    if(this.$('flash').disabled)return;
    const selected=this.source==='local'?this.prepared:null;
    this.panel.post({action:'upgrade-service',supported:true,firmware:selected?.token||'bundled'});
  }
  render(s,options){
    this.s=s;this.options=options;this.paint();
    const job=s.service_control?.job;if(job?.action!=='upgrade-service')return;
    const input=job.result?.input,note=input?.status==='recovering'?'手柄正在恢复。':input?.status==='error'?'手柄暂不可用，页面继续恢复连接。':'';
    showFeedback(this.$('status'),job.status==='completed'?'固件安装已完成。'+note+'运行状态见实时反馈。':job.status==='error'?'升级未完成，实际安装阶段与错误见系统日志。':'正在升级，完整输出实时显示在系统日志中…',job.status);
  }
  paint(){
    const s=this.s||{},o=this.options||{},local=this.source==='local',selected=local?this.prepared:this.info;
    const blocked=!!(s.service_control?.busy||this.panel.posting||this.loading||this.localLoading);
    this.$('bundled').disabled=blocked;this.$('bundled').classList.toggle('selected',!local);this.$('bundled').setAttribute('aria-pressed',String(!local));this.$('file').disabled=blocked;this.$('choose').disabled=blocked;this.$('flash').disabled=blocked||!selected?.verified;
    const message=this.localLoading?'正在校验本地 ZIP…':this.loading?'正在校验随包固件…':this.error||(selected?.verified?`已通过 SHA256 校验 · ${selected.sha256.slice(0,16)}…`:'请选择本版配套固件 ZIP');
    this.$('verification').textContent=message;this.$('verification').title=selected?.sha256||'';
    this.$('runtime').textContent=`实际运行版本：${s.bus?.build||'等待机器人回读'}${s.bus?.build&&!s.service_sample_fresh?' · 当前反馈未就绪':''}`;
  }
}
