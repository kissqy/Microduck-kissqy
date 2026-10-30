import * as T from './vendor/three.module.min.js?demo=20261013';
import {createBoardModel} from './assembly-board-models.js?v=20261030-hub-arcs';
import {attachPrintExplosion,PRINTED_MESH_NAMES} from './assembly-explosion.js?v=20261027-printed-clearance';
import {prepareServoModels,attachServoModel} from './assembly-servo-models.js?v=20261030-hub-arcs';
import {createHubModel} from './assembly-hub-model.js?v=20261030-hub-arcs';
import {loadWireCache,packCable,unpackCable,WIRE_CACHE_REVISION} from './assembly-wire-cache.js?v=20261030-hub-arcs';
import {parallelCablePaths} from './assembly-cable-bundles.js?v=20261030-hub-arcs';
import {softenCableCorners} from './assembly-wire-curves.js?v=20261030-hub-arcs';
import {createWireRouter} from './assembly-wire-routing.js?v=20261030-hub-arcs';

// Board footprints are documented; mounting offsets are assembly-reference
// placements, not a mechanical clearance or connector pin-direction drawing.
export const ELECTRONICS_LAYOUT=Object.freeze({
  hat:Object.freeze({name:'HAT',width:.065,height:.0309,color:0x208778,location:'face',outline:'documented'}),
  zero:Object.freeze({name:'ZERO 3W',width:.065,height:.030,color:0x286d9a,location:'face',outline:'documented'}),
  imu:Object.freeze({name:'IMU',width:.0227,height:.0256,color:0x8b61a5,location:'battery-back',outline:'documented'}),
  hub:Object.freeze({name:'HUB',width:.023,height:.034,color:0xb78142,location:'hip-center',outline:'documented'}),
});
const wire=(id,from,to,label,color,region)=>Object.freeze({id,from,to,label,color,region});
export const ELECTRONICS_WIRES=Object.freeze([
  wire('hat-zero','hat','zero','HAT J4 ↔ ZERO 3W · 40 针配对','#8e82c3','face'),
  wire('hat-34','hat','servo34','HAT → 34','#e4aa66','face'),
  ...[[34,33],[33,32],[32,31],[31,30]].map(([a,b])=>wire(`servo-${a}-${b}`,`servo${a}`,`servo${b}`,`${a} → ${b}`,'#e4aa66','neck')),
  wire('30-hub','servo30','hub','30 → HUB · 躯干分线','#e4aa66','trunk'),
  wire('hub-20','hub','servo20','HUB → 左腿 20','#96c474','left'),
  ...[[20,21],[21,22],[22,23],[23,24]].map(([a,b])=>wire(`servo-${a}-${b}`,`servo${a}`,`servo${b}`,`${a} → ${b}`,'#96c474','left')),
  wire('hub-10','hub','servo10','HUB → 右腿 10','#7eadd7','right'),
  ...[[10,11],[11,12],[12,13],[13,14]].map(([a,b])=>wire(`servo-${a}-${b}`,`servo${a}`,`servo${b}`,`${a} → ${b}`,'#7eadd7','right')),
  wire('hub-imu','hub','imu','HUB → 电池仓背面 IMU','#78beb7','battery'),
  wire('battery-hub','battery','hub','电池电源 → HUB CN1','#db8e83','battery'),
]);

const COVER_MESH_INDEX=21,FACE_MESH_INDEX=19,STL_URL=new URL('./assets/assembly-battery-holder.stl',import.meta.url);
const SERVO_INDEX=Object.freeze({20:0,21:1,22:2,23:3,24:4,30:5,31:6,32:7,33:8,34:9,10:10,11:11,12:12,13:13,14:14});
const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
const basisQuaternion=(x,y,z)=>new T.Quaternion().setFromRotationMatrix(new T.Matrix4().makeBasis(x,y,z));
const vector=(x,y,z)=>new T.Vector3(x,y,z);
const objectCenter=object=>new T.Box3().setFromObject(object).getCenter(new T.Vector3());

export function parseBatterySTL(buffer){
  const data=new DataView(buffer);if(data.byteLength<84)throw Error('电池仓 STL 不完整');
  const count=data.getUint32(80,true);if(count<1||count>200000||84+count*50!==data.byteLength)throw Error('电池仓 STL 格式不符');
  const positions=new Float32Array(count*9),normals=new Float32Array(count*9);
  for(let i=0;i<count;i++){
    const offset=84+i*50,n=[data.getFloat32(offset,true),data.getFloat32(offset+4,true),data.getFloat32(offset+8,true)];
    for(let j=0;j<3;j++)for(let axis=0;axis<3;axis++){
      const value=data.getFloat32(offset+12+j*12+axis*4,true);if(!Number.isFinite(value))throw Error('电池仓 STL 顶点无效');
      positions[i*9+j*3+axis]=value*.001;normals[i*9+j*3+axis]=n[axis];
    }
  }
  const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.BufferAttribute(positions,3));geometry.setAttribute('normal',new T.BufferAttribute(normals,3));geometry.computeBoundingBox();geometry.computeBoundingSphere();return geometry;
}

