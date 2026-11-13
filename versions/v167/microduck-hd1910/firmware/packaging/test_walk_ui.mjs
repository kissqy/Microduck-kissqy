import assert from 'node:assert/strict';
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import {pathToFileURL} from 'node:url';
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-r17-ui-'));fs.cpSync(process.argv[2],path.join(temp,'static'),{recursive:true});fs.writeFileSync(path.join(temp,'package.json'),'{"type":"module"}');
const nodes=new Map();class Element {
 constructor(id=''){this.id=id;this.disabled=false;this.value='';this.classList={toggle(){}};this.files=[];this.dataset={};if(id)nodes.set(id,this);}
 set innerHTML(html){for(const m of html.matchAll(/id="([^"]+)"/g))new Element(m[1]);}
 querySelectorAll(selector){return selector==='[data-model]'?[]:[...nodes.values()];}querySelector(selector){return nodes.get(selector.replace(/^#/,'').replace('management-','management-'))??new Element();}append(){}before(){}setAttribute(){}
}
globalThis.document={createElement:()=>new Element(),querySelector:()=>new Element(),getElementById:id=>nodes.get(id)};globalThis.confirm=()=>true;
const {ServiceManagement}=await import(pathToFileURL(path.join(temp,'static/service-management.js')));
const sent=[];const panel={cfg:{control_token:'test'},$:()=>new Element(),post:async x=>sent.push(x)};
const m=new ServiceManagement(panel);m.supported=true;m.connection={management_revision:'R17',process_matches:true,actual_port:'/dev/ttyS2',pid:5};m.options={};
const WALK='0b8f04476cab068f6db14b4b08856212',SIT='1c94934c6421ec72ed48079cea749668';
m.catalog={management_actions:['advanced-parameters'],default_servo_parameters:{kp:3,kd:0,torque_limit:681},action_scale:.9,configured_model:WALK,models:[{id:WALK,name:'联合行走起身',slot:'walk',active:true,available:true,action_scale:.9},{id:SIT,name:'起坐',slot:'sitstand',active:true,available:true,action_scale:1}]};
m.$('model').value=WALK;m.s={service_sample_fresh:true,bus:{build:'1fa8438-feetech-ft6-control.5',action_scale:.9,head_lowpass:.5,legs_lowpass:.7,active_action_scale:.936},service_control:{}};
m.paint();assert.equal(m.$('scale').value,'0.9');assert.match(m.$('live-scale').textContent,/头 0.5.*腿 0.7.*0.936/);assert.equal(nodes.has('management-hold'),false);
m.$('scale').value='.6';await m.advanced.applyScale();assert.deepEqual(sent[0],{action:'set-action-scale',model:WALK,scale:.6,kp:3,kd:0,torque_limit:681,supported:true});
m.$('model').value=SIT;m.paint();assert.equal(m.$('scale').value,'.6');assert.equal(m.$('scale').disabled,false);assert.equal(m.$('scale-apply').disabled,false);
await m.advanced.applyScale();assert.equal(sent[1].model,WALK);
m.s.service_sample_fresh=false;m.paint();assert.equal(m.$('scale').disabled,false);
delete m.catalog.action_scale;m.paint();assert.equal(m.$('scale').disabled,true);assert.equal(m.$('scale-value').textContent,'—');
m.catalog.action_scale=.7;m.catalog.default_action_scale=.7;new Element('parameter-action-default');m.paint();assert.equal(m.$('scale').value,'0.7');assert.equal(m.$('scale').disabled,false);assert.match(nodes.get('parameter-action-default').textContent,/默认 0.70/);
m.catalog.management_actions=[];m.paint();assert.equal(m.$('scale').disabled,true);assert.match(m.$('scale-status').textContent,/未提供高级参数/);
assert.equal(nodes.has('management-upgrade'),false);
console.log('PASS official global scale capability, active walk dispatch, stale telemetry configuration and explicit missing capability reason');fs.rmSync(temp,{recursive:true});
