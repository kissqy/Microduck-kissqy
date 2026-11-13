import assert from 'node:assert/strict';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const source=path.resolve(process.argv[2]||'static');
const {ServicePanel}=await import(pathToFileURL(path.join(source,'service.js')));
const nodes=new Map();
const get=id=>{
  if(!nodes.has(id))nodes.set(id,{disabled:false,checked:false,value:'',textContent:'',className:'',classList:{add(){},remove(){},toggle(){}},contains(){return false}});
  return nodes.get(id);
};
let choice=false,calls=0,confirms=0;
globalThis.document={hidden:false,activeElement:null,body:{append(){}},createElement:()=>{
  const handlers=new Map();return {open:false,innerHTML:'',className:'',setAttribute(){},
    querySelector:id=>({addEventListener(event,handler){handlers.set(id,handler);}}),addEventListener(){},
    showModal(){this.open=true;confirms++;queueMicrotask(()=>handlers.get(choice?'[data-center-confirm]':'[data-center-cancel]')());},
    close(){this.open=false;},remove(){}};
}};
const panel=Object.assign(Object.create(ServicePanel.prototype),{
  cfg:{service_enabled:true,control_token:'test'},options:{},
  s:{service_sample_fresh:true,service_compatible:true,saved_calibrated_count:15,calibrated_count:15,
    bus:{build:'1fa8438-feetech-ft6-control.56',mode:'commissioning',phase:'ready',torque_state:'off'},channels:{bus:{status:'live'}},servos:[]},
  id:20,inspection:{render(){}},gamepadRepair:{render(){}},root:{querySelector(){return null}},$:get,
  feedback(){},client:'testcenter184',seq:0,lastSample:performance.now(),paint:ServicePanel.prototype.paint,
});
panel.paint();assert.equal(get('service-center').disabled,true);
get('service-unassembled').checked=true;panel.paint();assert.equal(get('service-center').disabled,false);
globalThis.fetch=async()=>{calls++;return {ok:true,json:async()=>({accepted:true,message:'ok'})}};
const command={action:'center',unassembled:true,duration_ms:2000};
await panel.post({...command});assert.equal(calls,0);assert.equal(panel.seq,0);
choice=true;await panel.post({...command});assert.equal(calls,1);assert.equal(panel.seq,1);assert.equal(confirms,2);
await panel.post({...command,unassembled:false});assert.equal(calls,1);assert.equal(confirms,2);
console.log(JSON.stringify({saved_calibrations_allowed:true,checkbox_required:true,cancel_sends_nothing:true,confirm_sends_once:true}));
