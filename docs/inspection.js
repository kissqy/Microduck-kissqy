import {showFeedback} from './feedback.js';
import {readTiming,isLateRead,acceptedLateRead,failureText} from './read-timing.js';

const finite=v=>typeof v==='number'&&Number.isFinite(v);
const fmt=(v,n=1)=>finite(v)?v.toFixed(n):'—';
const errorsOf=b=>b.errors_by_id||b.diagnostics?.missing_by_id||{};
const totalsOf=b=>{
  const t=b.native?.telemetry;
  return t&&finite(t.total_reads)&&finite(t.failed_reads)&&t.missing_by_id?t:null;
};
const deviceStatsOf=b=>b.device_communication?.by_id?b.device_communication:null;
// v107 counted deadline misses twice. Convert that documented legacy schema;
// older native totals do not contain enough evidence to split cumulative causes.
export const separatedCounts=(stats,id)=>{
  const d=stats?.by_id?.[id];if(!d)return null;
  return stats.classification==='exclusive-v2'?d:{missing:Math.max(0,d.missing-(d.timeout||0)),timeout:d.timeout};
};
const isLoop=b=>b.mode==='motion'&&finite(b.cycle);
const late=isLateRead;

// This panel only observes robot.busStatus. The manual endpoint enables a
// bounded console recording; neither path opens a bus or issues device reads.
export class DeviceInspection {
  constructor(cfg,root){
    this.cfg=cfg;this.root=root;this.manual=false;this.pending=false;this.base=null;this.cells=new Map();this.s=null;this.options={};
    this.$=id=>root.querySelector('#inspection-'+id);
    for(const [i,id] of [...cfg.ids,200].entries()){
      const cell=document.createElement('div'),number=document.createElement('b'),name=document.createElement('span'),detail=document.createElement('small');
      cell.className='inspection-device';number.textContent=id;name.textContent=id===200?'IMU':cfg.labels[i];detail.textContent='未检测';
      cell.dataset.id=id;cell.append(number,name,detail);this.$('devices').append(cell);this.cells.set(id,{cell,detail});
    }
    this.$('start').onclick=()=>this.toggle(true);this.$('stop').onclick=()=>this.toggle(false);
    window.addEventListener('pagehide',()=>{if(this.manual)this.toggle(false,true);});
  }
  async toggle(enabled,keepalive=false){
    if(this.pending||enabled&&this.$('start').disabled)return;
    const b=this.s?.bus||{};
    const base=enabled?{session:b.session,cycle:b.total_cycles,failures:b.total_communication_failures,errors:{...errorsOf(b)}}:null;
    this.pending=true;this.paint();
    try{
      const response=await fetch('/api/inspection',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},body:JSON.stringify({enabled}),keepalive});
      if(!response.ok)throw Error('检测状态未保存，请重试');
      this.manual=enabled;if(enabled){this.base=base;this.summary='';this.lastLoopFailure=null;this.autoStopKey='';}
      this.requestError='';
    }catch(error){this.requestError=error.message;}
    finally{this.pending=false;this.paint();}
  }
  render(s,options={}){this.s=s;this.options=options;this.paint();}
  paint(){
    if(!this.s)return;
    const s=this.s,b=s.bus||{},options=this.options,loop=isLoop(b);
    const displayOnly=options.replay||options.paused||options.offline;
    const live=s.channels?.bus?.status==='live'&&!options.offline;
    const counters=finite(b.total_cycles)&&finite(b.total_communication_failures);
    this.$('start').disabled=!!(loop||this.manual||this.pending||displayOnly||!live||!counters);
    this.$('stop').disabled=!this.manual||this.pending||!!displayOnly;
    const context=options.replay?'历史回放':options.paused?'显示已暂停':!live?'反馈已中断':'';
    this.$('source').textContent=loop?'运动循环 · 自动接入':this.manual?'手动检测':'手动检测 · 待启动';
    this.$('source').className='badge '+(context?'warn':loop?'inspection-auto':'neutral');
    // A mode change ends the old manual interval; never subtract counters from
    // two robotd processes. Loop observation continues without an API start.
    const stopKey=`${b.mode}:${b.session}`;
    if(this.manual&&(loop||b.session!==this.base?.session||b.total_cycles<this.base?.cycle)&&!displayOnly&&!this.pending&&this.autoStopKey!==stopKey){
      this.autoStopKey=stopKey;this.toggle(false);return;
    }
    if(loop){
      if(!this.wasLoop)this.summary='';
      const totals=totalsOf(b),session=totals?.session;
      if(this.loopCycle===undefined||b.cycle<this.loopCycle||session!==this.loopSession)this.lastLoopFailure=null;
      this.loopSession=session;
      this.loopCycle=b.cycle;
      const sync=b.native?.sync;
      const counts=totals?` · 本次服务读取 ${totals.total_reads} 轮 · 异常 ${totals.failed_reads} 轮${finite(totals.complete_but_late)?` · 收齐但超时 ${totals.complete_but_late} 轮${finite(totals.accepted_complete_but_late)?`（已接纳 ${totals.accepted_complete_but_late} 轮）`:''}`:''}`:' · 当前服务未提供累计计数';
      this.$('status').textContent=`${context||'使用现有运动循环数据'} · 第 ${b.cycle} 轮${finite(sync?.elapsed_us)?` · 本轮 ${(sync.elapsed_us/1000).toFixed(2)} ms`:''}${counts}`;
      this.paintDevices(s,{loop:true,live:live&&!options.paused});
    }else if(this.manual&&this.base&&counters&&b.session===this.base.session){
      const rounds=Math.max(0,b.total_cycles-this.base.cycle),failed=Math.max(0,b.total_communication_failures-this.base.failures);
      this.summary=`读取 ${rounds} 轮 · 成功 ${Math.max(0,rounds-failed)} 轮 · 异常 ${failed} 轮`;
      this.$('status').textContent=`${context||'检测中'} · ${this.summary}`;
      this.paintDevices(s,{rounds,live:live&&!options.paused});
    }else{
      this.loopCycle=undefined;this.lastLoopFailure=null;
      this.$('status').textContent=context||this.summary&&`已停止 · ${this.summary} · 保留本次结果`||'未启动运动循环，点击“开始检测”测试通信';
      // A loop that just stopped must not leave a row labelled live/normal.
      this.paintDevices(s,{live:live&&!options.paused});
    }
    const deviceStats=deviceStatsOf(b);
    if(deviceStats){
      if(!loop)this.$('status').textContent+=` · 本次服务累计采集 ${deviceStats.total_reads} 轮`;
      this.$('status').textContent+=` · 完整回包超时 ${deviceStats.complete_but_late??0} 轮（整轮，未归因到设备）`;
    }
    this.wasLoop=loop;
    this.paintStatus(s,{loop,live,context});
  }
  paintDevices(s,{loop=false,rounds=0,live}){
    const b=s.bus,stats=deviceStatsOf(b),trace=stats?.last_trace||b.native?.sync||b.diagnostics?.sync,totals=loop?totalsOf(b):null;
    // A torque-confirmation Sync Read is not a 16-device telemetry frame.
    const telemetry=trace?.address===56&&trace?.length===15;
    const missing=new Set(telemetry&&trace.request_sent!==false?trace.missing_ids||[]:[]),errors=errorsOf(b);
    for(const [id,{cell,detail}] of this.cells){
      const row=id===200?s.imu:s.servos?.find(r=>r.id===id),fresh=live&&s.service_sample_fresh&&row?.status==='live';
      const device=separatedCounts(stats,id);
      const legacyCount=loop?(totals?totals.missing_by_id[id]||0:null):this.base?Math.max(0,(errors[id]||0)-(this.base.errors[id]||0)):errors[id]??null;
      const failures=device?.missing, timeouts=device?.timeout;
      let label,tone='';
      if(!live){label='反馈暂停 / 中断';tone='warn';}
      else if(telemetry&&missing.has(id)){label=trace.deadline_exceeded?'本轮超时未回':'本轮非超时缺包';tone=trace.deadline_exceeded?'warn':'bad';}
      else if(telemetry&&trace.request_sent===false){label='总线请求发送失败';tone='warn';}
      else if(telemetry&&trace.complete_but_late){label=acceptedLateRead(b)?'回包齐全 · 超时已接纳':'回包齐全 · 本轮超时';tone='warn';}
      else if(loop&&!fresh){label=telemetry&&!missing.has(id)?'本轮有回包 · 样本未更新':'等待新鲜反馈';tone='warn';}
      else if((failures||timeouts||!device&&legacyCount)&&fresh){label='当前正常 · 曾'+(timeouts?'超时未回':failures?'非超时缺包':'未回（旧版未分类）');tone='warn';}
      else if(failures||timeouts){label='等待恢复';tone='warn';}
      else if(fresh&&(loop||rounds||stats?.total_reads)){label='通信正常';tone='good';}
      else{label=rounds?'等待新鲜反馈':'等待第一轮';tone=rounds?'warn':'';}
      const current=id===200?`IMU ${fresh?'在线':'等待有效数据'}`:`${fmt(row?.voltage_v)} V · ${fmt(row?.temperature_c,0)} °C${fresh?'':'（上次有效值）'}`;
      const history=device?`\n累计非超时缺包 ${failures} 次\n累计超时未回 ${finite(timeouts)?timeouts+' 次':'未上报'}${finite(device.consecutive_timeout)?`\n连续：超时 ${device.consecutive_timeout} / 缺包 ${device.consecutive_missing}`:''}${finite(device.last_timeout_read)?`\n最近超时：第 ${device.last_timeout_read} 次采集`:''}${finite(device.last_missing_read)?`\n最近缺包：第 ${device.last_missing_read} 次采集`:''}`:`\n旧版未回 / 异常 ${finite(legacyCount)?legacyCount+' 次':'未上报'}\n超时与缺包未分开上报，请升级固件`;
      cell.className='inspection-device '+tone;detail.textContent=label+history+'\n'+current;
    }
  }
  paintStatus(s,{loop,live,context}){
    const b=s.bus||{},trace=b.native?.sync,totals=loop?totalsOf(b):null;
    let current=b.error||b.last_cycle_error||totals?.last_error||(b.torque_off_pending?'正在确认卸力':'')||'',tone='error';
    if(loop&&trace?.address===56&&trace?.length===15){
      if(trace.request_sent===false)current=totals?.last_error||'总线请求未能发送，未归因到具体设备';
      else if(trace.missing_ids?.length)current=`${trace.deadline_exceeded?'超时未回':'非超时缺包'} ID：${trace.missing_ids.join(', ')}`;
      else if(trace.complete_but_late){current=acceptedLateRead(b)?'回包齐全 · 超时反馈已接纳'+(s.service_sample_fresh?'':' · 等待传感器有效样本'):'回包齐全，但超过事务截止时间（本轮未接纳）';tone='warning';}
      else if(!s.service_sample_fresh&&!current)current='循环暂未取得新鲜完整样本，等待反馈恢复';
      if(current&&live&&!context&&!acceptedLateRead(b))this.lastLoopFailure={cycle:b.cycle,error:current,elapsed_us:trace.elapsed_us,complete_but_late:trace.complete_but_late};
    }
    let failure=loop?(totals?totals.last_failure:this.lastLoopFailure):b.last_failure||b.diagnostics?.last_failure;
    const lastLate=totals?.last_complete_but_late;
    if(lastLate?.accepted&&finite(lastLate.read)&&(!failure||lastLate.read>failure.read)){
      failure={...lastLate,complete_but_late:true,error:'回包齐全 · 超时反馈已接纳'};
    }
    // A retained failure has its own elapsed_us. A later successful sync must
    // never supply the number beside that historical error.
    const historical=failureText(b,failure);
    const historicalLabel=failure?.accepted?'最近耗时提示':'最近异常';
    const currentRecord=trace?.address===56&&trace?.length===15?{...trace,error:current}:
      totals?.last_failure&&finite(totals.last_failure.read)&&totals.last_failure.read===totals.total_reads?totals.last_failure:null;
    const currentDetail=current&&(currentRecord||late(current))?`\n${readTiming(b,currentRecord)}`:'';
    const failureAt=finite(failure?.read)?`第 ${failure.read} 次采集`:`第 ${failure?.cycle??'—'} 轮`;
    let message='';
    if(this.requestError){message=this.requestError;tone='error';}
    else if(context){message=`${context} · ${s.channels?.bus?.error||'当前画面不代表实时通信正常'}${historical?`\n${historicalLabel} · ${failureAt} · ${historical}`:''}`;tone='warning';}
    else if(current){message=`${acceptedLateRead(b)?'本轮耗时提示':'当前异常'}${finite(b.cycle??b.total_cycles)?` · 第 ${b.cycle??b.total_cycles} 轮`:''} · ${current}${currentDetail}`;if(late(current))tone='warning';}
    else if(historical){message=`${historicalLabel} · ${failureAt} · ${historical}${s.service_sample_fresh?failure.accepted?'\n当前通信正常；保留该次耗时供核对。':'\n当前通信已恢复；保留最近异常供核对。':''}`;tone='warning';}
    else if((loop||this.manual)&&s.service_sample_fresh){message=loop?'通信正常 · 已自动接入运动循环反馈':'通信正常 · 手动检测中';tone='completed';}
    else{message=this.manual?'等待新鲜反馈':loop?'等待运动循环反馈':'未启动运动循环时，点击“开始检测”查看本次通信结果。';tone='info';}
    showFeedback(this.$('feedback'),message,tone);
  }
}
