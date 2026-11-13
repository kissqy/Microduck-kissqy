import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-connection155-'));
let raw;
try{
  const source=path.resolve(process.argv[2]||'static');
  fs.cpSync(source,path.join(temporary,'static'),{recursive:true});
  fs.writeFileSync(path.join(temporary,'package.json'),'{"type":"module"}');
  const load=name=>import(pathToFileURL(path.join(temporary,'static',name)));
  const {connectionNotice,startupFailure}=await load('startup-status.js');
  const {ServicePanel}=await load('service.js');
  const {RawTelemetry}=await load('raw-telemetry.js');
  const removed=new Set(['service-phase','service-torque','service-message','service-heading','service-mode-label','service-mode-indicator','service-startup','service-gait-status','service-gait-export']);
  const nodes=new Map(),get=id=>{
    assert.ok(!removed.has(id),'removed display must have no remaining renderer: '+id);
    if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',className:'',hidden:false,disabled:false,classList:{toggle(){}},setAttribute(){}});
    return nodes.get(id);
  };
  globalThis.document={hidden:false,activeElement:null,getElementById:get};
  const panel=Object.create(ServicePanel.prototype);
  Object.assign(panel,{cfg:{service_enabled:true,connection_ui:true},$:get,id:20,options:{},posting:false,
    inspection:{render(){}},gamepadRepair:{render(){}}});
  const app=fs.readFileSync(path.join(source,'app.js'),'utf8');
  const bannerStart=app.indexOf("  const cb=$('connection-banner');");
  const bannerEnd=app.indexOf('\n}\nfunction renderTof',bannerStart);
  assert.ok(bannerStart>=0&&bannerEnd>bannerStart,'test must execute the actual top-banner render fragment');
  const bannerPaint=new Function('$','s','cfg','apiOkay','replay','service','sy','connectionNotice',app.slice(bannerStart,bannerEnd));
  const config={connection_ui:true,baseline:'1fa84386'};
  const waiting=()=>Object.fromEntries(['state','health','bus','system','capabilities'].map(name=>[name,{status:'waiting',error:'',age_ms:null,seq:0}]));
  const snapshot=(overrides={})=>({mode:'service',channels:waiting(),connection_paused:false,
    connection:{active:true,connected:false,error:''},bus:{},health:{},state:{},servos:[],imu:{},
    service_sample_fresh:false,service_compatible:true,service_control:{},...overrides});
  function paint(s,{replay=false,cfg=config}={}){
    const original=structuredClone(s);
    bannerPaint(get,s,cfg,true,replay,s.mode==='service',s.channels.system?.status==='live',connectionNotice);
    panel.s=s;panel.options={replay};panel.cfg.connection_ui=cfg.connection_ui;panel.paint();
    assert.deepEqual(s,original,'presentation must not modify telemetry or control state');
    return {notice:connectionNotice(s,{connectionUI:cfg.connection_ui}),banner:get('connection-banner')};
  }
  {
    const s=snapshot({connection_paused:true,connection:{active:false,connected:false}});
    const {banner}=paint(s);assert.equal(banner.hidden,true);
    
  }
  {
    // A leftover reason by itself is not a current health response.
    const s=snapshot({health:{healthy:false,reason:'old IMU missing'}});
    const {notice,banner}=paint(s);assert.equal(notice.tone,'neutral');
    assert.equal(banner.className,'banner neutral');assert.match(banner.textContent,/正在连接 Zero/);
    assert.doesNotMatch(banner.textContent,/IMU|15 颗|检查|失败|异常/);
  }
  {
    const s=snapshot({connection:{active:true,connected:true,error:''}});
    const {banner}=paint(s);assert.equal(banner.className,'banner neutral');
    assert.match(banner.textContent,/SSH 已连接.*首次完整反馈/);
    
    s.channels.health={status:'live',seq:1,age_ms:0};
    s.health={healthy:false,reason:'control loop has not completed a cycle yet'};
    s.channels.bus={status:'live',seq:1,age_ms:0};s.bus={phase:'recovering_uart'};
    const starting=paint(s);assert.equal(starting.banner.className,'banner neutral');
    
  }
  {
    const s=snapshot();s.channels.state={status:'error',error:'SSH 登录失败：密码错误',seq:0,age_ms:null};
    s.channels.bus={...s.channels.state};s.connection.error=s.channels.state.error;
    const {banner}=paint(s);assert.equal(banner.className,'banner warning');
    assert.match(banner.textContent,/SSH 登录失败/);
  }
  const live=snapshot({connection:{active:true,connected:true,error:''},service_sample_fresh:true,
    bus:{mode:'motion',phase:'control',native:{torque_state_confirmed:false}},health:{healthy:true}});
  live.channels.bus={status:'live',seq:2,age_ms:0};live.channels.state={status:'live',seq:2,age_ms:0};
  live.channels.health={status:'live',seq:1,age_ms:0};
  {
    const {banner}=paint(live);assert.equal(banner.hidden,true);
    const early=structuredClone(live);early.connection.connected=false;
    assert.equal(paint(early).banner.hidden,true,'native feedback is authoritative before the next SSH auxiliary update');
    const lost=structuredClone(live);lost.service_sample_fresh=false;
    lost.channels.bus={status:'error',error:'Connection reset by peer',seq:2,age_ms:1200};
    lost.channels.state={...lost.channels.bus};
    const broken=paint(lost);assert.equal(broken.banner.className,'banner warning');
    assert.match(broken.banner.textContent,/机器人服务连接异常/);
    const stale=structuredClone(live);stale.service_sample_fresh=false;
    stale.channels.bus.status='stale';stale.channels.state.status='stale';
    const delayed=paint(stale);assert.match(delayed.banner.textContent,/旧反馈/);
    const unfresh=structuredClone(live);unfresh.service_sample_fresh=false;
    
  }
  {
    const failed=structuredClone(live);failed.bus={phase:'configuration_error',error:'torque readback missing [10]'};
    failed.service_sample_fresh=false;failed.channels.bus.status='stale';failed.channels.state=waiting().state;
    const failure=paint(failed);assert.match(failure.banner.textContent,/总线启动失败.*torque readback/);
    
    failed.channels.health.status='stale';assert.equal(startupFailure(failed),'');
    const disconnected=structuredClone(live);disconnected.connection_paused=true;disconnected.connection.active=false;
    disconnected.bus={phase:'configuration_error',error:'previous robot failure'};
    const off=paint(disconnected);assert.equal(off.banner.hidden,true);
    assert.equal(startupFailure(disconnected),'');
    const realHealth=structuredClone(live);realHealth.health={healthy:false,reason:'policy unavailable: bad contract'};
    assert.match(paint(realHealth).banner.textContent,/机器人服务报告异常/);
    const legacy=snapshot();legacy.channels.state={status:'error',error:'Connection refused'};
    legacy.channels.bus={...legacy.channels.state};delete legacy.connection;
    assert.equal(paint(legacy,{cfg:{...config,connection_ui:false}}).banner.className,'banner warning');
    const revision=structuredClone(live);revision.service_compatible=false;
    revision.channels.system={status:'live',age_ms:0,seq:1};revision.system={identities:{robotd:{revision:'old-build'}}};
    assert.match(paint(revision).banner.textContent,/运行标识 old-build/,'current incompatible identity remains visible');
    revision.connection_paused=true;revision.connection.active=false;
    assert.equal(paint(revision).banner.hidden,true,'a retained old system identity is not a new connection failure');
  }
  {
    // Drive actual generation/reset handling; no previous report may become
    // a freshly timestamped failure in the replacement SSH session.
    globalThis.location={protocol:'http:',host:'localhost:8765'};
    globalThis.WebSocket=class{constructor(){this.close=()=>{};}};
    raw=new RawTelemetry({version:'1.0.155',mode:'service',control_token:'test',ids:[],names:[],labels:[]},()=>{},()=>{});
    let now=0;raw.store.clock=()=>now;
    const message=value=>raw.socket.onmessage({data:JSON.stringify(value)});
    message({reset:1});
    message({aux:{connection_paused:false,connection:{active:true,connected:true}},generation:1});
    message({event:{channel:'bus',data:{mode:'motion',phase:'configuration_error',error:'old device missing'}}});
    message({event:{channel:'health',data:{healthy:false,reason:'motor bus startup: old device missing'}}});
    message({event:{channel:'system',data:{identities:{robotd:{revision:'previous-device'}}}}});
    assert.match(connectionNotice(raw.store.snapshot(false),{connectionUI:true}).message,/old device missing/);
    message({reset:2,preserve:true});
    assert.equal(connectionNotice(raw.store.snapshot(false),{connectionUI:true}).hidden,true);
    message({reset:3});
    message({aux:{connection_paused:false,connection:{active:true,connected:false}},generation:3});
    message({aux:{connection_paused:false,connection:{active:true,connected:true,error:'old error'}},generation:1});
    assert.equal(raw.store.snapshot(false).connection.connected,false);
    assert.deepEqual(raw.store.snapshot(false).system,{},'new connection clears the old identity as well as startup reports');
    const reconnect=connectionNotice(raw.store.snapshot(false),{connectionUI:true});
    assert.equal(reconnect.tone,'neutral');assert.doesNotMatch(reconnect.message,/old device|old error|失败/);
    message({aux:{connection:{active:true,connected:true}},generation:3});
    message({event:{channel:'bus',data:{build:'1fa8438-feetech-ft6-control.33',mode:'motion',phase:'control',fresh_sample:true,native:{sample_age_ms:0}}}});
    message({event:{channel:'state',data:{joints:[]}}});
    assert.equal(connectionNotice(raw.store.snapshot(false),{connectionUI:true}).hidden,true);
    now=2;
    assert.match(connectionNotice(raw.store.snapshot(false),{connectionUI:true}).message,/旧反馈/);
  }
  assert.doesNotMatch(fs.readFileSync(path.join(source,'startup-status.js'),'utf8'),/setInterval|setTimeout|fetch\(/,'no timer or extra poller may mask startup faults');
  console.log('PASS duplicate status UI removed; connection pending/first feedback neutral; real SSH, state, health and startup failures visible; stale data warning; actual banner and ServicePanel.paint agree; generation reset retires old reports; no telemetry mutation');
}finally{
  raw?.close();fs.rmSync(temporary,{recursive:true,force:true});
}
