import * as T from './vendor/three.module.min.js?demo=20261013';

// Indexes refer to the pinned duck-visual.bin / duck-visual.json mesh manifest.
// These are printed structural parts, including the soft TPU mouth/soles and
// printed camera holder. Metal bearings (0/13), servo housings (3), optical lens
// (18), and speaker (27) remain assembled. Instances are separated individually;
// a repeated mesh on the other leg is not treated as the same physical part.
export const PRINTED_MESH_NAMES=Object.freeze({
  1:'右躯干外壳',2:'躯干底座',4:'左躯干外壳',5:'髋部连接件',
  6:'髋部轴承支架',7:'髋部支架',8:'左上腿外壳',9:'上腿加强板',
  10:'小腿结构件',11:'左脚底',12:'左脚掌',14:'左踝支架',
  15:'颈部侧板',16:'颈部俯仰连接件',17:'头部转向连接件',
  19:'面部壳体',20:'嘴部软垫',21:'头盖',22:'上嘴软垫',
  23:'眼部外饰件',24:'下颌',25:'头部底壳',26:'镜头支架',
  28:'右上腿外壳',29:'右踝支架',30:'右脚底',31:'右脚掌',
});

const v=(x,y,z)=>new T.Vector3(x,y,z);

// Directions describe the assembled duck's own axes (+X face, +Y left, +Z up).
// The offsets are then expressed in each part's parent frame, so switching the
// model pose still carries the separated part along with its original joint.
function separation(meshIndex,center,partIndex){
  const side=center.y<0?-1:1;
  switch(meshIndex){
    case 1:return v(-.014,-.075,.024);
    case 4:return v(-.014,.075,.024);
    case 2:return v(.025,0,-.034);
    case 5:return v(.024,side*.067,-.008);
    case 6:return v(.030,side*.096,-.012);
    case 7:return v(.012,side*.116,-.014);
    case 8:case 28:return v(-.025,side*.147,-.017);
    case 9:return v(-.025,side*.185,-.017);
    case 10:return v(-.060,side*.132,-.027);
    case 11:case 30:return v(-.030,side*.132,-.095);
    case 12:case 31:return v(.023,side*.132,-.062);
    case 14:case 29:return v(-.052,side*.123,-.019);
    case 15:return v(0,side*.067,.033);
    // Separate the neck-pitch bracket behind the head; moving it forward
    // intersects the HAT/ZERO stack when the printed parts are expanded.
    case 16:return v(-.075,0,.060);
    case 17:return v(-.044,-.024,.078);
    case 19:return v(.100,0,.042);
    case 20:return v(.074,0,-.039);
    case 21:return v(-.012,0,.110);
    case 22:return v(.078,0,.016);
    case 23:return v(.159,0,.044);
    case 24:return v(.091,0,-.012);
    case 25:return v(-.063,.020,-.029);
    case 26:return v(.127,.025,.043);
    default:throw Error(`未定义的打印件爆炸方向：${partIndex}`);
  }
}

/**
 * Separate every printed part represented by the frozen structure model.
 * This is an assembly illustration, not an installation order or force model.
 *
 * No animation/frame methods are patched. The scene calls apply() AFTER its
 * head-cover update and BEFORE cable/label updates. To compose a raised lid,
 * pass basePositions: new Map([[coverMesh, coverMesh.position.clone()]]) after
 * computing that lid position. Other parts use their exact captured local rest.
 */
export function attachPrintExplosion(view,{extraMeshes=[],followers=new Map()}={}){
  if(!view?.actual?.parts||!view?.model?.parts)throw Error('打印件结构模型尚未加载');
  const root=view.actual.root,entries=[];
  root.updateMatrixWorld(true);

  function add(mesh,index,name,deltaRoot){
    if(!mesh?.parent||!mesh.geometry)throw Error('打印件爆炸图缺少有效网格');
    const parent=mesh.parent;
    // Convert a root-local direction into this joint parent's local frame once
    // in the assembled reference pose. No world-space mesh reparenting occurs.
    const origin=root.localToWorld(v(0,0,0));
    const end=root.localToWorld(deltaRoot.clone());
    const offset=parent.worldToLocal(end.clone()).sub(parent.worldToLocal(origin.clone()));
    if(!offset.toArray().every(Number.isFinite)||offset.length()<.0001)throw Error('打印件爆炸方向无效');
    const following=(followers.get(mesh)||[]).map(object=>({object,rest:object.position.clone(),offset:object.parent.worldToLocal(end.clone()).sub(object.parent.worldToLocal(origin.clone()))}));
    entries.push({mesh,index,name,rest:mesh.position.clone(),offset,following});
  }

  view.model.parts.forEach((part,index)=>{
    const name=PRINTED_MESH_NAMES[part.mesh];if(!name)return;
    const mesh=view.actual.parts[index];
    const center=new T.Box3().setFromObject(mesh).getCenter(new T.Vector3());
    root.worldToLocal(center);
    add(mesh,index,name,separation(part.mesh,center,index));
  });
  extraMeshes.filter(Boolean).forEach((mesh,index)=>add(mesh,`extra-${index}`,'电池仓',v(-.110,0,.015)));
  let expanded=false,disposed=false;

  function apply({basePositions}={}){
    if(disposed)return;
    for(const entry of entries){
      const base=basePositions?.get(entry.mesh)||entry.rest;
      // Clone the base first: a caller may pass mesh.position itself in its Map.
      const position=base.clone();
      if(expanded)position.add(entry.offset);
      entry.mesh.position.copy(position);
      entry.mesh.updateMatrix();
      // Mounted boards, their actual connector objects and power terminal move
      // with the holder. They remain separately selectable/visible components.
      for(const follower of entry.following){follower.object.position.copy(follower.rest);if(expanded)follower.object.position.add(follower.offset);follower.object.updateMatrix();}
    }
    root.updateMatrixWorld(true);
  }
  const printedParts=Object.freeze(entries.map(entry=>Object.freeze({index:entry.index,name:entry.name,mesh:entry.mesh})));
  return{
    printedParts,count:entries.length,
    get expanded(){return expanded;},
    setExpanded(value){expanded=!!value;return expanded;},
    apply,update:apply,
    reset(options){expanded=false;apply(options);},
    dispose(options){if(disposed)return;expanded=false;apply(options);disposed=true;},
  };
}
