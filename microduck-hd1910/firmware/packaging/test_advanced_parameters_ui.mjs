import assert from 'node:assert/strict';
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import {pathToFileURL} from 'node:url';
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-advanced-'));
try{
 fs.cpSync(process.argv[2],path.join(temp,'static'),{recursive:true});fs.writeFileSync(path.join(temp,'package.json'),'{"type":"module"}');
 const nodes=new Map();const get=id=>{if(!nodes.has(id))nodes.set(id,{value:'',textContent:''});return nodes.get(id);};
 let confirmation=0;globalThis.confirm=()=>{confirmation++;return true;};globalThis.document={getElementById:get};
 const {AdvancedParameters}=await import(pathToFileURL(path.join(temp,'static/advanced-parameters.js')));
 const editor=Object.create(AdvancedParameters.prototype);const sent=[];
 const owner={panel:{},catalog:{models:[{slot:'walk',active:true,available:true,id:'walk-id'}],management_actions:['advanced-parameters'],action_scale:.7,default_action_scale:.7,default_servo_parameters:{kp:3,kd:0,torque_limit:681},servo_parameters:null},command:async c=>sent.push(c)};
 Object.assign(editor,{owner,$:get});const s={service_sample_fresh:true,bus:{action_scale:.7,head_lowpass:.5,legs_lowpass:.7},service_control:{}};
 editor.paint(s,{});assert.equal(get('kp').value,'3');assert.equal(get('kd').value,'0');assert.equal(get('torque-limit').value,'681');assert.match(get('kp-saved').textContent,/待应用/);assert.equal(sent.length,0);
 get('kp').value='4';get('kd').value='1';get('torque-limit').value='700';get('scale').value='.63';editor.paint(s,{});editor.paint(s,{});
 assert.equal(get('kp').value,'4');assert.equal(get('scale').value,'.63');assert.equal(sent.length,0);assert.equal(get('scale-apply').disabled,false);
 await editor.applyScale();assert.equal(sent.length,1);assert.equal(confirmation,1);assert.deepEqual(sent[0],{action:'set-action-scale',model:'walk-id',scale:.63,kp:4,kd:1,torque_limit:700,supported:true});
 owner.catalog={...owner.catalog,action_scale:.63,servo_parameters:{kp:4,kd:1,torque_limit:700}};
 editor.paint({...s,bus:{...s.bus,action_scale:.63,native:{hd1910:{temporary_gains_applied:true,servo_parameters:owner.catalog.servo_parameters}}}},{});
 assert.equal(get('scale-apply').disabled,true);assert.match(get('live-scale').textContent,/舵机已确认 P 4 \/ D 1 \/ 转矩 700/);
 get('kp').value='';editor.paint(s,{});assert.equal(get('scale-apply').disabled,true);
 await editor.applyScale();assert.equal(sent.length,1);
 console.log('PASS drafts have no writes; single apply carries all four; saved/live values are distinct; empty input cannot apply');
}finally{fs.rmSync(temp,{recursive:true});}
