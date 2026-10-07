import {SSHConnection} from './connection.js';
let sshConnection;
import {ServicePanel} from './service.js';
import {SystemLogPanel} from './system-log.js';
let servicePanel;
import {Camera} from './camera.js';
import {ControlPanel} from './control.js';
import {messageZh,tofView} from './messages.js';
import {officialStandingDegrees,modelJointLimits,referenceAngle} from './joint-reference.js';
import {loopHz} from './metrics.js';
import {historyFrame} from './history-frame.js';
import {RawTelemetry} from './raw-telemetry.js';
let rawTelemetry;

const $=id=>document.getElementById(id);
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const fmt=(n,d=1)=>finite(n)?n.toFixed(d):'—';
const vec=(v,d=3)=>Array.isArray(v)?v.map(x=>fmt(x,d)).join(' / '):'未导出';
const radians=n=>finite(n)?n*180/Math.PI:null;
const text=(id,value)=>{const el=$(id),next=String(value??'');if(el.textContent!==next)el.textContent=next;};
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let controls,cfg,latest,shown,duck,paused=false,selected=0,selectedId=20,group='all',history=[],replay=null,replayTimer=null;
let apiOkay=true,polling=false;
const colors=['#c1f577','#7caedd','#ed9890'];
const statusNames={live:'实时',stale:'数据过期',error:'连接异常',waiting:'等待',unavailable:'未提供'};
function badge(id,status,label){const el=$(id);el.className='badge '+(status==='live'?'':status==='error'?'bad':status==='stale'?'warn':'neutral');el.textContent=label||statusNames[status]||'未知';}
function notify(message){text('toast',message);$('toast').hidden=false;clearTimeout(notify.timer);notify.timer=setTimeout(()=>$('toast').hidden=true,3600);}
function valueCell(v,d=1){return finite(v)?fmt(v,d):'<span class="na" title="数据源未提供，或样本已过期">—</span>';}
function sourceLive(s,name){return s.channels?.[name]?.status==='live';}
function canvasContext(id){
  const c=$(id),box=c.getBoundingClientRect(),dpr=Math.min(devicePixelRatio,2),w=box.width,h=box.height;
  if(!w||!h)return null;
  if(c.width!==Math.round(w*dpr)||c.height!==Math.round(h*dpr)){c.width=Math.round(w*dpr);c.height=Math.round(h*dpr);}
  const ctx=c.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);return {ctx,w,h};
}
function plot(id,series,{mini=false,range=null}={}){
  const cv=canvasContext(id);if(!cv)return;const {ctx,w,h}=cv;
  const margin=mini?{l:0,r:0,t:3,b:2}:{l:50,r:14,t:12,b:22};
  const all=series.flatMap(s=>s.values.filter(finite));
  let lo=range?.[0]??(all.length?Math.min(...all):0),hi=range?.[1]??(all.length?Math.max(...all):1);
  if(hi===lo){const pad=Math.max(1,Math.abs(lo)*.02);lo-=pad;hi+=pad;}
  if(!range&&!mini){const pad=(hi-lo)*.15;lo-=pad;hi+=pad;}
  const cw=w-margin.l-margin.r,ch=h-margin.t-margin.b;
  const y=v=>margin.t+(hi-v)/(hi-lo)*ch;
  const end=history.at(-1)?.at,start=end-60;
  if(!mini){
    ctx.font='12px ui-monospace,monospace';ctx.textAlign='right';
    for(let i=0;i<3;i++){const value=lo+(hi-lo)*i/2,yp=y(value);ctx.strokeStyle='#28382d';ctx.lineWidth=.6;ctx.beginPath();ctx.moveTo(margin.l,yp);ctx.lineTo(w-margin.r,yp);ctx.stroke();ctx.fillStyle='#647d65';ctx.fillText(value.toFixed(Math.abs(hi-lo)<3?2:1),margin.l-6,yp+3);}
    ctx.fillStyle='#536d54';ctx.textAlign='left';ctx.fillText('−60 s',margin.l,h-3);ctx.textAlign='right';ctx.fillText('当前',w-margin.r,h-3);
  }
  if(!all.length){if(!mini){ctx.fillStyle='#667e64';ctx.textAlign='center';ctx.fillText('等待有效数据',w/2,h/2);}return;}
  for(let k=0;k<series.length;k++){
    const s=series[k],n=s.values.length;ctx.strokeStyle=s.color||colors[k%3];ctx.lineWidth=mini?1.3:1.6;ctx.beginPath();let pen=false;
    s.values.forEach((v,i)=>{if(!finite(v)){pen=false;return;}const t=history[i]?.at,ratio=finite(t)&&finite(end)?Math.max(0,Math.min(1,(t-start)/60)):(n<=1?1:i/(n-1));const x=margin.l+ratio*cw;if(!pen){ctx.moveTo(x,y(v));pen=true;}else ctx.lineTo(x,y(v));});ctx.stroke();
    if(n===1&&finite(s.values[0])){ctx.fillStyle=ctx.strokeStyle;ctx.beginPath();ctx.arc(w-margin.r,y(s.values[0]),2,0,Math.PI*2);ctx.fill();}
  }
}
function duration(v){if(!finite(v))return '—';const n=Math.floor(v);return `${Math.floor(n/3600)}h ${Math.floor(n%3600/60)}m ${n%60}s`;}
function modeDisplay(s){
  const mode=replay?'replay':s.mode;
  text('mode-chip',mode==='replay'?'REPLAY · 历史回放':mode==='service'?'LIVE · 舵机服务':'LIVE · 实机连接');
  text('access-chip',cfg?.control_enabled&&!replay?(mode==='service'?'✥ 关节与行走控制':'✥ 手动控制'):'◈ 只读');
  const b=$('mode-banner');b.hidden=mode!=='replay';
  if(mode==='replay')b.textContent='历史回放：画面与数值来自记录文件，不代表机器人当前状态。摄像头已断开。';
  const live=mode==='service'?s.service_sample_fresh:sourceLive(s,'state');
  text('side-status',mode==='replay'?'历史记录':live?'实机状态在线':'等待实机状态');
  $('side-dot').style.background=live?'#c1f577':'#9a7755';
}
function render(s,addHistory=true){
  shown=s;modeDisplay(s);sshConnection?.render(s);controls?.render(s,{replay:!!replay,paused});
  servicePanel?.render(s,{replay:!!replay,offline:!apiOkay||cfg.connection_ui&&!s.connection?.active,paused});
  if(addHistory){history.push(historyFrame(s));const cutoff=s.at-60;while(history.length>650||history[0]?.at<cutoff)history.shift();}
  const hs=sourceLive(s,'health'),ss=sourceLive(s,'state'),sy=sourceLive(s,'system');
  const h=hs?s.health:{},st=ss?s.state:{};
  text('robot-name',s.system?.hostname||'duck-10e4');
  text('metric-zero-temp',sy?fmt(s.system?.cpu_temp_c):'—');text('zero-temp-caption',sy?'ZERO 主板 CPU 实测':'等待主板温度回读');
  text('last-update',`${paused?'已暂停 · ':replay?'记录 · ':''}${new Date(s.at*1000).toLocaleTimeString('zh-CN',{hour12:false})}`);
  const service=s.mode==='service',bus=sourceLive(s,'bus')?s.bus:{};
  const hz=loopHz(s);
  text('metric-hz',fmt(hz));text('loop-badge',finite(hz)?hz>=48?'稳定':'留意频率':'未知');
  text('loop-caption',`目标 ${fmt(h.control_loop?.target_hz,0)} Hz · 超期 ${fmt(h.control_loop?.missed??st.loop?.missed,0)} 次`);
  if(service)text('loop-caption',`目标 ${fmt(bus.target_hz??h.control_loop?.target_hz,0)} Hz · 曲线 30–60 Hz`);
  const online=s.servos.slice(0,15).filter(r=>r.status==='live'&&finite(service?r.position_raw:r.angle_deg)).length;
  text('metric-joints',online|| (ss?0:'—'));
  text('joint-caption',online===15?'15 个关节均有有效反馈':`实测角度反馈 ${online}/15 · 非总线 Ping 结果`);
  if(service){text('metric-joints',sourceLive(s,'bus')?online:'—');text('joint-caption',`已标定 ${s.calibrated_count||0}/15`);}
  $('joint-dots').replaceChildren(...s.servos.slice(0,15).map(r=>{const i=document.createElement('i');i.className=r.status==='live'?'on':'';i.title=`ID ${r.id} ${statusNames[r.status]}`;return i;}));
  const br=s.servos.filter(x=>x.status==='live');const volts=br.map(x=>x.voltage_v).filter(finite),temps=br.map(x=>x.temperature_c).filter(finite);
  text('metric-volts',fmt(h.battery?.volts,2));text('metric-temp',fmt(h.motors?.max_c));
  text('temp-caption',h.motors?`${h.motors.hottest} · 平均 ${fmt(h.motors.mean_c)} °C`:'等待 robot.health · 非逐颗温度');
  if(service){text('metric-volts',fmt(volts.length?Math.min(...volts):null,2));text('metric-temp',fmt(temps.length?Math.max(...temps):null));text('temp-caption','舵机实测最高温度');}
  const gravity=s.imu?.gravity,imuLive=s.imu?.status==='live',canTilt=imuLive&&Array.isArray(gravity);
  text('hud-roll',`${fmt(canTilt?s.imu.roll_deg:null)}°`);text('hud-pitch',`${fmt(canTilt?s.imu.pitch_deg:null)}°`);
  text('imu-roll',`${fmt(canTilt?s.imu.roll_deg:null)}°`);text('imu-pitch',`${fmt(canTilt?s.imu.pitch_deg:null)}°`);
  if(service)h.imu={...h.imu,ready:s.imu.ready};
  text('imu-ready',typeof h.imu?.ready==='boolean'?h.imu.ready?'已收敛':'未收敛':'未知');text('imu-stale',fmt(h.imu?.consecutive_stale_blocks,0));
  text('imu-gravity',canTilt?vec(gravity):'— / — / —');text('imu-gyro',imuLive?vec(s.imu.gyro):'无有效样本');text('imu-quat',imuLive?vec(s.imu.quat):'无有效样本');
  badge('imu-badge',s.imu?.status||'waiting',imuLive?(s.imu.gyro?'含原始遥测':'重力方向'):undefined);
  $('imu-badge').title=messageZh(s.imu?.reason)||s.imu?.source||'';
  const roll=canTilt?s.imu.roll_deg:0,pitch=canTilt?s.imu.pitch_deg:0;
  $('horizon').setAttribute('transform',`rotate(${-roll} 85 85) translate(0 ${Math.max(-45,Math.min(45,pitch))})`);
  $('horizon').style.opacity=canTilt?1:.25;
  text('tilt-status',canTilt?st.safety?.fallen?'已报告跌倒':'倾斜由重力估计':'姿态未知');
  const poseLive=(ss||service&&s.service_sample_fresh)&&online===15&&(!service||s.pose_calibrated);
  badge('pose-badge',poseLive?'live':s.channels.state.status,poseLive?(replay?'历史姿态':canTilt?'实测姿态':'关节实测 / 倾斜未知'):duck?.hasPose?'已冻结 / 旧姿态':'参考模型');
  text('pose-label',poseLive?canTilt?'关节实测 + IMU · 仅显示，不做仿真':'关节实测 · 身体倾斜未知':duck?.hasPose?'数据已断流 · 保留最后姿态':'官方静态参考 · 尚无完整关节反馈');
  if(service){text('pose-label',poseLive?`已标定关节实测 · ${s.imu.mount_verified?'IMU 安装已确认':'机身方向待确认，暂用参考朝向'}`:s.pose_calibrated?'数据过期 · 保留最后姿态':`静态参考 · ${s.calibrated_count||0}/15 已标定`);badge('pose-badge',poseLive?'live':'waiting',poseLive?'关节实测':s.pose_calibrated?'旧姿态':'标定中');text('tilt-status',s.imu.mount_verified?'按已确认安装方向显示':'安装待核对 · 当前变换预览');}
  duck?.update(s);
  text('hud-yaw',`${fmt(radians(ss?duck?.displayYaw:null))}°`);
  $('hud-yaw').title=`相对画面初始朝向；原始航向 ${fmt(radians(st.odom?.yaw))}°`;
  renderTof(s);renderSystem(s,sy);renderMotors(s);renderDiagnostics(s);drawHistory();
  if(!$('raw-json').hidden&&(!render.rawAt||Date.now()-render.rawAt>=300)){render.rawAt=Date.now();text('raw-json',JSON.stringify(s,null,2));}
  const cb=$('connection-banner');
  if(apiOkay && !replay){
    const stateOkay=service?sourceLive(s,'bus'):ss;
    cb.hidden=stateOkay;
    cb.textContent=s.connection_paused?'SSH 连接已暂停，请在右侧连接 Zero。':stateOkay?'':`尚未收到完整实机姿态。${messageZh(s.channels.state.error||s.health.reason)||'请检查 SSH、robotd、15 颗舵机与 ID200；ToF/摄像头可独立工作。'}`;
    if(s.connection_paused)cb.hidden=false;
    if(cfg.connection_ui&&!s.connection?.active)cb.hidden=true;
    const revision=sy?s.system.identities?.robotd?.revision:null;
    if(typeof revision==='string'&&!(service&&s.service_compatible)&&(!/^[a-f0-9]{7,40}$/i.test(revision)||!cfg.baseline.startsWith(revision.toLowerCase()))){cb.hidden=false;cb.textContent=`运行标识 ${revision} 与适配基线 590b986 不同，字段/关节映射尚未核验。${cb.textContent}`;}
  }else if(apiOkay)cb.hidden=true;
}
function renderTof(s){
  const view=tofView(s),live=view.status==='live',f=s.tof||{},grid=$('tof-grid');
  const validShape=view.validFrame;
  badge('tof-badge',view.status,view.label);
  text('tof-message',view.detail);
  const n=validShape?f.rows*f.cols:64;grid.style.gridTemplateColumns=`repeat(${validShape?f.cols:8},1fr)`;grid.style.gridTemplateRows=`repeat(${validShape?f.rows:8},1fr)`;
  if(grid.children.length!==n){grid.replaceChildren(...Array.from({length:n},(_,i)=>{const b=document.createElement('button');b.className='tof-cell invalid';b.addEventListener('click',()=>{const f=shown?.tof||{};text('tof-detail',`分区 ${i} · 行 ${Math.floor(i/(f.cols||8))} / 列 ${i%(f.cols||8)} · 原始 ${f.distance_mm?.[i]??'—'} mm · 状态码 ${f.status?.[i]??'—'} · 原始排列未镜像`);});return b;}));}
  const ranged=[];
  [...grid.children].forEach((cell,i)=>{
    const mm=f.distance_mm?.[i],status=f.status?.[i],valid=validShape&&[5,9].includes(status)&&finite(mm)&&mm>0;
    cell.className='tof-cell'+(valid?'':' invalid');
    cell.textContent=valid?String(Math.round(mm/10)):status===255?'∞':'—';
    cell.style.background=valid?`hsl(${25+Math.min(1,mm/4000)*185} 32% ${28+Math.min(1,mm/4000)*10}%)`:'';
    cell.title=`${valid?'距离 '+mm+' mm':'无有效测距'} · 状态 ${status??'未知'} · 格内单位 cm`;
    if(valid)ranged.push(mm);
  });
  grid.style.opacity=live?1:.35;
  text('tof-near',live&&ranged.length?`${Math.min(...ranged)} mm`:'— mm');text('tof-far',live&&ranged.length?`${Math.max(...ranged)} mm`:'— mm');text('tof-valid',live&&validShape?`${ranged.length}/${n}`:`—/${n}`);
  text('tof-seq',validShape?`第 ${f.seq} 帧 · 格内 cm`:'尚未收到测距帧');
}
function renderSystem(s,live){
  const v=live?s.system:{},available=v.memory_available,total=v.memory_total,used=finite(total)&&finite(available)?total-available:null;
  const identity=v.identities?.robotd,revision=typeof identity?.revision==='string'?identity.revision:null;
  const matches=typeof revision==='string'&&/^[a-f0-9]{7,40}$/i.test(revision)&&cfg.baseline.startsWith(revision.toLowerCase());
  text('runtime-revision',revision?`运行标识 ${revision.slice(0,12)}${matches?' · 基线匹配':' · 与基线不同'}`:'运行版未提供 revision');
  $('runtime-revision').title=identity?JSON.stringify(identity):'读取 robotd 的公开 identity.json；不是对二进制文件的校验';
  $('runtime-revision').classList.toggle('data-warn',!!revision&&!matches);
  if(s.mode==='service'){text('runtime-revision',s.bus?.build||'等待正式服务构建标识');$('runtime-revision').classList.toggle('data-warn',!s.service_compatible);}
  const camera=v.camera,cameraFresh=camera&&finite(v.camera_age_ms)&&v.camera_age_ms<5000;
  text('camera-capture',camera?`${cameraFresh?'采集端':'采集端旧统计'} ${fmt(camera.fps)} / ${fmt(camera.targetFps,0)} fps · ${fmt(camera.width,0)}×${fmt(camera.height,0)} ${camera.format||''} · 驱动丢帧 ${fmt(camera.dropped,0)} · 接收者 ${fmt(camera.consumers,0)} · ${fmt(v.camera_age_ms,0)} ms 前`:'');
  text('sys-cpu',`${fmt(v.cpu_percent)} %`);$('cpu-bar').style.width=`${finite(v.cpu_percent)?Math.max(0,Math.min(100,v.cpu_percent)):0}%`;
  text('sys-memory',finite(used)?`${(used/2**20).toFixed(0)} / ${(total/2**20).toFixed(0)} MB`:'—');$('memory-bar').style.width=`${finite(used)&&total?used/total*100:0}%`;
  text('sys-temp',`${fmt(v.cpu_temp_c)} °C`);text('sys-uptime',duration(v.uptime_s));
  const odom=sourceLive(s,'state')?s.state.odom:{};
  text('odom-x',`${fmt(odom?.position?.[0],3)} m`);text('odom-y',`${fmt(odom?.position?.[1],3)} m`);text('odom-yaw',`${fmt(radians(odom?.yaw))}°`);
  const cv=canvasContext('odom-chart');if(!cv)return;const {ctx,w,h}=cv;
  ctx.strokeStyle='#24372b';ctx.lineWidth=.6;for(let i=0;i<w;i+=23){ctx.beginPath();ctx.moveTo(i,0);ctx.lineTo(i,h);ctx.stroke();}for(let i=0;i<h;i+=23){ctx.beginPath();ctx.moveTo(0,i);ctx.lineTo(w,i);ctx.stroke();}
  const pts=history.filter(x=>sourceLive(x,'state')).map(x=>x.state.odom?.position).filter(p=>p?.length===3&&p.every(finite));
  if(!pts.length){ctx.fillStyle='#6e826c';ctx.textAlign='center';ctx.font='12px sans-serif';ctx.fillText('等待接触里程计',w/2,h/2);return;}
  const xmin=Math.min(0,...pts.map(p=>p[0])),xmax=Math.max(0,...pts.map(p=>p[0])),ymin=Math.min(0,...pts.map(p=>p[1])),ymax=Math.max(0,...pts.map(p=>p[1]));
  const scale=Math.min((w-50)/Math.max(.25,xmax-xmin),(h-42)/Math.max(.25,ymax-ymin));const xy=p=>[w/2+(p[0]-(xmax+xmin)/2)*scale,h/2-(p[1]-(ymax+ymin)/2)*scale];
  ctx.beginPath();pts.forEach((p,i)=>{const [x,y]=xy(p);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);});ctx.strokeStyle='#abc983';ctx.lineWidth=1.8;ctx.stroke();
  const [x,y]=xy(pts.at(-1));ctx.fillStyle='#d2f3aa';ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();ctx.fillStyle='#6f8b68';ctx.font='12px monospace';ctx.fillText('接触里程计 / m · 非绝对定位',18,h-10);
}
// Keep the pointer target alive when feedback changes between press and release.
function patchMotorNode(node,fresh){
  if(node.nodeType!==fresh.nodeType||node.nodeName!==fresh.nodeName){node.replaceWith(fresh);return;}
  if(node.nodeType===Node.TEXT_NODE){if(node.nodeValue!==fresh.nodeValue)node.nodeValue=fresh.nodeValue;return;}
  for(const attr of [...node.attributes])if(!fresh.hasAttribute(attr.name))node.removeAttribute(attr.name);
  for(const attr of fresh.attributes)if(node.getAttribute(attr.name)!==attr.value)node.setAttribute(attr.name,attr.value);
  for(let i=0;i<fresh.childNodes.length;i++){
    const next=fresh.childNodes[i].cloneNode(true);
    if(node.childNodes[i])patchMotorNode(node.childNodes[i],next);else node.append(next);
  }
  while(node.childNodes.length>fresh.childNodes.length)node.lastChild.remove();
}
function updateMotorRows(html){
  const body=$('motor-rows'),template=document.createElement('template');
  template.innerHTML='<table><tbody>'+html+'</tbody></table>';
  const previous=new Map([...body.children].map(row=>[row.dataset.id,row]));
  const next=[...template.content.querySelector('tbody').children];
  for(let i=0;i<next.length;i++){
    const fresh=next[i],row=previous.get(fresh.dataset.id)||fresh;
    if(row!==fresh)patchMotorNode(row,fresh);
    if(body.children[i]!==row)body.insertBefore(row,body.children[i]||null);
  }
  while(body.children.length>next.length)body.lastElementChild.remove();
}
function renderMotors(s){
  const q=$('motor-search').value.toLowerCase();
  const rows=s.servos.filter(r=>(group==='all'||r.group===group)&&`${r.id} ${r.label} ${r.name}`.toLowerCase().includes(q));
  updateMotorRows(rows.map(r=>{
    const live=r.status==='live',torque=typeof r.torque_enabled==='boolean'?r.torque_enabled?'ON':'OFF':'—';
    const fault=finite(r.hardware_error)?`0x${r.hardware_error.toString(16).padStart(2,'0')}`:'—';
    const cell=(key,d=1)=>valueCell(r[key],d);
    const rawMode=s.mode==='service';
    const referenceLimits=modelJointLimits[r.id];
    const officialReference=s.mode==='service'?`<td class="model-ref model-home">${referenceAngle(officialStandingDegrees[r.id],2)}</td><td class="model-ref model-limit">${referenceAngle(referenceLimits?.[0])}</td><td class="model-ref model-limit">${referenceAngle(referenceLimits?.[1])}</td>`:'';
    const cal=r.calibration;
    const saved=cal?.calibrated===true&&cal.name===r.name&&finite(cal.min_rad)&&finite(cal.max_rad)&&cal.min_rad<cal.max_rad;
    const savedLimits=s.mode==='service'?`<td class="saved-limit">${saved?referenceAngle(radians(cal.min_rad),2):'—'}</td><td class="saved-limit">${saved?referenceAngle(radians(cal.max_rad),2):'—'}</td>`:'';
    return `<tr data-id="${escape(r.id)}" class="${r.id===selectedId?'selected':''} ${live?'':'old-sample'}" tabindex="0" title="${escape(r.source)}；${live?'有效样本':'非实时样本'}；${escape(r.error||'')}"><td><span class="servo-id">${escape(r.id)}</span><span class="servo-name">${escape(r.label)}</span></td><td><span class="status-text ${live?'':r.status==='error'?'error':'unknown'}">${escape(statusNames[r.status]||'未知')}</span></td>${s.mode==='service'?`<td>${cell('position_raw',0)}</td>`:''}<td>${cell('angle_deg')}${s.mode==='service'&&!r.calibrated?'<small class="muted"> 未标定</small>':''}</td>${officialReference}${savedLimits}<td class="target-angle">${cell('target_deg')}</td><td class="${Math.abs(r.error_deg)>5?'data-warn':''}">${cell('error_deg',2)}</td><td>${cell(rawMode?'speed_raw':'velocity_rpm',rawMode?0:2)}</td><td>${cell(rawMode?'current_raw':'current_ma',0)}</td><td>${cell('temperature_c')}</td><td>${cell('voltage_v',2)}</td>${s.mode==='service'?'':`<td>${cell('current_ratio_percent')}</td><td>${cell('pwm_percent')}</td>`}<td class="${r.hardware_error?'data-warn':''}">${s.mode==='service'?torque:`${torque} / ${fault}`}</td></tr>`;
  }).join('')||`<tr><td colspan="${s.mode==='service'?18:12}" class="muted">无匹配关节</td></tr>`);
  const chosen=s.servos.find(r=>r.id===selectedId);
  if(chosen){text('selected-joint',`${chosen.label} · ID ${chosen.id}`);text('joint-extra',chosen.model_number?`型号 ${chosen.model_number} · 固件 ${chosen.firmware??'—'} · PID ${chosen.p_gain??'—'}/${chosen.i_gain??'—'}/${chosen.d_gain??'—'} · Homing Offset ${chosen.homing_offset??'—'} · Current Limit ${chosen.current_limit_ma??'—'} mA`:`${chosen.name} · ${chosen.source} · 电流 ${chosen.current_source||'未导出'}`);}
  if(s.mode==='service'&&chosen)text('joint-extra',`${chosen.calibrated?'已标定关节反馈':'尚未标定 · 编码器反馈'} · 最近 60 秒`);
  const registers=[['model_number','型号编号'],['firmware','固件版本'],['configured_id','寄存器 ID'],['baud_code','波特率代码'],['return_delay','返回延迟原值 (2 μs)'],['drive_mode','Drive Mode'],['operating_mode','Operating Mode'],['homing_offset','零位偏移 / counts'],['position_raw','反馈位置 / counts'],['goal_position_raw','目标位置 / counts'],['current_limit_ma','电流限值 / mA'],['pwm_limit','PWM 限值原值'],['velocity_limit_rpm','速度限值 / rpm'],['voltage_min_v','最低电压限值 / V'],['voltage_max_v','最高电压限值 / V'],['temperature_limit_c','温度限值 / °C'],['p_gain','位置 P'],['i_gain','位置 I'],['d_gain','位置 D'],['goal_current_ma','目标电流 / mA'],['goal_velocity_rpm','目标速度 / rpm'],['goal_pwm','目标 PWM 原值'],['profile_acceleration_raw','轮廓加速度原值'],['profile_velocity_raw','轮廓速度原值'],['bus_watchdog','Bus Watchdog 原值'],['realtime_tick_ms','舵机 tick / ms'],['moving','Moving 标记'],['moving_status','Moving Status 原值'],['hardware_error','Hardware Error 位域']];
  if(s.mode==='service')registers.unshift(['speed_raw','速度原始计数'],['load_raw','负载原始计数'],['current_raw','电流原始计数']);
  const shownRegisters=s.mode==='service'?registers.filter(([key])=>['goal_position_raw','speed_raw','load_raw','current_raw','moving'].includes(key)):registers;
  $('joint-registers').innerHTML=shownRegisters.map(([key,label])=>{const value=chosen?.[key];return `<div><dt>${s.mode==='service'&&key==='goal_position_raw'?'服务目标 / counts':s.mode==='service'&&key==='moving'?'运动标记':label}</dt><dd>${typeof value==='boolean'?(value?'1':'0'):finite(value)?fmt(value,Number.isInteger(value)?0:2):'—'}</dd></div>`;}).join('');
}
function choose(id){
  const index=cfg.ids.indexOf(id);if(index<0&&!shown?.servos.some(r=>r.id===id))return;
  selectedId=id;selected=index;if(index>=0)servicePanel?.select(id);
  if(duck){duck.selected=selected;if(shown)duck.update(shown);duck.focusJoint(selected);}
  if(shown){renderMotors(shown);drawHistory();}
}
function renderDiagnostics(s){
  const names={state:'robotd / 姿态状态',health:'robotd / 健康指标',tof:'tofd / 深度矩阵',system:'Zero / 系统信息',capabilities:'robotd / 可用动作'};
  names.bus='robotd / 舵机总线';names.calibration='robotd / 已保存标定';
  const tof=tofView(s);
  $('channel-list').innerHTML=Object.entries(s.channels).filter(([k])=>k!=='bench'&&(s.mode==='service'?(s.bus?.mode!=='commissioning'||!['state','capabilities'].includes(k)):!['bus','calibration'].includes(k))).map(([k,c])=>{
    const status=k==='tof'?tof.status:c.status,label=k==='tof'?tof.label:statusNames[status];
    const detail=k==='tof'?tof.detail:messageZh(c.error);
    const age=k==='tof'&&!tof.validFrame?'尚无测距帧':finite(c.age_ms)?`${c.age_ms} ms`:'尚无样本';
    return `<div class="channel-line" title="${escape(detail)}"><span class="channel-title">${names[k]}</span><span class="latency">${age}</span><span class="badge ${status==='live'?'':status==='error'?'bad':status==='stale'?'warn':'neutral'}">${label}</span></div>`;
  }).join('');
  const h=s.health,live=sourceLive(s,'health');badge('health-badge',live?(h.healthy?'live':'error'):s.channels.health.status,live?(h.healthy?'官方健康检查通过':h.degraded?'硬件未就绪':'官方报告异常'):undefined);
  text('health-detail',`${messageZh(h.reason)|| (live?'官方健康接口未报告异常原因':'等待官方健康响应')}\n总线连续失败 ${fmt(h.bus?.consecutive_errors,0)} · 启动失败 ${fmt(h.bus?.startup_failures,0)} · 最近控制周期 ${fmt(h.control_loop?.last_tick_age_ms,0)} ms 前 · IMU 历史旧样本 ${fmt(h.imu?.stale_blocks,0)}${s.extended?' · 扩展遥测已接入':' · 原版数据能力'}`);
  if(s.mode==='service'&&s.bus?.mode==='commissioning'){badge('health-badge',s.service_sample_fresh?'live':'waiting',s.service_sample_fresh?'接入模式 · 数据在线':'等待新鲜数据');text('health-detail',`正式服务 ${s.bus.phase} · 标定 ${s.calibrated_count}/15 · IMU 安装${s.bus.imu_mount_verified?'已确认':'待确认'}。策略控制尚未启用；通信在线不等于已通过行走验证。`);}
  text('move-request',sourceLive(s,'state')?vec(s.state.move?.requested):'—');text('move-applied',sourceLive(s,'state')?vec(s.state.move?.applied):'—');
  text('move-limits',sourceLive(s,'state')?`当前策略 ${s.state.policy||'未知'} · kp ${s.state.safety?.gain??'未知'} · 限制 ${(s.state.move?.limited_by||[]).join(', ')||'无报告'}`:'没有有效状态，不判断运动与限制。');
  $('events').innerHTML=s.events?.length?s.events.slice().reverse().map(e=>`<div class="event ${e.level==='error'?'bad':''}"><time>${new Date(e.at*1000).toLocaleTimeString('zh-CN',{hour12:false})} / ${escape(names[e.channel]||e.channel)}</time>${escape(messageZh(e.message))}</div>`).join(''):'<div class="muted">暂无链路事件</div>';
}
function drawHistory(){
  plot('mini-loop',[{values:history.map(loopHz)}],{mini:true,range:[30,60]});
  plot('mini-volts',[{values:history.map(s=>sourceLive(s,'health')?s.health.battery?.volts:null)}],{mini:true,range:[4,8]});
  plot('mini-temp',[{values:history.map(s=>sourceLive(s,'health')?s.health.motors?.max_c:null),color:'#d6b16e'}],{mini:true});
  plot('gravity-chart',[0,1,2].map((i)=>({values:history.map(s=>s.imu?.status==='live'?s.imu.gravity?.[i]:null),color:['#ed9890','#c1f577','#7caedd'][i]})),{range:[-1.15,1.15]});
  const option=$('plot-field').value,fields={raw:['position_raw','goal_position_raw'],angle:['angle_deg','target_deg'],current:['current_ma'],temperature:['temperature_c'],velocity:['velocity_rpm'],error:['error_deg']}[option];
  if(cfg?.service_enabled){if(option==='current')fields[0]='current_raw';if(option==='velocity')fields[0]='speed_raw';}
  const labels={raw:'编码器位置 counts',angle:'实测角度 °',current:'电流 mA',temperature:'温度 °C',velocity:'速度 rpm',error:'跟随误差 °'};
  if(cfg?.service_enabled){labels.current='电流原始计数';labels.velocity='速度原始计数';}
  text('chart-label',`● ${labels[option]}`);$('target-label').hidden=!['angle','raw'].includes(option);$('target-label').textContent=option==='raw'?'● 终点目标 counts':'● 目标角度';
  plot('joint-chart',fields.map(key=>({values:history.map(s=>{const r=s.servos.find(r=>r.id===selectedId);return r?.status==='live'?r[key]:null;})})));
}
const camera=new Camera($('camera'),(status,message)=>{
  badge('camera-badge',status,status==='live'?'视频在线':status==='connecting'?'连接中':status==='error'?'连接失败':'未连接');
  $('camera-placeholder').hidden=status==='live';$('camera-overlay').hidden=status!=='live';text('camera-message',message);
  $('camera-connect').disabled=status==='connecting';
  if(status!=='live'){text('camera-fps','— fps');text('camera-bitrate','— Mb/s');text('camera-loss','—');}
},s=>{text('camera-fps',`${fmt(s.fps)} fps`);text('camera-bitrate',`${fmt(s.mbps,2)} Mb/s`);text('camera-loss',fmt(s.loss,0));});
function cameraAddress(){return {host:localStorage.getItem('microduck-camera-host')||cfg.camera_host,port:Number(localStorage.getItem('microduck-camera-port')||cfg.camera_port)};}
function refreshCameraAddress(){const a=cameraAddress();$('camera-host').value=a.host;$('camera-port').value=a.port;text('camera-address',`摄像头 ${a.host}:${a.port}`);}
function openReplayAt(i){
  if(!replay)return;i=Math.max(0,Math.min(replay.frames.length-1,i));replay.index=i;
  const s=structuredClone(replay.frames[i]);history=replay.frames.slice(Math.max(0,i-600),i+1);render(s,false);$('replay-range').value=i;
  text('replay-label',`${i+1} / ${replay.frames.length} 帧 · ${new Date(s.at*1000).toLocaleTimeString()}`);
}
function validateRecording(data){
  if(data?.schema!=='microduck-console-recording/v1'||!Array.isArray(data.frames)||!data.frames.length||data.frames.length>1500)throw Error('不是受支持的中控记录，或帧数超出上限');
  let t=-Infinity;for(const f of data.frames){if(f.schema!=='microduck-console/v1'||!finite(f.at)||f.at<t||!f.channels||!Array.isArray(f.servos)||f.servos.length>253||!f.state||!f.health||!f.system||!f.imu||!f.tof)throw Error('记录结构不完整或时间顺序异常');t=f.at;for(const k of ['state','health','tof','system'])if(!f.channels[k])throw Error('缺失数据源状态');}
  return data;
}
function telemetryError(){
  controls?.suspend();servicePanel?.suspend();apiOkay=false;
  if(latest)servicePanel?.render(latest,{replay:!!replay,offline:true,paused});
  if(!replay){
    $('connection-banner').hidden=false;text('connection-banner','本地采集后端已断开；当前数值为旧样本。请检查启动终端。');
    if(!paused&&latest){const stale=structuredClone(latest);for(const c of Object.values(stale.channels))c.status='error';for(const row of stale.servos)row.status='stale';stale.imu.status='error';render(stale,false);}
  }
}
function download(body,name,type){
  const url=URL.createObjectURL(new Blob([body],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function exportRecording(){
  if(replay)return notify('当前为回放；原始记录文件已在你的电脑上');
  if(rawTelemetry)return download(JSON.stringify(rawTelemetry.store.recording()),'microduck-recording.json','application/json');
  const a=document.createElement('a');a.href='/api/recording';a.download='microduck-recording.json';a.click();
}
function exportCSV(){
  const s=rawTelemetry.store.snapshot(false),fields=['angle_deg','target_deg','error_deg','current_ma','temperature_c','voltage_v','velocity_rpm','current_ratio_percent','position_raw','speed_raw','load_raw','current_raw','torque_enabled'];
  const rows=[['mode','timestamp','id','joint','status',...fields],...s.servos.map(row=>[s.mode,s.at,row.id,row.name,row.status,...fields.map(key=>row[key])])];
  const cell=value=>{const text=value==null?'':value===true?'True':value===false?'False':String(value);return /[",\r\n]/.test(text)?'"'+text.replaceAll('"','""')+'"':text;};
  download('\ufeff'+rows.map(row=>row.map(cell).join(',')).join('\r\n')+'\r\n','microduck-servos.csv','text/csv');
}
// Direct local observer mode remains available; the dashboard uses raw WebSocket.
async function poll(){
  if(polling)return;polling=true;
  try{
    const r=await fetch('/api/snapshot',{signal:AbortSignal.timeout(2500)});if(!r.ok)throw Error(`HTTP ${r.status}`);
    latest=await r.json();apiOkay=true;if(!paused&&!replay)render(latest);
  }catch(e){
    controls?.suspend();servicePanel?.suspend();apiOkay=false;if(latest){servicePanel?.render(latest,{replay:!!replay,offline:true,paused});}if(!replay){$('connection-banner').hidden=false;text('connection-banner','本地采集后端已断开；当前数值为旧样本。请检查启动终端。');
      if(!paused&&latest){const stale=structuredClone(latest);for(const c of Object.values(stale.channels))c.status='error';for(const row of stale.servos)row.status='stale';stale.imu.status='error';render(stale,false);}
    }
  }finally{polling=false;setTimeout(poll,100);}
}
async function init(){
  const r=await fetch('/api/config');cfg=await r.json();text('console-version',`Console v${cfg.version} · 本地运行`);controls=new ControlPanel(cfg,$('control-panel'));servicePanel=new ServicePanel(cfg,choose);new SystemLogPanel();document.querySelector('main footer').before($('diagnostics'));refreshCameraAddress();text('settings-mode',cfg.mode);
  sshConnection=new SSHConnection(cfg,()=>{
    controls.suspend();controls.connected=false;controls.linkEpoch++;controls.socket.close();
    controls.options={...controls.options,offline:true};camera.disconnect();
  },state=>{
    history=[];latest=null;
    if(state.active){localStorage.setItem('microduck-camera-host',state.camera_host);refreshCameraAddress();}
    servicePanel?.management?.invalidate();
  });
  $('settings-button').onclick=()=>$('settings-dialog').showModal();$('open-recording').onclick=()=>$('recording-dialog').showModal();
  $('camera-save').onclick=()=>{
    const host=$('camera-host').value.trim(),port=Number($('camera-port').value);
    if(!/^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/.test(host)||!Number.isInteger(port)||port<1||port>65535)return notify('请检查主机名和端口');
    camera.disconnect();localStorage.setItem('microduck-camera-host',host);localStorage.setItem('microduck-camera-port',port);refreshCameraAddress();notify('摄像头地址已保存，点击连接开始接收');
  };
  $('camera-connect').onclick=()=>{if(replay)return notify('请先退出回放');try{const a=cameraAddress();camera.connect(a.host,a.port);}catch(e){notify(e.message);}};
  $('camera-disconnect').onclick=()=>camera.disconnect();
  $('camera-rotation').onchange=()=>{const a=Number($('camera-rotation').value);$('camera').style.transform=`rotate(${a}deg)`;if(a===90||a===270){$('camera').style.width='65%';$('camera').style.height='150%';}else{$('camera').style.width='100%';$('camera').style.height='100%';}};
  $('pause').onclick=()=>{if(replay)return notify('回放请使用录制窗口中的播放按钮');paused=!paused;if(paused){controls.suspend();servicePanel.suspend();if(latest)servicePanel.render(latest,{paused:true});}text('pause',paused?'▶ 继续显示':'Ⅱ 暂停显示');if(!paused&&latest)render(latest);else if(shown)text('last-update',`已暂停 · ${new Date(shown.at*1000).toLocaleTimeString()}`);notify(paused?'已暂停数字与姿态显示；后台仍在采集，摄像头不暂停':'已恢复实时显示');};
  $('export').onclick=exportRecording;
  document.querySelector('a[href="/api/recording"]').onclick=e=>{e.preventDefault();exportRecording();};
  document.querySelector('a[href="/api/servos.csv"]').onclick=e=>{if(rawTelemetry){e.preventDefault();exportCSV();}};
  $('group-filter').onclick=e=>{const b=e.target.closest('button');if(!b)return;group=b.dataset.group;$('group-filter').querySelectorAll('button').forEach(x=>x.classList.toggle('selected',x===b));if(shown)renderMotors(shown);};
  $('motor-search').oninput=()=>shown&&renderMotors(shown);
  $('motor-rows').onclick=e=>{const row=e.target.closest('[data-id]');if(row)choose(Number(row.dataset.id));};
  $('motor-rows').onkeydown=e=>{if(e.key==='Enter'){const row=e.target.closest('[data-id]');if(row)choose(Number(row.dataset.id));}};
  $('plot-field').onchange=drawHistory;
  $('ghost').onchange=()=>{if(duck){duck.showGhost=$('ghost').checked;duck.update(shown);}};
  $('heat').onchange=()=>{if(duck){duck.heat=$('heat').checked;duck.update(shown);}};
  $('reset-view').onclick=()=>{duck?.resetHeading();duck?.view('front');if(shown)render(shown,false);};document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>duck?.view(b.dataset.view));
  document.querySelectorAll('.sidebar nav a').forEach(a=>a.addEventListener('click',()=>{document.querySelectorAll('.sidebar nav a').forEach(x=>x.classList.toggle('active',x===a));}));
  $('replay-file').onchange=async()=>{
    try{const f=$('replay-file').files[0];if(!f)return;if(f.size>64*1024*1024)throw Error('记录不能超过 64 MB');
      const data=validateRecording(JSON.parse(await f.text()));clearInterval(replayTimer);replayTimer=null;controls.suspend();servicePanel.suspend();camera.disconnect();replay={frames:data.frames,index:0};paused=false;text('pause','Ⅱ 暂停显示');
      $('replay-controls').hidden=false;$('replay-range').max=replay.frames.length-1;text('replay-error','');openReplayAt(0);notify('已进入历史回放，不会连接或控制实机');
    }catch(e){text('replay-error',e.message);}
  };
  $('replay-range').oninput=()=>openReplayAt(Number($('replay-range').value));
  $('replay-play').onclick=()=>{if(replayTimer){clearInterval(replayTimer);replayTimer=null;return;}if(!replay)return;replayTimer=setInterval(()=>{if(replay.index>=replay.frames.length-1){clearInterval(replayTimer);replayTimer=null;}else openReplayAt(replay.index+1);},100);};
  $('replay-exit').onclick=()=>{clearInterval(replayTimer);replayTimer=null;replay=null;history=[];$('replay-controls').hidden=true;if(latest)render(latest);};
  if(cfg.raw_telemetry)rawTelemetry=new RawTelemetry(cfg,s=>{latest=s;apiOkay=true;if(!paused&&!replay)render(latest);},telemetryError);
  else poll();
  // Isolate renderer failure: the rest of the diagnostics must remain useful without WebGL.
  try{const {DuckView}=await import('./duck.js');duck=await new DuckView().init($('duck-canvas'),cfg.home,i=>choose(cfg.ids[i]));duck.selected=selected;if(shown)duck.update(shown);}
  catch(e){$('model-error').hidden=false;text('model-error',`3D 视图不可用：${e.message}。其他数据面板仍可使用。`);console.warn('Duck view:',e);}
}
window.addEventListener('beforeunload',()=>{rawTelemetry?.close();camera.disconnect(false);});
window.addEventListener('resize',()=>{drawHistory();if(shown)renderSystem(shown,sourceLive(shown,'system'));});
init().catch(e=>{$('connection-banner').hidden=false;text('connection-banner',`启动失败：${e.message}。请通过 Python 启动器打开，不要双击 HTML 文件。`);});
