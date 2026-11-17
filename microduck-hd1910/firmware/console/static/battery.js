// Battery card text. The percentage itself is robotd's single mapping
// (duck-control/src/model.rs: 8.2 V full, 6.6 V empty), so nothing here
// recomputes one from a voltage; the alarm thresholds come from alarms.js so
// this card, the servo card and the CPU card agree on what "red" means.
import {level,alarmReason} from './alarms.js';

export const BATTERY_FULL_V=8.2,BATTERY_EMPTY_V=6.6;
const finite=v=>typeof v==='number'&&Number.isFinite(v);

export function batteryTone(percent){
  const state=level('battery',percent);
  if(state==='critical')return 'critical';
  if(state==='warn')return 'low';
  return finite(percent)?'ok':'unknown';
}

export function batteryCaption(percent,volts,minVolts){
  if(!finite(percent))return '等待 robot.health · 不自行换算';
  const head=finite(volts)?`${volts.toFixed(2)} V · `:'';
  const tail=finite(minVolts)?`最低 ${minVolts.toFixed(2)} V`:`满 ${BATTERY_FULL_V} / 空 ${BATTERY_EMPTY_V}`;
  const reason=alarmReason('battery',percent);
  if(reason)return `${head}${reason}, 先充电再走`;
  return `${head}${tail}`;
}
