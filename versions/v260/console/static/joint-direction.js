const unknown=()=>({value:null,label:'—',title:'未读取已保存的关节方向'});

// Saved installation calibration owns this sign; model geometry cannot infer it.
export function jointDirection(snapshot,row){
  if(snapshot?.mode!=='service'||snapshot.connection_paused===true||snapshot.connection?.connected===false)return unknown();
  const channel=snapshot.channels?.calibration;
  if(channel&&channel.status!=='live')return unknown();
  let calibration;
  const joints=snapshot.calibration?.calibration?.joints;
  if(Array.isArray(joints)){
    const matches=joints.filter(joint=>joint?.id===row.id);
    if(matches.length!==1)return unknown();
    calibration=matches[0];
  }else if(!Object.hasOwn(snapshot,'calibration')){
    // Earlier recordings kept installation metadata on each row only.
    calibration=row.calibration;
  }
  if(calibration?.id!==row.id||calibration.name!==row.name||calibration.calibrated!==true||![1,-1].includes(calibration.direction))return unknown();
  const value=calibration.direction;
  return {value,label:value===1?'正向 +1':'反向 −1',title:`已保存标定：编码器 counts 递增时，关节角度${value===1?'增加':'减少'}（${value===1?'+1':'−1'}）`};
}
