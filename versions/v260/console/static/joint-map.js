// Physical servo housings in the pinned duck-visual.bin (64 part instances).
// A housing is often fixed to the parent link. Link ancestry is NOT its servo ID.
// Order follows the frozen robot model JOINT_IDS; geometry/hinges remain unchanged.
export const SERVO_PARTS=Object.freeze([
  {id:20,part:3}, {id:21,part:8}, {id:22,part:17}, {id:23,part:14}, {id:24,part:19},
  {id:30,part:25}, {id:31,part:26}, {id:32,part:31}, {id:33,part:39}, {id:34,part:36},
  {id:10,part:4}, {id:11,part:48}, {id:12,part:57}, {id:13,part:53}, {id:14,part:58},
].map(Object.freeze));

export function servoPartMap(model){
  if(model.parts.length!==64||SERVO_PARTS.some(({part})=>model.parts[part]?.mesh!==3))throw Error('视觉模型与舵机定位表不一致');
  return new Map(SERVO_PARTS.map(({part},joint)=>[part,joint]));
}
