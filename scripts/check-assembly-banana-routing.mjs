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
const createdElements=[];
globalThis.document={createElement(){const node=element();createdElements.push(node);return node;}};
globalThis.window={matchMedia:()=>({matches:true})};
globalThis.fetch=async url=>{const path=new URL(url).pathname;assert(path.startsWith(dir+'assets/'));const data=readFileSync(path);return{ok:true,arrayBuffer:async()=>arrayBuffer(data),json:async()=>JSON.parse(data.toString())};};
const view=new DuckView();view.model=parseDuck(arrayBuffer(buffer));
view.geometry=view.model.meshes.map(m=>{const g=new T.BufferGeometry();g.setAttribute('position',new T.BufferAttribute(m.vertices,3));g.setAttribute('normal',new T.BufferAttribute(m.normals,3));g.setIndex(new T.BufferAttribute(m.indices,1));g.computeBoundingBox();g.computeBoundingSphere();return g;});
view.actual=view.build(false);view.actual.parts.forEach((mesh,index)=>{mesh.name='reference-part-'+index;});view.ghost=view.build(true);view.scene=new T.Scene();view.scene.add(view.actual.root,view.ghost.root);
view.container={...element(),clientWidth:800,clientHeight:600};view.renderer={domElement:element()};
view.camera=new T.PerspectiveCamera(37,4/3,.005,20);view.camera.up.set(0,0,1);
view.controls={target:new T.Vector3(0,0,.15),update(){view.camera.lookAt(this.target);view.camera.updateMatrixWorld(true);}};
view.pose(view.actual,Array(15).fill(0),[0,0,-1],0);view.view('front');

const api=await attachElectronics(view,()=>{},{useWireCache:false});
api.setWiringVisible(true);
const w=api.routes.find(w=>w.id==='battery-hub');

function audit(){
 view.actual.root.updateMatrixWorld(true);
 return w.conductors.map(c=>{
  assert(c.mesh.visible&&!c.mesh.userData.routingError,'power conductor must remain connected');
  const path=c.mesh.geometry.parameters.path;
  const points=path.getPoints(120).map(p=>api.batteryHolder.group.worldToLocal(view.actual.root.localToWorld(p.clone())));
  return{length:path.getLength(),maxZ:Math.max(...points.map(p=>p.z))};
 });
}
const pack=api.batteryHolder.pack.group,holder=api.batteryHolder.mesh;
const relative=()=>pack.getWorldPosition(new T.Vector3()).sub(holder.getWorldPosition(new T.Vector3()));
const assembledRelative=relative();
const assembled=audit();
assert(assembled.every(c=>c.maxZ<.0825),'assembled power cable escaped above the torso skin');
api.setExploded(true);const expanded=audit();
assert(relative().distanceTo(assembledRelative)>.05,'battery did not separate from its holder');
assert(expanded.every(c=>c.length>.1),'exploded power cable did not follow the battery holder');
api.setExploded(false);const restored=audit();
assert(relative().distanceTo(assembledRelative)<1e-8,'battery did not return to its seated position');
restored.forEach((c,i)=>{assert(c.maxZ<.0825,'restored wire retained exploded exterior route');assert(Math.abs(c.length-assembled[i].length)<1e-6,'restored power route changed');});
api.dispose();
console.log('PASS: connected power conductors stay inside the assembled torso and return after explosion.');
