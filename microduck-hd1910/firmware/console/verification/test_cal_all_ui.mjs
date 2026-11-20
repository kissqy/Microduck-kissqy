/** One-click calibrate-all gating and progress; no browser, robot or network.
 * Run: node verification/test_cal_all_ui.mjs [static-dir]
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-cal-all-'));
try{
  const source=path.resolve(process.argv[2]||'static');
  fs.cpSync(source,path.join(temporary,'static'),{recursive:true});
  fs.writeFileSync(path.join(temporary,'package.json'),'{"type":"module"}');
  const {ServicePanel}=await import(pathToFileURL(path.join(temporary,'static','service.js')));
  const nodes=new Map();
  const get=id=>{
    if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',className:'',hidden:false,disabled:false,checked:false,
      classList:{add(){},toggle(){}},setAttribute(){}});
    return nodes.get(id);
  };
  globalThis.document={hidden:false,activeElement:null,getElementById:get};
  globalThis.confirm=()=>true;

  const panel=Object.create(ServicePanel.prototype);
  Object.assign(panel,{cfg:{service_enabled:true},$:get,id:20,options:{},posting:false,
    root:{querySelector:()=>null},inspection:{render(){}},gamepadRepair:{render(){}}});
  let posted=[];
  panel.post=command=>posted.push(command);

  const calibration={zero_raw:2048,direction:1,min_rad:-Math.PI/2,max_rad:Math.PI/2,calibrated:true};
  const snapshot=(over={})=>({
    mode:'service',service_sample_fresh:true,service_compatible:true,connection_paused:false,
    bus:{mode:'commissioning',phase:'ready',torque_state:'off',torque_off_pending:null,native:{},motion:null,calibrate_all:true},
    channels:{bus:{status:'live'}},imu:{gravity:[0,0,-1]},saved_calibrated_count:15,calibrated_count:15,
    calibration:{calibration_path:'/etc/robot/feetech-ft5/hd1910-calibration.toml',calibration:{imu_mount_quat:[1,0,0,0],imu_mount_verified:true}},
    servos:[{id:20,name:'left_hip_yaw',label:'左髋旋转',status:'live',position_raw:2048,angle_deg:0,
      calibrated:true,calibration}],
    service_control:{busy:false,stopping:false,job:null},...over});

  const paint=s=>{panel.s=s;panel.paint();return s;};
  const calAll=()=>get('service-cal-all');
  const ready=()=>get('service-cal-all-ready');

  paint(snapshot());assert.equal(calAll().disabled,true,'unchecked must be disabled');
  ready().checked=true;
  paint(snapshot());assert.equal(calAll().disabled,false,'all gates + checkbox must enable');
  paint(snapshot({service_sample_fresh:false}));assert.equal(calAll().disabled,true,'stale must disable');
  paint(snapshot({service_compatible:false}));assert.equal(calAll().disabled,true,'incompatible must disable');
  paint(snapshot({bus:{mode:'motion',phase:'control',torque_state:'off',native:{},calibrate_all:true}}));assert.equal(calAll().disabled,true,'motion must disable');
  paint(snapshot({bus:{mode:'commissioning',phase:'ready',torque_state:'single_joint_enabled',native:{},calibrate_all:true}}));assert.equal(calAll().disabled,true,'torque on must disable');
  paint(snapshot({saved_calibrated_count:14}));assert.equal(calAll().disabled,true,'uncalibrated must disable');
  assert.match(get('service-cal-all-progress').textContent,/当前 14\/15/);
  paint(snapshot({bus:{mode:'commissioning',phase:'ready',torque_state:'off',native:{},calibrate_all:false}}));assert.equal(calAll().disabled,true,'old firmware must disable');
  assert.match(get('service-cal-all-progress').textContent,/不支持一键标定/);
  paint(snapshot({service_control:{busy:true,stopping:false,job:null}}));assert.equal(calAll().disabled,true,'busy must disable');
  paint(snapshot({service_control:{busy:false,stopping:false,job:{action:'calibrate-all',status:'running',at:1,phase:'calibrating',message:'CAL 4/15 · ID 23',calibration_all:{done_ids:[20,21,22],sync_results:[]}}}}));
  assert.equal(calAll().disabled,true,'running must disable');
  assert.match(get('service-cal-all-progress').textContent,/CAL 3\/15/);
  assert.equal(get('service-quick-stop').disabled,true,'stop must be locked while CAL runs');
  paint(snapshot({service_control:{busy:false,stopping:false,job:{action:'calibrate-all',status:'running',at:4,phase:'syncing',message:'同步中',calibration_all:{done_ids:[20,21,22],sync_results:[{id:20},{id:21},{id:22}]}}}}));
  assert.match(get('service-cal-all-progress').textContent,/同步 TOML 3\/15/);
  assert.equal(get('service-reboot').disabled,true,'reboot must be locked while CAL runs');
  assert.equal(get('service-shutdown').disabled,true,'shutdown must be locked while CAL runs');
  paint(snapshot({service_control:{busy:false,stopping:false,job:{action:'calibrate-all',status:'completed',at:2,phase:'verified',result:{backup:'/etc/robot/feetech-ft5/hd1910-calibration.toml.bak-cal-all-x'},calibration_all:{done_ids:[20],sync_results:[{id:20}],before:[{id:20,name:'left_hip_yaw',position_raw:2000,zero_raw:2048,angle_deg:4.2}]}}}}));
  assert.match(get('service-cal-all-progress').textContent,/15\/15 已完成/);
  assert.match(get('service-cal-all-progress').textContent,/bak-cal-all-x/);
  assert.equal(get('service-quick-stop').disabled,false,'stop must unlock after CAL');
  assert.equal(get('service-cal-all-before-wrap').hidden,false,'completed job must show before snapshot');
  assert.match(get('service-cal-all-before').innerHTML,/left_hip_yaw/);
  assert.equal(get('service-cal-all-next').hidden,false,'completed job must offer motion');
  assert.equal(get('service-cal-all-motion').disabled,false,'motion action must be enabled after CAL');
  paint(snapshot({service_control:{busy:false,stopping:false,job:{action:'calibrate-all',status:'error',at:3,phase:'syncing',error:'ID 30 失败',calibration_all:{done_ids:[20],sync_results:[]}}}}));
  assert.match(get('service-cal-all-progress').textContent,/失败于 syncing/);
  assert.match(get('service-cal-all-progress').textContent,/ID 30 失败/);

  ready().checked=false;
  posted=[];
  panel.calibrateAll();
  assert.deepEqual(posted,[],'unchecked click must not post');
  ready().checked=true;
  globalThis.confirm=()=>false;
  panel.calibrateAll();
  assert.deepEqual(posted,[],'cancel must not post');
  globalThis.confirm=()=>true;
  panel.calibrateAll();
  assert.deepEqual(posted,[{action:'calibrate-all',confirmed:true}]);
  console.log('PASS calibrate-all gating, progress, stop lockout and confirm payload');
}finally{
  fs.rmSync(temporary,{recursive:true,force:true});
}
