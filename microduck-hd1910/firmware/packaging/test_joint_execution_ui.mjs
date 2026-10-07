/** Production parameter renderers distinguish model mapping, live output and saved globals. */
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const rootPath=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const staticRoot=path.resolve(process.argv[2]||path.join(rootPath,'console/static'));
class Element {
  constructor(){this.value='';this.textContent='';this.dataset={};this.disabled=false;this.classList={toggle(){}};}
  setAttribute(){}
  querySelectorAll(){return [];}
}
const nodes=new Map(),get=selector=>{if(!nodes.has(selector))nodes.set(selector,new Element());return nodes.get(selector);};
globalThis.document={getElementById:id=>get('#'+id)};
globalThis.confirm=()=>true;
const {ControlPanel}=await import(pathToFileURL(path.join(staticRoot,'control.js')));
const {AdvancedParameters}=await import(pathToFileURL(path.join(staticRoot,'advanced-parameters.js')));
const {ServiceManagement}=await import(pathToFileURL(path.join(staticRoot,'service-management.js')));
const {jointExecutionProfile}=await import(pathToFileURL(path.join(staticRoot,'execution-profile.js')));
const sha='9'.repeat(64),profile={schema:'microduck-runtime-execution/v1',mode:'uniform',model_sha256:sha,
  action_scale:.9,head_lowpass:.5,legs_lowpass:.7};
const model={sha256:sha,task:'Mjlab-VelStand-Rough-Backlash-MicroDuck',runtime_execution_profile:profile};
const panel=Object.create(ControlPanel.prototype);
Object.assign(panel,{root:{querySelector:get,querySelectorAll:()=>[]},cfg:{service_enabled:true},connected:true,options:{},feedback:new Element(),pad:{paint(){},reset(){}},volumeDirty:false,mouthDirty:false,volumeBusy:false});
const base={service_sample_fresh:true,state:{safety:{fallen:false}},bus:{build:'1fa8438-feetech-ft6-control.29',mode:'motion',phase:'control',homed:true,policy_enabled:false,
  action_scale:.7,head_lowpass:.44,legs_lowpass:.66,voltage_adapt:true,voltage_scale_mult:1.05,
  loaded_models:{walk:model},active_model:null},control:{connected:true,webpad:{available:true}},service_control:{}};
const render=(bus={},extra={})=>{const sample={...base,...extra,bus:{...base.bus,...bus}};panel.render(sample);return sample;};
render();
assert.equal(get('#parameter-action').textContent,'0.90');
assert.equal(get('#parameter-actual').textContent,'—');assert.equal(get('#parameter-head').textContent,'—');
assert.match(get('#control-model').textContent,/统一输出参数.*策略未启用/);
assert.match(get('#control-readback').textContent,/基础 0.90 \/ 头 0.50 \/ 腿 0.70.*全程使用统一输出参数/);
assert.equal(jointExecutionProfile({...model,sha256:'8'.repeat(64)}),null,'A profile attached to another SHA is not this model\'s configuration');
assert.equal(jointExecutionProfile({...model,runtime_execution_profile:{...profile,head_lowpass:NaN}}),null);
assert.equal(jointExecutionProfile({...model,runtime_execution_profile:{...profile,action_scale:1.5}})?.action_scale,1.5,
  'The native/Python supported scale range extends to 2.0; valid uniform models must not fall back to the global editor');

const active=()=>({policy_enabled:true,active_model:model,scale_use:'joint_uniform',active_action_scale:.945,
  active_target_filters:{head_lowpass:.5,legs_lowpass:.7}});
render(active());
assert.equal(get('#parameter-action').textContent,'0.90');assert.equal(get('#parameter-actual').textContent,'0.945');
assert.equal(get('#parameter-head').textContent,'0.50');assert.equal(get('#parameter-legs').textContent,'0.70');
assert.match(get('#parameter-actual-desc').textContent,/联合模型.*基础 0.90.*电压补偿/);
assert(!get('#control-readback').textContent.includes('0.44'),'Saved global filters cannot be described as joint model output');
render(active(),{state:{safety:{fallen:true}}});
assert.equal(get('#parameter-action').textContent,'0.90');assert.equal(get('#parameter-actual').textContent,'0.945');
assert.equal(get('#parameter-head').textContent,'0.50');assert.equal(get('#parameter-legs').textContent,'0.70');
assert.match(get('#control-model').textContent,/统一输出参数/,'The browser never switches output parameters based on posture');
render({...active(),active_action_scale:null,active_target_filters:null,scale_use:'held'});
assert.equal(get('#parameter-action').textContent,'0.90','Static model base remains distinguishable from unknown actual output');
assert.equal(get('#parameter-head').textContent,'—');assert.equal(get('#parameter-actual').textContent,'未推理');
assert.match(get('#control-model').textContent,/实际值待回读/);
render({...active(),active_model:null,active_action_scale:null,active_target_filters:null,scale_use:'held'});
assert.equal(get('#parameter-action').textContent,'0.90','Before the first successful inference, loaded mapping must not fall back to saved global .7');
assert.equal(get('#parameter-head').textContent,'—');assert.equal(get('#parameter-actual').textContent,'未推理');
render({...active(),active_target_filters:{head_lowpass:.55,legs_lowpass:.75}});
assert.equal(get('#parameter-head').textContent,'0.55','Live readback must not be fabricated from the static profile');
assert.equal(get('#parameter-legs').textContent,'0.75');
render(active(),{service_sample_fresh:false});
for(const key of ['action','actual','head','legs'])assert.equal(get('#parameter-'+key).textContent,'—');
assert.match(get('#parameter-status').textContent,/等待机器人新鲜反馈/);