const WIRE_SIGNALS=['gnd','power','data'];
const SIGNAL_COLORS={gnd:0x465054,power:0xd8756c,data:0xe3e4da};
function makeTerminal(parent,name,{count=3,pitch=.002,position=vector(0,0,0),quaternion=new T.Quaternion(),kind=count===2?'power2':'bus3'}={}){
  const root=new T.Group();root.name=name;root.position.copy(position);root.quaternion.copy(quaternion);parent.add(root);
  const shellMaterial=new T.MeshStandardMaterial({color:0xe7e4d9,roughness:.66,metalness:.02});
  const metalMaterial=new T.MeshStandardMaterial({color:0xc9b26b,roughness:.32,metalness:.65});
  const width=(count-1)*pitch+.0032,depth=.0044,height=.0046;
  const add=(w,h,d,x,y,z,material=shellMaterial)=>{const m=new T.Mesh(new T.BoxGeometry(w,h,d),material);m.position.set(x,y,z);root.add(m);return m;};
  add(width,depth,.0007,0,0,-height/2);
  add(width,.0007,height,0,depth/2-.00035,0);
  for(const sign of[-1,1])add(.00065,depth,height,sign*(width/2-.000325),0,0);
  add(width*.45,.00065,.001,0,-depth/2+.000325,-.0008);
  const pins={},ordered=[];const signalNames=count===2?['gnd','power']:WIRE_SIGNALS;
  signalNames.forEach((signal,i)=>{
    const x=(i-(count-1)/2)*pitch;
    add(.00055,.0008,.0027,x,.00045,-.00035,metalMaterial);
    const pin=new T.Object3D();pin.name=name+'-'+signal;pin.position.set(x,.00045,.001);pin.userData.signal=signal;root.add(pin);pins[signal]=pin;ordered.push(pin);
  });
  const mouth=new T.Object3D();mouth.position.set(0,.00045,height/2);root.add(mouth);
  const outward=new T.Object3D();outward.position.set(0,.00045,height/2+.0045);root.add(outward);
  return{root,pins,ordered,mouth,outward,kind,pinCount:count};
}
function boundsInFrame(mesh,frame){
  const box=mesh.geometry.boundingBox||mesh.geometry.computeBoundingBox()||mesh.geometry.boundingBox;
  mesh.updateWorldMatrix(true,false);frame.updateWorldMatrix(true,false);const result=new T.Box3();
  for(const x of[box.min.x,box.max.x])for(const y of[box.min.y,box.max.y])for(const z of[box.min.z,box.max.z])result.expandByPoint(frame.worldToLocal(mesh.localToWorld(vector(x,y,z))));
  return result;
}

// Find the supporting backplate in the actual STL around the IMU's four-hole
// mounting region. The global minimum Y is a retaining-bar tip, not this face.
export function batteryBackMountPlane(geometry,{centerX=0,centerZ=.0264,halfWidth=.013,halfHeight=.015}={}){
  const positions=geometry?.getAttribute('position');if(!positions)return null;
  const planes=new Map();
  for(let i=0;i+2<positions.count;i+=3){
    const x0=positions.getX(i),y0=positions.getY(i),z0=positions.getZ(i),x1=positions.getX(i+1),y1=positions.getY(i+1),z1=positions.getZ(i+1),x2=positions.getX(i+2),y2=positions.getY(i+2),z2=positions.getZ(i+2);
    if(Math.max(y0,y1,y2)-Math.min(y0,y1,y2)>1e-7)continue;
    const cx=(x0+x1+x2)/3,cz=(z0+z1+z2)/3;
    if(Math.abs(cx-centerX)>halfWidth||Math.abs(cz-centerZ)>halfHeight)continue;
    const crossY=(z1-z0)*(x2-x0)-(x1-x0)*(z2-z0);
    if(crossY>=-1e-12)continue; // supporting face points towards raw -Y
    const key=Math.round((y0+y1+y2)/3*1e6),plane=planes.get(key)||{y:key/1e6,area:0,triangles:0};
    plane.area-=crossY/2;plane.triangles++;planes.set(key,plane);
  }
  return [...planes.values()].sort((a,b)=>b.area-a.area)[0]||null;
}

