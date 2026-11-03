import * as T from './vendor/three.module.min.js?demo=20261013';

// Display geometry in the unmodified holder STL's raw XYZ frame (metres).
// The two 2.6 mm bores were measured at raw X=+/-9.5, Y=20.5 mm;
// their upper openings are at Z=72.2961 mm. This is an assembly illustration.
export const BATTERY_PICKUP=Object.freeze({x:[-.0095,.0095],y:.0205,top:.0722961});
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
export function createBatteryPack(){
  const group=new T.Group();group.name='NP-F550-battery';group.position.set(0,.0458,.0409);
  const {width,depth,length}=NPF550,r=.0016,x=width/2,z=length/2,shape=new T.Shape();
  shape.moveTo(-x+r,-z);shape.lineTo(x-r,-z);shape.quadraticCurveTo(x,-z,x,-z+r);shape.lineTo(x,z-r);shape.quadraticCurveTo(x,z,x-r,z);shape.lineTo(-x+r,z);shape.quadraticCurveTo(-x,z,-x,z-r);shape.lineTo(-x,-z+r);shape.quadraticCurveTo(-x,-z,-x+r,-z);
  const geometry=new T.ExtrudeGeometry(shape,{depth,bevelEnabled:false,curveSegments:8});geometry.translate(0,0,-depth/2);geometry.rotateX(Math.PI/2);
  const body=part(group,geometry,material(0x242a2b),'NP-F550-case');
  const seam=part(group,new T.BoxGeometry(width+.0001,.0003,length-.004),material(0x424a4b),'NP-F550-case-seam',[0,.0072,0]);seam.userData.hubSolid=false;
  decal(group,'NP-F550',.029,.014,[0,depth/2+.00006,.006],[-Math.PI/2,0,Math.PI]);
  for(const sign of[-1,1])for(let i=0;i<4;i++){
    const rib=part(group,new T.BoxGeometry(.0003,.013,.001),material(0x3c4445),'NP-F550-grip',[sign*(x+.00003),0,-.021+i*.004]);rib.userData.hubSolid=false;
  }
  group.userData.dimensions=NPF550;return{group,body};
}
export function createBatteryPickup(){
  const root=new T.Group();root.name='BATTERY-SCREW-PICKUP';const pins={},ordered=[],screws={};
  const steel=material(0xbec5c5,.85),brass=material(0xb79850,.75),top=BATTERY_PICKUP.top;
  for(const [i,signal]of ['gnd','power'].entries()){
    const x=BATTERY_PICKUP.x[i],y=BATTERY_PICKUP.y;
    const shaft=cylinder(root,.00122,.008,steel,'battery-'+signal+'-M2.6-shaft',[x,y,top-.0035]);
    const head=cylinder(root,.0022,.0014,steel,'battery-'+signal+'-screw-head',[x,y,top+.00125]);
    const ring=part(root,new T.RingGeometry(.0013,.00265,28),brass,'battery-'+signal+'-wire-lug',[x,y,top+.00055]);
    const tab=part(root,new T.BoxGeometry(.0014,.0033,.00035),brass,'battery-'+signal+'-lug-tab',[x,y-.0029,top+.000375]);
    const slot=part(root,new T.BoxGeometry(.0027,.00038,.00005),material(0x3a4445),'battery-'+signal+'-screw-slot',[x,y,top+.00198]);slot.userData.hubSolid=false;
    const collar=part(root,new T.BoxGeometry(.0021,.0016,.0012),material(signal==='power'?0xc76a60:0x30383c),'battery-'+signal+'-sleeve',[x,y-.004,top+.0003]);
    collar.userData.hubSolid=false;
    const pin=new T.Object3D();pin.name='battery-'+signal+'-lug-contact';pin.position.set(x,y,top+.00235);pin.userData={signal,target:head.name};root.add(pin);pins[signal]=pin;ordered.push(pin);
    screws[signal]={shaft,head,ring,tab,collar,pin,hole:[x,y,top]};
  }
  const mouth=new T.Object3D();mouth.position.set(0,BATTERY_PICKUP.y,top+.00235);root.add(mouth);
  const outward=new T.Object3D();outward.position.copy(mouth.position).add(new T.Vector3(0,0,.004));root.add(outward);
  return{root,pins,ordered,mouth,outward,screws,kind:'power2',pinCount:2};
}