const sent=[],editor=Object.create(AdvancedParameters.prototype);
const catalogModel={id:'joint-id',name:'联合9600',sha256:sha,slot:'walk',active:true,available:true,execution_profile:profile,policy_settings:{action_scale:1,head_lowpass:1,legs_lowpass:1}};
const owner={panel:{},catalog:{models:[catalogModel],management_actions:['advanced-parameters'],action_scale:.7,default_action_scale:.7,
  servo_parameters:{kp:3,kd:0,torque_limit:681},default_servo_parameters:{kp:3,kd:0,torque_limit:681}},command:async command=>sent.push(command)};
Object.assign(editor,{owner,$:id=>get('#management-'+id)});
let sample=render(active());editor.paint(sample,{});
assert.equal(get('#management-scale').disabled,true);assert.equal(get('#management-scale').value,'0.7');
assert.equal(get('#management-kp').disabled,false,'P/D/48 testing remains available with the fixed output profile');
assert.equal(get('#management-scale-apply').textContent,'应用舵机参数');
assert.match(get('#management-live-scale').textContent,/联合模型.*统一输出参数.*基础 0.90.*头 0.5 \/ 腿 0.7.*实际 0.945/);
assert(!get('#management-live-scale').textContent.includes('官方行走 0.7'));
assert.match(get('#management-scale-status').textContent,/全局保存值仅供其他模型/);
get('#management-kp').value='4';get('#management-scale').value='.2';editor.paint(sample,{});
assert.equal(get('#management-scale').value,'0.7','A stale slider draft must not change global settings during a servo-only apply');
assert.equal(get('#management-scale-apply').disabled,false);await editor.applyScale();
assert.deepEqual(sent,[{action:'set-action-scale',model:'joint-id',scale:.7,kp:4,kd:0,torque_limit:681,supported:true}]);
editor.paint({...base,bus:{...base.bus,loaded_models:undefined}},{});
assert.equal(get('#management-scale').disabled,true,'Validated catalog metadata can describe a bound model before streaming begins');
assert.match(get('#management-live-scale').textContent,/统一配置.*策略未启用/);
assert(!get('#management-live-scale').textContent.includes('基础 1.00'),'Training policy_settings do not override deployment readback');
editor.paint({...sample,bus:{...sample.bus,active_model:null,active_action_scale:null,active_target_filters:null,scale_use:'held'}},{});
assert.match(get('#management-live-scale').textContent,/统一输出参数.*基础 0.90.*实际倍率待回读/);
editor.paint({...sample,service_sample_fresh:false},{});assert.equal(get('#management-live-scale').textContent,'等待运行反馈');

const management=Object.create(ServiceManagement.prototype);
Object.assign(management,{panel:{},root:{querySelectorAll:()=>[]},$:id=>get('#management-'+id),selectedSlot:'walk',supported:true,
  catalog:owner.catalog,s:sample,options:{},advanced:editor});
management.paint();
assert.match(get('#management-target').textContent,/联合9600.*联合模型统一输出参数.*基础 0.90 \/ 头 0.50 \/ 腿 0.70/);

// A subsequently imported ordinary model still has the ordinary editor; LB keeps v145 readback.
const ordinary={sha256:'7'.repeat(64),task:'Mjlab-Velocity-Rough-Backlash-MicroDuck'};
owner.catalog.models=[{id:'ordinary',slot:'walk',active:true,available:true,...ordinary}];
sample=render({loaded_models:{walk:ordinary},policy_enabled:true,active_model:ordinary,
  active_action_scale:.735,active_target_filters:{head_lowpass:.44,legs_lowpass:.66},scale_use:'walking'});
editor.paint(sample,{});
assert.equal(get('#management-scale').disabled,false);assert.equal(get('#parameter-action').textContent,'0.70');
assert.equal(get('#parameter-head').textContent,'0.44');assert.equal(get('#parameter-legs').textContent,'0.66');
sample=render({policy_enabled:true,active_model:{sha256:'6'.repeat(64),task:'Mjlab-StandUp-Rough-Backlash-MicroDuck'},
  scale_use:'stand_test',active_action_scale:1.05,active_target_filters:{head_lowpass:1,legs_lowpass:1}});
assert.match(get('#control-readback').textContent,/LB 起身.*头腿直通/);
assert(!get('#control-readback').textContent.includes('统一输出参数'));
console.log('PASS uniform model metadata, posture-independent UI, actual output/null/stale readback, catalog binding, preserved global scale and servo editing, ordinary/LB restoration');
