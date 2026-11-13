import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-startup-ui-'));
try{
  fs.cpSync(path.resolve(process.argv[2]||'static'),path.join(temporary,'static'),{recursive:true});
  fs.writeFileSync(path.join(temporary,'package.json'),'{"type":"module"}');
  const {startupFailure}=await import(pathToFileURL(path.join(temporary,'static/startup-status.js')));
  const failed={bus:{phase:'configuration_error',error:'torque readback: missing IDs [10,11]'},service_sample_fresh:false,
    channels:{health:{status:'live'}}};
  assert.match(startupFailure(failed),/总线启动失败.*torque readback/);
  assert.equal(startupFailure({...failed,channels:{health:{status:'disconnected'}}}),'');
  assert.equal(startupFailure({...failed,bus:{phase:'recovering_uart'}}),'');
  const {ServiceManagement}=await import(pathToFileURL(path.join(temporary,'static/service-management.js')));
  const nodes=new Map();
  const get=id=>{if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',dataset:{},classList:{add(){},remove(){},toggle(){}},setAttribute(){}});return nodes.get(id);};
  const downloads=[];
  globalThis.document={body:{append(){}},createElement:()=>({click(){downloads.push(this.download);},remove(){}})};
  const management=Object.create(ServiceManagement.prototype);
  Object.assign(management,{cfg:{control_token:'test-token'},panel:{$:get,post(){throw Error('diagnostic must not post a motion job');}},
    $:get,recoveryBlocked:false,paint(){}});
  let complete;const pending=new Promise(resolve=>{complete=resolve;});const sent=[];
  globalThis.fetch=async(url,options)=>{sent.push({url,options});await pending;return {ok:true,json:async()=>({message:'已收集',diagnostic:{schema:'test'}})};};
  get('service-sudo-password').value='secret';
  const first=management.diagnose();await management.diagnose();
  assert.equal(sent.length,1,'double click must not launch another diagnostic');
  assert.equal(sent[0].url,'/api/service/diagnostic');
  assert.deepEqual(JSON.parse(sent[0].options.body),{sudo_password:'secret'});
  assert.equal(get('service-sudo-password').value,'');
  complete();await first;
  assert.equal(downloads.length,1);assert.match(downloads[0],/^Microduck-startup-diagnostic-.*\.json$/);
  assert.equal(management.diagnosticBusy,false);
  assert.ok(!get('hat-status').textContent.includes('secret'));
  management.recoveryBlocked=true;await management.diagnose();assert.equal(sent.length,1);
  console.log('PASS stale bus startup error, live health requirement, one-click diagnostic download, duplicate guard and no motion job');
}finally{fs.rmSync(temporary,{recursive:true,force:true});}
