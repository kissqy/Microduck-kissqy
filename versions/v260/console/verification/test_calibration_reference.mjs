/** Production Three.js pose/camera tests, without WebGL, telemetry or a robot.
 * Run: node verification/test_calibration_reference.mjs [pinned-training-robot.xml]
 * With no argument, the independent FK uses the bundled runtime MJCF. The
 * optional training XML also verifies its own 64 visual placements; its neck
 * mounting point differs from the runtime by 0.02093 mm, not a joint sign.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import * as T from '../static/vendor/three.module.min.js';
import {parseDuck} from '../static/pose.js';
import {DuckView} from '../static/duck.js';
import {REFERENCE_IDS,referencePose,hasReferenceHinge} from '../static/calibration-reference.js';
import {SERVO_PARTS} from '../static/joint-map.js';

const root=new URL('../',import.meta.url);
const read=relative=>fs.readFileSync(new URL(relative,root));
const names=['left_hip_yaw','left_hip_roll','left_hip_pitch','left_knee','left_ankle',
  'neck_pitch','head_pitch','head_yaw','head_roll','mouth',
  'right_hip_yaw','right_hip_roll','right_hip_pitch','right_knee','right_ankle'];
const ids=[20,21,22,23,24,30,31,32,33,34,10,11,12,13,14];
const degrees=[0,-5,-26.24,-.28,25.95,20,20,0,0,0,0,5,26.24,.28,-25.95];
const trainingHome=[0,-.0873,-.4579,-.0049,.4530,.3491,.3491,0,0,0,0,.0873,.4579,.0049,-.4530];
const radians=x=>x*Math.PI/180;
const near=(a,b,tolerance=1e-11,label='value')=>assert.ok(Math.abs(a-b)<=tolerance,`${label}: ${a} != ${b}`);
const nearArray=(a,b,tolerance=1e-11,label='vector')=>{
  assert.equal(a.length,b.length,label+' length');a.forEach((v,i)=>near(v,b[i],tolerance,`${label}[${i}]`));
};
const bytes=read('static/assets/duck-visual.bin');
const model=parseDuck(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength));
assert.deepEqual(REFERENCE_IDS,ids);
assert.deepEqual(SERVO_PARTS.map(p=>p.id),ids,'click IDs and reference slots must agree');
assert.equal(model.bodies.filter(b=>b.joint>=0).length,14,'mouth is not a fifteenth visual hinge');
const geometry=model.meshes.map(m=>{
  const g=new T.BufferGeometry();g.setAttribute('position',new T.BufferAttribute(m.vertices,3));
  g.setAttribute('normal',new T.BufferAttribute(m.normals,3));g.setIndex(new T.BufferAttribute(m.indices,1));
  g.computeBoundingBox();return g;
});
function makeView(){
  const view=new DuckView();view.model=model;view.geometry=geometry;
  // A deliberately wrong caller HOME catches accidental dependence on saved
  // calibration/policy defaults when the user asks for a model reference.
  view.home=Array(15).fill(2.123);view.actual=view.build(false);view.ghost=view.build(true);
  view.camera=new T.PerspectiveCamera(37,1.5,.005,20);view.camera.up.set(0,0,1);
  view.controls={target:new T.Vector3(),update(){view.camera.lookAt(this.target);view.camera.updateMatrixWorld(true);}};
  view.container={clientWidth:900,clientHeight:600};view.bodyAxes=new T.Group();
  view.sideTags=[{style:{}},{style:{}}];
  view.pose(view.actual,Array(15).fill(0),[0,0,-1],0);
  return view;
}

// Independent quaternion FK keeps this test from merely comparing the renderer
// against another invocation of the same Three.js multiplication path.
const norm=q=>{const n=Math.hypot(...q);return q.map(x=>x/n);};
const mul=(a,b)=>{
  const [w,x,y,z]=a,[v,i,j,k]=b;
  return [w*v-x*i-y*j-z*k,w*i+x*v+y*k-z*j,w*j-x*k+y*v+z*i,w*k+x*j-y*i+z*v];
};
const rotate=(q,p)=>mul(mul(q,[0,...p]),[q[0],-q[1],-q[2],-q[3]]).slice(1);
function compose(a,b){const p=rotate(a.quat,b.pos);return {pos:p.map((v,i)=>v+a.pos[i]),quat:mul(a.quat,b.quat)};}
function matrix(pose){
  const axes=[[1,0,0],[0,1,0],[0,0,1]].map(v=>rotate(pose.quat,v));
  return [...axes[0],0,...axes[1],0,...axes[2],0,...pose.pos,1];
}
function parseReferenceXml(text){
  const bodies=[],parts=[],stack=[],hidden=new Set(['np_f970','pcb__raspberry_pi_zero_2_w',
    'elec_rpi_robot_hat_pcb','power_support','banana_pcb_locker','motor_support']);
  const attrs=text=>Object.fromEntries([...text.matchAll(/([\w-]+)="([^"]*)"/g)].map(m=>[m[1],m[2]]));
  const numbers=(a,key,fallback)=>String(a[key]??fallback).trim().split(/\s+/).map(Number);
  for(const [,closing,tag,raw] of text.replace(/<!--[\s\S]*?-->/g,'').matchAll(/<(\/?)(body|joint|geom)\b([^>]*)>/g)){
    if(closing){if(tag==='body')stack.pop();continue;}
    const a=attrs(raw),parent=stack.at(-1)??-1;
    if(tag==='body'){
      const index=bodies.length;
      bodies.push({name:a.name,parent,joint:-1,pos:numbers(a,'pos','0 0 0'),quat:norm(numbers(a,'quat','1 0 0 0')),axis:[0,0,0]});
      if(!raw.trimEnd().endsWith('/'))stack.push(index);
    }else if(tag==='joint'&&parent>=0&&names.includes(a.name)){
      assert.equal(bodies[parent].joint,-1,'one actuated hinge per body');
      bodies[parent].joint=names.indexOf(a.name);bodies[parent].axis=norm(numbers(a,'axis','0 0 1'));
    }else if(tag==='geom'&&parent>=0&&a.class==='visual'&&a.type==='mesh'&&!hidden.has(a.mesh)){
      parts.push({body:parent,pos:numbers(a,'pos','0 0 0'),quat:norm(numbers(a,'quat','1 0 0 0'))});
    }
  }
  assert.equal(bodies.length,model.bodies.length,'reference body count');
  bodies.forEach((b,i)=>{
    assert.equal(b.parent,model.bodies[i].parent,`body ${i} parent`);
    assert.equal(b.joint,model.bodies[i].joint,`body ${i} joint slot`);
    nearArray(b.axis,model.bodies[i].axis,1e-12,`body ${i} axis`);
  });
  // The runtime XML intentionally contains no visual geoms. In that mode,
  // compare its independently read body tree with the shipped visual parts.
  if(parts.length)assert.equal(parts.length,64,'training visual count');
  return {bodies,parts:parts.length?parts:model.parts,trainingVisuals:parts.length>0};
}
const xmlPath=process.argv[2]||fileURLToPath(new URL('verification/reference_runtime.xml',root));
const reference=parseReferenceXml(fs.readFileSync(xmlPath,'utf8'));
function referenceMatrices(joints){
  const frames=[];
  for(const b of reference.bodies){
    let pose=compose(b.parent<0?{pos:[0,0,0],quat:[1,0,0,0]}:frames[b.parent],b);
    if(b.joint>=0){const h=joints[b.joint]/2;pose.quat=mul(pose.quat,[Math.cos(h),...b.axis.map(v=>v*Math.sin(h))]);}
    frames.push(pose);
  }
  return reference.parts.map(p=>matrix(compose(frames[p.body],{pos:p.pos,quat:norm(p.quat)})));
}
function localPartMatrices(view){
  view.actual.root.updateMatrixWorld(true);
  const inverse=view.actual.root.matrixWorld.clone().invert();
  return view.actual.parts.map(p=>new T.Matrix4().multiplyMatrices(inverse,p.matrixWorld).elements);
}

const view=makeView();let poseCases=0,maxRotationError=0,maxPositionError=0;
for(const base of [Array(15).fill(0),trainingHome])for(let joint=0;joint<15;joint++)for(const angle of [0,10,-10]){
  const q=base.slice();q[joint]=radians(angle);view.pose(view.actual,q,[0,0,-1],0);
  const expected=referenceMatrices(q),actual=localPartMatrices(view);
  for(let part=0;part<64;part++)for(let n=0;n<16;n++){
    const error=Math.abs(actual[part][n]-expected[part][n]),translation=n>=12&&n<=14;
    if(translation)maxPositionError=Math.max(maxPositionError,error);else maxRotationError=Math.max(maxRotationError,error);
    near(actual[part][n],expected[part][n],translation?(reference.trainingVisuals?2.2e-5:1e-8):1e-11,
      `${ids[joint]} at ${angle} deg, part ${part}, matrix ${n}`);
  }
  poseCases++;
}
assert.equal(poseCases,90);

// References remain available before the first telemetry sample, and never
// borrow a measured angle or add a stored zero offset to the official HOME.
nearArray(referencePose('zero'),Array(15).fill(0));
nearArray(referencePose('home'),degrees.map(radians));
near(referencePose('home')[ids.indexOf(21)],radians(-5));
near(referencePose('home')[ids.indexOf(11)],radians(5));
assert.throws(()=>referencePose('measured'));assert.throws(()=>referencePose('unknown'));
const copy=referencePose('zero');copy[0]=99;nearArray(referencePose('zero'),Array(15).fill(0));
for(let joint=0;joint<15;joint++){
  if(ids[joint]===34){
    assert.equal(hasReferenceHinge(joint),false);
    assert.throws(()=>referencePose('positive',joint));assert.throws(()=>referencePose('negative',joint));continue;
  }
  for(const [mode,sign] of [['positive',1],['negative',-1]])for(const t of [0,.5,1]){
    const q=referencePose(mode,joint,t);
    q.forEach((v,i)=>near(v,i===joint?sign*radians(10)*t:0,1e-12,`${ids[joint]} ${mode} slot ${i}`));
  }
}
for(const invalid of [-1,15,1.5,NaN])assert.equal(hasReferenceHinge(invalid),false);
near(referencePose('positive',7,-1)[7],0);near(referencePose('positive',7,2)[7],radians(10));
near(referencePose('positive',7,NaN)[7],0);

const beforeNetwork=globalThis.fetch;let networkCalls=0;
globalThis.fetch=()=>{networkCalls++;throw Error('Reference display must not contact a robot');};
try{
  const offline=makeView();
  for(const mode of ['zero','home']){
    assert.equal(offline.setReference(mode),true);nearArray(offline.referenceJoints,referencePose(mode));
    assert.equal(offline.lastSample.live,false,'reference must work with no telemetry');
  }
  for(let selected=0;selected<15;selected++)if(hasReferenceHinge(selected))for(const mode of ['positive','negative']){
    offline.selectJoint(selected);assert.equal(offline.setReference(mode),true);
    offline.renderReference(offline.referenceStarted+1500);
    nearArray(offline.referenceJoints,referencePose(mode,selected));
    // Descendant links physically follow the selected joint, but their own
    // local hinge angles must stay at zero instead of moving to HOME.
    model.bodies.forEach((body,i)=>{
      if(body.joint!==selected)near(Math.abs(offline.actual.bodies[i].quaternion.dot(offline.actual.bodies[i].userData.rest)),1,1e-12,'unselected local joint');
    });
  }
  offline.selectJoint(7);offline.setReference('positive');offline.referenceStarted=performance.now()-1500;
  offline.update({mode:'daemon',channels:{state:{status:'live'}},state:{joints:Array(15).fill(.7),odom:{yaw:1.2}},
    imu:{status:'live',gravity:[.3,.4,-.8]},servos:[]});
  nearArray(offline.referenceJoints,referencePose('positive',7));
  nearArray(offline.actual.root.quaternion.toArray(),[0,0,0,1],1e-12,'reference upright despite live tilted feedback');
  offline.selectJoint(ids.indexOf(34));assert.equal(offline.referenceMode,'zero');
  const before=localPartMatrices(offline);
  assert.equal(offline.setReference('positive'),false);assert.equal(offline.setReference('negative'),false);
  assert.deepEqual(localPartMatrices(offline),before,'mouth rejection must not alter the model');
  assert.equal(networkCalls,0);
}finally{globalThis.fetch=beforeNetwork;}

// Presets name the robot's sides even after heading changes. Checking the
// model before/after prevents a tempting fix that rotates the robot itself.
let cameraCases=0;
for(const yaw of [0,Math.PI/2,Math.PI]){
  view.pose(view.actual,trainingHome,[0,0,-1],yaw);view.hasPose=true;
  const rootPose=[...view.actual.root.position.toArray(),...view.actual.root.quaternion.toArray()];
  const bodies=view.actual.bodies.map(b=>[...b.position.toArray(),...b.quaternion.toArray()]);
  for(const [name,offset] of Object.entries({front:[.52,0,.11],back:[-.52,0,.11],left:[0,.52,.11],side:[0,-.52,.11]})){
    view.view(name);
    const localOffset=view.camera.position.clone().sub(view.controls.target).applyQuaternion(view.actual.root.quaternion.clone().invert());
    nearArray(localOffset.toArray(),offset,1e-12,`${name}, heading ${yaw}`);
    nearArray([...view.actual.root.position.toArray(),...view.actual.root.quaternion.toArray()],rootPose);
    view.actual.bodies.forEach((b,i)=>nearArray([...b.position.toArray(),...b.quaternion.toArray()],bodies[i]));
    view.updateBodyMarkers();
    nearArray(view.bodyAxes.quaternion.toArray(),view.actual.root.quaternion.toArray());
    view.sideTags.forEach((tag,i)=>{
      const p=view.actual.bodies[0].localToWorld(new T.Vector3(0,i?-.075:.075,-.014)).project(view.camera);
      near(parseFloat(tag.style.left),(p.x+1)*450,1e-9,'body-anchored side tag X');
      near(parseFloat(tag.style.top),(1-p.y)*300,1e-9,'body-anchored side tag Y');
    });
    cameraCases++;
  }
  // The physical mouth tip is used, not the camera optical quaternion: model
  // +32 turns toward body +Y, which is screen-right when facing the robot.
  const point=new T.Vector3(-.00809334,0,-.0777383);
  const headIndex=model.bodies.findIndex(b=>b.joint===8);
  const samples=[];
  for(const angle of [0,10,-10]){
    const q=trainingHome.slice();q[7]=radians(angle);view.pose(view.actual,q,[0,0,-1],yaw);view.view('front');
    const world=view.actual.bodies[headIndex].localToWorld(point.clone());
    const body=view.actual.bodies[0].worldToLocal(world.clone()),screen=world.clone().project(view.camera);
    samples.push({bodyY:body.y,screenX:screen.x});
    view.updateBodyMarkers();
    assert.ok(parseFloat(view.sideTags[0].style.left)>parseFloat(view.sideTags[1].style.left),'robot-left appears screen-right in front view');
  }
  assert.ok(samples[1].bodyY>samples[0].bodyY&&samples[2].bodyY<samples[0].bodyY,'head yaw sign in trunk frame');
  assert.ok(samples[1].screenX>samples[0].screenX&&samples[2].screenX<samples[0].screenX,'head yaw sign in front-screen frame');
}
assert.equal(cameraCases,12);
console.log(JSON.stringify({passed:true,reference_xml:xmlPath,pose_cases:poseCases,visual_parts:64,
  moving_hinges:14,mouth_animation_rejected:true,offline_references:true,one_local_joint_only:true,
  camera_cases:cameraCases,body_anchored_labels:true,head_yaw_body_and_screen_sign:true,
  max_rotation_matrix_error:maxRotationError,max_position_coordinate_error_mm:maxPositionError*1000}));
