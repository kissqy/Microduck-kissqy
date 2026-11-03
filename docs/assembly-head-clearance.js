import * as T from './vendor/three.module.min.js?demo=20261013';

// Assembly-view accommodation for the HD1910 cases. The frozen speaker was
// placed against an XL330; its lower face clips the taller HD1910 ID 33 case.
// Translate a private display geometry, preserving every part/joint transform.
export function attachHeadClearance(view){
  const index=view.model.parts.findIndex(part=>part.mesh===27),speaker=view.actual.parts[index];
  if(!speaker?.geometry)throw Error('头部喇叭显示模型缺失');
  const original=speaker.geometry,root=view.actual.root;
  root.updateMatrixWorld(true);
  const origin=speaker.worldToLocal(root.localToWorld(new T.Vector3()));
  const offset=speaker.worldToLocal(root.localToWorld(new T.Vector3(0,0,.003))).sub(origin);
  const geometry=original.clone();geometry.translate(offset.x,offset.y,offset.z);
  geometry.computeBoundingBox();geometry.computeBoundingSphere();speaker.geometry=geometry;
  let disposed=false;
  return{speaker,lift:.003,
    dispose(){if(disposed)return;disposed=true;speaker.geometry=original;geometry.dispose();},
  };
}
