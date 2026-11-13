import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const source=path.resolve(process.argv[2]||new URL('../static',import.meta.url).pathname);
const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-direction155-'));
try{
  fs.cpSync(source,path.join(temporary,'static'),{recursive:true});
  fs.writeFileSync(path.join(temporary,'package.json'),'{"type":"module"}');
  const load=name=>import(pathToFileURL(path.join(temporary,'static',name)));
  const {jointDirection}=await load('joint-direction.js');
  const {TelemetryStore}=await load('raw-telemetry.js');
  const {referenceAngle,officialStandingDegrees,modelJointLimits}=await load('joint-reference.js');
  const ids=[20,21,22,23,24,30,31,32,33,34,10,11,12,13,14];
  const names=['left_hip_yaw','left_hip_roll','left_hip_pitch','left_knee','left_ankle','neck_pitch','head_pitch','head_yaw','head_roll','mouth','right_hip_yaw','right_hip_roll','right_hip_pitch','right_knee','right_ankle'];
  const joints=ids.map((id,index)=>({id,name:names[index],calibrated:true,direction:index%3===1?-1:1,zero_raw:2048,min_rad:-1,max_rad:1}));
  const fixture=()=>({mode:'service',connection_paused:false,connection:{active:true,connected:true},channels:{calibration:{status:'live'}},calibration:{calibration:{joints:structuredClone(joints).reverse()}},servos:ids.map((id,index)=>({id,name:names[index],label:names[index],group:index<5?'left':index<10?'head':'right',status:'live',calibrated:true,angle_deg:index-7,target_deg:index/2,error_deg:0,position_raw:2000+index,source:'robot.busStatus',calibration:{...joints[index],direction:-joints[index].direction}}))});
  const deepFreeze=value=>{if(value&&typeof value==='object'){Object.values(value).forEach(deepFreeze);Object.freeze(value);}return value;};
  const check=(name,run)=>{run();console.log('PASS '+name);};

  check('all fifteen physical IDs use saved directions regardless of array order or stale row metadata',()=>{
    const snapshot=fixture(),before=structuredClone(snapshot);
    snapshot.servos.reverse();before.servos.reverse();deepFreeze(snapshot);
    for(const row of snapshot.servos){
      const expected=joints.find(joint=>joint.id===row.id).direction,view=jointDirection(snapshot,row);
      assert.equal(view.value,expected,`ID ${row.id}`);
      assert.equal(view.label,expected===1?'正向 +1':'反向 −1');
      assert.match(view.title,expected===1?/counts 递增时，关节角度增加/:/counts 递增时，关节角度减少/);
    }
    assert.deepEqual(snapshot,before,'display must never change calibration or feedback');
    assert.equal(jointDirection(snapshot,snapshot.servos.find(row=>row.id===34)).value,joints.find(row=>row.id===34).direction,'mouth is included');
  });

  check('missing, duplicate, mismatched, unsaved or invalid calibration never defaults to forward',()=>{
    const unknown=view=>{assert.equal(view.value,null);assert.equal(view.label,'—');assert.match(view.title,/未读取/);};
    for(const direction of [undefined,null,0,2,-2,'1','-1',true,false,NaN,Infinity]){
      const snapshot=fixture();snapshot.calibration.calibration.joints.find(row=>row.id===20).direction=direction;
      unknown(jointDirection(deepFreeze(snapshot),snapshot.servos[0]));
    }
    for(const defect of ['missing','duplicate','name','saved','missing-root','empty-root','waiting-channel','error-channel','paused','connecting']){
      const snapshot=fixture(),saved=snapshot.calibration.calibration.joints.find(row=>row.id===20);
      if(defect==='missing')snapshot.calibration.calibration.joints=snapshot.calibration.calibration.joints.filter(row=>row.id!==20);
      if(defect==='duplicate')snapshot.calibration.calibration.joints.push({...saved});
      if(defect==='name')saved.name='right_hip_yaw';
      if(defect==='saved')saved.calibrated=false;
      if(defect==='missing-root')snapshot.calibration=null;
      if(defect==='empty-root')snapshot.calibration={};
      if(defect==='waiting-channel')snapshot.channels.calibration.status='waiting';
      if(defect==='error-channel')snapshot.channels.calibration.status='error';
      if(defect==='paused')snapshot.connection_paused=true;
      if(defect==='connecting')snapshot.connection.connected=false;
      unknown(jointDirection(deepFreeze(snapshot),snapshot.servos[0]));
    }
    const legacy=fixture();delete legacy.calibration;
    assert.equal(jointDirection(legacy,legacy.servos[0]).value,-joints[0].direction,'old recordings can use their own per-row metadata');
    legacy.servos[0].calibration.id=10;unknown(jointDirection(legacy,legacy.servos[0]));
  });

  check('actual telemetry reset and disconnect cannot carry prior robot directions into a new session',()=>{
    const config={mode:'service',ids,names,labels:names,control_enabled:true},store=new TelemetryStore(config,()=>1,()=>1);
    store.auxiliary({connection_paused:false,connection:{active:true,connected:true}});
    store.ingest({channel:'calibration',data:{calibration:{joints}}});
    let snapshot=store.snapshot(false);assert.equal(jointDirection(snapshot,snapshot.servos[1]).value,-1);
    store.disconnect();snapshot=store.snapshot(false);assert.equal(jointDirection(snapshot,snapshot.servos[1]).value,null);
    store.reset();store.auxiliary({connection_paused:false,connection:{active:true,connected:true}});
    snapshot=store.snapshot(false);assert.equal(jointDirection(snapshot,snapshot.servos[1]).value,null);
    store.ingest({channel:'calibration',data:{calibration:{joints:joints.map(row=>({...row,direction:1}))}}});
    snapshot=store.snapshot(false);assert.equal(jointDirection(snapshot,snapshot.servos[1]).value,1);
  });

  check('actual table renderer adds one direction cell to all fifteen rows and preserves actual angles',()=>{
    const app=fs.readFileSync(path.join(source,'app.js'),'utf8');
    const begin=app.indexOf('function renderMotors(s){'),end=app.indexOf('\nfunction choose(',begin);
    assert.ok(begin>=0&&end>begin,'load the production renderer');
    const elements=new Map([['motor-search',{value:''}],['joint-registers',{innerHTML:''}]]),finite=value=>typeof value==='number'&&Number.isFinite(value),fmt=(value,d=1)=>finite(value)?value.toFixed(d):'—';
    const escape=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    let rendered='';
    const render=new Function('jointDirection','$','updateMotorRows','finite','fmt','escape','referenceAngle','officialStandingDegrees','modelJointLimits',`const group='all',selectedId=-1,statusNames={live:'实时'},radians=value=>finite(value)?value*180/Math.PI:null,valueCell=(value,d=1)=>fmt(value,d),text=()=>{};${app.slice(begin,end)};return renderMotors;`)(jointDirection,id=>elements.get(id),html=>{rendered=html;},finite,fmt,escape,referenceAngle,officialStandingDegrees,modelJointLimits);
    const snapshot=deepFreeze(fixture());render(snapshot);
    const rows=[...rendered.matchAll(/<tr data-id="(\d+)"[^>]*>(.*?)<\/tr>/g)];
    assert.equal(rows.length,15);
    for(const [,id,html] of rows){
      const row=snapshot.servos.find(row=>row.id===Number(id)),cells=[...html.matchAll(/<td\b[^>]*>(.*?)<\/td>/g)].map(match=>match[1]);
      assert.equal(cells.length,17,`ID ${id} retains matching column count`);
      assert.equal(cells[2],jointDirection(snapshot,row).label);
      assert.equal(cells[3],String(row.position_raw));assert.equal(cells[4],row.angle_deg.toFixed(1),'direction is display only; no second sign application');
    }
    const header=fs.readFileSync(path.join(source,'service.js'),'utf8');
    assert.match(header,/heads\[2\]\.insertAdjacentHTML\('beforebegin','<th class="saved-direction"[^\n]*>方向<\/th><th>当前位置 \/ counts<\/th>'\)/);
    render({...fixture(),servos:[]});assert.match(rendered,/colspan="17"/);
    render({...fixture(),mode:'monitor'});assert.doesNotMatch(rendered,/saved-direction/);
    assert.equal([...rendered.matchAll(/<td\b/g)].length,15*12,'observer table stays unchanged');
  });
}finally{fs.rmSync(temporary,{recursive:true,force:true});}
