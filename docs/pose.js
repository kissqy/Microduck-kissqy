// Display-only transforms from frozen robotctl/src/duck.rs. Not a controller.
export function qmul(a, b) {
  const [w,x,y,z]=a, [v,i,j,k]=b;
  return [w*v-x*i-y*j-z*k,w*i+x*v+y*k-z*j,w*j-x*k+y*v+z*i,w*k+x*j-y*i+z*v];
}
export function gravityQuaternion(g) {
  if (!Array.isArray(g) || g.length!==3 || !g.every(Number.isFinite)) return null;
  const n=Math.hypot(...g); if(n<.1) return null;
  const [x,y,z]=g.map(v=>v/n), dot=-z;
  if(dot<-.999999) return [0,1,0,0];
  const q=[1+dot,-y,x,0], norm=Math.hypot(...q);
  return q.map(v=>v/norm); // shortest rotation carrying trunk gravity to world down
}
export function rootQuaternion(g,yaw=0) {
  const tilt=gravityQuaternion(g); if(!tilt) return null;
  // Tilt's shortest-arc construction has its own azimuth. Remove that before
  // applying contact odometry yaw; do not double-count heading.
  const [w,x,y,z]=tilt;
  const tiltYaw=Math.atan2(2*(w*z+x*y),1-2*(y*y+z*z));
  const h=(Number.isFinite(yaw)?yaw:0)-tiltYaw;
  return qmul([Math.cos(h/2),0,0,Math.sin(h/2)],tilt);
}
// The service already publishes gravity in the calibrated trunk frame.
// Render that same frame; installation errors must be corrected in the mount,
// not hidden by reversing both horizontal axes only in the viewer.
export function displayRootQuaternion(g,yaw=0) {
  return rootQuaternion(g,yaw);
}
export function parseDuck(buffer) {
  const d=new DataView(buffer); let p=0;
  const read=(type,size)=>{if(p+size>d.byteLength)throw Error('官方模型被截断');const v=d[type](p,true);p+=size;return v;};
  const u16=()=>read('getUint16',2), i16=()=>read('getInt16',2), f32=()=>read('getFloat32',4);
  if(d.byteLength<14 || read('getUint32',4)!==0x4b435544)throw Error('DUCK 模型格式不符');
  const version=read('getUint32',4);if(![1,2].includes(version))throw Error('DUCK 模型版本不符');
  const nm=u16(), nb=u16(), np=u16(); if(nm>1024||nb>128||np>2048)throw Error('模型数量异常');
  if(version===2)u16(); // alignment padding for the full-resolution arrays
  const array=(Type,count)=>{const bytes=count*Type.BYTES_PER_ELEMENT;if(p+bytes>d.byteLength)throw Error('官方模型被截断');const v=new Type(buffer,p,count);p+=bytes;return v;};
  const meshes=Array.from({length:nm},()=>{
    const nv=version===2?read('getUint32',4):u16(), nt=version===2?read('getUint32',4):u16();
    if(nv>1000000||nt>1000000)throw Error('模型网格数量异常');
    const vertices=version===2?array(Float32Array,nv*3):Array.from({length:nv*3},f32);
    const normals=version===2?array(Float32Array,nv*3):null;
    const indices=version===2?array(Uint32Array,nt*3):Array.from({length:nt*3},u16);
    if(indices.some(i=>i>=nv)||vertices.some(v=>!Number.isFinite(v)))throw Error('模型网格非法');
    if(normals?.some(v=>!Number.isFinite(v)))throw Error('模型法线非法');
    return {vertices,indices,normals};
  });
  const bodies=Array.from({length:nb},(_,i)=>{
    const parent=i16(),joint=i16(),pos=Array.from({length:3},f32),quat=Array.from({length:4},f32),axis=Array.from({length:3},f32);
    if(parent>=i || parent< -1 || joint< -1 || joint>=15)throw Error('模型骨架非法');
    return {parent,joint,pos,quat,axis};
  });
  const parts=Array.from({length:np},()=>{
    const body=u16(),mesh=u16(),rgb=[read('getUint8',1),read('getUint8',1),read('getUint8',1)];read('getUint8',1);
    const pos=Array.from({length:3},f32),quat=Array.from({length:4},f32);
    if(body>=nb||mesh>=nm)throw Error('模型零件非法');return {body,mesh,rgb,pos,quat};
  });
  if(p!==d.byteLength)throw Error('模型存在未知尾部');
  return {version,meshes,bodies,parts};
}
