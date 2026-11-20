import assert from 'node:assert/strict';
import * as T from '../docs/vendor/three.module.min.js?demo=20261013';
import {createBatteryPack,createBatteryPickup,BATTERY_PICKUP} from '../docs/assembly-battery-model.js';
const pack=createBatteryPack(),pickup=createBatteryPickup();
pack.group.updateMatrixWorld(true);pickup.root.updateMatrixWorld(true);
const box=new T.Box3().setFromObject(pack.body),size=box.getSize(new T.Vector3());
assert(size.distanceTo(new T.Vector3(.0384,.0206,.0708))<1e-8,'NP-F550 envelope changed');
assert(box.min.y>.029&&box.min.y<.031,'battery must seat between the holder rails, not outside them');
assert(pack.body.getObjectByName('NP-F550-recessed-terminal-cap'),'missing recessed contact cap');
for(const [signal,x]of [['gnd',.0169],['power',-.0169]]){
 const at=pickup.contacts[signal].getWorldPosition(new T.Vector3());
 assert(Math.abs(at.x-x)<1e-9&&Math.abs(at.y-BATTERY_PICKUP.y)<1e-9,'banana contact left battery socket axis');
 const socket=pack.group.getObjectByName(signal==='gnd'?'NP-F550-negative-socket':'NP-F550-positive-socket');
 const target=socket.getWorldPosition(new T.Vector3());
 assert(Math.abs(target.x-at.x)<1e-8&&Math.abs(target.y-at.y)<1e-8,'banana and battery contact axes do not meet');
}
const mouth=pickup.mouth.getWorldPosition(new T.Vector3()),out=pickup.outward.getWorldPosition(new T.Vector3());
assert(out.y<mouth.y&&Math.abs(out.z-mouth.z)<1e-9,'power cable must leave horizontally toward holder interior');
assert.equal(pickup.pinCount,3);assert(pickup.pins.nc);
console.log('PASS: NP-F550 envelope, seated placement, aligned recessed battery contacts and inward right-angle power exit.');
