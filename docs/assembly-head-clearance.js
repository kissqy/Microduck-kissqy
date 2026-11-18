import * as T from './vendor/three.module.min.js?demo=20261013';

// Display model based on the repository's 3525 cavity-speaker photographs.
// Keep the joint transform; display the speaker beside/above the head so IDs remain readable.
export function attachHeadClearance(view){
  const index=view.model.parts.findIndex(part=>part.mesh===27),speaker=view.actual.parts[index];
  if(!speaker?.geometry)throw Error('头部喇叭显示模型缺失');
  const original=speaker.geometry,root=view.actual.root;
  root.updateMatrixWorld(true);
  const origin=speaker.worldToLocal(root.localToWorld(new T.Vector3()));
  const offset=speaker.worldToLocal(root.localToWorld(new T.Vector3(0,.032,.045))).sub(origin);
  const group=new T.Group();group.name='3525-cavity-speaker';group.position.copy(offset);speaker.add(group);
  const materials={
    shell:new T.MeshStandardMaterial({color:0x202225,roughness:.72}),
    silver:new T.MeshStandardMaterial({color:0xb9bec3,metalness:.78,roughness:.32}),
    rubber:new T.MeshStandardMaterial({color:0x111214,roughness:.94}),
    cone:new T.MeshStandardMaterial({color:0x292b2e,roughness:.86}),
    terminal:new T.MeshStandardMaterial({color:0xb68b49,metalness:.8,roughness:.35})
  };
  function rounded(w,h,r){
    const s=new T.Shape(),x=-w/2,y=-h/2;
    s.moveTo(x+r,y);s.lineTo(x+w-r,y);s.quadraticCurveTo(x+w,y,x+w,y+r);
    s.lineTo(x+w,y+h-r);s.quadraticCurveTo(x+w,y+h,x+w-r,y+h);
    s.lineTo(x+r,y+h);s.quadraticCurveTo(x,y+h,x,y+h-r);
    s.lineTo(x,y+r);s.quadraticCurveTo(x,y,x+r,y);return s;
  }
  function layer(name,w,h,r,z,depth,material,hole){
    const shape=rounded(w,h,r);if(hole)shape.holes.push(new T.Path(rounded(...hole).getPoints(48)));
    const geometry=new T.ExtrudeGeometry(shape,{depth,bevelEnabled:false,curveSegments:16});
    const mesh=new T.Mesh(geometry,materials[material]);mesh.name=name;mesh.position.set(.0175,-.0125,z);group.add(mesh);return mesh;
  }
  layer('black-acoustic-cavity',.035,.025,.002,0,.0058,'shell');
  layer('silver-face-frame',.034,.024,.002,.0058,.0007,'silver',[.028,.018,.009]);
  layer('oval-rubber-surround',.028,.018,.009,.0059,.0007,'rubber',[.0235,.0135,.00675]);
  layer('oval-diaphragm',.0235,.0135,.00675,.0059,.00035,'cone');
  // Small terminals on the short edge; the red/black pair leaves the enclosure sideways.
  const portRoot=new T.Group();portRoot.name='speaker-solder-terminals';portRoot.position.set(.035,-.0125,.0025);group.add(portRoot);
  const pins={};
  for(const [signal,y]of [['spk_p',.0007],['spk_n',-.0007]]){
    const pad=new T.Mesh(new T.BoxGeometry(.0005,.0008,.0012),materials.terminal);pad.position.set(.00005,y,0);pad.name=signal+'-terminal';portRoot.add(pad);
    const pin=new T.Object3D();pin.position.set(.0003,y,0);portRoot.add(pin);pins[signal]=pin;
  }
  const mouth=new T.Object3D(),outward=new T.Object3D();mouth.position.x=.0004;outward.position.x=.004;portRoot.add(mouth,outward);
  const port={kind:'speaker2',pinCount:2,root:portRoot,pins,mouth,outward,sourceRef:'speaker'};
  const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.Float32BufferAttribute([],3));speaker.geometry=geometry;
  let disposed=false;
  return{speaker,group,port,lift:.045,
    dispose(){if(disposed)return;disposed=true;speaker.geometry=original;speaker.remove(group);group.traverse(o=>{if(o.isMesh)o.geometry.dispose();});Object.values(materials).forEach(m=>m.dispose());geometry.dispose();}
  };
}
