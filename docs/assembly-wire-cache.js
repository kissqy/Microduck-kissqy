import * as T from './vendor/three.module.min.js?demo=20261013';
export const WIRE_CACHE_REVISION='20261030-hub-arcs-v1';
const SCALE=1e7;
const packed=p=>p.toArray().map(v=>Math.round(v*SCALE));
const unpacked=a=>new T.Vector3(...a.map(v=>v/SCALE));
export function packCable(curve,metadata={}){
 const pieces=curve.curves||[curve];
 return{...metadata,segments:pieces.map(piece=>piece.isQuadraticBezierCurve3?[1,...packed(piece.v1),...packed(piece.v2)]:[0,...packed(piece.getPoint(1))])};
}
export function unpackCable(record,start,end){
 const curve=new T.CurvePath(),points=[start.clone()];let previous=start.clone();
 record.segments.forEach((s,i)=>{
  const last=i===record.segments.length-1,next=last?end.clone():unpacked(s.slice(s[0]===1?4:1));
  curve.add(s[0]===1?new T.QuadraticBezierCurve3(previous.clone(),unpacked(s.slice(1,4)),next):new T.LineCurve3(previous.clone(),next));points.push(next.clone());previous=next;
 });
 return{curve,points,bundled:record.bundled,clearance:record.clearance,cached:true};
}
export async function loadWireCache(){
 try{const response=await fetch(new URL('./assets/assembly-wire-cache.json?v='+WIRE_CACHE_REVISION,import.meta.url));if(!response.ok)return new Map();const data=await response.json();if(data.revision!==WIRE_CACHE_REVISION)return new Map();return new Map(data.states.map(state=>[state.obstacles,state]));}catch{return new Map();}
}
