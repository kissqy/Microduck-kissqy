// Read-only geometry regression; run: node scripts/check-assembly-wiring.mjs [--all]
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import * as T from '../docs/vendor/three.module.min.js?demo=20261013';
import {parseDuck} from '../docs/pose.js?demo=20261013';
import {DuckView} from '../docs/duck.js';
import {attachElectronics} from '../docs/assembly-electronics.js';
import {independentRayMesh} from './assembly-ray-audit.mjs';
const dir=new URL('../docs/',import.meta.url).pathname;
const buffer=readFileSync(dir+'assets/duck-visual.bin');
const stl=readFileSync(dir+'assets/assembly-battery-holder.stl');
const arrayBuffer=b=>b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);
const element=()=>({style:{},hidden:false,attrs:{},listeners:{},setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,v){this.listeners[k]=v;},removeEventListener(k){delete this.listeners[k];},remove(){},append(){},getContext(){return null;},getBoundingClientRect(){return{left:0,top:0,width:800,height:600};}});
globalThis.document={createElement:element};
globalThis.window={matchMedia:()=>({matches:true})};
globalThis.fetch=async url=>{const path=new URL(url).pathname;assert(path.startsWith(dir+'assets/'));const data=readFileSync(path);return{ok:true,arrayBuffer:async()=>arrayBuffer(data),json:async()=>JSON.parse(data.toString())};};
const view=new DuckView();view.model=parseDuck(arrayBuffer(buffer));
view.geometry=view.model.meshes.map(m=>{const g=new T.BufferGeometry();g.setAttribute('position',new T.BufferAttribute(m.vertices,3));g.setAttribute('normal',new T.BufferAttribute(m.normals,3));g.setIndex(new T.BufferAttribute(m.indices,1));g.computeBoundingBox();g.computeBoundingSphere();return g;});
view.actual=view.build(false);view.ghost=view.build(true);view.scene=new T.Scene();view.scene.add(view.actual.root,view.ghost.root);
view.container={...element(),clientWidth:800,clientHeight:600};view.renderer={domElement:element()};
view.camera=new T.PerspectiveCamera(37,4/3,.005,20);view.camera.up.set(0,0,1);
view.controls={target:new T.Vector3(0,0,.15),update(){view.camera.lookAt(this.target);view.camera.updateMatrixWorld(true);}};
view.pose(view.actual,Array(15).fill(0),[0,0,-1],0);view.view('front');
const rest=view.actual.parts.map(p=>p.position.clone());
const api=await attachElectronics(view,()=>{},{useWireCache:!process.argv.includes('--fresh-cache')});assert.equal(api.batteryHolder.error,null);assert(api.batteryHolder.mesh);
api.setWiringVisible(true);assert.equal(view.model.parts.length,64);assert.equal(api.explosion.count,34);
const hub=api.components.get('hub');view.actual.root.updateMatrixWorld(true);
const hubForward=new T.Vector3(0,1,0).transformDirection(hub.group.matrixWorld);
assert(hubForward.x>.999,'HUB front/back mounting direction reversed');
const cap=hub.group.getObjectByName('HUB-C1-can');
assert(hub.group.worldToLocal(cap.getWorldPosition(new T.Vector3())).z<0,'HUB capacitor must be mounted on reverse side');

const {meshCollider}=await import('../docs/assembly-mesh-clearance.js');
// Surface clearance must detect thin walls and preserve real openings.
const panel=new T.Mesh(new T.BoxGeometry(.03,.03,.002));
const collider=meshCollider(panel.geometry);
assert(collider.hit(new T.Vector3(0,0,-.01),new T.Vector3(0,0,.01),.00055));
assert(collider.hit(new T.Vector3(0,0,.0013),new T.Vector3(.005,0,.0013),.00055));
assert(!collider.hit(new T.Vector3(.02,0,-.01),new T.Vector3(.02,0,.01),.00055));
const frameShape=new T.Shape();frameShape.moveTo(-.02,-.02);frameShape.lineTo(.02,-.02);frameShape.lineTo(.02,.02);frameShape.lineTo(-.02,.02);frameShape.closePath();
const opening=new T.Path();opening.absarc(0,0,.006,0,Math.PI*2,true);frameShape.holes.push(opening);
const hollow=meshCollider(new T.ExtrudeGeometry(frameShape,{depth:.002,bevelEnabled:false}));
assert(!hollow.hit(new T.Vector3(0,0,-.01),new T.Vector3(0,0,.01),.00055),'real cable opening was filled by a box');
assert(hollow.hit(new T.Vector3(.012,0,-.01),new T.Vector3(.012,0,.01),.00055),'printed frame wall was ignored');

