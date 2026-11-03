import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import * as T from '../docs/vendor/three.module.min.js?demo=20261013';
import {createBatteryPack,createBatteryPickup} from '../docs/assembly-battery-model.js';
import {parseBatterySTL} from '../docs/assembly-electronics.js';
import {independentRayMesh} from './assembly-ray-audit.mjs';

const buffer=readFileSync(new URL('../docs/assets/assembly-battery-holder.stl',import.meta.url));
const holder=new T.Mesh(parseBatterySTL(buffer.buffer.slice(buffer.byteOffset,buffer.byteOffset+buffer.byteLength)));
const pack=createBatteryPack(),pickup=createBatteryPickup();
holder.updateMatrixWorld(true);pickup.root.updateMatrixWorld(true);pack.group.updateMatrixWorld(true);
pack.body.geometry.computeBoundingBox();
const size=pack.body.geometry.boundingBox.getSize(new T.Vector3());
assert(size.distanceTo(new T.Vector3(.0384,.0206,.0708))<1e-8,'NP-F550 exterior dimensions changed');
assert(new T.Box3().setFromObject(pack.body).min.y>.035,'pack cuts into the holder rail envelope');
// Face the battery label from raw +Y with its contact end up: +X is left.
for(const [signal,x]of [['gnd',.0169],['power',-.0169]]){
 const screw=pickup.screws[signal];assert(screw,'missing pickup screw');
 const at=screw.shaft.getWorldPosition(new T.Vector3());
 assert(Math.abs(at.x-x)<1e-9&&Math.abs(at.y-.0316)<1e-9,'screw left the actual contact-hole axis');
 assert(!independentRayMesh(new T.Vector3(x,.0316,.0755),new T.Vector3(x,.0316,.080),holder),'screw axis misses the arrowed vertical contact hole');
 // Each opening is bounded by a real 2 mm bore, not empty exterior space.
 for(const [dx,dy]of [[.00115,0],[-.00115,0],[0,.00115],[0,-.00115]])assert(independentRayMesh(new T.Vector3(x+dx,.0316+dy,.0755),new T.Vector3(x+dx,.0316+dy,.080),holder),'missing contact-hole wall');
 assert.equal(screw.pin,pickup.pins[signal]);
 assert(screw.head.getWorldPosition(new T.Vector3()).z>.0775,'screw head must sit above the top contact hole');
 const axis=new T.Vector3(0,1,0).transformDirection(screw.shaft.matrixWorld);assert(axis.z>.999999,'screw shaft is not vertical through the contact hole');
 assert(screw.pin.getWorldPosition(new T.Vector3()).distanceTo(screw.head.getWorldPosition(new T.Vector3()))<.002,'wire contact detached from screw head');
}
assert.notEqual(pickup.pins.gnd,pickup.pins.power);
assert(pickup.pins.gnd.getWorldPosition(new T.Vector3()).x>pickup.pins.power.getWorldPosition(new T.Vector3()).x,'battery label view must be left negative, right positive');
console.log('PASS: vertical NP-F550, two bounded top contact holes, vertical screws, battery left negative/right positive and attached wire contacts.');
