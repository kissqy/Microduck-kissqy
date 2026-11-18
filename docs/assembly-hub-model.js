import * as T from './vendor/three.module.min.js?demo=20261013';
import {HUB_LAYOUT} from './assembly-hub-layout.js?v=20261118-amp-cad-shape';
const MM=.001,HALF=HUB_LAYOUT.thickness/2;
const mat=(color,metalness=.04)=>new T.MeshStandardMaterial({color,roughness:metalness>.5?.33:.65,metalness});
const signal=net=>net==='GND'?'gnd':net==='VIN'?'power':'data';
function mesh(parent,geometry,material,name,x=0,y=0,z=0){const m=new T.Mesh(geometry,material);m.name=name;m.position.set(x*MM,y*MM,z*MM);m.userData.hubSolid=true;parent.add(m);return m;}
function box(parent,w,d,h,material,name,x,y,z){return mesh(parent,new T.BoxGeometry(w*MM,d*MM,h*MM),material,name,x,y,z);}
function pin(parent,material,name,a,b,r=.25){const start=new T.Vector3(...a).multiplyScalar(MM),end=new T.Vector3(...b).multiplyScalar(MM),dir=end.clone().sub(start);const m=mesh(parent,new T.CylinderGeometry(r*MM,r*MM,dir.length(),8),material,name);m.position.copy(start.add(end).multiplyScalar(.5));m.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),dir.normalize());return m;}
function point(parent,name,x,y,z){const p=new T.Object3D();p.name=name;p.position.set(x*MM,y*MM,z*MM);parent.add(p);return p;}
function pcbPad(c,p){const a=c.angle*Math.PI/180,x=p.x,y=c.bottom?-p.y:p.y;return[c.position[0]+x*Math.cos(a)-y*Math.sin(a),c.position[1]+x*Math.sin(a)+y*Math.cos(a)];}
function label(parent,text,x,y,z,material){
 const font={C:[[1,0,0,0,0,2,1,2]],J:[[0,0,1,0,1,2,0,2,0,1.5]],N:[[0,2,0,0,1,2,1,0]],'1':[[.2,.4,.6,0,.6,2],[.2,2,1,2]],'2':[[0,.3,.2,0,.8,0,1,.3,1,.8,0,2,1,2]],'3':[[0,0,1,0,.4,1,1,1.3,1,1.8,.8,2,0,2]],'4':[[.8,2,.8,0,0,1.3,1,1.3]],'5':[[1,0,0,0,0,1,1,1,1,2,0,2]]};
 let offset=0;for(const char of text){for(const line of font[char]||[])for(let i=2;i<line.length;i+=2)pin(parent,material,'silk-'+text,[x+offset+line[i-2]*.55,y-line[i-1]*.55,z],[x+offset+line[i]*.55,y-line[i+1]*.55,z],.055).userData.hubSolid=false;offset+=.9;}
}
function capacitorMark(parent,z){
 if(typeof document==='undefined')return;
 const canvas=document.createElement('canvas');canvas.width=256;canvas.height=256;const ctx=canvas.getContext('2d');if(!ctx)return;
 ctx.fillStyle='#edf0ec';ctx.fillRect(0,0,256,256);ctx.fillStyle='#c53832';ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(55,0);ctx.lineTo(140,256);ctx.lineTo(0,256);ctx.fill();
 ctx.fillStyle='#bd302e';ctx.textAlign='center';ctx.font='58px sans-serif';ctx.fillText('8X8',162,128);ctx.font='42px sans-serif';ctx.fillText('YCK',162,183);
 const texture=new T.CanvasTexture(canvas);texture.colorSpace=T.SRGBColorSpace;
 const mark=mesh(parent,new T.CircleGeometry(.00378,40),new T.MeshBasicMaterial({map:texture,side:T.DoubleSide}),'HUB-C1-top-mark',0,0,z);mark.userData.hubSolid=false;
}
export function createHubModel(){
 const group=new T.Group(),ports={},shell=mat(0xf1f0e9),metal=mat(0xbcc3c4,.8),gold=mat(0xc9ad58,.7),silk=mat(0xeef3f0),mask=mat(0x075cae),trace=mat(0x073760);
 const shape=new T.Shape();HUB_LAYOUT.outline.forEach(([x,y],i)=>i?shape.lineTo(x*MM,y*MM):shape.moveTo(x*MM,y*MM));shape.closePath();
 const holes=[...HUB_LAYOUT.holes];for(const c of HUB_LAYOUT.components)for(const p of c.pads){if(!(p.hole>0))continue;const [x,y]=pcbPad(c,p);holes.push([x,y,p.hole/2]);}
 for(const[x,y,r]of holes){const hole=new T.Path();hole.absarc(x*MM,y*MM,r*MM,0,2*Math.PI,true);shape.holes.push(hole);}
 const geometry=new T.ExtrudeGeometry(shape,{depth:HUB_LAYOUT.thickness*MM,bevelEnabled:false,curveSegments:12});geometry.translate(0,0,-HALF*MM);
 const pcb=mesh(group,geometry,mask,'HUB-V2-PCB');pcb.userData.primaryPCB=true;
 for(const[x,y,r]of holes)for(const side of[-1,1]){const ring=mesh(group,new T.RingGeometry(r*MM,(r+.32)*MM,20),gold,'HUB-plated-ring',x,y,side*(HALF+.015));if(side<0)ring.rotation.x=Math.PI;ring.userData.hubSolid=false;}
 for(const[x1,y1,x2,y2,w,layer]of HUB_LAYOUT.traces){const a=new T.Vector3(x1*MM,y1*MM,(layer===1?1:-1)*(HALF+.02)*MM),b=new T.Vector3(x2*MM,y2*MM,a.z);const m=mesh(group,new T.BoxGeometry(a.distanceTo(b),w*MM,.000012),trace,'HUB-copper');m.position.copy(a.clone().add(b).multiplyScalar(.5));m.rotation.z=Math.atan2(y2-y1,x2-x1);m.userData.hubSolid=false;}
 for(const c of HUB_LAYOUT.components){
  // C1 and straight CN2-CN5 stay underneath; CN1 is the top-side A2007WR-3P right-angle wafer.
  const bottom=HUB_LAYOUT.assemblyOverrides?.[c.ref]?.bottom??c.bottom;
  const part=new T.Group();part.name='HUB-'+c.ref;part.position.set(c.position[0]*MM,c.position[1]*MM,0);part.rotation.z=c.angle*Math.PI/180;if(bottom)part.rotateX(Math.PI);group.add(part);
  if(c.ref==='C1'){
   const can=mesh(part,new T.CylinderGeometry(.004,.004,.008,40),mat(0x555e62,.45),'HUB-C1-can',0,0,HALF+4.1);can.rotation.x=Math.PI/2;
   const top=mesh(part,new T.CylinderGeometry(.0038,.0038,.0002,40),metal,'HUB-C1-top',0,0,HALF+8.15);top.rotation.x=Math.PI/2;capacitorMark(part,HALF+8.30);
   for(const a of[-Math.PI/4,Math.PI/4]){const vent=box(part,4.2,.10,.035,mat(0x637174,.3),'HUB-C1-vent',0,0,HALF+8.27);vent.rotation.z=a;}
   const stripe=mesh(part,new T.CylinderGeometry(.00402,.00402,.0078,32,1,true,-Math.PI*.2,Math.PI*.32),mat(0xdce1df,.4),'HUB-C1-polarity',0,0,HALF+4.1);stripe.rotation.x=Math.PI/2;
   c.pads.forEach(p=>pin(part,metal,'HUB-C1-leg-'+p.pin,[p.x,0,-HALF-.6],[p.x,0,HALF+1],.25));label(group,'C1',...c.silk.position,bottom?-HALF-.03:HALF+.03,silk);continue;
  }
  if(c.ref==='CN1'){
   // A2007WR-3P wafer, from the V3 footprint and CJT A2007 drawing.
   // Open-top mating tray, guide rails and three exposed round pins;
   // unlike XH, this connector does not have a closed rectangular roof.
   const z=HALF,w=7.96,front=-7.1,rear=-1.7;
   box(part,w,5.4,.65,shell,'CN1-AMP-open-tray',0,(front+rear)/2,z+.325);
   box(part,w,.65,3.35,shell,'CN1-AMP-pin-retainer',0,rear+.325,z+2.325);
   // Stepped side guides with the rectangular locking windows seen in CAD.
   for(const sign of[-1,1]){
    const side=new T.Shape();
    side.moveTo(front,0);side.lineTo(rear+.65,0);side.lineTo(rear+.65,4);
    side.lineTo(front+.6,4);side.lineTo(front+.6,3.4);side.lineTo(front,3.4);side.closePath();
    const window=new T.Path();window.moveTo(front+1.3,1.45);window.lineTo(front+1.3,2.85);
    window.lineTo(front+3.3,2.85);window.lineTo(front+3.3,1.45);window.closePath();side.holes.push(window);
    const geo=new T.ExtrudeGeometry(side,{depth:.6*MM,bevelEnabled:false,curveSegments:8});
    // Shape plane (u,v) -> part (Y,Z), extrusion -> X.
    geo.applyMatrix4(new T.Matrix4().set(0,0,1,0, 1,0,0,0, 0,1,0,0, 0,0,0,1));
    // Shape coordinates were mm; convert Y/Z to metres, depth already metres.
    geo.scale(1,MM,MM);
    mesh(part,geo,shell,'CN1-AMP-lock-window-'+sign,sign>0?w/2-.6:-w/2,0,z);
    box(part,.6,4.6,.4,shell,'CN1-AMP-inner-guide-'+sign,sign*3.08,-4.4,z+.85);
   }
   // Three distinct retaining collars and contact channels; 2 mm pitch.
   const pins={},ordered=[];
   for(const p of c.pads){
    const net=p.net,name=net==='NC'?'nc':signal(net);
    box(part,1.05,1.6,.7,shell,'CN1-AMP-pin-collar-'+p.pin,p.x,-1.1,z+.35);
    box(part,.45,4.3,.30,shell,'CN1-AMP-contact-rib-'+p.pin,p.x,-4.0,z+.80);
    pin(part,metal,'CN1-AMP-bent-leg-'+p.pin,[p.x,0,-HALF-1],[p.x,0,z+1.7],.30);
    pin(part,metal,'CN1-AMP-round-contact-'+p.pin,[p.x,0,z+1.7],[p.x,front+.55,z+1.7],.30);
    const tip=mesh(part,new T.SphereGeometry(.30*MM,10,8),metal,'CN1-AMP-rounded-tip-'+p.pin,p.x,front+.55,z+1.7);
    const contact=point(part,'CN1-'+name,p.x,front+.55,z+1.7);
    contact.userData={signal:name,pin:p.pin,net};pins[name]=contact;ordered.push(contact);
   }
   const mouth=point(part,'CN1-mouth',0,front,z+1.7);
   const outward=point(part,'CN1-outward',0,front-4,z+1.7);
   ports.CN1={root:part,pins,ordered,mouth,outward,kind:'power2',pinCount:3,sourceRef:'CN1'};
   label(group,c.ref,...c.silk.position,HALF+.04,silk);continue;
  }
  const power=c.ref==='CN1',width=power?6.2:7.6;
  // Every connector exits perpendicular to the PCB. The part's fitted-side
  // rotation directs all four bus plugs downwards, and CN1 upwards.
  box(part,width,5.8,.7,shell,c.ref+'-base',0,-.5,HALF+.35);
  box(part,width,.65,6,shell,c.ref+'-back',0,-3.05,HALF+3);
  for(const sign of[-1,1])box(part,.65,5.8,6,shell,c.ref+'-side',sign*(width/2-.325),-.5,HALF+3);
  box(part,2.4,.65,1.4,shell,c.ref+'-key',0,2.08,HALF+1.05);
  const pins={},ordered=[];
  for(const p of c.pads){
   const name=signal(p.net);pin(part,metal,c.ref+'-tail-'+p.pin,[p.x,0,-HALF-.8],[p.x,0,HALF+4.2],.25);
   const contact=point(part,c.ref+'-'+name,p.x,0,HALF+4.2);contact.userData={signal:name,pin:p.pin,net:p.net};pins[name]=contact;ordered.push(contact);
  }
  const mouth=point(part,c.ref+'-mouth',0,0,HALF+6.0);
  const outward=point(part,c.ref+'-outward',0,0,HALF+10.0);
  ports[c.ref]={root:part,pins,ordered,mouth,outward,kind:power?'power2':'bus3',pinCount:c.pads.length,sourceRef:c.ref};
  label(group,c.ref,...c.silk.position,c.bottom?-HALF-.04:HALF+.04,silk);
 }
 group.userData.source=HUB_LAYOUT.source;group.userData.referenceImages=HUB_LAYOUT.referenceImages;
 return{group,pcb,width:HUB_LAYOUT.width*MM,height:HUB_LAYOUT.height*MM,ports};
}
