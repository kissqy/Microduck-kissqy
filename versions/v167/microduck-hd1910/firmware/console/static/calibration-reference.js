import {officialStandingDegrees} from './joint-reference.js';

// These references belong to the model, never to a saved encoder calibration.
export const REFERENCE_IDS=Object.freeze([20,21,22,23,24,30,31,32,33,34,10,11,12,13,14]);
export const REFERENCE_LABELS=Object.freeze(['左髋转向','左髋侧摆','左髋俯仰','左膝','左踝','颈部俯仰','头部俯仰','头部转向','头部侧摆','嘴部','右髋转向','右髋侧摆','右髋俯仰','右膝','右踝']);
export const REFERENCE_MODES=Object.freeze(['measured','zero','home','positive','negative']);
export const hasReferenceHinge=index=>Number.isInteger(index)&&index>=0&&index<15&&REFERENCE_IDS[index]!==34;
export function referencePose(mode,selected=0,progress=1){
  if(!REFERENCE_MODES.includes(mode)||mode==='measured')throw Error('未知的独立姿态参考');
  if(mode==='home')return REFERENCE_IDS.map(id=>officialStandingDegrees[id]*Math.PI/180);
  const joints=Array(15).fill(0);
  if(mode==='positive'||mode==='negative'){
    if(!hasReferenceHinge(selected))throw Error('嘴部没有可用于标定的三维转轴');
    const t=Math.min(1,Math.max(0,Number.isFinite(progress)?progress:0));
    joints[selected]=(mode==='positive'?1:-1)*10*Math.PI/180*t;
  }
  return joints;
}
