/** One-click IMU mount calibration: gating, payload and level math; no browser, robot or network.
 * Run: node verification/test_imu_ui.mjs [static-dir]
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-imu-'));
try{
  const source=path.resolve(process.argv[2]||'static');
  fs.cpSync(source,path.join(temporary,'static'),{recursive:true});
  fs.writeFileSync(path.join(temporary,'package.json'),'{"type":"module"}');
  const {ServicePanel}=await import(pathToFileURL(path.join(temporary,'static','service.js')));
  const markup=fs.readFileSync(path.join(source,'service.js'),'utf8');
  assert.ok(markup.indexOf('id="service-cal-all-next"')<markup.indexOf('service-cal-all-warning'),
    'the switch-back action must sit next to the confirmation row, above the warning');

  const nodes=new Map();
  const get=id=>{
    if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',className:'',hidden:false,disabled:false,checked:false,
      classList:{add(){},toggle(){}},setAttribute(){}});
    return nodes.get(id);
  };
  globalThis.document={hidden:false,activeElement:null,getElementById:get};
  let confirmed=true;
  globalThis.confirm=()=>confirmed;

  const panel=Object.create(ServicePanel.prototype);
  Object.assign(panel,{cfg:{service_enabled:true},$:get,id:20,options:{},posting:false,
    root:{querySelector:()=>null},inspection:{render(){}},gamepadRepair:{render(){}}});
  const posted=[];
  panel.post=command=>posted.push(command);

  const MOUNT=[0.003621111, -0.687883360, 0.004144772, -0.725800380];
  const snapshot=(over={})=>({
    mode:'service',service_sample_fresh:true,service_compatible:true,connection_paused:false,
    bus:{mode:'commissioning',phase:'ready',torque_state:'off',torque_off_pending:null,native:{},motion:null,calibrate_all:true},
    channels:{bus:{status:'live'}},
    imu:{status:'live',gravity:[-0.056248,-0.039109,-0.997651]},
    saved_calibrated_count:15,calibrated_count:15,
    calibration:{calibration_path:'/etc/robot/feetech-ft5/hd1910-calibration.toml',
      calibration:{imu_mount_quat:MOUNT,imu_mount_verified:true}},
    servos:[{id:20,name:'left_hip_yaw',label:'左髋旋转',status:'live',position_raw:2048,angle_deg:0,
      calibrated:true,calibration:{zero_raw:2048,direction:1,min_rad:-1,max_rad:1,calibrated:true}}],
    service_control:{busy:false,stopping:false,job:null},...over});

  const paint=s=>{panel.s=s;panel.paint();return s;};
  const button=()=>get('service-imu-calibrate');
  const level=()=>get('service-imu-level');

  paint(snapshot());
  assert.match(get('service-imu-tilt').textContent,/当前倾角 3\.9\d°/,'tilt must be reported');
  assert.equal(button().disabled,true,'level confirmation is required');

  level().checked=true;
  paint(snapshot());
  assert.equal(button().disabled,false,'commissioning + level + tilt must enable');
  assert.equal(get('service-imu-tilt').textContent.includes('需切到标定模式'),false);

  paint(snapshot({bus:{mode:'motion',phase:'control',torque_state:'off',native:{},calibrate_all:true}}));
  assert.equal(button().disabled,true,'motion mode must disable');
  assert.match(get('service-imu-tilt').textContent,/需切到标定模式/);

  paint(snapshot({imu:{status:'live',gravity:[0.001,0.0002,-0.9999995]}}));
  assert.equal(button().disabled,true,'already level must not offer a fix');

  paint(snapshot({imu:{status:'stale',gravity:[-0.056248,-0.039109,-0.997651]}}));
  assert.equal(button().disabled,true,'stale IMU must disable');

  paint(snapshot());
  posted.length=0;confirmed=false;panel.calibrateImu();
  assert.deepEqual(posted,[],'cancelled confirm must not post');
  confirmed=true;panel.calibrateImu();
  assert.equal(posted.length,1);
  assert.equal(posted[0].action,'verify-imu');
  assert.equal(posted[0].confirmed,true);
  const q=posted[0].mount_wxyz;
  assert.equal(q.length,4);
  assert.ok(Math.abs(Math.hypot(...q)-1)<1e-9,'quaternion must be unit length');
  assert.ok(q.every(v=>v>=-1&&v<=1),'components must stay in [-1,1]');

  // The delta rotation between the new and the saved mount must take the measured
  // gravity exactly onto (0, 0, -1) in the trunk frame.
  const mul=(a,b)=>{const[aw,ax,ay,az]=a,[bw,bx,by,bz]=b;return[aw*bw-ax*bx-ay*by-az*bz,
    aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw];};
  const inverse=q=>[q[0],-q[1],-q[2],-q[3]];
  const rotate=(quat,v)=>{const[w,x,y,z]=quat;
    const t=[2*(y*v[2]-z*v[1]),2*(z*v[0]-x*v[2]),2*(x*v[1]-y*v[0])];
    return [v[0]+w*t[0]+(y*t[2]-z*t[1]),v[1]+w*t[1]+(z*t[0]-x*t[2]),v[2]+w*t[2]+(x*t[1]-y*t[0])];};
  const g=[-0.056248,-0.039109,-0.997651],n=Math.hypot(...g),u=g.map(v=>v/n);
  const rotated=rotate(mul(q,inverse(MOUNT)),u);
  assert.ok(Math.abs(rotated[0])<1e-9&&Math.abs(rotated[1])<1e-9&&Math.abs(rotated[2]+1)<1e-9,
    `corrected gravity must be (0,0,-1), got ${rotated.join(',')}`);

  console.log('PASS imu mount calibration gating, payload and level math');
}finally{
  fs.rmSync(temporary,{recursive:true,force:true});
}
