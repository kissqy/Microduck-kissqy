import * as T from './vendor/three.module.min.js?demo=20261013';

// Display geometry in the unmodified holder STL's raw XYZ frame (metres).
// The author's arrows select the upward contact holes in the top crossbar:
// raw X=+/-16.9, Y=31.6 mm; surface Z is approximately 77.5 mm.
// Viewed straight at the battery label, raw +X is left: GND left, VIN right.
// Banana contacts enter the battery along raw -Z; the AMP2.0 mouth opens in -Y (toward the holder interior).
export const BATTERY_PICKUP=Object.freeze({x:[.0169,-.0169],y:.0316,z:.0775});
export const NPF550=Object.freeze({width:.0384,depth:.0206,length:.0708,
  source:'https://www.sony.com.au/electronics/support/camera-camcorder-accessories-batteries-chargers/np-f550/specifications'});
const material=(color,metalness=0)=>new T.MeshStandardMaterial({color,metalness,roughness:metalness?.35:.7});
function part(parent,geometry,mat,name,position){const mesh=new T.Mesh(geometry,mat);mesh.name=name;if(position)mesh.position.fromArray(position);parent.add(mesh);return mesh;}
function cylinder(parent,radius,height,mat,name,position){const mesh=part(parent,new T.CylinderGeometry(radius,radius,height,24),mat,name,position);mesh.rotation.x=Math.PI/2;return mesh;}
function decal(parent,text,width,height,position,rotation){
  if(typeof document==='undefined')return null;
  const canvas=document.createElement('canvas');canvas.width=512;canvas.height=256;const ctx=canvas.getContext('2d');if(!ctx)return null;
  ctx.fillStyle='#202729';ctx.fillRect(0,0,512,256);ctx.strokeStyle='#7d8988';ctx.lineWidth=4;ctx.strokeRect(5,5,502,246);
  ctx.fillStyle='#e4e9e7';ctx.textAlign='center';ctx.font='bold 72px sans-serif';ctx.fillText(text,256,110);
  ctx.fillStyle='#a3b3ac';ctx.font='35px sans-serif';ctx.fillText('RECHARGEABLE BATTERY',256,180);
  const texture=new T.CanvasTexture(canvas);texture.colorSpace=T.SRGBColorSpace;
  const mesh=part(parent,new T.PlaneGeometry(width,height),new T.MeshBasicMaterial({map:texture,side:T.DoubleSide}),'NP-F550-label',position);
  mesh.rotation.set(...rotation);mesh.userData.hubSolid=false;return mesh;
}
// NP-F550: Sony envelope + the author's two-cell shell / terminal-side photographs.
// Independent display reconstruction, not a downloaded manufacturer CAD model.
export function createBatteryPack(){
  const group=new T.Group();group.name='NP-F550-battery';group.position.set(0,.0400,.0409);
  const {width,depth,length}=NPF550,x=width/2,y=depth/2;
  // Two rounded cell lobes with a real recessed centre valley; rear slide face flat.
  function outline(){
    const shape=new T.Shape();
    shape.moveTo(-x,-y);shape.lineTo(x,-y);shape.lineTo(x,.001);
    shape.quadraticCurveTo(x,y,x-.0085,y);shape.lineTo(.0016,y);
    shape.quadraticCurveTo(.0008,y,.00065,y-.0013);shape.lineTo(-.00065,y-.0013);
    shape.quadraticCurveTo(-.0008,y,-.0016,y);shape.lineTo(-x+.0085,y);
    shape.quadraticCurveTo(-x,y,-x,.001);shape.closePath();return shape;
  }
  const black=material(0x202425),body=new T.Group();body.name='NP-F550-case';group.add(body);
  const lower=new T.ExtrudeGeometry(outline(),{depth:length-.010,bevelEnabled:false,curveSegments:16});lower.translate(0,0,-length/2);
  part(body,lower,black,'NP-F550-two-cell-shell');
  const capShape=outline();
  // Recessed contact sockets, aligned with the banana contacts at raw Y=31.6 mm.
  for(const px of BATTERY_PICKUP.x){const hole=new T.Path();hole.absarc(px,-.0084,.00145,0,Math.PI*2,false);capShape.holes.push(hole);}
  const cap=new T.ExtrudeGeometry(capShape,{depth:.010,bevelEnabled:false,curveSegments:16});cap.translate(0,0,length/2-.010);part(body,cap,black,'NP-F550-recessed-terminal-cap');
  for(const [i,px] of BATTERY_PICKUP.x.entries()){
    const tube=new T.Mesh(new T.CylinderGeometry(.00135,.00135,.008,24,1,true),material(0xb7a16b,.8));tube.name=i?'NP-F550-positive-socket':'NP-F550-negative-socket';tube.rotation.x=Math.PI/2;tube.position.set(px,-.0084,length/2-.0043);group.add(tube);
  }
  // Slide rails on the mounting face, with an interrupted locking shoulder.
  for(const sign of[-1,1]){
    part(group,new T.BoxGeometry(.0018,.0012,.046),black,'NP-F550-slide-rail',[sign*.0158,-y+.0006,-.006]);
    part(group,new T.BoxGeometry(.0026,.0014,.006),black,'NP-F550-lock-shoulder',[sign*.0158,-y+.0007,.021]);
  }
  part(group,new T.BoxGeometry(.005,.00035,.003),material(0x101415),'NP-F550-latch-recess',[0,-y-.00003,-.026]);
  group.userData.dimensions=NPF550;group.userData.reference='Sony NP-F550 specifications and author battery photographs';
  return{group,body};
}
// Rebuilt from the author's front / rear / side photographs. Display model only.
export const BANANA_BOARD=Object.freeze({width:.03919,depth:.0125,thickness:.001,contactPitch:.0338});
export function createBatteryPickup(){
  const root=new T.Group();root.name='AMP2.0-BANANA-POWER-BOARD';root.position.set(0,BATTERY_PICKUP.y,BATTERY_PICKUP.z);
  const pins={},ordered=[],contacts={};
  const green=material(0x166347),gold=material(0xd5b653,.8),white=material(0xe9ebe2),steel=material(0xc0c5bd,.8);
  const box=(parent,w,d,h,mat,name,pos)=>part(parent,new T.BoxGeometry(w,d,h),mat,name,pos);
  box(root,BANANA_BOARD.width,BANANA_BOARD.depth,BANANA_BOARD.thickness,green,'banana-PCB',[0,0,.001]);
  for(const [i,signal] of ['gnd','power'].entries()){
    const x=BATTERY_PICKUP.x[i];
    // Cylindrical spring contacts with longitudinal slots, opposite the socket face.
    const stem=cylinder(root,.00125,.0095,gold,'banana-'+signal+'-contact',[x,0,-.00425]);
    cylinder(root,.00165,.00035,gold,'banana-'+signal+'-pad',[x,0,.00165]);
    cylinder(root,.00075,.0013,gold,'banana-'+signal+'-solder-tail',[x,0,.002]);
    for(let j=0;j<4;j++){
      const angle=j*Math.PI/2,slot=box(root,.00016,.0002,.006,material(0x5a4d2b),'banana-spring-slot',[x+Math.cos(angle)*.00122,Math.sin(angle)*.00122,-.004]);slot.rotation.z=angle;slot.userData.hubSolid=false;
    }
    const tip=part(root,new T.SphereGeometry(.00125,16,8),gold,'banana-'+signal+'-rounded-tip',[x,0,-.009]);tip.scale.z=.7;
    contacts[signal]=stem;
  }
  // Open right-angle 3P AMP housing, with parallel-to-PCB insertion and guide key.
  const socket=new T.Group();socket.name='banana-AMP2.0-3P-right-angle';socket.position.set(-.004,0,.0015);socket.rotation.z=Math.PI;root.add(socket);
  box(socket,.008,.001,.0042,white,'AMP-rear-wall',[0,-.0025,.0021]);
  box(socket,.008,.005,.0007,white,'AMP-floor',[0,0,.00035]);
  box(socket,.008,.005,.0007,white,'AMP-roof',[0,0,.00385]);
  for(const x of[-.00365,.00365])box(socket,.0007,.005,.0042,white,'AMP-side-guide',[x,0,.0021]);
  for(const x of[-.001,.001])box(socket,.00045,.0015,.0005,white,'AMP-key-guide',[x,.00175,.00085]);
  for(const [i,signal] of ['nc','power','gnd'].entries()){
    const x=-.002+i*.002;
    box(socket,.00048,.0038,.00048,steel,'AMP-'+signal+'-pin',[x,-.0002,.0019]);
    box(socket,.00055,.0018,.0004,steel,'AMP-'+signal+'-solder-pad',[x,-.0038,.0002]);
    const pin=new T.Object3D();pin.name='banana-AMP-'+signal+'-wire-contact';pin.position.set(x,.0026,.0019);pin.userData={signal,target:'AMP-'+signal+'-pin'};socket.add(pin);pins[signal]=pin;ordered.push(pin);
  }
  const mouth=new T.Object3D();mouth.position.set(0,.0026,.0019);socket.add(mouth);
  const outward=new T.Object3D();outward.position.set(0,.0066,.0019);socket.add(outward);
  if(typeof document!=='undefined'){
    const canvas=document.createElement('canvas');canvas.width=512;canvas.height=128;const ctx=canvas.getContext('2d');
    if(ctx){ctx.clearRect(0,0,512,128);ctx.fillStyle='#edf2dc';ctx.font='bold 36px sans-serif';ctx.fillText('BAT+',18,85);ctx.fillText('GND',390,85);
      const texture=new T.CanvasTexture(canvas);texture.colorSpace=T.SRGBColorSpace;
      const label=part(root,new T.PlaneGeometry(.035,.007),new T.MeshBasicMaterial({map:texture,transparent:true,side:T.DoubleSide}),'banana-polarity-silkscreen',[0,-.002,.00153]);label.userData.hubSolid=false;}
  }
  root.userData.dimensions=BANANA_BOARD;
  return{root,pins,ordered,mouth,outward,contacts,kind:'power2',pinCount:3};
}
