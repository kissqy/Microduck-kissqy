import assert from 'node:assert/strict';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const source=path.resolve(process.argv[2]||'static');
const {ServicePanel}=await import(pathToFileURL(path.join(source,'service.js')));
function fixture(mode,shutdownPath){
  const nodes=new Map();
  const get=id=>{
    if(!nodes.has(id)){
      const classes=new Set();
      nodes.set(id,{value:'',disabled:false,checked:false,textContent:'',
        classList:{add(...values){for(const value of values)classes.add(value);},
          toggle(value,on){if(on)classes.add(value);else classes.delete(value);},
          contains(value){return classes.has(value);}}});
    }
    return nodes.get(id);
  };
  const panel=Object.assign(Object.create(ServicePanel.prototype),{
    cfg:{service_enabled:true},options:{},id:20,$:get,blocked:true,
    inspection:{render(){}},gamepadRepair:{render(){}},chorale:{render(){}},
    s:{bus:{mode},servos:[],channels:{},connection:{active:false,connected:false},
      connection_paused:true,service_control:{job:{action:'shutdown',at:2,status:'completed',
        result:{accepted:true,shutdown_requested:true,shutdown_path:shutdownPath}}}},
  });
  return {panel,get};
}
globalThis.document={hidden:false,activeElement:null};
const commissioning=fixture('commissioning','commissioning.systemctl');
const motion=fixture('motion','robot.shutdown');
// A previous failure's red class must be cleared by the accepted shutdown.
commissioning.get('service-power-job').classList.add('error');
for(const f of [commissioning,motion]){
  f.panel.paint();
  const feedback=f.get('service-power-job');
  assert.equal(feedback.classList.contains('completed'),true);
  assert.equal(feedback.classList.contains('error'),false);
  assert.match(feedback.textContent,/关机请求已接收/);
  assert.doesNotMatch(feedback.textContent,/关机请求未确认/);
  f.panel.s.channels={bus:{status:'error',error:'Connection reset by peer'}};
  f.panel.options.offline=true;f.panel.paint();
  assert.equal(feedback.classList.contains('completed'),true,'expected offline state retains green feedback');
  assert.equal(feedback.classList.contains('error'),false);
}
assert.equal(commissioning.get('service-power-job').textContent,motion.get('service-power-job').textContent);
console.log('PASS commissioning and motion use identical green shutdown feedback; expected disconnection keeps it green');
