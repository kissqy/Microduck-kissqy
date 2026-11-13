import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {ControlPanel} from '../static/control.js';

class Element extends EventTarget {
  constructor(dataset={}){super();this.dataset=dataset;this.disabled=false;this.attributes={};this.value='';this.style={};this.textContent='';this.nodes=new Map();this.classes=new Set();this.classList={contains:x=>this.classes.has(x),add:x=>this.classes.add(x),remove:x=>this.classes.delete(x),toggle:(x,on)=>{if(on)this.classes.add(x);else this.classes.delete(x);}};}
  setAttribute(k,v){this.attributes[k]=v;}
  setPointerCapture(){}
  querySelector(selector){if(!this.nodes.has(selector))this.nodes.set(selector,new Element());return this.nodes.get(selector);}
  querySelectorAll(){return [];}
}
const root=new Element(),padRoot=new Element(),start=new Element({button:'start'}),center=new Element();
root.nodes.set('.official-pad',padRoot);padRoot.nodes.set('[data-pad-center]',center);
padRoot.querySelectorAll=selector=>selector==='[data-button],[data-dpad],[data-trigger]'?[start]:selector==='button'?[start,center]:[];
globalThis.window=new EventTarget();globalThis.document=new EventTarget();document.hidden=false;
const interval=globalThis.setInterval;globalThis.setInterval=()=>0;
const panel=new ControlPanel({control_token:'fixture',service_enabled:true},root);
globalThis.setInterval=interval;
const alias=new Element({button:'start'});
panel.bindStartButton(alias);panel.bindStartButton(alias);
assert.equal(alias.disabled,true,'alias must be disabled before connection');
const calls=[];panel.socket.request=async payload=>{calls.push(payload);return {accepted:true,available:true,real_connected:false};};
const bus={build:'1fa8438-feetech-ft6-control.71',mode:'motion',phase:'control',homed:false,policy_enabled:false};
panel.connected=true;panel.state={available:true,real_connected:false};panel.s={bus,control:{webpad:{available:true,real_connected:false}}};panel.paint();
assert.equal(alias.disabled,false);assert.equal(alias.textContent,'Start · 回 HOME');
const event=(type,fields={})=>{const e=new Event(type,{cancelable:true});for(const [k,v] of Object.entries(fields))Object.defineProperty(e,k,{value:v});return e;};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function tap(button,id){button.dispatchEvent(event('pointerdown',{button:0,pointerId:id}));window.dispatchEvent(event('pointerup',{pointerId:id}));await flush();}
await tap(start,1);const reference=calls.splice(0);
assert.deepEqual(reference.map(x=>x.action),['webpad_state','webpad_state']);
assert.deepEqual(reference.map(x=>x.frame.buttons),[['start'],[]]);
await tap(alias,2);const first=calls.splice(0);
assert.deepEqual(first.filter(x=>x.action==='webpad_state').map(x=>x.frame),reference.map(x=>x.frame),'AI button must send exactly the existing Start press/release frames');
assert.equal(first.filter(x=>x.action==='webpad_state').length,2,'one click must never chain a second Start');
assert.equal(first.at(-1).action,'webpad_close','release the AI button owner so the AI is not blocked by an idle webpad');
assert.equal(bus.homed,false,'a receipt must not pretend HOME has completed');
assert.equal(alias.textContent,'Start · 回 HOME');
bus.homed=true;panel.paint();assert.equal(alias.textContent,'Start · 进入保持');assert.equal(calls.length,0,'readback and label updates must not send commands');
await tap(alias,3);assert.deepEqual(calls.splice(0).filter(x=>x.action==='webpad_state').map(x=>x.frame.buttons),[['start'],[]]);
bus.policy_enabled=true;panel.paint();assert.equal(alias.textContent,'Start · 回 HOME');assert.equal(calls.length,0);
await tap(alias,4);assert.deepEqual(calls.splice(0).filter(x=>x.action==='webpad_state').map(x=>x.frame.buttons),[['start'],[]]);
for(const block of ['real','maintenance','offline']){
  panel.s.control.webpad.real_connected=block==='real';panel.state.real_connected=block==='real';panel.s.service_operation=block==='maintenance'?{}:null;panel.options.offline=block==='offline';panel.paint();
  assert.equal(alias.disabled,true,block);await tap(alias,10);assert.equal(calls.length,0,block+' must not send input');
}
panel.s.control.webpad.real_connected=false;panel.state.real_connected=false;panel.s.service_operation=null;panel.options.offline=false;panel.paint();
alias.dispatchEvent(event('keydown',{code:'Enter',repeat:false}));alias.dispatchEvent(event('keydown',{code:'Enter',repeat:true}));alias.dispatchEvent(event('keyup',{code:'Enter'}));await flush();
assert.deepEqual(calls.splice(0).filter(x=>x.action==='webpad_state').map(x=>x.frame.buttons),[['start'],[]],'keyboard repeats must not duplicate Start');
alias.dispatchEvent(event('pointerdown',{button:0,pointerId:20}));await flush();assert.equal(alias.classList.contains('held'),true);
panel.suspend();await flush();assert.equal(alias.classList.contains('held'),false);assert.deepEqual(panel.pad.frame().buttons,[]);
const before=calls.length;window.dispatchEvent(event('pointerup',{pointerId:20}));await flush();assert.equal(calls.length,before,'late release after suspend must not replay input');
// AI unload is a click-only Select pulse. Holding it cannot become shutdown.
const relax=new Element({button:'select'});panel.bindRelaxButton(relax);panel.bindRelaxButton(relax);
calls.length=0;
relax.dispatchEvent(event('pointerdown',{button:0,pointerId:30}));
await flush();assert.equal(calls.length,0,'pointer hold must not send a held Select');
relax.dispatchEvent(event('click'));await flush();
const unload=calls.splice(0);
assert.deepEqual(unload.filter(x=>x.action==='webpad_state').map(x=>x.frame.buttons),[['select'],[]]);
assert.equal(unload.at(-1).action,'webpad_close');
assert.equal(unload.filter(x=>x.action==='webpad_state').length,2,'one unload click sends one short pulse');
for(const block of ['real','maintenance','offline']){
 panel.s.control.webpad.real_connected=block==='real';panel.state.real_connected=block==='real';panel.s.service_operation=block==='maintenance'?{}:null;panel.options.offline=block==='offline';panel.paint();
 assert.equal(relax.disabled,true,block);relax.dispatchEvent(event('click'));await flush();assert.equal(calls.length,0);
}
panel.s.control.webpad.real_connected=false;panel.state.real_connected=false;panel.s.service_operation=null;panel.options.offline=false;panel.paint();
const repeated=event('keydown',{code:'Enter',repeat:true});relax.dispatchEvent(repeated);assert.equal(repeated.defaultPrevented,true);
const html=await fs.readFile(new URL('../static/index.html',import.meta.url),'utf8');
assert.equal((html.match(/id="ai-motion-start"/g)||[]).length,1);
assert.ok(html.indexOf('id="ai-motion-relax"')>html.indexOf('id="ai-motion-start"'));
assert.equal((html.match(/id="ai-motion-relax"/g)||[]).length,1);
console.log(JSON.stringify({passed:true,scope:'real ControlPanel and PadControls; identical Start frames; one click one press/release; HOME then hold labels from readback; disabled during takeover/maintenance/offline; keyboard repeat; suspend reset; no automatic commands'}));
