import * as T from './vendor/three.module.min.js?demo=20261013';
import {meshCollider,segmentBox} from './assembly-mesh-clearance.js?v=20261027-printed-clearance';

// Display-only routing against actual servo AND printed-part surfaces. BVHs
// retain cavities and openings that a solid box would incorrectly close.
const CLEARANCE=.00055,SAMPLE_STEP=.0004;
const p0=new T.Vector3(),p1=new T.Vector3();
function corners(box,matrix){
 const result=[];
 for(const x of[box.min.x,box.max.x])for(const y of[box.min.y,box.max.y])for(const z of[box.min.z,box.max.z])result.push(new T.Vector3(x,y,z).applyMatrix4(matrix));
 return result;
}
function onLead(point,start,end){
 const direction=end.clone().sub(start),length=direction.lengthSq();
 if(length<1e-18)return point.distanceToSquared(start)<1e-16;
 const t=point.clone().sub(start).dot(direction)/length;
 return t>=-1e-7&&t<=1+1e-7&&point.distanceToSquared(start.clone().addScaledVector(direction,t))<1e-16;
}
function roundedPath(points,radius){
 const curve=new T.CurvePath();let current=points[0].clone();
 const addLine=end=>{if(current.distanceToSquared(end)>1e-18)curve.add(new T.LineCurve3(current.clone(),end.clone()));current=end.clone();};
 for(let i=1;i<points.length-1;i++){
  const previous=points[i-1],corner=points[i],next=points[i+1];
  const before=corner.distanceTo(previous),after=corner.distanceTo(next);
  const trim=Math.min(radius,before*.42,after*.42,i===1||i===points.length-2?.0007:Infinity);
  if(trim<1e-9){addLine(corner);continue;}
  const entry=corner.clone().lerp(previous,trim/before),exit=corner.clone().lerp(next,trim/after);
  addLine(entry);curve.add(new T.QuadraticBezierCurve3(entry,corner.clone(),exit));current=exit;
 }
 addLine(points.at(-1));curve.arcLengthDivisions=Math.max(200,Math.ceil(curve.getLength()/SAMPLE_STEP));return curve;
}

