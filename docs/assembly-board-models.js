import * as T from './vendor/three.module.min.js?demo=20261013';
import {PCB_LAYOUTS} from './assembly-board-layouts.js?v=20261030-harness';

// HAT / IMU: actual board outlines, mounting holes, component XY / rotation and
// copper routes from the current HAT (2026-10-30) / IMU (2026-10-15) sources. Heights and
// package shells are simplified visualization, not manufacturing / clearance CAD.
// ZERO: official Radxa ZERO 3W product brief Rev1.8 (65 x 30 mm mechanical drawing
// and front / back board photographs); component bodies are representative.
const MM=.001,THICK=1.6;
const COLORS={pcb:0x125b45,edge:0x81916a,chip:0x252b2b,resistor:0x353b39,ceramic:0xaaa07b,metal:0xb7c3bf,gold:0xc7a653,white:0xe6e2d3,black:0x181e1d,led:0x91d46c};
const material=key=>new T.MeshStandardMaterial({color:COLORS[key],roughness:key==='metal'?.32:key==='gold'?.3:.7,metalness:['metal','gold'].includes(key)?.75:.04});

// Small details are merged by material to keep the assembled robot inexpensive
// to orbit on mobile; connectors still have actual cavities, contacts and pins.
class DetailBatch{
  constructor(){this.parts=new Map();}
  add(geometry,key,x=0,y=0,z=0,angle=0,rx=0){
    let g=geometry.index?geometry.toNonIndexed():geometry;
    if(g!==geometry)geometry.dispose();
    const q=new T.Quaternion().setFromEuler(new T.Euler(rx,0,angle));
    g.applyMatrix4(new T.Matrix4().compose(new T.Vector3(x*MM,y*MM,z*MM),q,new T.Vector3(1,1,1)));
    if(!this.parts.has(key))this.parts.set(key,[]);this.parts.get(key).push(g);
  }
  box(w,h,d,key,x,y,z,a=0){this.add(new T.BoxGeometry(w*MM,h*MM,d*MM),key,x,y,z,a);}
  cylinder(r,h,key,x,y,z){this.add(new T.CylinderGeometry(r*MM,r*MM,h*MM,12),key,x,y,z,0,Math.PI/2);}
  finish(parent){
    for(const [key,geometries]of this.parts){
      const arrays={position:[],normal:[]};
      for(const g of geometries){for(const name of ['position','normal'])arrays[name].push(g.getAttribute(name).array);}
      const merged=new T.BufferGeometry();
      for(const name of ['position','normal']){const list=arrays[name],all=new Float32Array(list.reduce((n,a)=>n+a.length,0));let offset=0;for(const a of list){all.set(a,offset);offset+=a.length;}merged.setAttribute(name,new T.BufferAttribute(all,3));}
      merged.computeBoundingBox();merged.computeBoundingSphere();
      const mesh=new T.Mesh(merged,material(key));mesh.name=`board-details-${key}`;parent.add(mesh);
      geometries.forEach(g=>g.dispose());
    }
  }
}
function boardShape(w,h,r,holes){
  const shape=new T.Shape(),x=-w/2*MM,y=-h/2*MM,W=w*MM,H=h*MM,R=Math.min(r,w/3,h/3)*MM;
  shape.moveTo(x+R,y);shape.lineTo(x+W-R,y);shape.quadraticCurveTo(x+W,y,x+W,y+R);shape.lineTo(x+W,y+H-R);shape.quadraticCurveTo(x+W,y+H,x+W-R,y+H);shape.lineTo(x+R,y+H);shape.quadraticCurveTo(x,y+H,x,y+H-R);shape.lineTo(x,y+R);shape.quadraticCurveTo(x,y,x+R,y);
  holes.forEach(([hx,hy,hr])=>{const hole=new T.Path();hole.absarc(hx*MM,hy*MM,hr*MM,0,Math.PI*2,true);shape.holes.push(hole);});
  return shape;
}
function pcbMesh(w,h,r,holes){
  const geo=new T.ExtrudeGeometry(boardShape(w,h,r,holes),{depth:THICK*MM,bevelEnabled:false,curveSegments:6});geo.translate(0,0,-THICK/2*MM);
  const mesh=new T.Mesh(geo,material('pcb'));mesh.userData.primaryPCB=true;return mesh;
}
function rotatePoint(x,y,a){return[x*Math.cos(a)-y*Math.sin(a),x*Math.sin(a)+y*Math.cos(a)];}
function at(c,x,y,z){const [dx,dy]=rotatePoint(x,y,c.angle*Math.PI/180);return[c.x+dx,c.y+dy,z];}
function localBox(batch,c,w,h,d,key,x=0,y=0,z=0){const p=at(c,x,y,z);batch.box(w,h,d,key,...p,c.angle*Math.PI/180);}
function rings(batch,holes){
  holes.forEach(([x,y,r])=>{for(const side of[-1,1])batch.add(new T.RingGeometry(r*MM,(r+.45)*MM,16),'gold',x,y,side*(THICK/2+.025));});
}
function pinHeader(batch,c,count,rows=1,pitch=2.54,female=false,bottom=false){
  const n=Math.ceil(count/rows),w=(n-1)*pitch+2.54,h=rows*pitch,side=bottom?-1:1;
  localBox(batch,c,w,h,female?5.0:2.4,'black',0,0,side*(THICK/2+(female?2.5:1.2)));
  for(let row=0;row<rows;row++)for(let col=0;col<n;col++){
    const x=(col-(n-1)/2)*pitch,y=(row-(rows-1)/2)*pitch;
    if(female){
      localBox(batch,c,.95,.95,.3,'gold',x,y,side*(THICK/2+5.05));
      localBox(batch,c,.56,.56,.32,'black',x,y,side*(THICK/2+5.1));
    }else localBox(batch,c,.6,.6,5.8,'gold',x,y,side*(THICK/2+2.4));
  }
}
function whiteConnector(batch,c,count,pitch=2,w=null,h=4.4,height=5.3){
  w=w||((count-1)*pitch+3.9);
  // Open front face and separate upright sidewalls, not an opaque white cube.
  localBox(batch,c,w,h,.8,'white',0,0,THICK/2+.4);
  localBox(batch,c,w,.75,height,'white',0,h/2-.38,THICK/2+height/2);
  for(const sign of[-1,1])localBox(batch,c,.8,h,height,'white',sign*(w/2-.4),0,THICK/2+height/2);
  localBox(batch,c,w*.44,.8,1.0,'white',0,-h/2+.4,THICK/2+1.25);
  for(let p=0;p<count;p++)localBox(batch,c,.5,.65,height*.62,'gold',(p-(count-1)/2)*pitch,.45,THICK/2+height*.34);
}
// Contact anchors use the same connector-local coordinates as the visible
// merged package geometry above. The wire renderer must use these Objects,
// never the PCB centre. Object positions are metres, package inputs are mm.
function portObject(parent,name,x=0,y=0,z=0){
  const object=new T.Object3D();object.name=name;object.position.set(x*MM,y*MM,z*MM);parent.add(object);return object;
}
function addBusPort(parent,c,{name=c.ref,pitch=2,height=5.3,h=4.4}={}){
  const root=portObject(parent,`${name}-connector`,c.x,c.y,0);root.rotation.z=c.angle*Math.PI/180;
  root.userData.connector=name;root.userData.role='three-wire-bus';
  // CJT A2007WV is a vertical header (cjt.com/upload/A2007.pdf). The
  // mating opening is above the PCB, not towards its edge. These anchors sit
  // at the actual visible pin tips and follow the IMU's mounted board group.
  const z=THICK/2+height*.65;
  const pins={
    gnd:portObject(root,`${name}-GND`,c.busPins?.gnd?.[0]??-pitch,.45,z),
    power:portObject(root,`${name}-POWER`,c.busPins?.power?.[0]??0,.45,z),
    data:portObject(root,`${name}-DATA`,c.busPins?.data?.[0]??pitch,.45,z),
  };
  for(const [signal,pin]of Object.entries(pins))pin.userData.signal=signal;
  const mouth=portObject(root,`${name}-mouth`,0,.45,THICK/2+height);
  const outward=portObject(root,`${name}-outward`,0,.45,THICK/2+height+4);
  return{kind:'bus3',pinCount:3,root,pins,mouth,outward,sourceRef:c.ref};
}
function addHeaderPort(parent,c,{name=c.ref,count=40,rows=2,pitch=2.54,female=false,bottom=false}={}){
  const root=portObject(parent,`${name}-connector`,c.x,c.y,0);root.rotation.z=c.angle*Math.PI/180;
  root.userData.connector=name;root.userData.role='header';
  const n=Math.ceil(count/rows),side=bottom?-1:1;
  // Female holes at the open face; male anchors at the free metal pin tips.
  const z=side*(THICK/2+(female?5.1:2.4+5.8/2));
  const ordered=[];
  for(let row=0;row<rows;row++)for(let col=0;col<n;col++){
    const pin=portObject(root,`${name}-contact-${row}-${col}`,(col-(n-1)/2)*pitch,(row-(rows-1)/2)*pitch,z);
    pin.userData.displayContact=ordered.length;ordered.push(pin);
  }
  const mouth=portObject(root,`${name}-mouth`,0,0,z);
  const outward=portObject(root,`${name}-outward`,0,0,z+side*4);
  // This is geometric row-major contact order, deliberately NOT GPIO numbers
  // or the HAT footprint's paired / mirrored electrical numbering.
  return{kind:'header40',pinCount:count,root,pins:{ordered},ordered,mouth,outward,sourceRef:c.ref,numbering:'display-contact-order'};
}
function pcbPorts(parent,layout,id){
  const ports={};
  for(const c of layout.components){
    if(id==='hat'&&['J13','J14'].includes(c.ref))ports[c.ref]=addBusPort(parent,c);
    else if(id==='imu'&&c.ref==='J1')ports.J1=addBusPort(parent,c);
    else if(id==='hat'&&c.ref==='J4')ports.J4=addHeaderPort(parent,c,{female:true,bottom:true});
  }
  if(id==='hat'){ports.bus=ports.J13;ports.header=ports.J4;}
  if(id==='imu')ports.bus=ports.J1;
  return ports;
}
function icBody(batch,c,w,h,height=1,metal=false){
  const side=c.bottom?-1:1;
  localBox(batch,c,w,h,height,metal?'metal':'chip',0,0,side*(THICK/2+height/2+.07));
  // Package contact positions come directly from the associated footprint.
  for(const [x,y,pw,ph]of c.pads||[]){
    if(pw>Math.max(w,h)||ph>Math.max(w,h))continue;
    localBox(batch,c,Math.min(pw,.65),Math.min(ph,1.1),.13,'metal',x,y,side*(THICK/2+.12));
  }
}
function renderPCBParts(batch,layout){
  for(const c of layout.components){
    const pkg=c.package,ref=c.ref||'',name=c.name||'';
    if(pkg.includes('40P')){pinHeader(batch,c,40,2,2.54,true,true);continue;}
    if(pkg.includes('HDR-TH_5P')){pinHeader(batch,c,5);continue;}
    if(pkg.includes('A2007')){whiteConnector(batch,c,3);continue;}
    if(pkg.includes('A1251')){whiteConnector(batch,c,2,1.25,4.2,3.2,3.5);continue;}
    if(pkg.includes('BM04B')){whiteConnector(batch,c,4,1,5.5,3,2.7);continue;}
    if(pkg.includes('IND-SMD')){localBox(batch,c,6,6,4.5,'chip',0,0,THICK/2+2.25);localBox(batch,c,4.8,4.8,.10,'metal',0,0,THICK/2+4.53);continue;}
    const dims=pkg.match(/_L([\d.]+)-W([\d.]+)/);
    if(ref.startsWith('U')&&dims){icBody(batch,c,Number(dims[1]),Number(dims[2]),pkg.includes('SOIC')?1.5:.9);continue;}
    if(pkg.includes('MIC-SMD')){icBody(batch,c,2.8,1.9,.9,true);const p=at(c,.6,0,THICK/2+1);batch.cylinder(.18,.05,'black',...p);continue;}
    if(pkg.includes('OSC-SMD')){icBody(batch,c,2.5,2,.65,true);continue;}
    const isCap=ref.startsWith('C'),isLED=pkg.includes('LED'),isDiode=ref.startsWith('D'),size=pkg.includes('1206')?[3.2,1.6]:pkg.includes('0805')?[2,1.25]:[1.6,.8];
    const height=isCap?.75:.5;
    localBox(batch,c,size[0],size[1],height,isLED?'led':isCap?'ceramic':isDiode?'black':'resistor',0,0,THICK/2+height/2+.03);
    for(const side of[-1,1])localBox(batch,c,.25,size[1]+.04,height*.9,'metal',side*(size[0]/2-.1),0,THICK/2+height*.45);
  }
}
function pcbTexture(layout,id,bottom=false){
  if(typeof document==='undefined')return null;
  const canvas=document.createElement('canvas');canvas.width=2048;canvas.height=Math.round(2048*layout.height/layout.width);const ctx=canvas.getContext('2d');if(!ctx)return null;
  const sx=canvas.width/layout.width,sy=canvas.height/layout.height;
  const xy=(x,y)=>[(x+layout.width/2)*sx,(layout.height/2-y)*sy];
  ctx.clearRect(0,0,canvas.width,canvas.height);ctx.lineCap='round';ctx.strokeStyle='rgba(96,171,111,.3)';
  for(const [x,y,X,Y,w,layer]of layout.traces||[]){if(layer!==(bottom?2:1))continue;const a=xy(x,y),b=xy(X,Y);ctx.lineWidth=Math.max(1,w*sx*.55);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();}
  ctx.fillStyle='#d4e2c4';ctx.font=`${Math.round(sx*.8)}px sans-serif`;ctx.textAlign='center';ctx.textBaseline='middle';
  for(const c of layout.components){if(!!c.bottom!==bottom)continue;const p=xy(c.x,c.y-1.8);ctx.fillText(c.ref||'',...p);}
  ctx.fillStyle='#eef1db';ctx.font=`600 ${Math.round(sx*1.2)}px sans-serif`;ctx.textAlign='right';ctx.fillText(id==='hat'?'MICRODUCK HAT':'IMU → DXL',canvas.width-2.5*sx,2.1*sy);
  const texture=new T.CanvasTexture(canvas);texture.colorSpace=T.SRGBColorSpace;texture.anisotropy=4;return texture;
}
function texturedSurface(group,layout,id){
  for(const bottom of[false,true]){const map=pcbTexture(layout,id,bottom);if(!map)continue;
    const surface=new T.Mesh(new T.PlaneGeometry(layout.width*MM,layout.height*MM),new T.MeshBasicMaterial({map,transparent:true,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-1,side:T.DoubleSide}));
    surface.position.z=(bottom?-1:1)*(THICK/2+.035)*MM;if(bottom)surface.rotation.y=Math.PI;group.add(surface);
  }
}
function portShell(batch,x,y,z,w,h,d,type){
  // Connector mouth points towards board's -Y edge.
  batch.box(w,h,d,'metal',x,y,z);batch.box(w-1.0,.12,d-1.0,'black',x,y-h/2-.065,z);
  batch.box(w-2.6,.30,.75,type==='hdmi'?'gold':'black',x,y-h/2-.15,z-.35);
  for(const side of[-1,1])batch.box(.5,h+1,.35,'metal',x+side*(w/2-.6),y,z-d/2-.2);
}
function zeroModel(){
  const width=65,height=30,group=new T.Group();
  const holes=[[-29,-11.4,1.4],[29,-11.4,1.4],[29,11.4,1.4],[-29,11.4,1.4]],pcb=pcbMesh(width,height,3,holes);group.add(pcb);
  const batch=new DetailBatch();rings(batch,holes);
  const gpio={ref:'gpio40',x:0,y:11.8,angle:0};pinHeader(batch,gpio,40,2);
  const gpio40=addHeaderPort(group,gpio),ports={gpio40,header:gpio40};
  // Official front photograph: RAM above RK3566, USB-C pair at opposite long
  // edge from GPIO, shielded radio towards HDMI / onboard antenna end.
  const chip=(x,y,w,h,d)=>icBody(batch,{x,y,angle:0,pads:[]},w,h,d);
  chip(-5,-1.2,15,15,1.15);chip(10.5,1,10.5,8,1.05);chip(25.3,1.5,7.6,7.6,.9);
  batch.box(12,11,1.65,'metal',-21,1,THICK/2+.825); // radio shield
  portShell(batch,21.5,-13.4,2.0,8.8,6.8,3.1,'usb');
  portShell(batch,7.8,-13.4,2.0,8.8,6.8,3.1,'usb');
  portShell(batch,-21,-13.7,2.2,6.5,5.7,3.0,'hdmi');
  // Bottom-side micro-SD slot and MIPI-CSI latch, no optional eMMC fitted.
  batch.box(13.8,12,1.45,'metal',25.1,-.2,-THICK/2-.725);
  batch.box(12.5,.7,.30,'black',25.1,-6,-THICK/2-.95);
  batch.box(16.3,3.2,2,'white',-27,-.5,-THICK/2-1);
  batch.box(14.8,.8,2.3,'black',-27,-1.9,-THICK/2-1.1);
  // Small passives are grouped around the actual large functional blocks.
  for(const [cx,cy,n]of [[-6,-10,8],[10,7,9],[25,-6,6],[-14,8,7],[-24,8,5]])for(let k=0;k<n;k++){
    const x=cx+(k%4-1.5)*1.45,y=cy+Math.floor(k/4)*1.25;batch.box(.85,.5,.4,k%3?'ceramic':'black',x,y,THICK/2+.2);
    batch.box(.15,.5,.35,'metal',x-.35,y,THICK/2+.2);batch.box(.15,.5,.35,'metal',x+.35,y,THICK/2+.2);
  }
  // RF antenna contact and printed antenna edge are distinctive, but do not
  // imply a precise antenna / connector placement across Zero hardware SKUs.
  batch.cylinder(.9,.6,'gold',-30,-3,1.1);batch.cylinder(.4,.7,'black',-30,-3,1.25);
  batch.finish(group);
  if(typeof document!=='undefined'){
    const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=512;const ctx=canvas.getContext('2d');if(ctx){
      ctx.fillStyle='#dfe9d6';ctx.font='600 48px sans-serif';ctx.textAlign='center';ctx.fillText('RK3566',430,270);ctx.font='28px sans-serif';ctx.fillText('radxa ZERO 3W',500,460);
      const map=new T.CanvasTexture(canvas);map.colorSpace=T.SRGBColorSpace;const mesh=new T.Mesh(new T.PlaneGeometry(.060,.027),new T.MeshBasicMaterial({map,transparent:true,depthWrite:false}));mesh.position.z=.0021;group.add(mesh);
    }
  }
  group.userData.detailSource='Radxa ZERO 3W Product Brief Rev1.8; package heights / small passives simplified';
  return{group,pcb,width:width*MM,height:height*MM,ports};
}

export function createBoardModel(id,spec={}){
  if(id==='zero')return zeroModel();
  const layout=PCB_LAYOUTS[id];if(!layout)return null;
  const group=new T.Group(),pcb=pcbMesh(layout.width,layout.height,Math.min(layout.radius,2.54),layout.holes);group.add(pcb);
  const batch=new DetailBatch();rings(batch,layout.holes);renderPCBParts(batch,layout);batch.finish(group);texturedSurface(group,layout,id);
  const ports=pcbPorts(group,layout,id);
  group.userData.detailSource=`Published ${id.toUpperCase()} PCB 2026-10-15; component XY / rotation and copper traces source-backed; heights simplified`;
  // IMU board is presented portrait to match its mount and the existing viewer.
  if(id==='imu'){
    const wrapper=new T.Group();wrapper.add(group);group.rotation.z=Math.PI/2;
    return{group:wrapper,pcb,width:layout.height*MM,height:layout.width*MM,ports};
  }
  return{group,pcb,width:layout.width*MM,height:layout.height*MM,ports};
}
