// Official alpha model joint ranges, keyed by the console's physical servo IDs.
// Mouth range comes from duck-control/src/model.rs, not the 14-joint MJCF.
// These are reference values, not verified mechanical stops for an assembled robot.
export const officialStandingDegrees=Object.freeze({
  20:0,21:-5,22:-26.24,23:-0.28,24:25.95,
  30:20,31:20,32:0,33:0,34:0,
  10:0,11:5,12:26.24,13:0.28,14:-25.95,
});
export const modelJointLimits=Object.freeze({
  20:[-25,30],21:[-22,22],22:[-90,90],23:[-90,90],24:[-90,90],
  30:[-90,60],31:[-90,90],32:[-170,170],33:[-25,25],34:[-5,30],
  10:[-30,25],11:[-22,22],12:[-90,90],13:[-90,90],14:[-90,90],
});
export const referenceAngle=(value,digits=0)=>typeof value==='number'&&Number.isFinite(value)?`${value>0?'+':''}${value.toFixed(digits).replace('-', '−')}`:'—';
