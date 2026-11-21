// Alarm thresholds and the one class that paints them.
//
// Each metric card answers the same question — "is this number telling me to
// stop?" — so the thresholds live here rather than in three places, and every
// alarm looks the same: amber for "watch it", red for "act now".
// A missing sample is never an alarm: an absent reading is not a hot servo.
const finite=v=>typeof v==='number'&&Number.isFinite(v);

export const LIMITS={
  // The pack: 8.2 V full, 6.6 V empty (robotd's own mapping). Under 20 % the walk
  // already sags into a brownout on this chassis, so that is the red line.
  battery:{warn:35,critical:20,unit:'%'},
  // HD-1910 case temperature. 60 °C is where a long hold starts cooking the
  // servo; 70 °C is past anything a normal hold should reach.
  servo:{warn:60,critical:70,unit:'°C'},
  // RK3566 throttles passively at 85 °C, and the walk diagnostics measured
  // 89–90 °C with nothing but idle services running.
  cpu:{warn:75,critical:85,unit:'°C'},
};

export function level(kind,value){
  const limit=LIMITS[kind];
  if(!limit||!finite(value))return 'none';
  if(kind==='battery'){
    // The battery is the one value where low is bad and high is good.
    if(value<limit.critical)return 'critical';
    if(value<limit.warn)return 'warn';
    return 'none';
  }
  if(value>=limit.critical)return 'critical';
  if(value>=limit.warn)return 'warn';
  return 'none';
}

export function alarmClass(kind,value){
  const state=level(kind,value);
  return 'metric'+(state==='none'?'':' alarm-'+state);
}

export function alarmLabel(kind,value){
  const state=level(kind,value);
  if(state==='critical')return '告警';
  if(state==='warn')return '注意';
  return '';
}

// The full rule, for the tooltip and the docs: both lines, in one place.
export function limitText(kind){
  const limit=LIMITS[kind];
  if(!limit)return '';
  if(kind==='battery')return `${limit.warn} % 注意 · ${limit.critical} % 告警`;
  return `${limit.warn} ${limit.unit} 注意 · ${limit.critical} ${limit.unit} 告警`;
}

// The one line that matters *now*. Cards are narrow, so a healthy card stays
// quiet and only an alarmed one spends caption space on the threshold.
export function alarmReason(kind,value){
  const limit=LIMITS[kind];
  const state=level(kind,value);
  if(!limit||state==='none')return '';
  if(kind==='battery')return `低于 ${state==='critical'?limit.critical:limit.warn} %`;
  return `高于 ${state==='critical'?limit.critical:limit.warn} ${limit.unit}`;
}