export function createWireRouter(root,servoMeshes,printedMeshes=[],{clearance=CLEARANCE}={}){
 const margin=clearance;
 const meshes=[...new Set([...servoMeshes,...printedMeshes])],graphs=new Map(),passages=[];let signature='',obstacles=[],lastFailure=null;
 function segmentHits(a,b,ignore=null){
  for(const obstacle of obstacles){
   if(obstacle.mesh===ignore||!segmentBox(a,b,obstacle.broad))continue;
   p0.copy(a).applyMatrix4(obstacle.toLocal);p1.copy(b).applyMatrix4(obstacle.toLocal);
   if(obstacle.collider.hit(p0,p1,obstacle.localClearance))return obstacle;
  }
  return null;
 }
 const clear=(a,b)=>!segmentHits(a,b);
 // CAD surfaces can contain seams/open ends; ray parity would falsely close
 // a connector cavity. Every complete cable is instead checked continuously
 // against surface distance, including its fixed physical contact segments.
 function outside(point){return !segmentHits(point,point);}
 function update(){
  root.updateWorldMatrix(true,true);const inverse=root.matrixWorld.clone().invert();
  const frames=meshes.map(mesh=>({mesh,matrix:new T.Matrix4().multiplyMatrices(inverse,mesh.matrixWorld)}));
  const next=frames.map(({matrix})=>matrix.elements.map(value=>value.toFixed(7)).join(',')).join(';');
  if(next===signature)return false;signature=next;graphs.clear();passages.length=0;
  obstacles=frames.map(({mesh,matrix})=>{
   if(!mesh.geometry.boundingBox)mesh.geometry.computeBoundingBox();
   const box=mesh.geometry.boundingBox.clone(),vertices=corners(box,matrix),broad=new T.Box3().setFromPoints(vertices).expandByScalar(margin),toLocal=matrix.clone().invert();
   return{mesh,box,broad,toRoot:matrix,toLocal,collider:meshCollider(mesh.geometry),localClearance:margin*toLocal.getMaxScaleOnAxis()};
  });
  return true;
 }
 function graphFor(lane,start,end){
  const level=Math.max(-1,Math.min(1,Math.round(lane))),region=new T.Box3().setFromPoints([start,end]).expandByScalar(.025);
  const key=level+'|'+[...region.min.toArray(),...region.max.toArray()].map(x=>Math.round(x/.01)).join(',');if(graphs.has(key))return graphs.get(key);
  // Separate stand-offs stop the three conductors from sharing every corner.
  const standOff=.001+(level+1)*.00065,points=[];
  for(const obstacle of obstacles){
   if(!region.intersectsBox(obstacle.broad))continue;
   const box=obstacle.box.clone().expandByScalar(standOff);
   for(const point of corners(box,obstacle.toRoot))if(outside(point))points.push(point);
  }
  const outer=new T.Box3();obstacles.forEach(obstacle=>outer.union(obstacle.broad));outer.intersect(region);outer.expandByScalar(.008+(level+1)*.001);
  for(const point of corners(outer,new T.Matrix4()))if(outside(point))points.push(point);
  const edges=points.map(()=>[]);
  const tested=new Set();
  for(let i=0;i<points.length;i++){
   const nearest=points.map((point,j)=>({j,distance:points[i].distanceTo(point)})).filter(p=>p.j!==i).sort((a,b)=>a.distance-b.distance).slice(0,28);
   for(const{j,distance}of nearest){const pair=Math.min(i,j)*points.length+Math.max(i,j);if(tested.has(pair))continue;tested.add(pair);
    if(clear(points[i],points[j])){edges[i].push([j,distance]);edges[j].push([i,distance]);}
   }
  }
  const graph={points,edges};graphs.set(key,graph);return graph;
 }
 function compactPath(path){
  const compact=[path[0]];let at=0;
  while(at<path.length-1){let next=path.length-1;while(next>at+1&&!clear(path[at],path[next]))next--;compact.push(path[next]);at=next;}
  return compact;
 }
 function tightenPath(path){
  path=path.map(point=>point.clone());
  // Visibility corners sit outside whole-part bounds. Slide each corner
  // toward its neighbours using the actual triangles, so wires hug the
  // available passage rather than following oversized rectangular detours.
  for(let pass=0;pass<6;pass++){
   for(let i=1;i<path.length-1;i++){
    const original=path[i],target=path[i-1].clone().add(path[i+1]).multiplyScalar(.5);
    if(original.distanceToSquared(target)<1e-8)continue;
    let low=0,high=1;
    for(let search=0;search<9;search++){
     const amount=(low+high)/2,candidate=original.clone().lerp(target,amount);
     if(clear(path[i-1],candidate)&&clear(candidate,path[i+1]))low=amount;else high=amount;
    }
    if(low>0)path[i]=original.clone().lerp(target,low*.985);
   }
   path=compactPath(path);
  }
  return path;
 }
 // Visibility corners cover open runs. A small, lazy grid resolves the narrow
 // passages inside hollow brackets/head shells without filling those cavities
 // with solid bounding boxes. Every edge still uses exact mesh clearance.
 function passagePath(start,end,budget=2500){
  const step=.002,limit=new T.Box3().setFromPoints([start,end]).expandByScalar(.032),heap=[],nodes=new Map();
  const moves=[];for(let x=-1;x<=1;x++)for(let y=-1;y<=1;y++)for(let z=-1;z<=1;z++)if(x||y||z)moves.push([x,y,z,Math.hypot(x,y,z)*step]);
  function push(node){let i=heap.length;heap.push(node);while(i){const p=(i-1)>>1;if(heap[p].score<=node.score)break;heap[i]=heap[p];i=p;}heap[i]=node;}
  function pop(){const first=heap[0],last=heap.pop();if(heap.length){let i=0;while(i*2+1<heap.length){let j=i*2+1;if(j+1<heap.length&&heap[j+1].score<heap[j].score)j++;if(heap[j].score>=last.score)break;heap[i]=heap[j];i=j;}heap[i]=last;}return first;}
  const initial={x:0,y:0,z:0,point:start.clone(),cost:0,score:start.distanceTo(end),previous:null};nodes.set('0,0,0',initial);push(initial);
  for(let visits=0;heap.length&&visits<budget;visits++){
   const node=pop();if(node.done||nodes.get(node.x+','+node.y+','+node.z)!==node)continue;node.done=true;
   if(clear(node.point,end)){
    const path=[end.clone()];for(let at=node;at;at=at.previous)path.push(at.point);return compactPath(path.reverse());
   }
   for(const[dx,dy,dz,length]of moves){
    const x=node.x+dx,y=node.y+dy,z=node.z+dz,key=x+','+y+','+z,existing=nodes.get(key);if(existing?.done||existing?.blocked)continue;
    const point=existing?.point||start.clone().add(new T.Vector3(x*step,y*step,z*step));
    if(!limit.containsPoint(point)){nodes.set(key,{blocked:true});continue;}
    if(!clear(node.point,point))continue;
    const cost=node.cost+length;if(existing&&existing.cost<=cost)continue;
    const next={x,y,z,point,cost,score:cost+point.distanceTo(end)*1.18,previous:node};nodes.set(key,next);push(next);
   }
  }
  return null;
 }
 function simplePassage(start,end){
  const candidates=[];
  for(let mask=1;mask<7;mask++){
   const bend=start.clone();for(let axis=0;axis<3;axis++)if(mask&(1<<axis))bend.setComponent(axis,end.getComponent(axis));candidates.push([start.clone(),bend,end.clone()]);
  }
  for(const order of[[0,1,2],[0,2,1],[1,0,2],[1,2,0],[2,0,1],[2,1,0]]){
   const a=start.clone().setComponent(order[0],end.getComponent(order[0])),b=a.clone().setComponent(order[1],end.getComponent(order[1]));candidates.push([start.clone(),a,b,end.clone()]);
  }
  // Try compact runs around one nearby face before building a visibility
  // graph. This avoids long triangular excursions to distant CAD corners.
  for(let axis=0;axis<3;axis++)for(const sign of[-1,1])for(const gap of[.002,.004,.008,.012,.02]){
   const plane=(sign<0?Math.min(start.getComponent(axis),end.getComponent(axis)):Math.max(start.getComponent(axis),end.getComponent(axis)))+sign*gap;
   candidates.push([start.clone(),start.clone().setComponent(axis,plane),end.clone().setComponent(axis,plane),end.clone()]);
  }
  let best=null,score=Infinity;
  for(let path of candidates){
   path=path.filter((p,i)=>!i||p.distanceToSquared(path[i-1])>1e-18);
   const length=path.slice(1).reduce((sum,p,i)=>sum+p.distanceTo(path[i]),0),cost=length+(path.length-2)*.001;
   if(cost>=score||!path.slice(1).every((p,i)=>clear(path[i],p)))continue;score=cost;best=path;
  }
  return best;
 }
 function middlePath(start,end,lane){
  if(!outside(start)||!outside(end))return null;
  if(clear(start,end))return[start.clone(),end.clone()];
  const simple=simplePassage(start,end);if(simple)return tightenPath(simple);
  for(const path of passages){
   if(path[0].distanceTo(start)>.005||path.at(-1).distanceTo(end)>.005)continue;
   const da=start.clone().sub(path[0]),db=end.clone().sub(path.at(-1));
   const candidate=path.map((point,i)=>point.clone().addScaledVector(da,1-i/(path.length-1)).addScaledVector(db,i/(path.length-1)));
   if(candidate.slice(1).every((point,i)=>clear(candidate[i],point)))return candidate;
  }
  const graph=graphFor(lane,start,end),count=graph.points.length,startIndex=count,endIndex=count+1;
  const points=[...graph.points,start,end],edges=[...graph.edges.map(row=>[...row]),[],[]];
  for(let i=0;i<count;i++)for(const index of[startIndex,endIndex])if(clear(points[index],points[i])){
   const distance=points[index].distanceTo(points[i]);edges[index].push([i,distance]);edges[i].push([index,distance]);
  }
  const distances=new Float64Array(count+2);distances.fill(Infinity);distances[startIndex]=0;
  const previous=new Int32Array(count+2);previous.fill(-1);const done=new Uint8Array(count+2);
  for(let visit=0;visit<count+2;visit++){
   let index=-1,best=Infinity;
   for(let i=0;i<count+2;i++)if(!done[i]&&distances[i]<best){index=i;best=distances[i];}
   if(index<0)break;if(index===endIndex)break;done[index]=1;
   for(const[next,distance]of edges[index])if(!done[next]&&best+distance<distances[next]){distances[next]=best+distance;previous[next]=index;}
  }
  if(!Number.isFinite(distances[endIndex])){const path=passagePath(start,end);if(path)passages.push(path);return path;}
  const path=[];for(let at=endIndex;at!==-1;at=previous[at])path.push(points[at].clone());path.reverse();
  // Remove graph detours that became redundant after the shortest-path search.
  let compact=compactPath(path);
  const length=points=>points.slice(1).reduce((sum,point,i)=>sum+point.distanceTo(points[i]),0);
  if(length(compact)>start.distanceTo(end)*1.8+.012){const shorter=passagePath(start,end,1500);if(shorter&&length(shorter)<length(compact))compact=shorter;}
  compact=tightenPath(compact);passages.push(compact);return compact;
 }
 function validate(curve,{start,leadA,leadB,end,fromServo,toServo,fromContacts=[],toContacts=[]}){
  for(const segment of curve.curves){
   const divisions=Math.max(1,Math.ceil(segment.getLength()/SAMPLE_STEP));let a=segment.getPoint(0);
   for(let i=1;i<=divisions;i++){
    const b=segment.getPoint(i/divisions);
    for(const obstacle of obstacles){
     if((obstacle.mesh===fromServo||fromContacts.includes(obstacle.mesh))&&onLead(a,start,leadA)&&onLead(b,start,leadA))continue;
     if((obstacle.mesh===toServo||toContacts.includes(obstacle.mesh))&&onLead(a,end,leadB)&&onLead(b,end,leadB))continue;
     if(!segmentBox(a,b,obstacle.broad))continue;
     p0.copy(a).applyMatrix4(obstacle.toLocal);p1.copy(b).applyMatrix4(obstacle.toLocal);
     if(obstacle.collider.hit(p0,p1,obstacle.localClearance))return obstacle;
    }
    a=b;
   }
  }
  return null;
 }
 function separatedDirectPaths({leadA,leadB,fromServo,toServo,lane=0}){
  if(Math.abs(lane)<.1)return null;
  const direction=leadB.clone().sub(leadA).normalize();
  const owners=[fromServo,toServo].map(mesh=>obstacles.find(obstacle=>obstacle.mesh===mesh)).filter(Boolean);
  // When the contact row and cable run are collinear, three different pins can
  // otherwise produce almost the same line. Fan those cores apart after the
  // socket exits, keeping the original terminal straight segments intact.
  if(!owners.some(owner=>Math.abs(new T.Vector3(0,0,1).transformDirection(owner.toRoot).dot(direction))>.94))return null;
  const axes=[];
  for(const owner of owners)for(const axis of[new T.Vector3(1,0,0),new T.Vector3(0,1,0)])axes.push(axis.transformDirection(owner.toRoot));
  axes.push(new T.Vector3(1,0,0),new T.Vector3(0,1,0),new T.Vector3(0,0,1));
  const perpendiculars=[];
  for(const axis of axes){
   const perpendicular=axis.addScaledVector(direction,-axis.dot(direction));
   if(perpendicular.lengthSq()<1e-8)continue;perpendicular.normalize();
   if(perpendiculars.some(previous=>Math.abs(previous.dot(perpendicular))>.999))continue;
   perpendiculars.push(perpendicular);
  }
  const paths=[];
  for(const distance of[.0014,.0011,.0008])for(const perpendicular of perpendiculars)for(const side of[1,-1]){
   const offset=perpendicular.clone().multiplyScalar(lane*distance*side);
   const points=[leadA.clone(),leadA.clone().lerp(leadB,1/3).add(offset),leadA.clone().lerp(leadB,2/3).add(offset),leadB.clone()];
   if(points.slice(1).every((point,index)=>clear(points[index],point)))paths.push(points);
  }
  return paths;
 }
 function route(spec){
  if(!signature)update();lastFailure=null;
  const{start,leadA,leadB,end,lane=0}=spec;
  if(spec.previous?.length>3){
   const old=spec.previous,da=start.clone().sub(old[0]),db=end.clone().sub(old.at(-1));
   const points=old.map((point,i)=>point.clone().addScaledVector(da,1-i/(old.length-1)).addScaledVector(db,i/(old.length-1)));
   points[0]=start.clone();points[1]=leadA.clone();points[points.length-2]=leadB.clone();points[points.length-1]=end.clone();
   for(const radius of[.0035,.002,.001,.0003,0]){const curve=roundedPath(points,radius);if(!validate(curve,spec))return{curve,points,clearance:margin,bendRadius:radius,length:curve.getLength(),signature};}
  }
  const middle=middlePath(leadA,leadB,lane);
  if(!middle){lastFailure={reason:'no-clear-external-path'};return null;}
  const separated=middle.length===2?separatedDirectPaths(spec):null;
  if(separated&&separated.length===0){lastFailure={reason:'no-separated-direct-path'};return null;}
  for(const candidate of separated||[middle]){
   const points=[start.clone(),...candidate,end.clone()];
   for(const radius of[.0035,.002,.001,.00075,.0003,0]){
    const curve=roundedPath(points,radius),hit=validate(curve,spec);
    if(!hit)return{curve,points,clearance:margin,bendRadius:radius,length:curve.getLength(),signature,laneSeparated:!!separated};
    lastFailure={reason:'terminal-or-bend-clearance',obstacle:hit.mesh.userData?.hd1910Assembly?.id??hit.mesh.name};
   }
  }
  return null;
 }
 return{update,route,validate,clearSegment:clear,segmentHits,get signature(){return signature;},get obstacles(){return obstacles;},get lastFailure(){return lastFailure;},clearance:margin};
}
