// Display/export FK from the robot's compiled, static model. Angles are in
// radians; poses are metres and Hamilton quaternions [w,x,y,z]. The controller
// retains its native FK; this module only replaces the telemetry copy of it.

const compiled = new WeakMap();
const identity = () => ({pos:[0,0,0],quat:[1,0,0,0]});
const vector = (v,n) => Array.isArray(v) && v.length===n && v.every(Number.isFinite);
const mul = (a,b) => [
  a[0]*b[0]-a[1]*b[1]-a[2]*b[2]-a[3]*b[3],
  a[0]*b[1]+a[1]*b[0]+a[2]*b[3]-a[3]*b[2],
  a[0]*b[2]-a[1]*b[3]+a[2]*b[0]+a[3]*b[1],
  a[0]*b[3]+a[1]*b[2]-a[2]*b[1]+a[3]*b[0],
];
function rotate(q,v) {
  const [w,x,y,z]=q,[vx,vy,vz]=v;
  const tx=2*(y*vz-z*vy),ty=2*(z*vx-x*vz),tz=2*(x*vy-y*vx);
  return [vx+w*tx+y*tz-z*ty,vy+w*ty+z*tx-x*tz,vz+w*tz+x*ty-y*tx];
}
function compose(a,b) {
  const p=rotate(a.quat,b.pos);
  return {pos:[a.pos[0]+p[0],a.pos[1]+p[1],a.pos[2]+p[2]],quat:mul(a.quat,b.quat)};
}
function turn(pose,joint,angles) {
  if(joint!==null) {
    const half=angles[joint.index]*.5,s=Math.sin(half),axis=joint.axis;
    pose.quat=mul(pose.quat,[Math.cos(half),axis[0]*s,axis[1]*s,axis[2]*s]);
  }
  return pose;
}
function compile(definition) {
  if(!definition || definition.schema!=='r17.kinematics.v1')throw Error('机器人几何协议不符');
  const {joint_names:names,head_joints:heads,bodies,sites,site_to_cv2:cv2,sensor_in_cv2:sensor}=definition;
  if(!Array.isArray(names)||!names.length||names.length>128||names.some(n=>typeof n!=='string')||new Set(names).size!==names.length)throw Error('机器人几何关节定义无效');
  if(!Array.isArray(heads)||heads.length!==4||heads.some(n=>!names.includes(n))||new Set(heads).size!==4)throw Error('机器人几何头部定义无效');
  if(!Array.isArray(bodies)||!bodies.length||bodies.length>512||!sites||!Array.isArray(sites.head_camera)||!vector(cv2,4)||!vector(sensor,4))throw Error('机器人几何结构无效');
  const checkLink=link=>{
    if(!link?.rest||!vector(link.rest.pos,3)||!vector(link.rest.quat,4))throw Error('机器人几何变换无效');
    const j=link.joint;
    if(j!==null&&(!j||!Number.isInteger(j.index)||j.index<0||j.index>=names.length||!vector(j.axis,3)))throw Error('机器人几何转轴无效');
  };
  bodies.forEach((body,i)=>{
    checkLink(body);
    if(body.parent!==null&&(!Number.isInteger(body.parent)||body.parent<0||body.parent>=i))throw Error('机器人几何父子关系无效');
  });
  for(const name of ['head_camera','tof','head_imu'])if(sites[name]!==undefined) {
    if(!Array.isArray(sites[name])||!sites[name].length||sites[name].length>128)throw Error('机器人几何传感器链无效');
    sites[name].forEach(checkLink);
  }
  return {names,heads:new Set(heads),bodies,sites,cv2,sensor,wireMappings:new Map()};
}

export function deriveKinematics(definition,wireJointNames,positions) {
  let model=compiled.get(definition);
  if(!model){model=compile(definition);compiled.set(definition,model);}
  if(!Array.isArray(wireJointNames)||!Array.isArray(positions)||positions.some(v=>!Number.isFinite(v)))throw Error('机器人关节样本无效');
  const key=JSON.stringify(wireJointNames);
  let indices=model.wireMappings.get(key);
  if(!indices){
    indices=model.names.map(n=>wireJointNames.indexOf(n));
    if(model.wireMappings.size>=4)model.wireMappings.clear();
    model.wireMappings.set(key,indices);
  }
  // Match native mapping::skeleton_at: a wire without a named model joint
  // takes that joint at zero; no input or controller targets are generated.
  const angles=indices.map(i=>i>=0&&i<positions.length?positions[i]:0);
  const headAngles=angles.map((angle,i)=>model.heads.has(model.names[i])?angle:0);
  const skeleton=[];
  for(const body of model.bodies) {
    const pose=body.parent===null?{pos:[...body.rest.pos],quat:[...body.rest.quat]}:compose(skeleton[body.parent],body.rest);
    skeleton.push(turn(pose,body.joint,angles));
  }
  const site=name=>model.sites[name]?.reduce((pose,link)=>turn(compose(pose,link.rest),link.joint,headAngles),identity());
  const cameraSite=site('head_camera'),camera={pos:cameraSite.pos,quat:mul(cameraSite.quat,model.cv2)};
  const tofSite=site('tof');
  const tof=tofSite?{pos:tofSite.pos,quat:mul(mul(tofSite.quat,model.cv2),model.sensor)}:{pos:[...camera.pos],quat:mul(camera.quat,model.sensor)};
  const frames={camera,tof},imu=site('head_imu');
  if(imu)frames.head_imu=imu;
  return {frames,skeleton};
}
