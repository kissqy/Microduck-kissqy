// Display data only. These slots match the frozen model, not arrival order.
export const POSE_IDS=Object.freeze([20,21,22,23,24,30,31,32,33,34,10,11,12,13,14]);
// The mouth has a telemetry slot but no movable hinge in the visual model.
export const HINGE_IDS=Object.freeze(POSE_IDS.filter(id=>id!==34));
const finite=Number.isFinite;

function orderedRows(servos){
  const byId=new Map();
  for(const row of Array.isArray(servos)?servos:[]){
    if(!row||!POSE_IDS.includes(row.id))continue;
    // Ambiguous IDs must not silently choose whichever sample arrived last.
    byId.set(row.id,byId.has(row.id)?null:row);
  }
  return POSE_IDS.map(id=>byId.get(id)??null);
}

function jointArray(values){
  if(!Array.isArray(values)||values.length!==POSE_IDS.length)return POSE_IDS.map(()=>null);
  return POSE_IDS.map((_,i)=>finite(values[i])?values[i]:null);
}

function validGravity(value){
  if(!Array.isArray(value)||value.length!==3||![0,1,2].every(i=>finite(value[i])))return null;
  const norm=Math.hypot(...value);
  // Match gravityQuaternion's validity threshold; never label a vector live
  // when the renderer would replace it with its default upright orientation.
  return finite(norm)&&norm>=.1?value.slice():null;
}

/**
 * Resolve the current visual sample without changing calibration or inputs.
 * Missing/stale measurements are null; no HOME or zero pose is fabricated.
 * rows always has 15 slots (null for missing/duplicate IDs). missingIds only
 * lists the 14 visual hinges lacking current feedback; ID 34 cannot block them.
 */
export function resolvePoseSample(snapshot={}){
  const service=snapshot.mode==='service',rows=orderedRows(snapshot.servos);
  const stateLive=snapshot.channels?.state?.status==='live';
  const sampleFresh=service?snapshot.service_sample_fresh===true:stateLive;
  const joints=service?rows.map(row=>sampleFresh&&row?.status==='live'&&row.calibrated===true&&finite(row.angle_deg)
    ?row.angle_deg*(Math.PI/180):null):jointArray(sampleFresh?snapshot.state?.joints:null);
  const missingIds=POSE_IDS.filter((id,i)=>id!==34&&!finite(joints[i]));
  const live=sampleFresh&&missingIds.length===0;

  const imu=snapshot.imu||{},candidateGravity=validGravity(imu.gravity);
  let tiltStatus='unavailable';
  if(candidateGravity){
    if(service&&imu.mount_verified!==true)tiltStatus='unverified';
    else if(imu.status==='live'&&sampleFresh)tiltStatus='live';
    else if(['live','stale','error'].includes(imu.status))tiltStatus='stale';
  }
  const gravity=tiltStatus==='live'?candidateGravity:null;

  const targets=jointArray(snapshot.state?.targets);
  const targetsComplete=POSE_IDS.every((id,i)=>id===34||finite(targets[i]));
  const targetJoints=stateLive&&(!service||snapshot.bus?.mode==='motion')&&targetsComplete?targets:null;
  return {rows,joints,live,missingIds,gravity,tiltStatus,targetJoints};
}
