import * as T from './vendor/three.module.min.js?demo=20261013';

// Assembly-page display only. Keep the shared robot/pose materials untouched.
const printed=new Set([1,2,4,5,6,7,8,9,10,11,12,14,15,16,17,19,20,21,22,23,24,25,26,28,29,30,31]);
const shell=new Set([1,4,8,10,19,21,25,28]);
const orange=new Set([11,12,20,22,24,30,31]);
export function prepareAssemblyAppearance(view){
  view.actual.parts.forEach((mesh,index)=>{
    const id=view.model.parts[index].mesh;if(!printed.has(id))return;
    const color=new T.Color(orange.has(id)?0xf57c28:0xf3f1e9);
    mesh.userData.baseColor.copy(color);mesh.material.color.copy(color);
    mesh.material.roughness=.74;mesh.material.metalness=0;
    mesh.userData.assemblyShell=shell.has(id);
    if(shell.has(id)){
      // A light outline retains the shell silhouette when its faces are clear.
      const edge=new T.LineSegments(new T.EdgesGeometry(mesh.geometry,32),new T.LineBasicMaterial({color:0x9babb1,transparent:true,opacity:.28,depthWrite:false}));
      edge.name='assembly-shell-outline';edge.userData.hubSolid=false;edge.raycast=()=>{};mesh.add(edge);mesh.userData.assemblyOutline=edge;
    }
  });
}
export function applyAssemblyAppearance(mesh,{dimmed=false,expanded=false}={}){
  const opacity=dimmed?.11:mesh.userData.assemblyShell?(expanded?.66:.40):1;
  mesh.material.transparent=opacity<1;mesh.material.opacity=opacity;
  mesh.material.depthWrite=opacity===1;mesh.material.depthTest=true;
  mesh.renderOrder=opacity<1?2:0;
  if(mesh.userData.assemblyOutline)mesh.userData.assemblyOutline.material.opacity=dimmed?.09:expanded?.42:.28;
}