const ids=[20,21,22,23,24,30,31,32,33,34,10,11,12,13,14];
const poses=[{name:'zero',joints:Array(15).fill(0)}];
view.setReference('home');poses.push({name:'home',joints:[...view.referenceJoints]});
if(process.argv.includes('--all'))for(let i=0;i<15;i++)for(const sign of[-1,1]){const joints=Array(15).fill(0);joints[i]=sign*Math.PI/18;poses.push({name:'servo'+ids[i]+(sign<0?'-10':'+10'),joints});}
poses.push({name:'zero-open-lid',joints:poses[0].joints,open:true},{name:'zero-exploded-open-lid',joints:poses[0].joints,open:true,exploded:true},{name:'home-exploded-open-lid',joints:poses[1].joints,open:true,exploded:true},{name:'zero-exploded',joints:Array(15).fill(0),exploded:true},{name:'home-exploded',joints:poses[1].joints,exploded:true},{name:'home-open-lid',joints:poses[1].joints,open:true});
if(process.argv.includes('--zero-only'))poses.splice(1);
const allMeshes=api.collisionMeshes;
const raycaster=new T.Raycaster(),results=[],started=performance.now();
function assertAttached(){
 const root=view.actual.root;
 for(const route of api.routes)for(const conductor of route.conductors){
  assert(conductor.mesh.visible,`${route.id}/${conductor.signal}: hidden cable ${JSON.stringify(conductor.mesh.userData.routingError)}`);
  assert(!conductor.mesh.userData.routingError,route.id);
  const curve=conductor.mesh.geometry.parameters?.path;assert(curve,route.id+' has no actual tube');
  const actualStart=curve.getPoint(0).applyMatrix4(root.matrixWorld),actualEnd=curve.getPoint(1).applyMatrix4(root.matrixWorld);
  assert(actualStart.distanceTo(conductor.start.getWorldPosition(new T.Vector3()))<1e-8,route.id+' start detached');
  assert(actualEnd.distanceTo(conductor.end.getWorldPosition(new T.Vector3()))<1e-8,route.id+' end detached');
 }
}
function checkSegment(a,b,meshes,context){
 const length=a.distanceTo(b);if(length<1e-10)return;
 const segmentBounds=new T.Box3().setFromPoints([a,b]);raycaster.set(a,b.clone().sub(a).normalize());raycaster.near=1e-7;raycaster.far=length-1e-7;
 for(const obstacle of meshes){if(!segmentBounds.intersectsBox(obstacle.box))continue;
  const hit=independentRayMesh(a,b,obstacle.mesh);
  assert(!hit,`${context}: crosses ${obstacle.name} at ${hit?.toArray()}`);
 }
}
for(const pose of poses){
 const began=performance.now();api.setExploded(false);api.setCoverOpen(false);view.referenceMode='measured';view.pose(view.actual,pose.joints,[0,0,-1],0);
 if(pose.open)api.setCoverOpen(true);if(pose.exploded)api.setExploded(true);api.update();view.actual.root.updateMatrixWorld(true);assertAttached();
 const obstacles=allMeshes.map(mesh=>{mesh.material.side=T.DoubleSide;return{mesh,name:mesh.userData.hd1910Assembly?.id??api.explosion.printedParts.find(p=>p.mesh===mesh)?.name??mesh.name,box:mesh.geometry.boundingBox.clone().applyMatrix4(mesh.matrixWorld)};});
 let segments=0,cores=0;
 for(const route of api.routes){if(route.header)continue;
  for(const conductor of route.conductors){cores++;const curve=conductor.mesh.geometry.parameters.path;
   // Exact straight segments need one ray, regardless of length. Sample only
   // curved bends; resampling long lines thousands of times adds no coverage.
   const pieces=curve.curves||[curve],points=[pieces[0].getPoint(0)];
   for(const piece of pieces){const count=piece.isLineCurve3?1:Math.max(1,Math.ceil(piece.getLength()/.00035));for(let i=1;i<=count;i++)points.push(piece.getPoint(i/count));}
   for(let i=1;i<points.length;i++){const a=points[i-1].clone().applyMatrix4(view.actual.root.matrixWorld),b=points[i].clone().applyMatrix4(view.actual.root.matrixWorld);checkSegment(a,b,obstacles,pose.name+'/'+route.id+'/'+conductor.signal);segments++;}
   // Independent checks on the rendered TubeGeometry's six outer longitudinal
   // edges in the two common poses, not just the planner's sampled centreline.
   if(['zero','home'].includes(pose.name)){
    const positions=conductor.mesh.geometry.getAttribute('position'),radial=7;
    for(let i=radial;i<positions.count;i++)if(i%radial!==6){const a=new T.Vector3().fromBufferAttribute(positions,i-radial).applyMatrix4(conductor.mesh.matrixWorld),b=new T.Vector3().fromBufferAttribute(positions,i).applyMatrix4(conductor.mesh.matrixWorld);checkSegment(a,b,obstacles,pose.name+'/'+route.id+'/tube');segments++;}
   }
  }
 }
 assert.equal(cores,53);assert.equal(api.routes.find(r=>r.header).conductors.length,40);
 const imu=api.components.get('imu'),holder=api.batteryHolder.mesh;
 const boardRelative=holder.worldToLocal(imu.group.getWorldPosition(new T.Vector3()));
 const pinRelative=holder.worldToLocal(imu.ports.J1.pins.power.getWorldPosition(new T.Vector3()));
 if(!results.length){globalThis.mountReference={board:boardRelative.clone(),pin:pinRelative.clone()};}
 assert(boardRelative.distanceTo(globalThis.mountReference.board)<1e-8,'IMU left battery mount');
 assert(pinRelative.distanceTo(globalThis.mountReference.pin)<1e-8,'IMU socket left battery mount');
 assert(pinRelative.z>boardRelative.z+.005,'IMU socket not at top');
 const roundedCores=api.routes.filter(r=>!r.header).reduce((n,r)=>n+r.conductors.filter(c=>c.mesh.geometry.parameters.path.curves?.some(piece=>piece.isQuadraticBezierCurve3)).length,0);
 assert(roundedCores>=30,'rounded cable bends missing from rendered paths');
 results.push({pose:pose.name,cores,roundedCores,cachedCores:api.routes.filter(r=>!r.header).reduce((n,r)=>n+r.conductors.filter(c=>c.mesh.userData.cached).length,0),bundledCores:api.routes.filter(r=>!r.header).reduce((n,r)=>n+r.conductors.filter(c=>c.mesh.userData.bundled).length,0),segments,unexemptedCrossings:0,timeMS:Math.round(performance.now()-began)});
 if(process.argv.includes('--generate-cache'))writeFileSync(dir+'assets/assembly-wire-cache.json',JSON.stringify(api.exportWireCache())+'\n');
 console.log(JSON.stringify(results.at(-1)));
}
if(process.argv.includes('--generate-cache'))writeFileSync(dir+'assets/assembly-wire-cache.json',JSON.stringify(api.exportWireCache())+'\n');
api.setExploded(false);api.setCoverOpen(false);view.setReference('zero');assertAttached();
const output={result:'PASS',poses:results.length,servoMeshes:15,printedMeshes:api.explosion.count,electronicsAndSocketCollisionMeshes:api.collisionMeshes.length-15-api.explosion.count,cores:53,headerContacts:40,segments:results.reduce((n,r)=>n+r.segments,0),crossings:0,IMU:'board and actual J1 contacts follow battery holder, including explosion/collapse',timeMS:Math.round(performance.now()-started),results};
if(process.env.ASSEMBLY_WIRING_REPORT)writeFileSync(process.env.ASSEMBLY_WIRING_REPORT,JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify(output));api.dispose();
