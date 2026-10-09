
const $=id=>document.getElementById(id);
const set=(id,v)=>{const e=$(id);if(e)e.textContent=String(v)};
const toast=m=>{const e=$('toast');if(!e)return;e.textContent=m;e.hidden=false;clearTimeout(window.__toast);window.__toast=setTimeout(()=>e.hidden=true,2200)};
const joints=[
 ['左髋 yaw',20,'left',0],['左髋 roll',21,'left',-5],['左髋 pitch',22,'left',-26.24],['左膝',23,'left',-0.28],['左踝',24,'left',25.95],
 ['右髋 yaw',10,'right',0],['右髋 roll',11,'right',5],['右髋 pitch',12,'right',26.24],['右膝',13,'right',0.28],['右踝',14,'right',-25.95],
 ['颈 yaw',30,'head',20],['颈 pitch',31,'head',20],['头',32,'head',0],['嘴',33,'head',0],['颈',34,'head',0]
];
let paused=false, selected=0, started=performance.now();

const style=document.createElement('style');
style.textContent=`
#duck-canvas{position:relative;overflow:hidden;background:radial-gradient(circle at 50% 65%,#1c272a 0,#101619 55%,#0b1012 100%)}
.demo-duck{position:absolute;left:50%;top:50%;width:150px;height:220px;transform:translate(-50%,-50%);transition:transform .25s}
.demo-head{position:absolute;left:31px;top:0;width:88px;height:88px;background:#f4d65e;border-radius:50%;box-shadow:inset -10px -8px #e7c64a}
.demo-head:before,.demo-head:after{content:"";position:absolute;top:29px;width:9px;height:12px;background:#111;border-radius:50%}.demo-head:before{left:25px}.demo-head:after{right:25px}
.demo-beak{position:absolute;left:54px;top:56px;width:42px;height:16px;background:#ef9c3e;border-radius:55%}
.demo-body{position:absolute;left:42px;top:77px;width:66px;height:80px;background:#e8eef0;border-radius:45% 45% 35% 35%}
.demo-leg{position:absolute;top:145px;width:17px;height:58px;background:#c7d1d3;border-radius:9px}.demo-leg.l{left:48px}.demo-leg.r{right:48px}.demo-foot{position:absolute;bottom:0;width:41px;height:11px;background:#ef9c3e;border-radius:8px}.demo-leg.l .demo-foot{left:-22px}.demo-leg.r .demo-foot{right:-22px}
.demo-floor{position:absolute;left:8%;right:8%;bottom:10%;height:1px;background:#314044}
.demo-watermark{position:absolute;left:12px;top:12px;padding:5px 8px;border:1px solid #3c4b4f;border-radius:6px;color:#81918f;background:#0b1012cc;font-size:11px}
`;
document.head.appendChild(style);
if($('duck-canvas')) $('duck-canvas').innerHTML='<div class="demo-floor"></div><div class="demo-watermark">FAKE ROBOT · 在线演示</div><div class="demo-duck" id="demo-duck"><div class="demo-head"></div><div class="demo-beak"></div><div class="demo-body"></div><div class="demo-leg l"><div class="demo-foot"></div></div><div class="demo-leg r"><div class="demo-foot"></div></div></div>';

