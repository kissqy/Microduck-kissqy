import {formatError} from './messages.js?v=v260-20261113';

/** Manual Zero-side Wi-Fi management over the existing authenticated SSH link. */
export class WifiPanel {
  constructor(cfg) {
    this.cfg=cfg;
    this.$=id=>document.getElementById(id);
    this.available=false;this.busy=false;this.networks=[];this.epoch=0;
    this.savedCount=0;this.pendingJob=null;this.timer=null;this.ipv4Addresses=[];this.replaying=false;
    this.$('wifi-scan').onclick=()=>this.scan();
    this.$('wifi-networks').onchange=()=>{this.$('wifi-password').value='';this.paint();};
    this.$('wifi-connect').onclick=()=>this.connect();
    this.$('wifi-forget').onclick=()=>this.forget();
    this.paint();
  }
  selected() {return this.networks[Number(this.$('wifi-networks').value)]||null;}
  say(message) {this.$('wifi-feedback').textContent=message;}
  stopJobPoll() {clearTimeout(this.timer);this.timer=null;}
  readAddresses(result) {
    this.ipv4Addresses=[...new Set((Array.isArray(result.ipv4_addresses)?result.ipv4_addresses:[])
      .filter(address=>typeof address==='string'&&/^\d{1,3}(?:\.\d{1,3}){3}$/.test(address)&&
        address.split('.').every(octet=>Number(octet)<=255)))];
  }
  paintCurrent() {
    const current=this.$('wifi-current');
    if(this.available) {
      const address=this.ipv4Addresses.length?`IP：${this.ipv4Addresses.join(' / ')}`:'IP 待回读';
      current.textContent=address;
      current.title=[this.connectedSsid?`Wi-Fi：${this.connectedSsid}`:'',address].filter(Boolean).join(' · ');
    }else {
      current.textContent=this.replaying?'历史回放':this.cfg.service_enabled?'等待 Zero 连接':'当前模式不提供 Wi-Fi 操作';
      current.title=current.textContent;
    }
  }
  invalidate() {
    this.epoch++;this.stopJobPoll();this.available=false;this.busy=false;
    this.pendingJob=null;this.pendingAction=null;this.networks=[];this.savedCount=0;this.connectedSsid='';this.ipv4Addresses=[];
    this.$('wifi-password').value='';
    this.$('wifi-networks').replaceChildren(new Option('连接 Zero 后点击扫描',''));
    this.paintCurrent();
    this.say('先连接 Zero，再扫描周围 Wi-Fi。');this.paint();
  }
  render(snapshot,{replay=false,offline=false}={}) {
    this.replaying=replay;
    const wasAvailable=this.available;
    const available=!!this.cfg.service_enabled&&!replay&&!offline&&
      (!this.cfg.connection_ui||snapshot.connection?.connected===true);
    if(this.available&&!available) {
      this.epoch++;this.busy=false;this.stopJobPoll();this.$('wifi-password').value='';
      this.say(this.pendingJob?'Wi-Fi 操作请求已提交；SSH 已断开，尚未确认操作结果。地址变化后请在右侧填写新 IP 重连。':
        replay?'历史回放中不能操作 Wi-Fi。':'SSH 尚未连接，请先在右侧连接 Zero。');
      // A short disconnect can recover without an explicit SSH form submit.
      // Do not leave the old job permanently locking all controls in that case.
      this.pendingJob=null;this.pendingAction=null;this.ipv4Addresses=[];this.connectedSsid='';
    }
    this.available=available;
    this.paintCurrent();
    this.paint();
    // One cached status read per authenticated SSH connection, never a rescan
    // or a timer. Explicit scan and pending network jobs keep their own flow.
    if(available&&!wasAvailable&&!this.busy&&!this.pendingJob)this.statusRead=this.readStatus(this.epoch);
  }
  paint() {
    const selected=this.selected(),locked=!this.available||this.busy||!!this.pendingJob;
    this.$('wifi-scan').disabled=locked;
    this.$('wifi-scan').textContent=this.busy?'处理中…':'扫描';
    this.$('wifi-networks').disabled=locked||!this.networks.length;
    this.$('wifi-connect').disabled=locked||!selected||!!selected.connected;
    this.$('wifi-forget').disabled=locked||!selected?.saved||selected.can_forget!==true;
    const needsPassword=!!selected&&!selected.saved&&selected.security!=='OPEN'&&
      selected.security!=='--'&&selected.security!=='';
    this.$('wifi-password-field').hidden=!needsPassword;
    this.$('wifi-password').disabled=locked||!needsPassword;
    this.$('wifi-note').textContent=selected?.saved&&selected.can_forget!==true?
      '这是最后一个已保存的 Wi-Fi，不能取消保存。':'至少保留一个已保存的 Wi-Fi。';
  }
  async request(payload) {
    const response=await fetch('/api/service/wifi',{method:'POST',
      headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},
      body:JSON.stringify(payload),signal:AbortSignal.timeout(65000)});
    let result;
    try {result=await response.json();} catch {throw Error('Wi-Fi 操作未收到有效回执，请检查 SSH 连接。');}
    if(!response.ok||result.accepted!==true)throw Error(formatError(result.error||result.reason||'Wi-Fi 操作未完成'));
    return result;
  }
  applyList(result) {
    const previous=this.selected();
    this.networks=Array.isArray(result.networks)?result.networks:[];
    this.savedCount=result.saved_network_count||0;this.connectedSsid=result.connected_ssid||'';this.readAddresses(result);
    const options=this.networks.map((network,index)=>{
      const flags=[network.connected?'已连接':network.saved?'已保存':'',
        network.in_range===false?'不在扫描范围':Number.isFinite(network.signal)?`${network.signal}%`:'',
        network.security&&network.security!=='--'?network.security:'开放网络'].filter(Boolean);
      return new Option(`${network.ssid} · ${flags.join(' / ')}`,String(index));
    });
    this.$('wifi-networks').replaceChildren(...(options.length?options:[new Option('未找到 Wi-Fi，请稍后重新扫描','')]));
    let selected=previous?this.networks.findIndex(n=>n.uuid&&n.uuid===previous.uuid||!n.uuid&&!previous.uuid&&n.ssid===previous.ssid):-1;
    if(selected<0)selected=this.networks.findIndex(n=>n.connected);
    this.$('wifi-networks').value=String(selected<0?0:selected);
    this.$('wifi-password').value='';
    this.paintCurrent();
  }
  async readStatus(epoch) {
    if(epoch!==this.epoch||!this.available||this.busy||this.pendingJob)return;
    this.busy=true;this.say('正在读取 Zero 的 Wi-Fi 状态…');this.paint();
    try {
      const result=await this.request({action:'status'});
      if(epoch!==this.epoch)return;
      this.applyList(result);this.say('已读取 Wi-Fi 状态，点击扫描刷新周围网络。');
    }catch(error){if(epoch===this.epoch)this.say(`Wi-Fi 状态读取失败：${formatError(error.message)}`);}
    finally{if(epoch===this.epoch){this.busy=false;this.paint();}}
  }
  async scan() {
    if(!this.available||this.busy||this.pendingJob)return;
    const epoch=this.epoch;this.busy=true;this.say('正在扫描 Zero 周围的 Wi-Fi…');this.paint();
    try {
      const result=await this.request({action:'scan'});
      if(epoch!==this.epoch)return;
      this.applyList(result);this.say(this.networks.length?'选择 Wi-Fi 后点击连接。':'未扫描到 Wi-Fi，请稍后重试。');
    }catch(error){if(epoch===this.epoch)this.say(formatError(error.message));}
    finally{if(epoch===this.epoch){this.busy=false;this.paint();}}
  }
  async connect() {
    const network=this.selected();
    if(!this.available||this.busy||this.pendingJob||!network||network.connected)return;
    const epoch=this.epoch,password=this.$('wifi-password').value;
    this.$('wifi-password').value='';this.busy=true;this.say('正在提交 Wi-Fi 连接请求…');this.paint();
    try {
      const result=await this.request({action:'connect',ssid:network.ssid,uuid:network.uuid||'',
        password,request_id:crypto.randomUUID()});
      if(epoch!==this.epoch)return;
      if(result.scheduled!==true||!result.job_id)throw Error('尚未确认 Wi-Fi 连接任务已提交，请检查连接状态。');
      this.trackJob(result,'connect',epoch);
    }catch(error){if(epoch===this.epoch)this.say(formatError(error.message));}
    finally{if(epoch===this.epoch){this.busy=false;this.paint();}}
  }
  trackJob(result,action,epoch) {
    this.pendingJob=result.job_id;this.pendingAction=action;
    this.ipv4Addresses=[];this.connectedSsid='';this.paintCurrent();
    this.say(action==='forget'?'取消保存请求已提交，等待实际结果。若当前网络断开，请在右侧填写新 IP 重连。':
      '连接请求已提交，等待实际结果。切换后 IP 可能变化，请在右侧填写新 IP 重连。');
    this.timer=setTimeout(()=>this.pollJob(epoch,0),2500);
  }
  async pollJob(epoch,attempt) {
    this.timer=null;
    if(epoch!==this.epoch||!this.available||!this.pendingJob)return;
    try {
      const result=await this.request({action:'job',job_id:this.pendingJob});
      if(epoch!==this.epoch)return;
      if(['connected','forgotten'].includes(result.phase)) {
        this.pendingJob=null;this.pendingAction=null;this.connectedSsid='';
        this.readAddresses(result);this.paintCurrent();
        this.say(result.message||(result.phase==='forgotten'?'已取消保存所选 Wi-Fi。':'Wi-Fi 已连接。'));
        try {
          const current=await this.request({action:'status'});
          if(epoch===this.epoch)this.applyList(current);
        }catch(error){if(epoch===this.epoch)this.say(`${result.message||'Wi-Fi 操作已完成'}；列表刷新失败：${formatError(error.message)}`);}
      }else if(['failed','refused','error'].includes(result.phase)) {
        this.pendingJob=null;this.pendingAction=null;this.say(formatError(result.message||'Wi-Fi 操作失败，请核对网络状态。'));
      }else if(attempt<23) {
        this.timer=setTimeout(()=>this.pollJob(epoch,attempt+1),2500);
      }else {
        this.pendingJob=null;this.pendingAction=null;
        this.say('暂未收到 Wi-Fi 操作结果；请检查实际网络，点击扫描刷新。若地址变化，请填写新 IP 重连。');
      }
    }catch(error) {
      if(epoch===this.epoch){this.pendingJob=null;this.pendingAction=null;this.say(`未确认 Wi-Fi 操作结果：${formatError(error.message)}。若 IP 已变化，请在右侧重新连接。`);}
    }finally{if(epoch===this.epoch)this.paint();}
  }
  async forget() {
    const network=this.selected();
    if(!this.available||this.busy||this.pendingJob||!network?.saved||network.can_forget!==true)return;
    const epoch=this.epoch;this.busy=true;this.say('正在取消保存所选 Wi-Fi…');this.paint();
    try {
      const result=await this.request({action:'forget',uuid:network.uuid,request_id:crypto.randomUUID()});
      if(epoch!==this.epoch)return;
      if(result.scheduled===true) {
        if(!result.job_id)throw Error('尚未确认取消保存任务已提交，请检查网络状态。');
        this.trackJob(result,'forget',epoch);return;
      }
      // Re-read the saved profiles; cancellation must never infer the remaining count locally.
      if(Array.isArray(result.networks))this.applyList(result);
      else {
        const current=await this.request({action:'status'});
        if(epoch!==this.epoch)return;this.applyList(current);
      }
      this.say(result.message||'已取消保存所选 Wi-Fi。');
    }catch(error){if(epoch===this.epoch)this.say(formatError(error.message));}
    finally{if(epoch===this.epoch){this.busy=false;this.paint();}}
  }
}
