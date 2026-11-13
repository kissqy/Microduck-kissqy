// Keep chart samples separate from the latest full telemetry and log payload.
const fields=['id','status','angle_deg','target_deg','position_raw','goal_position_raw','current_ma','current_raw','temperature_c','velocity_rpm','speed_raw','error_deg'];
export function historyFrame(s){
  return {
    at:s.at,mode:s.mode,
    channels:Object.fromEntries(['bus','state','health'].map(name=>[name,{status:s.channels?.[name]?.status}])),
    bus:{achieved_hz:s.bus?.achieved_hz},
    state:{loop:{hz:s.state?.loop?.hz},odom:{position:s.state?.odom?.position?.slice()}},
    health:{control_loop:{achieved_hz:s.health?.control_loop?.achieved_hz},battery:{volts:s.health?.battery?.volts},motors:{max_c:s.health?.motors?.max_c}},
    imu:{status:s.imu?.status,gravity:s.imu?.gravity?.slice()},
    servos:(s.servos||[]).map(row=>Object.fromEntries(fields.map(key=>[key,row[key]]))),
  };
}
