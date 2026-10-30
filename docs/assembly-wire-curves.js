import * as T from './vendor/three.module.min.js?demo=20261013';

// Round a routed polyline without moving its contact endpoints. Each fillet
// must pass the same surface-clearance check as the original cable.
export function softenCableCorners(curve,{accept=()=>true,radius=.0035}={}){
 const pieces=curve.curves||[curve];
 if(!pieces.length||pieces.some(piece=>!piece.isLineCurve3))return curve;
 const raw=[pieces[0].getPoint(0),...pieces.map(piece=>piece.getPoint(1))];
 const points=[];
 for(const point of raw){
  if(points.length&&point.distanceToSquared(points.at(-1))<1e-18)continue;
  // Collapse only genuinely straight samples; retain the routed bend and
  // individual core's roll through narrow passages.
  while(points.length>1){
   const a=points.at(-2),b=points.at(-1),ab=b.clone().sub(a),bc=point.clone().sub(b);
   if(ab.lengthSq()<1e-18||bc.lengthSq()<1e-18||ab.normalize().dot(bc.normalize())<.99995)break;
   const line=new T.CurvePath();line.add(new T.LineCurve3(a.clone(),point.clone()));
   if(!accept(line))break;points.pop();
  }
  points.push(point.clone());
 }
 const result=new T.CurvePath();let current=points[0];
 const lineTo=end=>{if(current.distanceToSquared(end)>1e-18)result.add(new T.LineCurve3(current.clone(),end.clone()));current=end;};
 for(let i=1;i<points.length-1;i++){
  const corner=points[i],before=corner.distanceTo(points[i-1]),after=corner.distanceTo(points[i+1]);
  let rounded=null;
  const maximum=Math.min(radius,before*.42,after*.42,i===1||i===points.length-2?.0005:Infinity);
  for(let trim=maximum;trim>=.000025;trim*=.5){
   const entry=corner.clone().lerp(points[i-1],trim/before),exit=corner.clone().lerp(points[i+1],trim/after);
   const bend=new T.QuadraticBezierCurve3(entry,corner.clone(),exit),test=new T.CurvePath();test.add(bend);
   if(accept(test)){rounded={entry,exit,bend};break;}
  }
  if(!rounded){lineTo(corner);continue;}
  lineTo(rounded.entry);result.add(rounded.bend);current=rounded.exit;
 }
 lineTo(points.at(-1));
 result.arcLengthDivisions=Math.max(200,Math.ceil(result.getLength()/.00025));
 return accept(result)?result:curve;
}
