import * as T from './vendor/three.module.min.js?demo=20261013';

// Display geometry, never robot kinematics. Public manufacturer CAD:
// https://ftservo.github.io/ftservo-wiki/en/products/models/hd-1910-c001/images/HD-1910-C001-20260902.stp
// Native STEP mm -> frozen servo local m: (Z + 8, X, Y) / 1000.
// The shaft axis remains local X through Y=Z=0; the two output annuli end
// at X=+/-14.5 mm, exactly matching the pinned reference mesh's shaft planes.
// No non-uniform scaling, parent/body transforms or joint axes are changed.
// The supplied STEP's shell thickness is 25.5 mm, although its drawing says
// 23 mm. Preserve the supplied CAD and shaft datums rather than silently
// stretching either the housing or the socket placement to a reference box.
const MODEL_URL=new URL('./assets/hd1910-visible.json',import.meta.url);
const BIN_URL=new URL('./assets/hd1910-visible.bin',import.meta.url);
let prepared=null,assets=null;

export function prepareServoModels(){
  if(prepared)return prepared;
  prepared=(async()=>{
    const [manifestResponse,bufferResponse]=await Promise.all([fetch(MODEL_URL),fetch(BIN_URL)]);
    if(!manifestResponse.ok||!bufferResponse.ok)throw Error('HD1910 舵机装配模型读取失败');
    const [manifest,buffer]=await Promise.all([manifestResponse.json(),bufferResponse.arrayBuffer()]);
    if(manifest.format!=='hd1910-visible-v1'||manifest.meshes.length!==3)throw Error('HD1910 舵机模型格式不符');
    const geometries=manifest.meshes.map(mesh=>{
      const geometry=new T.BufferGeometry();
      for(const key of ['position','normal','index']){
        const {offset,count}=mesh[key];
        if(offset<0||count<0||offset+count*4>buffer.byteLength)throw Error('HD1910 模型数据不完整');
        const array=key==='index'?new Uint32Array(buffer,offset,count):new Float32Array(buffer,offset,count);
        if(key==='index')geometry.setIndex(new T.BufferAttribute(array,1));
        else geometry.setAttribute(key,new T.BufferAttribute(array,3));
      }
      geometry.computeBoundingBox();geometry.computeBoundingSphere();return geometry;
    });
    assets={manifest,geometries};return assets;
  })();
  return prepared;
}

function idTexture(id){
  if(typeof document==='undefined')return null;
  const canvas=document.createElement('canvas');canvas.width=128;canvas.height=96;
  const ctx=canvas.getContext('2d');if(!ctx)return null;
  ctx.clearRect(0,0,128,96);ctx.fillStyle='#172122';ctx.fillRect(6,8,116,80);
  ctx.strokeStyle='#c1f577';ctx.lineWidth=3;ctx.strokeRect(7,9,114,78);
  ctx.fillStyle='#d5f9a8';ctx.font='700 66px system-ui,sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(String(id),64,52);
  const texture=new T.CanvasTexture(canvas);texture.colorSpace=T.SRGBColorSpace;return texture;
}

/** Call prepareServoModels() once before attaching the 15 servo instances. */
export function attachServoModel(servo,id){
  if(!assets)throw Error('请先加载 HD1910 舵机模型');
  if(servo.userData.hd1910Assembly)throw Error('HD1910 舵机已安装');
  const originalGeometry=servo.geometry;
  servo.geometry=assets.geometries[0]; // Preserve the Mesh, selection and pose.
  const group=new T.Group();group.name=`servo-${id}-identification-and-ports`;servo.add(group);
  const shellMaterial=new T.MeshStandardMaterial({color:0xe7e4d9,roughness:.66,metalness:.02,side:T.DoubleSide});
  const metalMaterial=new T.MeshStandardMaterial({color:0xc9b26b,roughness:.32,metalness:.65});
  const ports={};
  for(const [index,label]of ['in','out'].entries()){
    const spec=assets.manifest.ports[label],root=new T.Group();root.name=`servo-${id}-${label.toUpperCase()}`;
    root.position.fromArray(spec.mouth);group.add(root);
    const shell=new T.Mesh(assets.geometries[index+1],shellMaterial);shell.name=`servo-${id}-${label}-official-socket`;
    shell.position.copy(root.position).multiplyScalar(-1);root.add(shell);
    const mouth=new T.Object3D();mouth.name='socket-mouth';root.add(mouth);
    const outward=new T.Object3D();outward.name='socket-exit';outward.position.fromArray(spec.normal).multiplyScalar(spec.exit_clearance_m);root.add(outward);
    const pins={},ordered=[];
    // Keep insulation outside the official socket shell. Metallic contacts
    // extend into the keyed cavity; their free tips sit 0.2 mm past its mouth.
    // Colours describe the harness, not an electrical pinout table.
    for(const [i,signal]of ['gnd','power','data'].entries()){
      const pin=new T.Object3D();pin.name=`servo-${id}-${label}-${signal}`;
      pin.position.set(-.0002,0,(i-1)*spec.contact_pitch_m);pin.userData.signal=signal;root.add(pin);
      const contact=new T.Mesh(new T.CylinderGeometry(.00030,.00030,.0015,10),metalMaterial);
      contact.rotation.z=Math.PI/2;contact.position.copy(pin.position).add(new T.Vector3(.00075,0,0));
      contact.name=`servo-${id}-${label}-${signal}-contact`;root.add(contact);
      pins[signal]=pin;ordered.push(pin);
    }
    ports[label]={root,mouth,outward,pins,ordered,kind:'bus3',pinCount:3,source:assets.manifest.source};
  }
  const texture=idTexture(id),decalMaterial=new T.MeshBasicMaterial({map:texture,color:texture?0xffffff:0xc1f577,transparent:!!texture,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-2,side:T.DoubleSide});
  const decals=[];
  // Verified flat case faces native X=+/-10 mm => frozen Y=+/-10 mm.
  // Label footprint lies in the intact tail panel, away from shaft and ports.
  for(const sign of [-1,1]){
    const decal=new T.Mesh(new T.PlaneGeometry(.0115,.0077),decalMaterial);
    decal.name=`servo-id-${id}-${sign>0?'left':'right'}`;
    decal.rotation.x=sign>0?-Math.PI/2:Math.PI/2;
    decal.position.set(.0005,sign*.01008,-.0175);group.add(decal);decals.push(decal);
  }
  const detail={group,ports,decals,texture,
    sync(){
      for(const material of [shellMaterial,metalMaterial]){
        material.opacity=servo.material.opacity;material.transparent=servo.material.transparent;
        material.depthWrite=servo.material.depthWrite;
      }
    },
    dispose(){
      group.removeFromParent();servo.geometry=originalGeometry;delete servo.userData.hd1910Assembly;
      shellMaterial.dispose();metalMaterial.dispose();decalMaterial.dispose();texture?.dispose();
      group.traverse(object=>{if(object.isMesh&&object.geometry!==assets.geometries[1]&&object.geometry!==assets.geometries[2])object.geometry.dispose();});
    },
  };
  servo.userData.hd1910Assembly={id,source:assets.manifest.source,mapping:assets.manifest.mapping};
  detail.sync();return detail;
}
