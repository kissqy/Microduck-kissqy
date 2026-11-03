import assert from 'node:assert/strict';
import * as T from '../docs/vendor/three.module.min.js?demo=20261013';
import {HUB_LAYOUT} from '../docs/assembly-hub-layout.js';
import {createHubModel} from '../docs/assembly-hub-model.js';
import {meshCollider} from '../docs/assembly-mesh-clearance.js';
const {group,pcb,ports}=createHubModel();group.updateMatrixWorld(true);
assert.equal(HUB_LAYOUT.thickness,1);assert.equal(HUB_LAYOUT.width,23);assert.equal(HUB_LAYOUT.height,34);assert.equal(HUB_LAYOUT.holes.length,4);
assert.deepEqual(Object.keys(ports).sort(),['CN1','CN2','CN3','CN4','CN5']);
for(const ref of ['CN2','CN3','CN4','CN5']){
 const port=ports[ref],c=HUB_LAYOUT.components.find(x=>x.ref===ref);
 assert.equal(port.pins.gnd.userData.pin,'3');assert.equal(port.pins.power.userData.pin,'2');assert.equal(port.pins.data.userData.pin,'1');
 const delta=port.outward.getWorldPosition(new T.Vector3()).sub(port.mouth.getWorldPosition(new T.Vector3()));
 assert(delta.z<-.0039&&Math.abs(delta.x)<1e-10&&Math.abs(delta.y)<1e-10,'bus socket must point straight down, perpendicular to PCB');assert.equal(port.kind,'bus3');assert.equal(port.pinCount,3);
 assert.equal(c.bottom,true);
 assert(Math.sign(port.pins.data.getWorldPosition(new T.Vector3()).z)===(c.bottom?-1:1));
}
assert.equal(ports.CN1.pins.gnd.userData.pin,'1');assert.equal(ports.CN1.pins.power.userData.pin,'2');
assert.equal(HUB_LAYOUT.components.find(c=>c.ref==='CN1').bottom,false);
assert(ports.CN1.outward.getWorldPosition(new T.Vector3()).z>ports.CN1.mouth.getWorldPosition(new T.Vector3()).z+.0039,'CN1 power socket must face up');
assert(group.getObjectByName('HUB-C1-can').getWorldPosition(new T.Vector3()).z<0,'capacitor must share the underside bus-connector face');
const collider=meshCollider(pcb.geometry);
for(const [x,y,r]of HUB_LAYOUT.holes){assert(Math.abs(r-1.2)<1e-6);assert(!collider.hit(new T.Vector3(x/1000,y/1000,-.003),new T.Vector3(x/1000,y/1000,.003),.001),'mounting hole filled');}
assert(!collider.hit(new T.Vector3(.010,0,-.003),new T.Vector3(.010,0,.003),0),'HUB notch filled by rectangular PCB');
assert(collider.hit(new T.Vector3(.005,0,-.003),new T.Vector3(.005,0,.003),0),'PCB missing between notches');
console.log('PASS: source-backed HUB outline, four real mounting holes, CN2-CN5 pin nets and board side, straight downward mouths, CN1 polarity and capacitor side.');
