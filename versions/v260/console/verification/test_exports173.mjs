import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-173-'));
try{
  const source=path.resolve(process.argv[2]||'console/static');
  fs.cpSync(source,path.join(temp,'static'),{recursive:true});
  fs.writeFileSync(path.join(temp,'package.json'),'{"type":"module"}');
  const load=n=>import(pathToFileURL(path.join(temp,'static',n)));
  const {ConnectionRetry}=await load('connection-retry.js');
  let now=0;const retry=new ConnectionRetry(()=>now);
  for(let i=0;i<4;i++){
    assert.equal(retry.ready,true);retry.connected();now+=1;retry.failed();
    now+=9999;assert.equal(retry.ready,false);now+=1;
  }
  now+=1000000;assert.equal(retry.ready,false);assert.equal(retry.exhausted,true);
  const {ControlPanel}=await load('control.js');
  const pad=Object.create(ControlPanel.prototype);let calls=0;
  Object.assign(pad,{reconnect:new ConnectionRetry(()=>now),connecting:false,linkEpoch:0,
    sessionUsed:false,servicePaused:()=>false,paint(){},s:{},feedback:{textContent:'',classList:{remove(){},add(){},toggle(){}},setAttribute(){}},
    socket:{close(){},async open(){}},async post(){calls++;throw Error('SSH refused');}});
  for(let i=0;i<4;i++){
    await pad.connect();await pad.connect();assert.equal(calls,i+1);now+=10000;
  }
  for(let i=0;i<100;i++){now+=10000;await pad.connect();}
  assert.equal(calls,4,'UI stops after three retries');
  pad.resetConnectionRetry();await pad.connect();assert.equal(calls,5,'explicit reconnect starts a new budget');

  const {diagnosticReport}=await load('diagnostic-export.js');
  const staticCalibration={calibration:{joints:Array.from({length:15},(_,id)=>({id,direction:-1,zero_raw:2000,min_rad:-1,max_rad:1}))}};
  const model={sha256:'a'.repeat(64),task:'V8',runtime_execution_profile:{action_scale:1,head_lowpass:.5,legs_lowpass:.7}};
  const frames=Array.from({length:1200},(_,i)=>({at:100+i*.1,version:'1.0.173',baseline:'pinned',
    bus:{build:'control.48',cycle:i,phase:'control',mode:'motion',policy_enabled:true,loaded_models:{walk:model},
      active_action_scale:1,native:{telemetry:{session:'same',total_reads:i,failed_reads:i>=351?1:0,
        last_failure:i>=351?{read:351,error:'checksum mismatch',missing_ids:[32]}:null}},
      last_cycle_error:i===351?'one-tick IMU fault':null},
    state:{policy:'walk',imu:{gyro:[.1,.2,.3],quat:[1,0,0,0]},skeleton:Array.from({length:15},()=>({pos:[.1,.2,.3],quat:[1,0,0,0]})),joints:Array(15).fill(.2)},
    channels:{state:{status:'live',age_ms:i%10}},health:{healthy:i!==351,cpu_temp_c:53},
    imu:{status:'live',gravity:[0,0,-1]},calibration:staticCalibration,
    servos:Array.from({length:15},(_,id)=>({id,status:'live',position_raw:2000+i%10,angle_deg:.2,target_deg:1,temperature_c:30,calibration:staticCalibration,display_label:'unchanged'})),
    tof:{seq:i,distance_mm:Array(64).fill(100),status:Array(64).fill(5)},system:{hostname:'duck'}}));
  const recording={schema:'microduck-console-recording/v1',frames,created_at:220,baseline:'pinned',mode:'service',
    service_commands:[{at:180.5,action:'init',status:'error',error:'torque readback missing [10]',command:{action:'init',sudo_password:'private-test'},log:'huge repeated data'}],last_failure:{read:351,error:'checksum mismatch'}};
  const original=JSON.stringify(recording),report=diagnosticReport(recording,frames.at(-1)),out=JSON.stringify(report);
  assert.equal(JSON.stringify(recording),original,'export must not mutate live/replay data');
  assert.deepEqual(report.samples[0].imu.gyro,[.1,.2,.3]);
  assert.deepEqual(report.samples[0].imu.quat,[1,0,0,0]);
  assert.equal(report.metadata.length,1,'calibration and model metadata stored once');
  assert.ok(report.events.some(e=>e.last_cycle_error==='one-tick IMU fault'),'transient failure survives 1 Hz normal sampling');
  assert.ok(report.samples.some(s=>s.at===frames[351].at));
  assert.ok(report.samples.some(s=>s.at===frames[342].at));
  assert.match(out,/torque readback missing/);assert.match(out,/checksum mismatch/);
  assert.doesNotMatch(out,/private-test|huge repeated data|skeleton|display_label/);
  assert.equal(report.metadata[0].models.walk.runtime_execution_profile.head_lowpass,.5);
  assert.ok(out.length/original.length<.2,'normal diagnostic should be substantially smaller than full repeated snapshots');
  const empty=diagnosticReport({frames:[],service_commands:[]},{});assert.equal(empty.samples.length,0);
  console.log(JSON.stringify({frontend_retry:'passed',diagnostic_retention:'passed',source_bytes:Buffer.byteLength(original),diagnostic_bytes:Buffer.byteLength(out),reduction_percent:Math.round((1-out.length/original.length)*100),saved_samples:report.samples.length}));
}finally{fs.rmSync(temp,{recursive:true,force:true});}