/** Add read-only electronics in their described assembly regions. No robot I/O. */
export async function attachElectronics(view,onSelect=()=>{},{useWireCache=true}={}){
  const wireCache=useWireCache?await loadWireCache():new Map();
  if(!view?.actual?.parts||!view?.model?.parts)throw Error('装配结构模型尚未加载');
  const root=view.actual.root,container=view.container,canvas=view.renderer.domElement,trunk=view.actual.bodies[0];
  const coverIndex=view.model.parts.findIndex(p=>p.mesh===COVER_MESH_INDEX),faceIndex=view.model.parts.findIndex(p=>p.mesh===FACE_MESH_INDEX);
  const cover=view.actual.parts[coverIndex],face=view.actual.parts[faceIndex];
  if(!cover||!face||view.model.parts[coverIndex].body!==9||view.model.parts[faceIndex].body!==9)throw Error('头盖或鸭脸定位与冻结模型不一致');
  await prepareServoModels();
  const servoDetails=new Map();
  for(const[id,index]of Object.entries(SERVO_INDEX))servoDetails.set(Number(id),attachServoModel(view.actual.servos[index],Number(id)));
  root.updateMatrixWorld(true);
  const headParent=face.parent,coverRest=cover.position.clone(),coverOpacity=cover.material.opacity;
  const coverWorldBox=new T.Box3().setFromObject(cover),headSize=coverWorldBox.getSize(new T.Vector3()),faceBox=new T.Box3().setFromObject(face),faceCenter=faceBox.getCenter(new T.Vector3());
  const leftHip=view.actual.servos[SERVO_INDEX[20]],rightHip=view.actual.servos[SERVO_INDEX[10]];
  const leftHipBox=new T.Box3().setFromObject(leftHip),rightHipBox=new T.Box3().setFromObject(rightHip);
  const hipCenter=objectCenter(leftHip).add(objectCenter(rightHip)).multiplyScalar(.5);
  // HUB lies flat across the top of the 10/20 housings on their centreline.
  const hubCenter=vector(hipCenter.x,hipCenter.y,Math.max(leftHipBox.max.z,rightHipBox.max.z)+.0063);
  const holderReferenceX=Math.min(leftHipBox.min.x,rightHipBox.min.x)-.003;
  // Actual STL axes: raw X = width, raw +Y = battery-rail side, raw Z = up.
  // Map raw X→robot Y, raw Y→robot -X; keep the holder at the rear mount.
  const batteryMount=new T.Group();batteryMount.name='assembly-battery-holder-mount';trunk.add(batteryMount);
  const holderOffset=vector(holderReferenceX+.017,hipCenter.y,hipCenter.z-.055);
  batteryMount.position.copy(trunk.worldToLocal(holderOffset.clone()));
  batteryMount.quaternion.copy(trunk.getWorldQuaternion(new T.Quaternion()).invert()).multiply(new T.Quaternion().setFromAxisAngle(vector(0,0,1),Math.PI/2));
  let batteryMesh=null,batteryError=null;
  try{
    const response=await fetch(STL_URL);if(!response.ok)throw Error('电池仓模型读取失败');
    const geometry=parseBatterySTL(await response.arrayBuffer());
    batteryMesh=new T.Mesh(geometry,new T.MeshStandardMaterial({color:0xc4c9c8,roughness:.73,metalness:.04,side:T.DoubleSide}));
    batteryMesh.name='电池仓_M2.5螺丝_HUB组合.stl';batteryMount.add(batteryMesh);
  }catch(error){batteryError=error?.message||'电池仓模型未加载';}
  const faceOrientation=basisQuaternion(vector(0,-1,0),vector(0,0,1),vector(-1,0,0));
  const rearBoardOrientation=basisQuaternion(vector(0,1,0),vector(0,0,1),vector(1,0,0));
  const facePositions={
    zero:vector(faceBox.min.x-.006,faceCenter.y,faceCenter.z),
    hat:vector(faceBox.min.x-.017,faceCenter.y,faceCenter.z),
  };
  const components=new Map(),boardTargets=[];
  const originalUpdate=view.update,originalAdvanceFocus=view.advanceFocus,originalPose=view.pose;
  let wireFocus=null;
  let disposed=false,selected=null,wiringVisible=false,batteryVisible=true,coverOpen=false,coverAmount=0,coverFrom=0,coverTo=0,coverStarted=0;
  let coverBaseOpacity=coverOpacity,coverBaseTransparent=cover.material.transparent,coverBaseDepthWrite=cover.material.depthWrite;
  const reducedMotion=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const coverUp=vector(0,0,1).applyQuaternion(headParent.getWorldQuaternion(new T.Quaternion()).invert()).normalize();
  const coverLift=clamp(headSize.z*1.3,.045,.075);
  const cutawayIndices=[1,2,3,4,5],cutawayBase=new Map();
  const captureCutaway=()=>cutawayIndices.forEach(index=>{const m=view.actual.parts[index].material;cutawayBase.set(index,{opacity:m.opacity,transparent:m.transparent,depthWrite:m.depthWrite});});captureCutaway();

  for(const [id,spec]of Object.entries(ELECTRONICS_LAYOUT)){
    const built=id==='hub'?createHubModel(spec):createBoardModel(id,spec),component={id,spec,...built,visible:true,label:null};
    component.group.name=`assembly-${id}`;component.group.userData.component=id;
    const parent=spec.location==='face'?headParent:spec.location==='battery-back'?batteryMount:trunk;parent.add(component.group);
    if(spec.location==='face'){
      component.group.position.copy(parent.worldToLocal(facePositions[id].clone()));
      component.group.quaternion.copy(parent.getWorldQuaternion(new T.Quaternion()).invert()).multiply(faceOrientation);
    }else if(id==='hub'){
      component.group.position.copy(parent.worldToLocal(hubCenter.clone()));
      // Keep the PCB horizontal; turn its long axis into the front/back
      // direction, rather than across the two hip servos.
      component.group.quaternion.copy(parent.getWorldQuaternion(new T.Quaternion()).invert()).multiply(new T.Quaternion().setFromAxisAngle(vector(0,0,1),-Math.PI/2));
    }else{
      // Lower backplate has the IMU's four through-hole region (raw Z16.6/36.2).
      component.group.position.set(0,0,.0264);
      component.group.quaternion.copy(parent.getWorldQuaternion(new T.Quaternion()).invert()).multiply(rearBoardOrientation);
      component.group.updateWorldMatrix(true,true);
      const port=component.ports?.J1;if(!port)throw Error('IMU 缺少 J1 端子定位');
      if(port.root.getWorldPosition(new T.Vector3()).z<component.group.getWorldPosition(new T.Vector3()).z)component.group.rotateZ(Math.PI);
      component.group.updateWorldMatrix(true,true);
      const pcbBounds=boundsInFrame(component.pcb,batteryMount);
      const mountSurface=batteryBackMountPlane(batteryMesh?.geometry,{centerZ:.0264,halfWidth:component.width/2+.0015,halfHeight:component.height/2+.0015});
      // The current source STL's measured backplate is raw Y=25 mm. Preserve
      // that source-backed fallback if its asset cannot be loaded.
      const flatBackY=mountSurface?.y??.025;
      component.group.position.y=flatBackY-.00005-pcbBounds.max.y;
      component.mountSurface={...mountSurface,y:flatBackY,gap:.00005,method:'dominant-local-negative-Y-face'};
    }
    component.group.traverse(object=>{if(object.isMesh){object.userData.component=id;boardTargets.push(object);}});
    const label=document.createElement('button');label.type='button';label.className='electronics-label';label.textContent=spec.name;label.setAttribute('aria-label',`查看 ${id==='zero'?'Radxa ZERO 3W':spec.name}`);
    Object.assign(label.style,{position:'absolute',zIndex:'3',transform:'translate(-50%,-50%)',font:'650 10px system-ui,sans-serif',whiteSpace:'nowrap',cursor:'pointer'});
    label.addEventListener('click',()=>{api.select(id);onSelect(id);});container.append(label);component.label=label;components.set(id,component);
  }
  root.updateMatrixWorld(true);
  const batteryPort=makeTerminal(batteryMount,'BATTERY-POWER',{count:2,position:vector(0,.034,.011),quaternion:new T.Quaternion().setFromAxisAngle(vector(1,0,0),Math.PI/2)});
  batteryPort.root.visible=false;
  const wireRoot=new T.Group();wireRoot.name='assembly-wiring-route-reference';root.add(wireRoot);wireRoot.visible=false;
  const printedMeshes=view.model.parts.flatMap((part,index)=>PRINTED_MESH_NAMES[part.mesh]?[view.actual.parts[index]]:[]);
  if(batteryMesh)printedMeshes.push(batteryMesh);
  // Include board bodies, connector housings and capacitor cans, not only the
  // original robot surfaces. Thin copper / labels are cosmetic overlays.
  const electronicsSolids=[],contactProxies=new Map();
  function solidProxies(group){
    group.updateWorldMatrix(true,true);const inverse=group.matrixWorld.clone().invert(),buckets=[[],[]];
    group.traverse(mesh=>{if(!mesh.isMesh||mesh.userData.hubSolid===false||mesh.userData.collisionProxy||[...servoDetails.values()].some(d=>d.decals.includes(mesh)))return;
      buckets[mesh.material?.metalness>.5?1:0].push(mesh);
    });
    return buckets.map((meshes,index)=>{
      if(!meshes.length)return null;
      const size=meshes.reduce((sum,m)=>sum+(m.geometry.index?.count||m.geometry.attributes.position.count)*3,0),positions=new Float32Array(size);let offset=0;
      for(const mesh of meshes){const transform=new T.Matrix4().multiplyMatrices(inverse,mesh.matrixWorld),p=mesh.geometry.attributes.position,ix=mesh.geometry.index;for(let i=0;i<(ix?.count||p.count);i++){const point=new T.Vector3().fromBufferAttribute(p,ix?ix.getX(i):i).applyMatrix4(transform);positions.set(point.toArray(),offset);offset+=3;}}
      const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.BufferAttribute(positions,3));geometry.computeBoundingBox();geometry.computeBoundingSphere();
      const proxy=new T.Mesh(geometry,new T.MeshBasicMaterial());proxy.name=group.name+(index?'-metal-clearance':'-body-clearance');proxy.visible=false;proxy.userData.collisionProxy=true;group.add(proxy);electronicsSolids.push(proxy);return proxy;
    });
  }
  components.forEach(component=>contactProxies.set(component.group,solidProxies(component.group)));
  servoDetails.forEach(detail=>contactProxies.set(detail.group,solidProxies(detail.group)));
  const collisionMeshes=[...printedMeshes,...electronicsSolids];
  const servoMeshes=[...servoDetails.values()].map(detail=>detail.group.parent);
  const wireRouter=createWireRouter(root,servoMeshes,collisionMeshes,{clearance:.00045});
  const bundleRouter=createWireRouter(root,servoMeshes,collisionMeshes,{clearance:.0010});
  const portContacts=port=>{
    for(const component of components.values())if(Object.values(component.ports).includes(port))return[contactProxies.get(component.group)?.[1]].filter(Boolean);
    for(const detail of servoDetails.values())if(Object.values(detail.ports).includes(port))return[contactProxies.get(detail.group)?.[1]].filter(Boolean);
    return[];
  };
  // Both physical sockets share the servo bus. Choose their routing roles
  // once for the complete chain, rather than forcing every cable across a case.
  root.updateMatrixWorld(true);
  const incoming=new Map(),outgoing=new Map();
  const center=port=>port.mouth.getWorldPosition(new T.Vector3());
  const direction=port=>port.outward.getWorldPosition(new T.Vector3()).sub(center(port)).normalize();
  const linkCost=(a,b)=>{
    const delta=center(b).sub(center(a)),distance=delta.length();delta.normalize();
    return distance+.008*(2-direction(a).dot(delta)+direction(b).dot(delta));
  };
  const chooseChain=(ids,source,target)=>{
    let best=Infinity,choice=0;
    for(let mask=0;mask<(1<<ids.length);mask++){
      let cost=0,previous=source;
      for(let i=0;i<ids.length;i++){
        const ports=servoDetails.get(ids[i]).ports,bit=(mask>>i)&1,input=ports[bit?'out':'in'];
        cost+=linkCost(previous,input);previous=ports[bit?'in':'out'];
      }
      if(target)cost+=linkCost(previous,target);
      if(cost<best){best=cost;choice=mask;}
    }
    ids.forEach((id,i)=>{const ports=servoDetails.get(id).ports,bit=(choice>>i)&1;incoming.set(id,ports[bit?'out':'in']);outgoing.set(id,ports[bit?'in':'out']);});
  };
  chooseChain([34,33,32,31,30],components.get('hat').ports.J13,components.get('hub').ports.J1);
  chooseChain([20,21,22,23,24],components.get('hub').ports.J3,null);
  chooseChain([10,11,12,13,14],components.get('hub').ports.J4,null);
  const portPairs=spec=>{
    if(spec.id==='hat-zero')return[components.get('hat').ports.J4,components.get('zero').ports.gpio40];
    if(spec.id==='hat-34')return[components.get('hat').ports.J13,incoming.get(34)];
    if(spec.id==='30-hub')return[outgoing.get(30),components.get('hub').ports.J1];
    if(spec.id==='hub-20')return[components.get('hub').ports.J3,incoming.get(20)];
    if(spec.id==='hub-10')return[components.get('hub').ports.J4,incoming.get(10)];
    if(spec.id==='hub-imu')return[components.get('hub').ports.J2,components.get('imu').ports.J1];
    if(spec.id==='battery-hub')return[batteryPort,components.get('hub').ports.CN1];
    return[outgoing.get(Number(spec.from.slice(5))),incoming.get(Number(spec.to.slice(5)))];
  };
  const cableMaterials=Object.fromEntries(Object.entries(SIGNAL_COLORS).map(([name,color])=>[name,new T.MeshStandardMaterial({color,roughness:.65,metalness:.02})]));
  const headerMaterial=new T.MeshStandardMaterial({color:0xb1b8bd,roughness:.6,metalness:.18});
  const wires=ELECTRONICS_WIRES.map(spec=>{
    const group=new T.Group();group.name=spec.id;wireRoot.add(group);
    const[fromPort,toPort]=portPairs(spec);if(!fromPort||!toPort)throw Error(`线束 ${spec.id} 缺少端子`);
    const header=fromPort.kind==='header40',signals=header?Array.from({length:40},(_,i)=>i):spec.id==='battery-hub'?['gnd','power']:WIRE_SIGNALS;
    const conductors=signals.map((signal,index)=>{
      const start=header?fromPort.ordered[index]:fromPort.pins[signal],end=header?toPort.ordered[index]:toPort.pins[signal];
      if(!start||!end)throw Error(`线束 ${spec.id} 缺少触点 ${signal}`);
      const mesh=new T.Mesh(new T.BufferGeometry(),header?headerMaterial:cableMaterials[signal].clone());mesh.name=header?`${spec.id}-contact-${index+1}`:`${spec.id}-${signal}`;
      mesh.userData={route:spec.id,signal:header?'header-contact':signal,contactOrder:header?index:undefined};group.add(mesh);
      return{signal,mesh,start,end};
    });
    return{...spec,group,mesh:group,fromPort,toPort,conductors,header,fromContacts:portContacts(fromPort),toContacts:portContacts(toPort),last:null};
  });
  const explosion=attachPrintExplosion(view,{extraMeshes:batteryMesh?[batteryMesh]:[],followers:new Map(batteryMesh?[[batteryMesh,[components.get('imu').group,batteryPort.root]]]:[])});
  const notice=document.createElement('span');notice.className='electronics-scene-note';notice.textContent=batteryError?'电池仓暂未加载；板卡位置按装配区显示':'端子接入 · 线束走向为装配示意';container.append(notice);
  const batteryLabel=document.createElement('button');batteryLabel.type='button';batteryLabel.className='electronics-label';batteryLabel.textContent='电池仓';batteryLabel.setAttribute('aria-label','查看电池仓');Object.assign(batteryLabel.style,{position:'absolute',zIndex:'3',transform:'translate(-50%,-50%)',font:'650 10px system-ui,sans-serif',whiteSpace:'nowrap',cursor:'pointer'});batteryLabel.addEventListener('click',()=>api.focus('battery'));container.append(batteryLabel);

  function applyWireFocus(){
    for(const item of wires){
      const relevant=!wireFocus||item.from===wireFocus||item.to===wireFocus||item.region===wireFocus||(wireFocus==='head'&&['face','neck','trunk'].includes(item.region));
      item.conductors.forEach(c=>{c.mesh.material.opacity=relevant?1:.12;c.mesh.material.transparent=!relevant;c.mesh.material.depthWrite=relevant;});
    }
  }
  function endpointVisible(id){return id.startsWith('servo')||id==='battery'?id!=='battery'||batteryVisible:components.get(id)?.visible;}
  function portLead(port,pin){
    const mouth=port.mouth.getWorldPosition(new T.Vector3()),out=port.outward.getWorldPosition(new T.Vector3()),point=pin.getWorldPosition(new T.Vector3());
    // Preserve each contact's sideways position all the way out of the socket.
    // Leave the physical mouth briefly, then bend before nearby printed
    // brackets. A fixed 9 mm straight extension cut through 2 mm support plates.
    const direction=out.sub(mouth).normalize(),distance=Math.max(.0006,mouth.clone().sub(point).dot(direction)+(port.source?.00125:.0008));
    return root.worldToLocal(point.addScaledVector(direction,distance));
  }
  function updateWires(){
    if(!wiringVisible)return;
    if(coverAmount!==coverTo&&wires.every(item=>item.last))return;
    root.updateMatrixWorld(true);
    wireRouter.update();bundleRouter.update();
    if(!wireCache.has(wireRouter.signature))wireCache.set(wireRouter.signature,{obstacles:wireRouter.signature,routes:{}});
    const cacheState=wireCache.get(wireRouter.signature);
    batteryPort.root.visible=components.get('hub').visible&&batteryVisible;
    for(const item of wires){
      item.group.visible=endpointVisible(item.from)&&endpointVisible(item.to);
      const positions=item.conductors.flatMap(c=>[...c.start.getWorldPosition(new T.Vector3()).toArray(),...c.end.getWorldPosition(new T.Vector3()).toArray()]);
      // Include connector direction so rotating a socket about a fixed contact
      // centre still updates the exit bend.
      positions.push(...item.fromPort.outward.getWorldPosition(new T.Vector3()).toArray(),...item.toPort.outward.getWorldPosition(new T.Vector3()).toArray());
      const endpointKey=positions.map(x=>x.toFixed(7)).join(',');
      const saved=cacheState.routes[item.id],cacheHit=!item.header&&saved?.endpoints===endpointKey;
      const signature=wireRouter.signature+'|'+endpointKey;if(signature===item.last)continue;item.last=signature;
      const starts=item.conductors.map(c=>root.worldToLocal(c.start.getWorldPosition(new T.Vector3())));
      const ends=item.conductors.map(c=>root.worldToLocal(c.end.getWorldPosition(new T.Vector3())));
      const leadsA=item.conductors.map(c=>portLead(item.fromPort,c.start)),leadsB=item.conductors.map(c=>portLead(item.toPort,c.end));
      const mean=points=>points.reduce((a,b)=>a.add(b),new T.Vector3()).multiplyScalar(1/points.length);
      const owner=id=>id.startsWith('servo')?servoDetails.get(Number(id.slice(5))).group.parent:null;
      const coreSpec=index=>({start:starts[index],leadA:leadsA[index],leadB:leadsB[index],end:ends[index],fromServo:owner(item.from),toServo:owner(item.to),fromContacts:item.fromContacts,toContacts:item.toContacts,lane:index-(item.conductors.length-1)/2});
      let bundles=null;
      if(!item.header&&!cacheHit){
        const outsideLead=(port,points)=>{
          const center=mean(points),dir=port.outward.getWorldPosition(new T.Vector3()).sub(port.mouth.getWorldPosition(new T.Vector3())).transformDirection(root.matrixWorld.clone().invert());
          if(bundleRouter.clearSegment(center,center))return center;
          for(const amount of[.0005,.001,.0015,.002]){const candidate=center.clone().addScaledVector(dir,amount);if(bundleRouter.clearSegment(candidate,candidate)&&wireRouter.clearSegment(center,candidate))return candidate;}
          return center;
        };
        const a=outsideLead(item.fromPort,leadsA),b=outsideLead(item.toPort,leadsB),shared=bundleRouter.route({start:a,leadA:a,leadB:b,end:b,previous:item.bundlePoints});
        const tryBundle=shared=>{
          if(!shared)return null;
          for(const flat of[false,true]){
            const paths=parallelCablePaths(shared.curve,starts,leadsA,leadsB,ends,{clearSegment:wireRouter.clearSegment,flat});
            if(paths&&paths.every((path,index)=>!wireRouter.validate(path.curve,coreSpec(index)))){item.bundlePoints=shared.points;return paths;}
          }
          return null;
        };
        bundles=tryBundle(shared);
        if(!bundles){const a=mean(leadsA),b=mean(leadsB);bundles=tryBundle(wireRouter.route({start:a,leadA:a,leadB:b,end:b}));}
      }
      item.conductors.forEach((c,index)=>{
        const start=starts[index],end=ends[index];
        const leadA=leadsA[index],leadB=leadsB[index];
        let curve,routing=null;
        if(item.header){
          // Forty separate contacts join the opposed HAT/Zero headers. Contact
          // order is geometric, not a GPIO pin assignment or a three-wire bus.
          curve=new T.LineCurve3(start,end);
        }else if(cacheHit){
          routing=unpackCable(saved.conductors[index],start,end);curve=routing.curve;c.routePoints=routing.points;
        }else{
          const spec=coreSpec(index);
          const bundle=bundles?.[index];
          routing=bundle&&!wireRouter.validate(bundle.curve,spec)?bundle:wireRouter.route({...spec,previous:bundle?.points||c.routePoints});
          if(!routing){c.mesh.visible=false;c.mesh.userData.routingError=wireRouter.lastFailure;return;}
          curve=softenCableCorners(routing.curve,{accept:candidate=>!wireRouter.validate(candidate,spec)});
          c.routePoints=routing.points;
        }
        const segments=item.header?12:Math.max(48,Math.min(1024,Math.ceil(curve.getLength()/.0004))),geometry=new T.TubeGeometry(curve,segments,item.header?.000105:.00034,6,false);
        c.mesh.visible=true;c.mesh.geometry.dispose();c.mesh.geometry=geometry;
        c.mesh.userData.start=start.toArray();c.mesh.userData.end=end.toArray();c.mesh.userData.leadA=leadA.toArray();c.mesh.userData.leadB=leadB.toArray();
        c.mesh.userData.cached=!!routing?.cached;c.mesh.userData.routingError=null;c.mesh.userData.bundled=!!routing?.bundled;c.mesh.userData.clearance=routing?.clearance??null;
      });
      if(!item.header&&item.conductors.every(c=>c.mesh.visible))cacheState.routes[item.id]={endpoints:endpointKey,conductors:item.conductors.map(c=>packCable(c.mesh.geometry.parameters.path,{signal:c.signal,bundled:c.mesh.userData.bundled,clearance:c.mesh.userData.clearance}))};
    }
  }
  function applyCutaway(){
    cutawayIndices.forEach(index=>{const mesh=view.actual.parts[index],base=cutawayBase.get(index);if(!base)return;const cutting=selected==='hub'||selected==='imu';const opacity=selected==='hub'?((index===3||index===4)?.24:.12):.12;mesh.material.opacity=cutting?Math.min(base.opacity,opacity):base.opacity;mesh.material.transparent=base.transparent||cutting;mesh.material.depthWrite=base.depthWrite&&!cutting;});
    if(batteryMesh){batteryMesh.material.transparent=false;batteryMesh.material.opacity=1;batteryMesh.material.depthWrite=true;}
  }
  function positionLabel(label,world,visible){const point=world.project(view.camera),width=container.clientWidth,height=container.clientHeight;label.hidden=!visible||point.z< -1||point.z>1||Math.abs(point.x)>1||Math.abs(point.y)>1;label.style.left=`${(point.x+1)*width/2}px`;label.style.top=`${(1-point.y)*height/2}px`;}
  function updateLabels(){
    view.camera.updateMatrixWorld(true);
    components.forEach(component=>{positionLabel(component.label,component.group.localToWorld(vector(0,component.height*.55,.007)),component.visible&&(component.spec.location!=='face'||coverAmount>.5));component.label.setAttribute('aria-pressed',String(component.id===selected));});
    positionLabel(batteryLabel,(batteryMesh||batteryMount).localToWorld(vector(.026,.025,.050)),batteryVisible&&!!batteryMesh);
    notice.hidden=![...components.values()].some(c=>c.visible)&&!coverOpen&&!wiringVisible&&!batteryVisible;
  }
  function updateCover(now=performance.now()){
    const progress=reducedMotion?1:clamp((now-coverStarted)/360,0,1),ease=progress*progress*(3-2*progress);coverAmount=T.MathUtils.lerp(coverFrom,coverTo,ease);if(progress===1)coverFrom=coverTo;
    cover.position.copy(coverRest).addScaledVector(coverUp,coverLift*coverAmount);cover.material.transparent=coverBaseTransparent||coverAmount>.001;cover.material.opacity=coverBaseOpacity*T.MathUtils.lerp(1,.25,coverAmount);cover.material.depthWrite=coverBaseDepthWrite&&coverAmount<.01;cover.updateMatrixWorld(true);
  }
  function highlight(){components.forEach(c=>{c.pcb.material.emissive.setHex(c.id===selected?0xc1f577:0);c.pcb.material.emissiveIntensity=c.id===selected?.45:0;});}
  function frame(now=performance.now()){if(disposed)return;updateCover(now);explosion.apply({basePositions:new Map([[cover,cover.position.clone()]])});applyCutaway();servoDetails.forEach(detail=>detail.sync());updateWires();updateLabels();}
  if(originalPose)view.pose=function(instance,...args){
    if(instance!==view.actual)return originalPose.call(this,instance,...args);
    const expanded=explosion.expanded;explosion.setExpanded(false);explosion.apply();
    // Stale wire paths from the preceding pose must not set the robot floor.
    wireRoot.removeFromParent();
    try{return originalPose.call(this,instance,...args);}
    finally{root.add(wireRoot);explosion.setExpanded(expanded);frame();}
  };
  view.update=function(...args){const expanded=explosion.expanded;explosion.setExpanded(false);explosion.apply();originalUpdate.apply(this,args);explosion.setExpanded(expanded);coverBaseOpacity=cover.material.opacity;coverBaseTransparent=cover.material.transparent;coverBaseDepthWrite=cover.material.depthWrite;captureCutaway();frame();};
  view.advanceFocus=function(now){originalAdvanceFocus.call(this,now);frame(now);};
  let pointerStart=null;
  const down=e=>{pointerStart=e.isPrimary&&e.button===0?{x:e.clientX,y:e.clientY,id:e.pointerId}:null;};
  const cancel=()=>{pointerStart=null;};
  const up=e=>{
    const start=pointerStart;pointerStart=null;if(!start||start.id!==e.pointerId||Math.hypot(e.clientX-start.x,e.clientY-start.y)>5)return;
    const bounds=canvas.getBoundingClientRect(),ray=new T.Raycaster();ray.setFromCamera(new T.Vector2((e.clientX-bounds.left)/bounds.width*2-1,1-(e.clientY-bounds.top)/bounds.height*2),view.camera);
    const candidates=boardTargets.filter(mesh=>{const c=components.get(mesh.userData.component);return c.visible&&(c.spec.location!=='face'||coverAmount>.5);});const hit=ray.intersectObjects(candidates,false)[0];if(!hit)return;
    const occluder=ray.intersectObjects([...view.actual.parts,...(batteryMesh?[batteryMesh]:[])].filter(mesh=>mesh.visible&&(!mesh.material.transparent||mesh.material.opacity>.6)),false)[0];if(occluder&&occluder.distance<hit.distance-.0002)return;
    const previousServos=view.actual.servos,empty=[];view.actual.servos=empty;queueMicrotask(()=>{if(view.actual.servos===empty)view.actual.servos=previousServos;});const id=hit.object.userData.component;api.select(id);onSelect(id);
  };
  canvas.addEventListener('pointerdown',down,{capture:true});canvas.addEventListener('pointercancel',cancel,{capture:true});canvas.addEventListener('pointerup',up,{capture:true});
  const api={
    exportWireCache(){return{revision:WIRE_CACHE_REVISION,states:[...wireCache.values()]};},components,wireRouter,bundleRouter,wires:ELECTRONICS_WIRES,routes:wires,collisionMeshes: [...servoMeshes,...collisionMeshes],servos:servoDetails,explosion,batteryHolder:{group:batteryMount,mesh:batteryMesh,error:batteryError},
    setCoverOpen(open){coverOpen=!!open;coverFrom=coverAmount;coverTo=coverOpen?1:0;coverStarted=performance.now();frame();return coverOpen;},
    setVisible(id,visible){const c=components.get(id);if(!c)return false;c.visible=!!visible;c.group.visible=c.visible;frame();return c.visible;},
    setBatteryVisible(visible){batteryVisible=!!visible;if(batteryMesh)batteryMesh.visible=batteryVisible;frame();return batteryVisible;},
    setWireFocus(value){wireFocus=value&&value!=='all'?value:null;applyWireFocus();},
    setWiringVisible(visible){wiringVisible=!!visible;wireRoot.visible=wiringVisible;batteryPort.root.visible=wiringVisible&&components.get('hub').visible&&batteryVisible;frame();return wiringVisible;},
    setServoIdsVisible(visible){servoDetails.forEach(s=>s.decals.forEach(d=>{d.visible=!!visible;}));return !!visible;},
    setExploded(expanded){
      explosion.setExpanded(expanded);frame();
      if(!expanded){view.update(view.lastSnapshot||{});view.view?.('front');}
      else{
        const sphere=new T.Box3().setFromObject(root).getBoundingSphere(new T.Sphere());
        const vertical=T.MathUtils.degToRad(view.camera.fov),horizontal=2*Math.atan(Math.tan(vertical/2)*view.camera.aspect);
        const distance=sphere.radius/Math.sin(Math.min(vertical,horizontal)/2)*1.16;
        const direction=vector(.52,-.22,.18).normalize().applyQuaternion(root.getWorldQuaternion(new T.Quaternion()));
        view.initialView=null;view.overviewName=null;view.focus=null;
        view.camera.position.copy(sphere.center).addScaledVector(direction,distance);
        view.controls.target.copy(sphere.center);view.controls.update?.();
      }
      return explosion.expanded;
    },
    get exploded(){return explosion.expanded;},
    clearSelection(){selected=null;highlight();frame();},
    select(id){const c=components.get(id);if(!c)return false;selected=id;this.setVisible(id,true);if(c.spec.location==='face')this.setCoverOpen(true);if(id==='imu')this.setBatteryVisible(true);highlight();this.focus(id);frame();return true;},
    focus(id){
      const c=components.get(id);if(!c&&!['head','battery'].includes(id))return false;root.updateMatrixWorld(true);
      const box=id==='head'?new T.Box3().union(new T.Box3().setFromObject(components.get('hat').group)).union(new T.Box3().setFromObject(components.get('zero').group)):id==='battery'?new T.Box3().setFromObject(batteryMount):new T.Box3().setFromObject(c.group);
      const target=box.getCenter(new T.Vector3()),radius=box.getBoundingSphere(new T.Sphere()).radius;const vertical=T.MathUtils.degToRad(view.camera.fov),horizontal=2*Math.atan(Math.tan(vertical/2)*view.camera.aspect);const distance=Math.max((id==='head'||id==='battery')?.18:.12,radius/Math.sin(Math.min(vertical,horizontal)/2)*1.45);
      // Face boards are viewed from the opened interior, not through the face.
      const direction=id==='head'||c?.spec.location==='face'?vector(-1,-.45,.9):id==='hub'?vector(.9,-.45,.75):id==='imu'?vector(1,-.30,.2):vector(-1,-.7,.4);
      view.initialView=null;view.overviewName=null;view.focus={start:performance.now(),from:view.camera.position.clone(),fromTarget:view.controls.target.clone(),to:target.clone().addScaledVector(direction.normalize(),distance),target};return true;
    },
    update:frame,
    dispose(){
      if(disposed)return;selected=null;applyCutaway();explosion.dispose();disposed=true;view.update=originalUpdate;view.advanceFocus=originalAdvanceFocus;if(originalPose)view.pose=originalPose;cover.position.copy(coverRest);cover.material.opacity=coverOpacity;cover.material.transparent=false;cover.material.depthWrite=true;
      canvas.removeEventListener('pointerdown',down,{capture:true});canvas.removeEventListener('pointercancel',cancel,{capture:true});canvas.removeEventListener('pointerup',up,{capture:true});
      const geometries=new Set(),materials=new Set();const release=object=>object.traverse(o=>{if(o.isMesh){geometries.add(o.geometry);if(Array.isArray(o.material))o.material.forEach(m=>materials.add(m));else materials.add(o.material);}});
      components.forEach(c=>{c.label.remove();c.group.removeFromParent();release(c.group);});wires.forEach(w=>release(w.group));servoDetails.forEach(detail=>detail.dispose());release(batteryMount);geometries.forEach(g=>g.dispose());materials.forEach(m=>{m.map?.dispose();m.dispose();});wireRoot.removeFromParent();batteryMount.removeFromParent();Object.values(cableMaterials).forEach(material=>material.dispose());notice.remove();batteryLabel.remove();
    },
  };
  frame();return api;
}
