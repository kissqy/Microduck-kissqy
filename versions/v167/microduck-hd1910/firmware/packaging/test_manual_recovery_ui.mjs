/** Actual ControlPanel + PadControls event tests in a small DOM fixture; no browser or robot. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {setImmediate as settle} from 'node:timers/promises';
const rootPath=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const staticRoot=path.resolve(process.argv[2]||path.join(rootPath,'console/static'));
const html=fs.readFileSync(path.join(staticRoot,'index.html'),'utf8');
class Element {
  constructor(){
    this.value='';this.textContent='';this.dataset={};this.disabled=false;this.attributes={};this.listeners=new Map();
    const classes=new Set();this.classList={add:(...names)=>names.forEach(n=>classes.add(n)),remove:(...names)=>names.forEach(n=>classes.delete(n)),contains:name=>classes.has(name),toggle:(name,on)=>{if(on??!classes.has(name))classes.add(name);else classes.delete(name);}};
  }
  addEventListener(name,callback){if(!this.listeners.has(name))this.listeners.set(name,[]);this.listeners.get(name).push(callback);}
  emit(name,event={}){for(const callback of this.listeners.get(name)||[])callback({button:0,preventDefault(){},...event});}
  setAttribute(name,value){this.attributes[name]=value;}
  setPointerCapture(){}
}
const nodes=new Map(),get=selector=>{if(!nodes.has(selector))nodes.set(selector,new Element());return nodes.get(selector);};
// Read button metadata from the shipped HTML so missing slot bindings are exercised too.
const buttons=new Map(['lb','start','select','x','a'].map(name=>{
  const el=new Element(),attributes=html.match(new RegExp(`<button\\s+([^>]*data-button="${name}"[^>]*)>`))?.[1];
  assert(attributes,`missing ${name} button`);
  for(const [,attr,value] of attributes.matchAll(/data-([a-z-]+)="([^"]*)"/g))el.dataset[attr.replace(/-([a-z])/g,(_,letter)=>letter.toUpperCase())]=value;
  return [name,el];
}));
const center=new Element(),allButtons=[...buttons.values(),center],padRoot=new Element();
padRoot.querySelector=selector=>selector==='[data-pad-center]'?center:get(selector);
padRoot.querySelectorAll=selector=>selector==='button'?allButtons:selector==='[data-button],[data-dpad],[data-trigger]'?[...buttons.values()]:selector==='.held'?allButtons.filter(b=>b.classList.contains('held')):[];
const root={querySelector:selector=>selector==='.official-pad'?padRoot:get(selector),querySelectorAll:selector=>selector==='[data-requires-slot]'?[...buttons.values()].filter(b=>b.dataset.requiresSlot):[]};
globalThis.window=new Element();globalThis.document=new Element();document.hidden=false;
const {ControlPanel}=await import(pathToFileURL(path.join(staticRoot,'control.js')));
const panel=new ControlPanel({service_enabled:true,control_token:'fixture'},root);clearInterval(panel.timer);panel.connected=true;
let sent=[];panel.socket.request=async command=>{sent.push(structuredClone(command));return {accepted:true,available:true,real_connected:panel.s?.control?.webpad?.real_connected===true,browser_rtt_ms:1};};
const base={service_sample_fresh:true,state:{safety:{fallen:true,limp:true}},
  bus:{build:'1fa8438-feetech-ft6-control.28',mode:'motion',phase:'control',
    policy_enabled:false,homed:false,home_recovery:false,
    home_start_guard:{ready:false,reason:'机身倾斜'},
    native:{torque_state_confirmed:false},action_scale:.7,head_lowpass:.5,legs_lowpass:.7,
    loaded_models:{stand_test:{sha256:'a481d9f211f31d9476ab1a319fe362a21ef0879d9fa59442a122845af598268c',task:'Mjlab-StandUp-Flat-MicroDuck'}}},
  control:{connected:true,webpad:{available:true,real_connected:false}},service_control:{}};
const render=(bus={},state={},options={},real=false)=>panel.render({...base,
  bus:{...base.bus,...bus},state:{safety:{...base.state.safety,...state}},
  control:{...base.control,webpad:{...base.control.webpad,real_connected:real}}},options);
const lb=buttons.get('lb'),start=buttons.get('start'),select=buttons.get('select');
let pointer=0;
async function pressLb(){
  sent=[];const pointerId=++pointer;lb.emit('pointerdown',{pointerId});window.emit('pointerup',{pointerId});await settle();
  assert(sent.some(c=>c.frame?.buttons.includes('lb')));
  assert(sent.every(c=>c.action==='webpad_state'),'LB uses ordinary virtual-pad frames, never HOME/enable commands');
  assert(!sent.some(c=>c.frame.buttons.includes('start')),'LB must not synthesize Start before recovery');
  assert.equal(sent.at(-1).frame.buttons.length,0,'pointer release must send neutral');
  assert.equal(panel.pad.active(),false);assert.equal(panel.armed,false);
}
render();
assert.equal(lb.disabled,false);assert.equal(start.disabled,false);assert.equal(select.disabled,false);
assert.deepEqual(sent,[],'a fallen snapshot must not start recovery automatically');
assert.match(get('#control-reason').textContent,/已倒地.*含卸力状态.*无需先回 HOME/);
await pressLb();
console.log('PASS startup fallen + limp: explicit LB press/release only; no automatic enable or synthesized HOME');

for(const [name,bus,state] of [
  ['HOME',{homed:true},{limp:false}],
  ['homing',{homed:false,native:{torque_state_confirmed:true}},{limp:false}],
  ['holding',{homed:true,policy_enabled:true,scale_use:'hold'},{limp:false}],
  ['walking',{homed:true,policy_enabled:true,scale_use:'walking'},{limp:false}],
]){
  render(bus,state);assert.equal(lb.disabled,false,`${name} must not add an LB gate`);await pressLb();
}
console.log('PASS fallen HOME, homing, holding and walking use the same production pad event path');

render({loaded_models:{}});
assert.equal(lb.disabled,true);assert.equal(start.disabled,false);assert.equal(select.disabled,false);
sent=[];lb.emit('pointerdown',{pointerId:++pointer});await settle();assert.deepEqual(sent,[]);
assert.match(lb.title,/模型未加载/);
render({homed:true},{fallen:false,limp:false});assert.equal(lb.disabled,false,'existing upright HOME testing stays available');
sent=[];render({last_enable_refusal:'LB 起身需要新鲜的整链样本'});
assert.match(get('#control-feedback').textContent,/需要新鲜的整链样本/);
assert.deepEqual(sent,[],'native refusal must not trigger retry or HOME');
console.log('PASS missing model disables only its action; upright HOME remains; native refusal displays without replay');

render({policy_enabled:true,home_recovery:true,scale_use:'stand_test',
  active_model:base.bus.loaded_models.stand_test,active_action_scale:1,
  active_target_filters:{head_lowpass:1,legs_lowpass:1}});
assert.match(get('#control-reason').textContent,/从当前姿态起身.*结束回 HOME/);
assert.equal(get('#parameter-actual').textContent,'1.000');
assert.equal(get('#parameter-head').textContent,'1.00');assert.equal(get('#parameter-legs').textContent,'1.00');
render({homed:true,policy_enabled:true,home_recovery:false,scale_use:'stand_test'});
assert.match(get('#control-reason').textContent,/结束回 Walk/);
console.log('PASS recovery readback shows current pose, actual scale/filters and HOME versus Walk return');

sent=[];render();const heldPointer=++pointer;lb.emit('pointerdown',{pointerId:heldPointer});await settle();
assert(sent.some(c=>c.frame?.buttons.includes('lb')));const boundary=sent.length;
render({}, {}, {}, true);window.emit('pointerup',{pointerId:heldPointer});await settle();
assert.equal(lb.disabled,true);assert.equal(start.disabled,true);
assert.match(get('#control-status').textContent,/真实手柄已接管/);
const afterTakeover=sent.slice(boundary);assert(afterTakeover.some(c=>c.action==='webpad_close'));
assert(!afterTakeover.some(c=>c.frame?.buttons.includes('lb')),'physical takeover must not replay held web LB');
assert.equal(panel.pad.active(),false);
console.log('PASS physical controller takeover releases held web LB and disables browser actions');

for(const option of ['replay','paused','offline']){
  render({}, {}, {[option]:true});assert.equal(lb.disabled,true,`${option} protects actions`);
  sent=[];lb.emit('pointerdown',{pointerId:++pointer});await settle();assert.deepEqual(sent,[]);
}
render();panel.connected=false;panel.paint();assert.equal(lb.disabled,true);
console.log('PASS replay, pause, offline and disconnected protections remain');
