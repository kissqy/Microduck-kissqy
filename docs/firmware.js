import {showFeedback} from './feedback.js?v=v260-20261113';
import {formatError} from './messages.js?v=v260-20261113';

const HOTSPOT_HELP='连接热点 Microduck-kissqy（密码 12345678），在浏览器打开 http://10.42.0.1:8088，重新配置 Wi-Fi。配网时需设置 Zero 登录密码；联网后查找鸭子的新 IP，在中控填写新 IP 和该密码后重新连接。';

export class FirmwarePanel {
  constructor(panel){
    this.panel=panel;this.cfg=panel.cfg;this.info=null;this.prepared=null;this.loading=false;this.localLoading=false;this.source='bundled';this.bundleError='';
    this.root=document.createElement('section');this.root.className='panel firmware-card';this.root.id='service-firmware';
    this.root.innerHTML=`<div class="panel-head"><div><span class="section-index">09</span><h2>系统维护</h2></div><span class="badge neutral">R17 · 官方 0.15.1</span></div>
      <div class="firmware-body"><p id="firmware-runtime" class="tiny muted">实际运行版本：等待机器人回读</p>
      <div class="firmware-toolbar"><button class="button" id="firmware-bundled">随包固件 · 正在核验</button>
      <div class="firmware-upload"><input id="firmware-file" type="file" accept=".zip" aria-label="本地固件 ZIP" hidden><button class="button" id="firmware-choose">选择 ZIP 文件</button><span id="firmware-filename" class="tiny muted">尚未选择文件</span></div><div class="service-action-row firmware-install-actions"><button class="button accent" id="firmware-flash" disabled>升级所选固件</button></div></div>
      <p class="tiny muted">每次安装均恢复随包模型及动作配置，并清理非随包旧模型；保留本机标定。安装后不自动回 HOME 或启动策略。</p>
      <p id="firmware-verification" class="tiny muted" role="status">正在校验随包固件…</p>
      <div id="firmware-status" class="panel-note service-job" role="status" aria-live="polite"></div>
      <div id="firmware-transfer" hidden><progress id="firmware-progress" max="100" value="0" aria-label="固件上传进度"></progress><p id="firmware-progress-text" class="tiny muted" role="status"></p></div>
      <div class="firmware-power"><button class="button hotspot-action" id="firmware-hotspot" disabled>开启热点</button><div id="firmware-hotspot-status" class="panel-note service-job" role="status" aria-live="polite"></div><p id="firmware-hotspot-help" class="tiny muted" hidden></p></div></div>`;
    document.getElementById('diagnostics').append(this.root);this.$=id=>document.getElementById('firmware-'+id);
    const old=panel.$('service-power-actions').closest('.service-power'),power=this.root.querySelector('.firmware-power');
    this.root.querySelector('#firmware-flash').parentElement.append(panel.$('management-reconnect'));
    panel.$('service-resume').after(this.$('hotspot'));
    power.append(panel.$('service-hat'),panel.$('service-power-actions'),this.$('hotspot-status'),this.$('hotspot-help'),panel.$('service-power-state'),panel.$('service-power-job'));old.remove();
    this.$('bundled').onclick=()=>{this.source='bundled';this.paint();};this.$('file').onchange=()=>this.prepare();
    this.$('choose').onclick=()=>this.$('file').click();
    this.$('flash').onclick=()=>this.flash();
    this.$('hotspot').onclick=()=>this.enableHotspot();
    this.root.querySelector('.firmware-body').append(document.getElementById('maintenance-events'));
    this.verify();
  }
  async verify(){
    this.info=null;this.bundleError='';this.loading=true;this.paint();
    try{
      const response=await fetch('/api/service/firmware',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},body:'{}',signal:AbortSignal.timeout(15000)});
      const data=await response.json();if(!response.ok||!data.verified)throw Error(data.error||'固件校验未通过');
      if(typeof data.build!=='string'||!data.build.trim())throw Error('固件未返回构建版本');this.info=data;this.error='';
    }catch(e){this.bundleError=this.error=e.message;}finally{this.loading=false;this.paint();}
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
  async enableHotspot(){
    this.paint();
    if(this.$('hotspot').disabled)return;
    if(!confirm('请先停止动作并放稳机器人。\n\n开启热点会清除已保存的 Wi‑Fi 连接信息（保留配网热点），并断开当前网络和中控连接，需要重新联网。\n\n'+HOTSPOT_HELP+'\n\n确认清除 Wi‑Fi 连接信息并开启热点？'))return;
    this.paint();
    if(this.$('hotspot').disabled)return;
    this.hotspotBaselineJobAt=this.s?.service_control?.job?.at;
    this.hotspotRequested=true;this.hotspotPending=true;this.hotspotQueued=false;this.hotspotSawDisconnect=false;this.hotspotReconnected=false;
    showFeedback(this.$('hotspot-status'),'正在提交热点切换请求…','running');
    this.$('hotspot-help').hidden=false;this.$('hotspot-help').textContent=HOTSPOT_HELP;
    // post checks the current button state synchronously; disable after that
    // check, so a pending local request cannot accidentally reject itself.
    const pending=this.panel.post({action:'enable-hotspot',supported:true,confirmed:true});
    this.paint();
    const receipt=await pending;
    this.hotspotPending=false;
    if(receipt?.accepted){
      this.hotspotSubmitted=true;
      this.hotspotQueued ||= receipt.queued===true||receipt.hotspot?.queued===true;
      showFeedback(this.$('hotspot-status'),'请求已提交，正在核对并调度热点切换；尚未确认热点已开启。网络切换后中控会断开，请按下方步骤重新联网。','running');
    }else if(receipt?.uncertain){
      showFeedback(this.$('hotspot-status'),'提交结果未确认：'+receipt.error+'。网络可能已切换，请先检查热点是否出现；不会自动重试。','warning');
    }else{
      showFeedback(this.$('hotspot-status'),'热点请求未提交'+(receipt?.error?'：'+receipt.error:'；当前状态已变化，请检查连接后重试。'),'error');
    }
    this.renderHotspot(this.s?.service_control?.job);
    this.observeHotspotConnection();
    this.paint();
  }
  observeHotspotConnection(){
    const s=this.s||{},o=this.options||{};
    if(!this.hotspotRequested||o.replay)return;
    if(s.connection_paused===true||s.connection?.active===false||s.connection?.connected===false)this.hotspotSawDisconnect=true;
    const connected=s.connection?.active===true&&s.connection?.connected===true&&!s.connection_paused&&!o.offline;
    if(this.hotspotQueued&&this.hotspotSubmitted&&!this.hotspotPending&&this.hotspotSawDisconnect&&connected){
      // A reconnect only rearms the button. It never resubmits a network reset.
      this.hotspotSubmitted=false;this.hotspotRequested=false;this.hotspotReconnected=true;
      this.hotspotReleasedJobAt=s.service_control?.job?.at;
      showFeedback(this.$('hotspot-status'),'Zero 已重新连接；需要再次配网时可点击“开启热点”。','info');
    }
  }
  renderHotspot(job){
    if(job?.action!=='enable-hotspot')return;
    if(this.hotspotRequested&&job.at===this.hotspotBaselineJobAt)return;
    if(this.hotspotReconnected&&!this.hotspotRequested&&job.at===this.hotspotReleasedJobAt)return;
    const queued=job.result?.queued===true||job.result?.hotspot?.queued===true;
    const previous=this.hotspotRequested?'':'上次请求：';
    if(this.hotspotRequested){this.hotspotSubmitted=job.status!=='error';if(queued)this.hotspotQueued=true;}
    const message=job.status==='error'?previous+'热点切换未完成：'+(job.error||'请查看实际错误'):
      job.status==='completed'?(queued?previous+'热点切换任务已调度；等待网络切换，尚未确认热点已开启。':previous+'未收到热点切换调度回执；请先检查热点和网络状态。'):
      previous+(job.message||'正在核对并调度热点切换…');
    showFeedback(this.$('hotspot-status'),message,job.status==='error'?'error':job.status==='completed'?'warning':'running');
    this.$('hotspot-help').hidden=false;this.$('hotspot-help').textContent=HOTSPOT_HELP;
  }
  render(s,options){
    this.s=s;this.options=options;this.renderHotspot(s.service_control?.job);this.observeHotspotConnection();this.paint();
    const job=s.service_control?.job;if(job?.action!=='upgrade-service'){this.$('transfer').hidden=true;return;}
    const input=job.result?.input,note=input?.status==='recovering'?'手柄正在恢复。':input?.status==='error'?'手柄恢复失败，请手动重新连接。':'';
    const p=job.transfer_progress;
    this.$('transfer').hidden=!p||!Number.isFinite(p.percent);
    if(p&&Number.isFinite(p.percent)){
      this.$('progress').value=p.percent;
      this.$('progress-text').textContent=`${p.step} · ${p.percent}% · ${(p.bytes/1048576).toFixed(1)} / ${(p.total/1048576).toFixed(1)} MiB · ${p.detail}`;
    }
    showFeedback(this.$('status'),job.status==='completed'?'固件安装已完成。'+note+'运行状态见实时反馈。':job.status==='error'?`升级未完成 · ${job.error||'实际错误见系统日志'}`:job.message||'正在准备固件安装…',job.status);
  }
  paint(){
    const s=this.s||{},o=this.options||{},local=this.source==='local',selected=local?this.prepared:this.info;
    const blocked=!!(s.service_control?.busy||this.panel.posting||this.loading||this.localLoading);
    this.$('hotspot').disabled=!this.cfg.service_enabled||s.connection?.active!==true||s.connection?.connected!==true||!!(o.replay||o.offline||s.connection_paused||s.service_control?.busy||s.service_control?.stopping||s.service_operation||this.panel.posting||this.hotspotPending||this.hotspotSubmitted);
    this.$('hotspot').textContent=this.hotspotPending?'正在提交…':this.hotspotSubmitted?'热点切换已提交':'开启热点';
    const bundledBuild=this.info?.build?.match(/control\.(\d+(?:\.\d+)?)$/)?.[1];
    const bundledLabel=this.info?`V${this.info.console_version.replace(/^1\.0\./,'')}_control.V${bundledBuild}`:'';
    this.$('bundled').textContent=this.loading?'随包固件 · 正在核验':this.bundleError?'随包固件 · 未知（核验失败）':this.info?.verified?`随包固件 · ${bundledLabel}`:'随包固件 · 未核验';
    this.$('bundled').disabled=blocked;this.$('bundled').classList.toggle('selected',!local);this.$('bundled').setAttribute('aria-pressed',String(!local));this.$('file').disabled=blocked;this.$('choose').disabled=blocked;this.$('flash').disabled=blocked||!selected?.verified;
    const message=this.localLoading?'正在校验本地 ZIP…':this.loading?'正在校验随包固件…':this.error||(selected?.verified?`已通过 SHA256 校验 · ${selected.sha256.slice(0,16)}…`:'请选择本版配套固件 ZIP');
    this.$('verification').textContent=this.error?formatError(message):message;this.$('verification').title=selected?.sha256||'';
    this.$('runtime').textContent=`实际运行版本：${s.bus?.build||'等待机器人回读'}${s.bus?.build&&!s.service_sample_fresh?' · 当前反馈未就绪':''}`;
  }
}
