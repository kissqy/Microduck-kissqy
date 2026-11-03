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
for(const [signal,x]of [['gnd',-.025],['power',.025]]){
 const screw=pickup.screws[signal];assert(screw,'missing pickup screw');
 const at=screw.shaft.getWorldPosition(new T.Vector3());
 assert(Math.abs(at.x-x)<1e-9&&Math.abs(at.z-.0801461)<1e-9,'screw left the actual bore axis');
 assert(!independentRayMesh(new T.Vector3(x,.0271,.0801461),new T.Vector3(x,.037,.0801461),holder),'screw axis misses the arrowed blind hole');
 assert.equal(screw.pin,pickup.pins[signal]);
 assert(screw.head.getWorldPosition(new T.Vector3()).y>.0348,'screw head must sit on the arrowed outward face');
 const axis=new T.Vector3(0,1,0).transformDirection(screw.shaft.matrixWorld);assert(axis.y>.999999,'screw shaft is not normal to the flange face');
 assert(screw.pin.getWorldPosition(new T.Vector3()).distanceTo(screw.head.getWorldPosition(new T.Vector3()))<.002,'wire contact detached from screw head');
}
assert.notEqual(pickup.pins.gnd,pickup.pins.power);
console.log('PASS: vertical NP-F550 envelope, two author-arrowed flange holes, separate screw heads and wire contacts.');