function initStatic(){
  set('runtime-revision','1fa8438-feetech-ft6-control.29 · DEMO');
  set('side-status','Fake Robot 在线'); set('console-version','Console · R17 v1.0.146 Demo');
  set('mode-chip','DEMO / FAKE ROBOT'); set('access-chip','◈ GitHub Pages'); set('robot-name','duck-demo');
  set('ssh-status','在线演示：SSH 已禁用'); set('service-sudo-status','不会保存密码');
  ['ssh-target','service-sudo-password','ssh-connect','ssh-disconnect','service-sudo-forget'].forEach(id=>{if($(id))$(id).disabled=true});
  if($('connection-banner')){$('connection-banner').hidden=false;set('connection-banner','GitHub Pages 在线演示：所有机器人数据均为 Fake Robot 模拟值，不连接真实 Zero、robotd、padd 或舵机。')}
  set('pose-badge','模拟姿态'); set('camera-badge','Demo'); set('camera-message','演示模式 · 不连接真实 IMX219');
  set('camera-address','真实中控通过 WebRTC 连接 Zero；这里仅展示界面。'); set('camera-capture','Demo 不访问摄像头。');
  ['camera-connect','camera-disconnect'].forEach(id=>{if($(id))$(id).disabled=true});
  set('camera-fps','30 fps'); set('camera-bitrate','2.4 Mb/s'); set('camera-loss','0');
  set('control-status','DEMO'); set('control-volume-value','72'); set('control-mouth-value','45');
  if($('control-volume')){$('control-volume').disabled=false;$('control-volume').value=72}
  if($('control-mouth')){$('control-mouth').disabled=false;$('control-mouth').value=45}
  set('control-audio-status','Fake Robot：音量与嘴部幅度仅演示'); set('control-reason','不会向 padd 发送输入');
  set('control-link-latency','Fake input · 0 ms'); set('control-model','行走老师 10000 · Demo');
  set('parameter-status','Demo'); set('parameter-action','0.70'); set('parameter-action-default','行走 / 保持');
  set('parameter-sit','1.00'); set('parameter-head','0.50'); set('parameter-legs','0.70');
  set('parameter-voltage','7.2 V'); set('parameter-actual','Fake Robot'); set('control-readback','在线演示不写入任何机器人参数。');
  set('imu-badge','实时'); set('imu-ready','YES'); set('imu-stale','0 ms'); set('imu-gravity','0.015 / -0.020 / -0.999');
  set('imu-gyro','0.01 / -0.02 / 0.00'); set('imu-quat','0.000 / 0.008 / -0.010 / 0.999');
  set('tof-badge','实时'); set('tof-near','214 mm'); set('tof-far','816 mm'); set('tof-valid','64 / 64'); set('tof-seq','12842');
  set('tof-message','VL53L8CX · Fake data'); set('tof-detail','8×8 距离阵列模拟');
  if($('tof-grid')) $('tof-grid').innerHTML=Array.from({length:64},(_,i)=>'<i style="opacity:'+(0.35+(i%8)/14)+'"></i>').join('');
  set('odom-x','0.12 m'); set('odom-y','-0.03 m'); set('odom-yaw','3.4°');
  set('sys-cpu','18%'); set('sys-memory','31%'); set('sys-temp','64 °C'); set('sys-uptime','00:18:42');
  if($('cpu-bar'))$('cpu-bar').style.width='18%'; if($('memory-bar'))$('memory-bar').style.width='31%';
  set('health-badge','正常'); set('health-detail','15 / 15 舵机实时 · IMU READY · Fake Robot');
  set('move-request','0.00 / 0.00 / 0.00'); set('move-applied','0.00 / 0.00 / 0.00'); set('move-limits','Demo：没有真实动作输出。');
  if($('channel-list')) $('channel-list').innerHTML=['robot.state','robot.health','servo bus','IMU','ToF','system'].map(x=>'<div><span class="status-dot"></span><b>'+x+'</b><small>Fake · live</small></div>').join('');
  set('system-log-status','Demo 日志');
  set('system-log-output','[demo] R17 v1.0.146 online preview\n[demo] Fake Robot connected\n[demo] 15 servos ready\n[demo] IMU ready\n[demo] No real hardware commands are sent.');
  set('raw-json','{"schema":"microduck-console/v1","mode":"demo","robot":"fake","servos":15,"imu":"ready"}');
  if($('events')) $('events').innerHTML='<div><b>Demo started</b><span>Fake Robot 数据源已启用</span></div>';
  set('settings-mode','GitHub Pages Demo'); if($('camera-host'))$('camera-host').value='duck-demo.local';
  document.querySelectorAll('#control-panel button,[data-head-amplitude]').forEach(b=>b.addEventListener('click',e=>{e.preventDefault();toast('Demo：'+(b.textContent.trim()||'模拟按键'))}));
  document.querySelectorAll('[data-demo-download]').forEach(a=>a.onclick=e=>{e.preventDefault();toast('Demo 页面不提供真实机器人下载')});
  if($('pause')) $('pause').onclick=()=>{paused=!paused;set('pause',paused?'▶ 继续显示':'Ⅱ 暂停显示');toast(paused?'Demo 已暂停':'Demo 已继续')};
  if($('export')) $('export').onclick=()=>{const blob=new Blob([JSON.stringify({schema:'microduck-console/v1',mode:'demo',servos:15,imu:'ready'},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='microduck-demo-recording.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
  if($('motor-search')) $('motor-search').addEventListener('input',renderMotors);
  document.querySelectorAll('#group-filter button').forEach(b=>b.onclick=()=>{document.querySelectorAll('#group-filter button').forEach(x=>x.classList.remove('selected'));b.classList.add('selected');renderMotors()});
}
function renderMotors(){
  const t=performance.now(),filter=document.querySelector('#group-filter .selected')?.dataset.group||'all',q=($('motor-search')?.value||'').trim().toLowerCase();
  const rows=joints.map((j,i)=>({name:j[0],id:j[1],group:j[2],base:j[3],i,actual:j[3]+Math.sin(t/850+i*.57)*2.2,target:j[3]+Math.sin(t/920+i*.49)*2.0,v:7.19+Math.sin(t/1800+i)*.08,temp:36+(i%5)+Math.sin(t/2700+i)}))
    .filter(r=>(filter==='all'||r.group===filter)&&(!q||r.name.toLowerCase().includes(q)||String(r.id).includes(q)));
  if($('motor-rows')) $('motor-rows').innerHTML=rows.map(r=>'<tr data-i="'+r.i+'"><td><strong>'+r.name+'</strong><small>ID '+r.id+'</small></td><td>'+r.target.toFixed(1)+'°</td><td>'+r.actual.toFixed(1)+'°</td><td>'+r.v.toFixed(2)+' V</td><td>'+r.temp.toFixed(1)+' °C</td><td><span class="badge">实时</span></td></tr>').join('');
  document.querySelectorAll('#motor-rows tr').forEach(tr=>tr.onclick=()=>{selected=+tr.dataset.i;paintSelected()});
}
function paintSelected(){
  const t=performance.now(),j=joints[selected],actual=j[3]+Math.sin(t/850+selected*.57)*2.2,target=j[3]+Math.sin(t/920+selected*.49)*2.0;
  set('selected-joint',j[0]+' · ID '+j[1]); set('chart-label','模拟反馈'); set('target-label','目标 '+target.toFixed(1)+'° / 实际 '+actual.toFixed(1)+'°');
  if($('joint-registers')) $('joint-registers').innerHTML='<div><span>通信</span><b>OK</b></div><div><span>扭矩</span><b>ON · DEMO</b></div><div><span>当前位置</span><b>'+actual.toFixed(1)+'°</b></div><div><span>电压</span><b>7.2 V</b></div>';
}
function draw(id,values,min,max,color){
  const c=$(id);if(!c)return;const w=Math.max(120,c.clientWidth||220),h=Math.max(32,c.clientHeight||44),d=devicePixelRatio||1;c.width=w*d;c.height=h*d;
  const x=c.getContext('2d');x.setTransform(d,0,0,d,0,0);x.clearRect(0,0,w,h);x.strokeStyle=color;x.lineWidth=1.4;x.beginPath();
  values.forEach((v,i)=>{const px=i/(values.length-1)*w,py=h-(v-min)/(max-min)*h;i?x.lineTo(px,py):x.moveTo(px,py)});x.stroke();
}
const H=Array(64).fill(50),V=Array(64).fill(7.2),T=Array(64).fill(39);
function tick(){
  if(paused)return;const t=performance.now(),hz=50+Math.sin(t/1200)*.35,v=7.22+Math.sin(t/2100)*.07,temp=39+Math.sin(t/3000)*2.1,z=64+Math.sin(t/3900)*1.3,roll=Math.sin(t/2200)*2.2,pitch=Math.sin(t/2700)*1.5;
  set('metric-hz',hz.toFixed(1));set('loop-caption','目标 50 Hz · Fake Robot');set('metric-joints','15');set('joint-caption','15 / 15 实时');set('metric-volts',v.toFixed(2));set('metric-temp',temp.toFixed(1));set('temp-caption','Fake servo telemetry');set('metric-zero-temp',z.toFixed(1));set('zero-temp-caption','Fake Zero temperature');set('last-update','刚刚 · Demo');
  set('hud-roll',roll.toFixed(1)+'°');set('hud-pitch',pitch.toFixed(1)+'°');set('hud-yaw',(Math.sin(t/6000)*4).toFixed(1)+'°');set('pose-label','Fake Robot · 模拟姿态');
  set('imu-roll',roll.toFixed(1)+'°');set('imu-pitch',pitch.toFixed(1)+'°');
  if($('horizon'))$('horizon').style.transform='rotate('+(-roll)+'deg) translateY('+(pitch*1.4)+'px)';
  if($('demo-duck'))$('demo-duck').style.transform='translate(-50%,-50%) rotate('+(roll*.5)+'deg)';
  H.push(hz);H.shift();V.push(v);V.shift();T.push(temp);T.shift();draw('mini-loop',H,30,60,'#c1f577');draw('mini-volts',V,4,8,'#7caedd');draw('mini-temp',T,20,70,'#e2b977');
  renderMotors();paintSelected();
}
initStatic();tick();setInterval(tick,500);
