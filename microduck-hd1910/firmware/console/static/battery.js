// Battery card rules. The percentage itself is robotd's single mapping
// (duck-control/src/model.rs: 8.2 V full, 6.6 V empty), so nothing here
// recomputes it from a voltage.
export const BATTERY_FULL_V=8.2,BATTERY_EMPTY_V=6.6;
const finite=v=>typeof v==='number'&&Number.isFinite(v);

export function batteryTone(percent){
  if(!finite(percent))return 'unknown';
  if(percent<20)return 'critical';
  if(percent<35)return 'low';
  return 'ok';
}

export function batteryClass(percent){
  const tone=batteryTone(percent);
  return 'metric'+(tone==='ok'||tone==='unknown'?'':' battery-'+tone);
}

export function batteryCaption(percent,volts,minVolts){
  if(!finite(percent))return '等待 robot.health · 不自行换算';
  const head=finite(volts)?`${volts.toFixed(2)} V · `:'';
  const tone=batteryTone(percent);
  if(tone==='critical')return head+'电量低，行走会欠压掉电';
  if(tone==='low')return head+'偏低，大动作前先充电';
  return finite(minVolts)?`${head}最低 ${minVolts.toFixed(2)} V`:`${head}满 ${BATTERY_FULL_V} / 空 ${BATTERY_EMPTY_V}`;
}
