// Durations belong to the acquisition that failed, never to the latest good read.
const finite=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
export const isLateRead=message=>/complete but transaction deadline exceeded/.test(message||'');

export function readTiming(bus,record){
  if(!finite(record?.elapsed_us))return '耗时未上报';
  const native=bus.native||{},revision=native.read_timing_revision;
  // These constants describe the bundled R16 backend, not arbitrary services.
  const r15=['590b986-feetech-ft6-control.15','590b986-feetech-ft6-control.16'].includes(bus.build)||revision==='r4.1-read-timing.1';
  const deadline=finite(record.deadline_us)?record.deadline_us:(revision==='r15-read-timing.2'||bus.build==='590b986-feetech-ft6-control.16')?20000:r15?15000:null;
  const maxAge=finite(record.complete_max_age_us)?record.complete_max_age_us:r15?20000:null;
  const ms=v=>(v/1000).toFixed(3)+' ms';
  const text=[`实际耗时 ${ms(record.elapsed_us)}`];
  if(deadline!==null){
    text.push(`截止 ${ms(deadline)}`);
    if(record.elapsed_us>=deadline)text.push(`超出 ${ms(record.elapsed_us-deadline)}`);
  }
  if(maxAge!==null&&(record.complete_but_late||isLateRead(record.error)))text.push(`完整反馈时效要求 <${ms(maxAge)}`);
  return text.join(' · ');
}

export function acceptedLateRead(bus){
  const totals=bus.native?.telemetry,last=totals?.last_complete_but_late;
  return bus.native?.sync?.complete_but_late===true&&last?.accepted===true&&last.read===totals.total_reads;
}

export function failureText(bus,failure){
  if(!failure?.error)return '';
  const hasMissing=Array.isArray(failure.missing_ids)&&failure.missing_ids.length;
  const knownR17=bus.native?.read_timing_revision==='r15-read-timing.2';
  const deadline=finite(failure.deadline_us)?failure.deadline_us:knownR17?20000:null;
  const timedMissing=hasMissing&&(failure.deadline_exceeded===true||deadline!==null&&finite(failure.elapsed_us)&&failure.elapsed_us>=deadline);
  const category=timedMissing?`超时未回 ID：${failure.missing_ids.join(', ')}（不重复计缺包）\n`:failure.complete_but_late||isLateRead(failure.error)?'完整回包超时（整轮，未归因到设备）\n':'';
  return category+failure.error+(finite(failure.elapsed_us)||isLateRead(failure.error)?`\n${readTiming(bus,failure)}`:'');
}
