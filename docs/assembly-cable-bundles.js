import * as T from './vendor/three.module.min.js?demo=20261013';
// Transport a compact three-core bundle along one route. A small dynamic
// program rolls its cross-section through narrow slots while keeping the
// terminal order and checking every inter-sample conductor segment.
export function parallelCablePaths(center,starts,leadsA,leadsB,ends,{clearSegment,flat=false}={}){
 const count=starts.length,length=center.getLength(),steps=Math.max(8,Math.min(360,Math.ceil(length/.001)));
 const frames=center.computeFrenetFrames(steps,false),points=center.getSpacedPoints(steps),states=12;
 const average=list=>list.reduce((sum,p)=>sum.add(p),new T.Vector3()).multiplyScalar(1/list.length);
 const ca=average(leadsA),cb=average(leadsB),da=leadsA.at(-1).clone().sub(leadsA[0]),db=leadsB.at(-1).clone().sub(leadsB[0]);
 const a=Math.atan2(da.dot(frames.binormals[0]),da.dot(frames.normals[0]));
 let b=Math.atan2(db.dot(frames.binormals[steps]),db.dot(frames.normals[steps]));while(b-a>Math.PI)b-=Math.PI*2;while(b-a< -Math.PI)b+=Math.PI*2;
 const offsets=count===3&&!flat?[[-.0004,.000231],[0,-.000462],[.0004,.000231]]:starts.map((_,i)=>[(i-(count-1)/2)*.0008,0]);
 const source=leadsA.map(p=>p.clone().sub(ca)),target=leadsB.map(p=>p.clone().sub(cb));
 const positions=(i,j)=>{
  const t=i/steps,angle=a+(b-a)*t+j*2*Math.PI/states,n=frames.normals[i],bin=frames.binormals[i],cs=Math.cos(angle),sn=Math.sin(angle);
  const fan=Math.min(.004,length*.22),from=Math.max(0,1-t*length/fan),to=Math.max(0,1-(1-t)*length/fan);
  return offsets.map(([x,y],lane)=>{
   const d=n.clone().multiplyScalar(x*cs-y*sn).addScaledVector(bin,x*sn+y*cs);
   if(from)d.lerp(source[lane],from*from*(3-2*from));if(to)d.lerp(target[lane],to*to*(3-2*to));
   return points[i].clone().add(d);
  });
 };
 const clear=(a,b)=>!clearSegment||clearSegment(a,b);
 let previous=[{j:0,positions:leadsA,cost:0,parent:null}];
 for(let i=1;i<steps;i++){
  const next=[];
  for(let j=0;j<states;j++){
   const p=positions(i,j);if(!p.every(v=>clear(v,v)))continue;
   let best=null,cost=Infinity;
   for(const before of previous){
    const difference=Math.min(Math.abs(j-before.j),states-Math.abs(j-before.j));if(i>1&&difference>3)continue;
    const distance=p.reduce((sum,v,lane)=>sum+v.distanceTo(before.positions[lane]),0),score=before.cost+distance+difference*.000025;
    if(score>=cost||!p.every((v,lane)=>clear(before.positions[lane],v)))continue;
    cost=score;best=before;
   }
   if(best)next.push({j,positions:p,cost,parent:best});
  }
  if(!next.length)return null;previous=next;
 }
 previous=previous.filter(node=>leadsB.every((p,lane)=>clear(node.positions[lane],p))).sort((a,b)=>a.cost-b.cost);if(!previous.length)return null;
 const crossSections=[leadsB];for(let node=previous[0];node;node=node.parent)crossSections.push(node.positions);crossSections.reverse();
 return starts.map((start,lane)=>{
  const path=[start.clone(),...crossSections.map(row=>row[lane].clone()),ends[lane].clone()],curve=new T.CurvePath();
  for(let i=1;i<path.length;i++)if(path[i-1].distanceToSquared(path[i])>1e-18)curve.add(new T.LineCurve3(path[i-1],path[i]));
  return{curve,points:path,length:curve.getLength(),clearance:.00045,bundled:true};
 });
}
