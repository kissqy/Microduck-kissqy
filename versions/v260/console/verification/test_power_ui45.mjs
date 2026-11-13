import assert from 'node:assert/strict';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const source=path.resolve(process.argv[2]||'static');
const {ServicePanel}=await import(pathToFileURL(path.join(source,'service.js')));

function fixture(){
  const nodes=new Map(),sent=[],feedback=[];
  const get=id=>{if(!nodes.has(id))nodes.set(id,{value:'',disabled:false,checked:false,textContent:''});return nodes.get(id);};
  globalThis.document={hidden:false};
  const panel=Object.assign(Object.create(ServicePanel.prototype),{
    cfg:{service_enabled:true,control_token:'test'},options:{},client:'power-ui45',seq:0,
    blocked:true,posting:false,ownsMotion:false,lastSample:0,id:20,$:get,
    inspection:{render(){}},gamepadRepair:{render(){}},chorale:{render(){}},
    feedback(...args){feedback.push(args);},
    s:{bus:{},channels:{},service_control:{},servos:[],connection:{active:true,connected:true}},
  });
  get('service-sudo-password').value='private-sudo';
  globalThis.fetch=async(url,options)=>{
    sent.push({url,body:JSON.parse(options.body)});
    return {ok:true,json:async()=>({accepted:true,message:'request accepted'})};
  };
  return {panel,get,sent,feedback};
}

{
  const f=fixture();
  await f.panel.post({action:'shutdown'});
  assert.equal(f.sent.length,1);
  assert.deepEqual(f.sent[0].body.command,{action:'shutdown',sudo_password:'private-sudo'},'shutdown passes the existing credential for commissioning; motion mode ignores it');
  assert.equal(f.panel.ownsMotion,false);
}
{
  const f=fixture();
  await f.panel.post({action:'reboot'});
  assert.equal(f.sent.length,1);
  assert.equal(f.sent[0].body.command.sudo_password,'private-sudo','OS reboot keeps the existing privileged path');
}
{
  const f=fixture();
  f.panel.paint();
  assert.match(f.get('service-power-state').textContent,/运动模式使用官方关机；标定模式确认卸力后关机/);
  f.panel.s.service_control.job={action:'shutdown',at:1,status:'running'};
  f.panel.paint();assert.match(f.get('service-power-state').textContent,/正在提交关机请求/);
  f.panel.s.service_control.job={action:'shutdown',at:2,status:'completed',result:{accepted:true,shutdown_requested:true,shutdown_path:'robot.shutdown'}};
  f.panel.paint();
  assert.match(f.get('service-power-state').textContent,/关机请求已接收/);
  assert.match(f.get('service-power-state').textContent,/尚未确认关机完成/);
  assert.match(f.feedback.at(-1)[1],/尚未确认关机完成/,'job completion means request accepted, not power-off observed');
  f.panel.s.service_control.job={action:'shutdown',at:3,status:'completed',result:{scheduled:true}};
  f.panel.paint();
  assert.match(f.get('service-power-state').textContent,/尚未确认关机请求已接收/);
  assert.match(f.feedback.at(-1)[1],/未取得关机接收确认/,'historical OS receipts cannot masquerade as the new official path');
  f.panel.s.service_control.job={action:'shutdown',at:4,status:'error',error:'robotd unavailable'};
  f.panel.paint();
  assert.match(f.get('service-power-state').textContent,/robotd unavailable/);
  assert.match(f.feedback.at(-1)[1],/关机请求未确认.*robotd unavailable/);
}
{
  const f=fixture();
  for(const change of [
    ()=>f.panel.s.connection={active:false,connected:false},
    ()=>f.panel.s.connection={active:true,connected:false},
    ()=>f.panel.s.connection_paused=true,
    ()=>f.panel.options.offline=true,
    ()=>f.panel.options.replay=true,
  ]){
    f.panel.s.connection={active:true,connected:true};f.panel.s.connection_paused=false;f.panel.options={};
    change();f.panel.paint();
    assert.equal(f.get('service-shutdown').disabled,true);
    await f.panel.post({action:'shutdown'});
    assert.equal(f.sent.length,0,'unconnected or replay state cannot send an official shutdown');
  }
  f.panel.options={};f.panel.s.connection={active:true,connected:true};f.panel.s.connection_paused=false;
  f.panel.paint();assert.equal(f.get('service-shutdown').disabled,false,'SSH authentication is sufficient without IMU telemetry');
  // This fixture creates plain nodes; the production title is set by mount().
  await f.panel.post({action:'shutdown'});assert.equal(f.sent.length,1);
}
console.log('PASS shutdown credential forwarding for commissioning, motion/commissioning receipt UI, disconnected/offline/replay gates, privileged reboot and request-vs-powered-off wording');
