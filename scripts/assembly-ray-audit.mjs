// Independent ray/triangle BVH for QA; does not use the route planner's
// distance-to-surface implementation or its collision exemptions.
import * as T from '../docs/vendor/three.module.min.js?demo=20261013';
const geometries=new WeakMap();
function treeFor(geometry){
 if(geometries.has(geometry))return geometries.get(geometry);
 const p=geometry.attributes.position,index=geometry.index,count=(index?.count||p.count)/3,triangles=[];
 for(let i=0;i<count;i++){
  const v=[0,1,2].map(j=>new T.Vector3().fromBufferAttribute(p,index?index.getX(i*3+j):i*3+j));
  triangles.push({v,box:new T.Box3().setFromPoints(v),center:v[0].clone().add(v[1]).add(v[2]).multiplyScalar(1/3)});
 }
 function build(list){const box=new T.Box3();for(const t of list)box.union(t.box);if(list.length<=12)return{box,triangles:list};const size=box.getSize(new T.Vector3()),axis=size.x>=size.y&&size.x>=size.z?'x':size.y>=size.z?'y':'z';list.sort((a,b)=>a.center[axis]-b.center[axis]);const half=list.length>>1;return{box,left:build(list.slice(0,half)),right:build(list.slice(half))};}
 const tree=build(triangles);geometries.set(geometry,tree);return tree;
}
export function independentRayMesh(a,b,mesh){
 const inverse=mesh.matrixWorld.clone().invert(),start=a.clone().applyMatrix4(inverse),end=b.clone().applyMatrix4(inverse),length=start.distanceTo(end);if(length<1e-12)return null;
 const ray=new T.Ray(start,end.sub(start).normalize()),hit=new T.Vector3(),boxHit=new T.Vector3();
 const visit=node=>{
  if(!node.box.containsPoint(start)&&(!ray.intersectBox(node.box,boxHit)||start.distanceTo(boxHit)>length))return null;
  if(node.triangles){for(const triangle of node.triangles)if(ray.intersectTriangle(...triangle.v,false,hit)){const distance=start.distanceTo(hit);if(distance>1e-7&&distance<length-1e-7)return hit.clone().applyMatrix4(mesh.matrixWorld);}return null;}
  return visit(node.left)||visit(node.right);
 };
 return visit(treeFor(mesh.geometry));
}
