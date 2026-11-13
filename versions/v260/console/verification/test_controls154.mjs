import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-controls154-'));
try{
  const source=path.resolve(process.argv[2]||'static');
  fs.cpSync(source,path.join(temporary,'static'),{recursive:true});
  fs.writeFileSync(path.join(temporary,'package.json'),'{"type":"module"}');
  const nodes=new Map();
  class Element {
    constructor(){this.value='';this.textContent='';this.dataset={};this.classList={toggle(){}};this.children=[];}
    set innerHTML(value){this.html=value;this.children=[];for(const match of value.matchAll(/<(button|input|[^ >]+)[^>]*id="([^"]+)"[^>]*>/g)){const node=get(match[2]);node.tag=match[1];this.children.push(node);}}
    querySelector(selector){return get(selector.replace(/^#/,''));}
    querySelectorAll(selector){return this.children.filter(node=>selector==='button,input'?['button','input'].includes(node.tag):selector==='[data-slot]'?node.dataset.slot:false);}
    append(){}before(){}setAttribute(){}replaceChildren(...children){this.children=children;}
  }
  const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
  globalThis.document={createElement:()=>new Element(),getElementById:get,querySelector:get};
  const load=name=>import(pathToFileURL(path.join(temporary,'static',name)));
  const {AdvancedParameters}=await load('advanced-parameters.js');
  const {ServiceManagement}=await load('service-management.js');
  const {ServicePanel}=await load('service.js');
  const {FirmwarePanel}=await load('firmware.js');
  const {ControlPanel}=await load('control.js');
  const {actionSlots}=await load('service-builds.js');
  const sent=[];
  const model={slot:'walk',active:true,available:true,id:'walk-model',sha256:'walk-hash',runtime_execution_profile:{schema:'microduck-runtime-execution/v1',mode:'uniform',model_sha256:'walk-hash',action_scale:1,head_lowpass:.5,legs_lowpass:.7}};
  const owner={catalog:{models:[model],management_actions:['action-scale','joint-action-scale'],default_joint_action_scale:1},panel:{posting:false},command:async command=>sent.push(command)};
  const scale=new AdvancedParameters(owner);
  assert.doesNotMatch(scale.root.html,/management-(?:kp|kd|torque-limit)/);
  const ready={service_sample_fresh:true,bus:{mode:'motion',phase:'control',homed:true,policy_enabled:true,torque_off_pending:false,native:{imu_ready:true,torque_state_confirmed:true},loaded_models:{walk:model}},capabilities:{skills:['kick_right']}};
  scale.paint(ready);assert.equal(scale.scaleBlocked,false,'scaling must work without any servo fields');
  get('management-scale').value='.72';scale.paint(ready);assert.equal(get('management-scale-apply').disabled,false);
  globalThis.confirm=()=>true;await scale.applyScale();
  assert.deepEqual(sent,[{action:'set-action-scale',model:'walk-model',scale:.72,supported:true}]);
  for(const option of ['replay','offline']){scale.paint(ready,{[option]:true});await scale.applyScale();}
  assert.equal(sent.length,1);

  const panel={cfg:{control_token:'test'},$:get,post:async command=>sent.push(command)};
  const management=new ServiceManagement(panel);
  assert.doesNotMatch(management.root.html,/management-(?:import|file)/);
  assert.equal(ServiceManagement.prototype.upload,undefined);
  Object.assign(management,{s:ready,options:{},supported:true,catalog:owner.catalog});
  management.paint();assert.doesNotMatch(management.root.html,/management-kick-right/);
  assert.equal(ServiceManagement.prototype.runKick,undefined);
  const control=Object.create(ControlPanel.prototype);control.s={service_operation:false,service_control:{busy:true,job:{action:'upgrade-service'}}};
  assert.equal(control.servicePaused(),true);
  assert.ok(actionSlots.some(row=>row.slot==='kick_right'&&row.task_prefixes.includes('BallKick')));
  assert.ok(actionSlots.every(row=>row.slot!=='stand'),'no independent Stand test selector');
  const html=fs.readFileSync(path.join(source,'index.html'),'utf8');
  assert.doesNotMatch(html,/data-button="lb"|起身测试|LB.*起身/);assert.match(html,/data-button="rb" data-requires-slot="kick_right"/);assert.match(html,/真实手柄 LB 为官方左踢/);
  for(const file of ['advanced-parameters.js','control.js','service-management.js'])assert.doesNotMatch(fs.readFileSync(path.join(source,file),'utf8'),/stand_test|manual_recovery|management-recovery|recoveryText/);
  const profile=JSON.parse(fs.readFileSync(path.join(source,'service-builds.js'),'utf8').match(/^const profile=(.*);$/m)[1]);
  assert.equal(profile.defaults.servo,undefined);assert.equal(profile.requested_skill_replacement,undefined);
  assert.equal(profile.builtin_models.length,5);assert.ok(profile.builtin_models.every(model=>model.slot!=='stand'));
  for(const file of ['service-management.js','service.js'])assert.doesNotMatch(fs.readFileSync(path.join(source,file),'utf8'),/models\/upload|management-import|import-model|X-Model-|async upload\(/);

  const firmware=Object.create(FirmwarePanel.prototype);
  Object.assign(firmware,{panel:{posting:false},cfg:{control_token:'test'},source:'bundled',info:null,$:id=>get('firmware-'+id)});
  firmware.paint();assert.equal(get('firmware-bundled').textContent,'随包固件 · 未核验');
  for(const number of [32,33]){
    globalThis.fetch=async()=>({ok:true,json:async()=>({verified:true,build:`release-feetech-ft6-control.${number}`,sha256:'a'.repeat(64)})});
    await firmware.verify();assert.equal(get('firmware-bundled').textContent,`随包固件 · control.${number}`);
  }
  let reject;globalThis.fetch=()=>new Promise((resolve,no)=>{reject=no;});
  const pending=firmware.verify();assert.equal(firmware.info,null);assert.equal(get('firmware-bundled').textContent,'随包固件 · 正在核验');
  reject(Error('校验失败'));await pending;
  assert.equal(get('firmware-bundled').textContent,'随包固件 · 未知（核验失败）');assert.equal(get('firmware-flash').disabled,true);
  assert.doesNotMatch(fs.readFileSync(path.join(source,'firmware.js'),'utf8'),/control\.18|control\.33/);
  console.log('PASS scale-only payload, removed servo/import/LB test UI, removed redundant kick shortcut, preserved RB, and verified firmware versions 32/33/error');
}finally{fs.rmSync(temporary,{recursive:true,force:true});}
