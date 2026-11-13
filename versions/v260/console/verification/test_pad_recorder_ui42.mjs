import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-recorder-ui42-'));
const performanceDescriptor=Object.getOwnPropertyDescriptor(globalThis,'performance');
try{
  const source=path.resolve(process.argv[2]||'static');
  fs.cpSync(source,path.join(temporary,'static'),{recursive:true});
  fs.writeFileSync(path.join(temporary,'package.json'),'{"type":"module"}');
  const {ControlPanel,recorderLabel}=await import(pathToFileURL(path.join(temporary,'static/control.js')));
  const report={available:true,checked_ms:10000,phase:'idle',elapsed_ms:1200,duration_ms:6000,has_last:true,reason:''};
  const label=change=>recorderLabel({...report,...change});
  assert.equal(label({phase:'recording'}),'录放：录制中 1.2秒');
  assert.equal(label({phase:'recording',reason:'请松开摇杆并等动作/表情结束后，再按保存'}),'录放：录制中 1.2秒 · 请松开摇杆并等动作/表情结束后，再按保存','a refused save must explain why recording continues');
  assert.equal(label({phase:'saving'}),'录放：保存中 6秒');
  assert.equal(label({phase:'playing'}),'录放：播放中 1.2秒 / 6秒');
  assert.equal(label({phase:'pending'}),'录放：等待按键判定');
  assert.equal(label({phase:'pending',reason:'正在检查回放'}),'录放：正在检查回放');
  assert.equal(label({phase:'idle'}),'录放：已保存 6秒');
  assert.equal(label({phase:'idle',has_last:false}),'录放：尚未录制');
  assert.equal(label({phase:'error',reason:'实体手柄已断开'}),'录放：实体手柄已断开');
  assert.equal(label({available:false,reason:'安装配套更新后支持录放'}),'录放：安装配套更新后支持录放');
  assert.equal(recorderLabel(report,false),'录放：等待回读');
  assert.equal(recorderLabel(undefined),'录放：等待回读');
  for(const change of [{phase:'saved'},{duration_ms:-1},{elapsed_ms:NaN},{has_last:1}])assert.equal(label(change),'录放：状态无效');

  let now=0;
  Object.defineProperty(globalThis,'performance',{configurable:true,value:{now:()=>now}});
  const nodes=new Map();
  const node=selector=>{
    if(!nodes.has(selector))nodes.set(selector,{value:'',textContent:'',dataset:{},classList:{toggle(){}},setAttribute(){}});
    return nodes.get(selector);
  };
  const control=Object.create(ControlPanel.prototype);
  Object.assign(control,{root:{querySelector:node,querySelectorAll:()=>[]},cfg:{service_enabled:true},options:{},connected:true,
    s:{control:{connected:true},bus:{}},state:{available:true,event_authoritative:true,real_connected:true,drive_speed:{recorder:{...report,phase:'recording'}}},
    pad:{paint(){}},servicePaused:()=>false});
  const paint=()=>{control.paint();return node('#control-recorder').textContent;};
  assert.match(paint(),/录制中/);
  now=3500;assert.match(paint(),/录制中/,'display receipt stays visible within its local freshness window');
  now=3501;assert.equal(paint(),'录放：等待回读','cached SSH state cannot show continuing recording forever');
  control.state.drive_speed.recorder={...report,checked_ms:11000};
  assert.match(paint(),/已保存 6秒/,'a new server validation receipt restores saved status');
  for(const change of [()=>control.connected=false,()=>control.s.control.connected=false,()=>control.state.available=false,()=>control.s.control.webpad={available:false},
                      ()=>control.options.replay=true,()=>control.options.offline=true,()=>control.servicePaused=()=>true]){
    control.connected=true;control.s.control={connected:true};control.state.available=true;control.options={};control.servicePaused=()=>false;
    change();assert.equal(paint(),'录放：等待回读','disconnect, maintenance and offline views never imply live success');
  }
  control.connected=true;control.options={};control.servicePaused=()=>false;control.state.drive_speed={supported:true};
  assert.equal(paint(),'录放：安装配套更新后支持录放','old payload with no report offers an update hint instead of retaining a prior saved state');
  control.state.drive_speed={supported:false};
  assert.equal(paint(),'录放：安装配套更新后支持录放','a missing installed drive helper also needs the matching firmware');

  const ordered=Object.create(ControlPanel.prototype);
  Object.assign(ordered,{root:control.root,cfg:{service_enabled:true},options:{},connected:true,linkEpoch:0,epoch:0,seq:0,client:'recorder-order-test',
    s:{control:{connected:true},bus:{}},state:{available:true,event_authoritative:true,real_connected:false},
    pad:{paint(){},reset(){}},frames:[],feedback:{textContent:''},servicePaused:()=>false});
  const receipt=(elapsed_ms,t_ms,checked_ms,change={})=>({...report,pid:42,t_ms,checked_ms,phase:'recording',elapsed_ms,...change});
  const status=recorder=>({accepted:true,available:true,event_authoritative:true,real_connected:false,drive_speed:{recorder}});
  const shown=()=>node('#control-recorder').textContent;
  const event=recorder=>{ordered.state={...ordered.state,...status(recorder)};ordered.paint();return shown();};
  const snapshot=recorder=>{ordered.render({control:{connected:true,webpad:status(recorder)},bus:{}});return shown();};
  const old=receipt(12000,112000,112100),latest=receipt(13000,113000,113100);
  now=10000;assert.equal(event(latest),'录放：录制中 13秒');
  now=10050;assert.equal(snapshot(old),'录放：录制中 13秒','older telemetry cannot replace a newer input-status receipt');
  now=10100;ordered.socket={request:async()=>status(old)};
  await ordered.post({action:'webpad_close'});
  assert.equal(shown(),'录放：录制中 13秒','an older command reply cannot rewind recorder display either');
  for(let elapsed=200;elapsed<=3400;elapsed+=200){now=10000+elapsed;elapsed%400?event(latest):snapshot(old);}
  assert.equal(ordered.recorderReceived,10000,'repeated or decreasing checked_ms cannot renew freshness');
  now=13500;assert.equal(event(latest),'录放：录制中 13秒');
  now=13501;assert.equal(snapshot(old),'录放：等待回读','alternating cached sources must expire after 3500ms');
  now=14000;assert.equal(event({...latest,checked_ms:113200}),'录放：录制中 13秒','a strictly newer validation receipt restores freshness');
  const saving=receipt(0,114000,114100,{phase:'saving',duration_ms:13000});
  now=14100;assert.equal(event(saving),'录放：保存中 13秒');
  now=14200;assert.equal(snapshot({...latest,checked_ms:114200}),'录放：保存中 13秒','a newer validation of an older native stamp cannot revive recording');
  assert.equal(ordered.recorderReceived,14100,'rejected native timestamps cannot renew freshness');
  assert.equal(ordered.recorderChecked,114100);
  const saved=receipt(0,115000,115100,{phase:'idle',duration_ms:13000});
  now=14300;assert.equal(event(saved),'录放：已保存 13秒');
  assert.equal(snapshot(saving),'录放：已保存 13秒','late saving reports cannot undo completion');
  now=14400;assert.equal(event(receipt(0,116000,116100,{phase:'playing',duration_ms:13000})),'录放：播放中 0秒 / 13秒');
  now=14500;assert.equal(event(receipt(1200,117000,117100,{phase:'playing',duration_ms:13000})),'录放：播放中 1.2秒 / 13秒');
  now=14600;assert.equal(event(receipt(0,118000,118100)),'录放：录制中 0秒','a new recording with a newer native stamp starts at zero');
  now=14700;assert.equal(event(receipt(0,118500,118600,{pid:77})),'录放：录制中 0秒','a new native process starts at zero');
  assert.equal(snapshot(receipt(13000,118000,118100)),'录放：录制中 0秒','a cached report from the previous process is rejected');
  now=14800;assert.equal(event(receipt(0,119000,119100,{phase:'error',reason:'实体手柄已断开'})),'录放：实体手柄已断开');
  now=14900;assert.equal(event(receipt(0,120000,120100,{phase:'unknown'})),'录放：状态无效');
  now=15000;assert.equal(event({available:false,checked_ms:120200,reason:'录放状态已过期或时钟无效'}),'录放：录放状态已过期或时钟无效');

  for(const block of [
    ()=>ordered.connected=false,()=>ordered.s.control.connected=false,()=>ordered.state.available=false,
    ()=>ordered.s.control.webpad={available:false},()=>ordered.options={replay:true},
    ()=>ordered.options={offline:true},()=>ordered.servicePaused=()=>true,
  ]){
    block();ordered.paint();assert.equal(shown(),'录放：等待回读');
    assert.equal(ordered.recorderChecked,undefined,'non-live views clear ordering context');
    ordered.connected=true;ordered.s={control:{connected:true},bus:{}};ordered.state={available:true};ordered.options={};ordered.servicePaused=()=>false;
    now+=100;assert.equal(event(receipt(0,10,20)),'录放：录制中 0秒','a fresh connection context accepts a lower monotonic clock');
  }
  ordered.linkEpoch++;
  assert.equal(event(receipt(0,1,2,{pid:99})),'录放：录制中 0秒','a target/link epoch change clears the previous ordering context');

  const html=fs.readFileSync(path.join(source,'index.html'),'utf8');
  assert.match(html,/<span class="section-index" id="ai-release-version">AI · 等待版本<\/span>/);
  assert.doesNotMatch(html,/AI · UI\d+/,'AI release must come from the console identity');
  assert.equal([...html.matchAll(/id="control-recorder"/g)].length,1);
  assert.match(html,/<p id="control-recorder"[^>]+role="status"[^>]+实体手柄 Logo：双击开始录制；录制中单击停止并保存；空闲单击等350ms后回放；回放中单击取消；长按忽略。/);
  assert.doesNotMatch(html,/单击录制／停止并覆盖 last；双击回放/,'Logo help must not retain the old overwrite-prone mapping');
  assert.doesNotMatch(html,/<button[^>]*(?:id|data-button)="[^"]*recorder/);
  assert.match(html,/data-button="start"/);
  assert.match(fs.readFileSync(path.join(source,'control.js'),'utf8'),/关闭策略 \/ 回 HOME/);
  console.log('PASS recorder labels, ordered event/snapshot/command receipts, stale replay expiry, new recording/process resets, disconnect/maintenance/replay suppression and readonly Logo help');
}finally{
  if(performanceDescriptor)Object.defineProperty(globalThis,'performance',performanceDescriptor);
  fs.rmSync(temporary,{recursive:true,force:true});
}
