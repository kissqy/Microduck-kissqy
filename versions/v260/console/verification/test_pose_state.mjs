import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

// Load the browser module directly without changing the repository's module mode.
const source=await readFile(new URL('../static/pose-state.js',import.meta.url),'utf8');
const {POSE_IDS,HINGE_IDS,resolvePoseSample}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const snapshot=()=>({
  mode:'service',service_sample_fresh:true,pose_calibrated:true,
  channels:{state:{status:'live'},bus:{status:'live'}},bus:{mode:'motion'},
  servos:POSE_IDS.map((id,index)=>({id,status:'live',calibrated:true,angle_deg:(index-7)*5,
    calibration:{direction:-1,zero_raw:2000}})),
  state:{joints:POSE_IDS.map((_,i)=>(i-7)/10),targets:POSE_IDS.map((_,i)=>(i-7)/20)},
  imu:{status:'live',mount_verified:true,gravity:[0,0,-1]},
});
function deepFreeze(value){
  if(value&&typeof value==='object'){Object.values(value).forEach(deepFreeze);Object.freeze(value);}
  return value;
}
function check(name,run){run();console.log('PASS '+name);}

check('physical IDs fix shuffled telemetry order; direction is not applied twice',()=>{
  const input=snapshot(),expected=resolvePoseSample(input);
  input.servos=[...input.servos.slice(7),...input.servos.slice(0,7)].reverse();
  const before=structuredClone(input),actual=resolvePoseSample(deepFreeze(input));
  assert.deepEqual(actual,expected);assert.deepEqual(input,before);
  assert.deepEqual(actual.rows.map(row=>row.id),POSE_IDS);
  assert.ok(Math.abs(actual.joints[0]-(-35*Math.PI/180))<1e-14);
  assert.equal(actual.live,true);assert.equal(actual.tiltStatus,'live');
  assert.deepEqual(actual.missingIds,[]);
  assert.equal(HINGE_IDS.length,14);assert.ok(!HINGE_IDS.includes(34));
});

check('unavailable mouth never freezes the fourteen actual hinges',()=>{
  const input=snapshot();input.pose_calibrated=false;
  Object.assign(input.servos.find(row=>row.id===34),{angle_deg:null,calibrated:false,status:'unavailable'});
  input.state.targets[9]=null;
  const result=resolvePoseSample(input);
  assert.equal(result.live,true);assert.deepEqual(result.missingIds,[]);
  assert.equal(result.joints[9],null);assert.equal(result.targetJoints[9],null);
  input.servos=input.servos.filter(row=>row.id!==34);
  assert.equal(resolvePoseSample(input).live,true);
  assert.equal(resolvePoseSample(input).rows[9],null);
});

check('missing, stale, uncalibrated, nonfinite or duplicated real hinges are rejected',()=>{
  for(const defect of ['missing','stale','uncalibrated','nonfinite','duplicate']){
    const input=snapshot(),row=input.servos.find(row=>row.id===32);
    if(defect==='missing')input.servos=input.servos.filter(row=>row.id!==32);
    if(defect==='stale')row.status='stale';
    if(defect==='uncalibrated')row.calibrated=false;
    if(defect==='nonfinite')row.angle_deg=NaN;
    if(defect==='duplicate')input.servos.push({...row},{...row});
    const result=resolvePoseSample(input);
    assert.equal(result.live,false,defect);assert.equal(result.joints[7],null,defect);
    assert.deepEqual(result.missingIds,[32],defect);
  }
  const input=snapshot();input.service_sample_fresh=false;
  assert.equal(resolvePoseSample(input).live,false);
  assert.deepEqual(resolvePoseSample(input).missingIds,HINGE_IDS);
});

check('ghost requires fresh state, complete visual targets and a motion context',()=>{
  const input=snapshot();assert.deepEqual(resolvePoseSample(input).targetJoints,input.state.targets);
  input.channels.state.status='stale';assert.equal(resolvePoseSample(input).targetJoints,null);
  input.channels.state.status='live';input.bus.mode='commissioning';
  assert.equal(resolvePoseSample(input).targetJoints,null);
  input.bus.mode='unknown';assert.equal(resolvePoseSample(input).targetJoints,null);
  delete input.bus.mode;assert.equal(resolvePoseSample(input).targetJoints,null);
  delete input.bus;assert.equal(resolvePoseSample(input).targetJoints,null);
  input.bus={mode:'motion'};
  input.bus.mode='motion';input.state.targets[5]=null;
  assert.equal(resolvePoseSample(input).targetJoints,null);
  input.state.targets=Array(14).fill(0);assert.equal(resolvePoseSample(input).targetJoints,null);
});

check('IMU status distinguishes unverified installation, stale samples and invalid vectors',()=>{
  const input=snapshot();input.imu.mount_verified=false;
  assert.equal(resolvePoseSample(input).tiltStatus,'unverified');assert.equal(resolvePoseSample(input).gravity,null);
  input.imu.mount_verified=true;input.imu.status='stale';
  assert.equal(resolvePoseSample(input).tiltStatus,'stale');assert.equal(resolvePoseSample(input).gravity,null);
  input.imu.status='live';input.service_sample_fresh=false;
  assert.equal(resolvePoseSample(input).tiltStatus,'stale');assert.equal(resolvePoseSample(input).gravity,null);
  input.service_sample_fresh=true;
  for(const value of [null,[0,0,0],[0,0,1e-9],[Infinity,0,-1],[NaN,0,-1],['0',0,-1],[0,0],Array(3)]){
    input.imu.gravity=value;const result=resolvePoseSample(input);
    assert.equal(result.tiltStatus,'unavailable');assert.equal(result.gravity,null);
  }
  input.imu.gravity=[.6,0,-.8];const result=resolvePoseSample(input);
  assert.equal(result.tiltStatus,'live');assert.deepEqual(result.gravity,input.imu.gravity);
  assert.notEqual(result.gravity,input.imu.gravity);
  input.imu.status='waiting';assert.equal(resolvePoseSample(input).tiltStatus,'unavailable');
});

check('nonservice uses the standard state radians, ignoring servo order and degree values',()=>{
  const input=snapshot();input.mode='monitor';input.servos=[];input.imu.mount_verified=false;delete input.bus;
  input.state.joints[9]=null;
  const result=resolvePoseSample(input);
  assert.deepEqual(result.joints,input.state.joints);assert.equal(result.live,true);
  assert.deepEqual(result.targetJoints,input.state.targets);
  assert.equal(result.tiltStatus,'live');assert.deepEqual(result.rows,Array(15).fill(null));
  assert.notEqual(result.joints,input.state.joints);assert.notEqual(result.targetJoints,input.state.targets);
  input.state.joints[14]=null;assert.deepEqual(resolvePoseSample(input).missingIds,[14]);
  input.channels.state.status='stale';assert.equal(resolvePoseSample(input).live,false);
  assert.equal(resolvePoseSample(input).tiltStatus,'stale');
  const empty=resolvePoseSample();assert.equal(empty.live,false);assert.equal(empty.tiltStatus,'unavailable');
  assert.deepEqual(empty.missingIds,HINGE_IDS);assert.equal(empty.targetJoints,null);
});
