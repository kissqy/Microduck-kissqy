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
 assert(Math.abs(delta.z)<1e-10,'right-angle connector points through PCB');assert(delta.length()>.0039);
 assert.equal(c.bottom,false);
 assert(Math.sign(port.pins.data.getWorldPosition(new T.Vector3()).z)===(c.bottom?-1:1));
}
assert.equal(ports.CN1.pins.gnd.userData.pin,'1');assert.equal(ports.CN1.pins.power.userData.pin,'2');
assert(group.getObjectByName('HUB-C1-can').getWorldPosition(new T.Vector3()).z>0,'capacitor must share the bus-connector side');
const collider=meshCollider(pcb.geometry);
for(const [x,y,r]of HUB_LAYOUT.holes){assert(Math.abs(r-1.2)<1e-6);assert(!collider.hit(new T.Vector3(x/1000,y/1000,-.003),new T.Vector3(x/1000,y/1000,.003),.001),'mounting hole filled');}
assert(!collider.hit(new T.Vector3(.010,0,-.003),new T.Vector3(.010,0,.003),0),'HUB notch filled by rectangular PCB');
assert(collider.hit(new T.Vector3(.005,0,-.003),new T.Vector3(.005,0,.003),0),'PCB missing between notches');
console.log('PASS: source-backed HUB outline, four real mounting holes, CN2-CN5 pin nets and board side, right-angle mouths, CN1 polarity and capacitor side.');
