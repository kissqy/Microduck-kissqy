/** Small fault report. Full 10 Hz replay remains an explicit separate export. */
const pick=(value,keys)=>Object.fromEntries(keys.filter(k=>value?.[k]!==undefined).map(k=>[k,value[k]]));
const clean=value=>{
  if(Array.isArray(value))return value.map(clean);
  if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).filter(([k])=>!/(password|secret|token|credential|private_key)/i.test(k)&&!['log','stdout','stderr','source'].includes(k)).map(([k,v])=>[k,clean(v)]));
  return value;
};
const servoFields=['id','status','position_raw','angle_deg','target_deg','speed_raw','current_raw','temperature_c','voltage_v','torque_enabled','hardware_error'];
function faults(frame){
  const b=frame.bus||{},n=b.native||{};
  return {
    channels:Object.fromEntries(Object.entries(frame.channels||{}).filter(([,v])=>['error','stale'].includes(v.status)||v.error).map(([k,v])=>[k,pick(v,['status','error'])])),
    ...pick(b,['last_cycle_error','last_enable_refusal','last_failure']),
    communication:pick(n.telemetry,['last_error','last_failure']),
    stale_joint_ids:n.stale_joint_ids||[],held_joint_ids:n.held_joint_ids||[],
    imu:pick(frame.imu,['status','reason']),
    servos:(frame.servos||[]).filter(s=>s.hardware_error||s.status==='error'||s.status==='stale').map(s=>pick(s,['id','status','hardware_error'])),
  };
}
function sample(f){
  const b=f.bus||{},n=b.native||{};
  return {at:f.at,service_sample_fresh:f.service_sample_fresh,
    state:pick(f.state,['policy','move','head','safety','loop','odom']),
    bus:pick(b,['cycle','phase','mode','policy_enabled','homed','torque_off_pending','active_action_scale','active_target_filters','voltage_scale_mult','scale_use','fresh_sample','read_recovery']),
    hardware:{...pick(n,['imu_ready','imu_sequence','imu_age_upper_bound_ms','sample_age_ms','all_joints_fresh','stale_joint_ids','held_joint_ids','torque_state_confirmed','command_clamps_total']),
      communication:pick(n.telemetry,['session','total_reads','failed_reads','complete_but_late']),sync:pick(n.sync,['missing_ids','bad_checksums','discarded','elapsed_us','deadline_exceeded','complete_but_late'])},
    health:f.health,imu:{...pick(f.imu,['gravity','roll_deg','pitch_deg','status','reason','age_ms']),
      gyro:f.state?.imu?.gyro??f.imu?.gyro,quat:f.state?.imu?.quat??f.imu?.quat},
    servos:(f.servos||[]).map(s=>servoFields.map(k=>s[k]??null)),
    tof:pick(f.tof,['seq','at_us','subscription']),
  };
}
export function diagnosticReport(recording,current){
  const frames=recording.frames||[],last=current||frames.at(-1)||{},selected=new Set(),events=[],metadata=[],seen=new Set();
  let next=-Infinity,previous=null;
  const addContext=i=>{for(let j=Math.max(0,i-10);j<=Math.min(frames.length-1,i+10);j++)selected.add(j);};
  for(let i=0;i<frames.length;i++){
    const f=frames[i];
    if(f.at>=next){selected.add(i);next=f.at+1;}
    const fault=faults(f),key=JSON.stringify(fault);
    if(key!==previous){events.push({at:f.at,...fault});if(previous!==null)addContext(i);previous=key;}
    // Metadata is stored once per actual configuration, never once per frame.
    const models=Object.fromEntries(Object.entries(f.bus?.loaded_models||{}).map(([slot,m])=>[slot,pick(m,['sha256','task','name','task_adapter','bam_parameter_sha256','runtime_execution_profile'])]));
    const config={version:f.version,build:f.bus?.build,models,calibration:f.calibration,
      parameters:pick(f.bus,['action_scale','walk_action_scale','head_lowpass','legs_lowpass','voltage_adapt','nominal_voltage','model_action_scales'])};
    const identity=JSON.stringify(config);
    if(!seen.has(identity)){seen.add(identity);metadata.push({at:f.at,...config});}
  }
  for(const command of recording.service_commands||[]){
    const at=command.recorded_at??command.at,index=frames.findIndex(f=>f.at>=at);
    if(index>=0)addContext(index);
  }
  if(frames.length)selected.add(frames.length-1);
  return clean({schema:'microduck-console-diagnostic/v1',version:last.version,baseline:recording.baseline,
    created_at:recording.created_at,mode:recording.mode,
    capture:{source_frames:frames.length,saved_samples:selected.size,normal_interval_seconds:1,fault_context_seconds:1,
      note:'用于排障；正常运行约每秒一份摘要，状态变化和操作前后保留原采样。完整动作回放从录制与回放单独导出。'},
    metadata,servo_columns:servoFields,events,
    samples:[...selected].sort((a,b)=>a-b).map(i=>sample(frames[i])),
    current:{...sample(last),faults:faults(last),startup:last.startup,system:last.system,
      connection:last.connection,control:last.control,service_control:last.service_control,
      communication:last.bus?.device_communication,latest_tof:last.tof},
    service_commands:(recording.service_commands||[]).map(c=>pick(c,['at','recorded_at','action','status','command','phase','message','error','result','install_progress','transfer_progress'])),
    last_failure:recording.last_failure,
  });
}
