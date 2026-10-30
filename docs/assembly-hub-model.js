import * as T from './vendor/three.module.min.js?demo=20261013';
import {HUB_LAYOUT} from './assembly-hub-layout.js?v=20261030-harness';
const MM=.001,HALF=.8;
const mat=(color,metalness=.04)=>new T.MeshStandardMaterial({color,roughness:metalness>.5?.33:.65,metalness});
const signal=net=>net==='GND'?'gnd':net==='VIN'?'power':'data';
function mesh(parent,geometry,material,name,x=0,y=0,z=0){const m=new T.Mesh(geometry,material);m.name=name;m.position.set(x*MM,y*MM,z*MM);m.userData.hubSolid=true;parent.add(m);return m;}
function box(parent,w,d,h,material,name,x,y,z){return mesh(parent,new T.BoxGeometry(w*MM,d*MM,h*MM),material,name,x,y,z);}
function pin(parent,material,name,a,b,r=.25){const start=new T.Vector3(...a).multiplyScalar(MM),end=new T.Vector3(...b).multiplyScalar(MM),dir=end.clone().sub(start);const m=mesh(parent,new T.CylinderGeometry(r*MM,r*MM,dir.length(),8),material,name);m.position.copy(start.add(end).multiplyScalar(.5));m.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),dir.normalize());return m;}
function point(parent,name,x,y,z){const p=new T.Object3D();p.name=name;p.position.set(x*MM,y*MM,z*MM);parent.add(p);return p;}
function pcbPad(c,p){const a=c.angle*Math.PI/180,x=p.x,y=c.bottom?-p.y:p.y;return[c.position[0]+x*Math.cos(a)-y*Math.sin(a),c.position[1]+x*Math.sin(a)+y*Math.cos(a)];}
function label(parent,text,x,y,z,material){
 const font={C:[[1,0,0,0,0,2,1,2]],J:[[0,0,1,0,1,2,0,2,0,1.5]],N:[[0,2,0,0,1,2,1,0]],'1':[[.2,.4,.6,0,.6,2],[.2,2,1,2]],'2':[[0,.3,.2,0,.8,0,1,.3,1,.8,0,2,1,2]],'3':[[0,0,1,0,.4,1,1,1.3,1,1.8,.8,2,0,2]],'4':[[.8,2,.8,0,0,1.3,1,1.3]]};
 let offset=0;for(const char of text){for(const line of font[char]||[])for(let i=2;i<line.length;i+=2)pin(parent,material,'silk-'+text,[x+offset+line[i-2]*.55,y-line[i-1]*.55,z],[x+offset+line[i]*.55,y-line[i+1]*.55,z],.055).userData.hubSolid=false;offset+=.9;}
}
export function createHubModel(){
 const group=new T.Group(),ports={},shell=mat(0xf1f0e9),metal=mat(0xbcc3c4,.8),gold=mat(0xc9ad58,.7),silk=mat(0xeef3f0),mask=mat(0x075cae),trace=mat(0x073760);
 const shape=new T.Shape();HUB_LAYOUT.outline.forEach(([x,y],i)=>i?shape.lineTo(x*MM,y*MM):shape.moveTo(x*MM,y*MM));shape.closePath();
 const holes=[...HUB_LAYOUT.holes];for(const c of HUB_LAYOUT.components)for(const p of c.pads){const [x,y]=pcbPad(c,p);holes.push([x,y,p.hole/2]);}
 for(const[x,y,r]of holes){const hole=new T.Path();hole.absarc(x*MM,y*MM,r*MM,0,2*Math.PI,true);shape.holes.push(hole);}
 const geometry=new T.ExtrudeGeometry(shape,{depth:1.6*MM,bevelEnabled:false,curveSegments:12});geometry.translate(0,0,-HALF*MM);
 const pcb=mesh(group,geometry,mask,'HUB-V2-PCB');pcb.userData.primaryPCB=true;
 for(const[x,y,r]of holes)for(const side of[-1,1]){const ring=mesh(group,new T.RingGeometry(r*MM,(r+.32)*MM,20),gold,'HUB-plated-ring',x,y,side*.815);if(side<0)ring.rotation.x=Math.PI;ring.userData.hubSolid=false;}
 for(const[x1,y1,x2,y2,w,layer]of HUB_LAYOUT.traces){const a=new T.Vector3(x1*MM,y1*MM,layer===1?.00082:-.00082),b=new T.Vector3(x2*MM,y2*MM,a.z);const m=mesh(group,new T.BoxGeometry(a.distanceTo(b),w*MM,.000012),trace,'HUB-copper');m.position.copy(a.clone().add(b).multiplyScalar(.5));m.rotation.z=Math.atan2(y2-y1,x2-x1);m.userData.hubSolid=false;}
 for(const c of HUB_LAYOUT.components){
  const part=new T.Group();part.name='HUB-'+c.ref;part.position.set(c.position[0]*MM,c.position[1]*MM,0);part.rotation.z=c.angle*Math.PI/180;if(c.bottom)part.rotateX(Math.PI);group.add(part);
  if(c.ref==='C1'){
   const can=mesh(part,new T.CylinderGeometry(.004,.004,.008,40),mat(0x555e62,.45),'HUB-C1-can',0,0,HALF+4.1);can.rotation.x=Math.PI/2;
   const top=mesh(part,new T.CylinderGeometry(.0038,.0038,.0002,40),metal,'HUB-C1-top',0,0,HALF+8.15);top.rotation.x=Math.PI/2;
   for(const a of[-Math.PI/4,Math.PI/4]){const vent=box(part,4.2,.10,.035,mat(0x637174,.3),'HUB-C1-vent',0,0,HALF+8.27);vent.rotation.z=a;}
   const stripe=mesh(part,new T.CylinderGeometry(.00402,.00402,.0078,32,1,true,-Math.PI*.2,Math.PI*.32),mat(0xdce1df,.4),'HUB-C1-polarity',0,0,HALF+4.1);stripe.rotation.x=Math.PI/2;
   c.pads.forEach(p=>pin(part,metal,'HUB-C1-leg-'+p.pin,[p.x,0,-1.8],[p.x,0,1.4],.25));label(group,'C1',...c.silk.position,.83,silk);continue;
  }
  const vertical=c.ref==='CN1';
  if(vertical){
   box(part,7.5,5.8,.7,shell,'CN1-base',0,-.5,1.15);box(part,7.5,.65,6,shell,'CN1-back',0,-3.05,3.8);
   for(const sign of[-1,1])box(part,.65,5.8,6,shell,'CN1-side',sign*3.43,-.5,3.8);
   box(part,2.4,.65,1.4,shell,'CN1-key',0,2.08,1.85);
  }else{
   box(part,7.6,7.0,.65,shell,c.ref+'-base',.15,2.5,1.125);box(part,7.6,.6,4.9,shell,c.ref+'-back',.15,-.7,3.25);
   for(const sign of[-1,1])box(part,.55,7.0,4.9,shell,c.ref+'-side',.15+sign*3.525,2.5,3.25);
   // The supplied views show exposed right-angle pins, with an open top.
   for(const x of[-1,1])box(part,.35,1.0,2.5,shell,c.ref+'-key',x,5.45,2.4);
  }
  const pins={},ordered=[];
  for(const p of c.pads){
   const name=signal(p.net);pin(part,metal,c.ref+'-tail-'+p.pin,[p.x,0,-1.6],[p.x,0,vertical?5.0:3.0],.25);
   if(!vertical)pin(part,metal,c.ref+'-contact-'+p.pin,[p.x,0,3.0],[p.x,6.2,3.0],.25);
   const contact=point(part,c.ref+'-'+name,p.x,vertical?0:6.2,vertical?5.0:3.0);contact.userData={signal:name,pin:p.pin,net:p.net};pins[name]=contact;ordered.push(contact);
  }
  const mouth=vertical?point(part,c.ref+'-mouth',0,0,6.8):point(part,c.ref+'-mouth',0,6.6,3.0);
  const outward=vertical?point(part,c.ref+'-outward',0,0,10.8):point(part,c.ref+'-outward',0,10.6,3.0);
  ports[c.ref]={root:part,pins,ordered,mouth,outward,kind:vertical?'power2':'bus3',pinCount:c.pads.length,sourceRef:c.ref};
  label(group,c.ref,...c.silk.position,c.bottom?-.84:.84,silk);
 }
 group.userData.source=HUB_LAYOUT.source;group.userData.sourceSHA256=HUB_LAYOUT.sha256;
 return{group,pcb,width:HUB_LAYOUT.width*MM,height:HUB_LAYOUT.height*MM,ports};
}
