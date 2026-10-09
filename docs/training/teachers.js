 'use strict';
// Current and known V2 teachers keep their own provenance and physical contracts.
const teacherRoles={walk:'walk',stand:'stand'};
let teacherStamp='';
function eligibleTeacher(c,role){
  return c.kind==='PT'&&c.job.target_compatible
    &&taskCatalog.tasks.find(t=>t.id===(c.job.resolved_task||c.job.request.task))?.role===teacherRoles[role];
}
window.jointTrainingParameters=(value,allowQueue=false)=>{
  if(taskCatalog.tasks.find(t=>t.id===value.task)?.role!=='joint'||value.source_job)return {};
  const walk=chosen('walk-teacher'),stand=chosen('stand-teacher');
  if(!(walk.source_job||(allowQueue&&walk.queue_entry))||!(stand.source_job||(allowQueue&&stand.queue_entry)))throw Error(allowQueue?'联合训练需要选择老师PT或排在前面的队列老师。':'队列老师请用“添加到队列”；单独启动需要已经训练好的两位老师PT。');
  return {walk_teacher:walk,stand_teacher:stand};
};
window.renderJointTraining=()=>{
  if(!state)return;
  const task=$('task').value,joint=taskCatalog.tasks.find(t=>t.id===task)?.role==='joint';
  $('joint-training-panel').hidden=!joint;
  const records=modelRecords().filter(c=>c.kind==='PT');
  const queued=(state.training_queue?.entries||[]).filter(e=>['waiting','starting','running','completed'].includes(e.status));
  const stamp=JSON.stringify([records.map(c=>[c.path,c.job.id,c.iteration,c.job.target_compatible,c.job.resolved_task,c.job.compatibility_label]),queued.map(e=>[e.id,e.status,e.request.task,e.request.label])]);
  if(stamp!==teacherStamp){
    for(const role of ['walk','stand']){
      const options=records.filter(c=>eligibleTeacher(c,role)).map(c=>`<option value="${esc(JSON.stringify(c.value))}">${esc(recordLabel(c))}</option>`).join('');
      const future=queued.filter(e=>taskCatalog.tasks.find(t=>t.id===e.request.task)?.role===role).map(e=>`<option value="${esc(JSON.stringify({queue_entry:e.id}))}">队列老师 · ${esc(e.request.label||taskCatalog.tasks.find(t=>t.id===e.request.task)?.name)} · 完成后取最新PT</option>`).join('');
      setOptions(role+'-teacher',`<option value="">选择${role==='walk'?'行走':'起身'}老师 PT</option>`+options+future);
    }
    teacherStamp=stamp;
  }
  const resuming=joint&&!!chosen('resume').source_job;
  $('joint-training-teachers').hidden=!joint||resuming;
  const legacySelected=['walk','stand'].some(role=>records.find(c=>c.job.id===chosen(role+'-teacher').source_job)?.job.compatibility_label);
  $('joint-training-note').textContent=resuming?'续训沿用原来的两位老师。':[(legacySelected?'使用既有 V2 老师原权重；本次联合训练继续启用官方摩擦随机化。':''),'可选择前面的队列老师，联合任务用“添加到队列”，老师完成后自动取最新PT。两位老师需与本次动作系数、头腿滤波一致；普通老师可用于齿隙学生，地形可不同。'].filter(Boolean).join(' ');
  const running=state.jobs.find(j=>j.op==='train'&&j.request.task===task&&active(j));
  const job=running||(current()?.request?.task===task?current():null),receipt=job?.effective_config?.joint||job?.validation?.joint;
  $('joint-training-runtime').hidden=!joint||!receipt;
  if(receipt)$('joint-training-runtime').textContent=`${receipt.mode==='resume'?'联合续训':'从行走老师热启动'} · 双教师 SHA256：${receipt.teachers.walk.sha256.slice(0,12)} / ${receipt.teachers.stand.sha256.slice(0,12)}`;
};
for(const id of ['walk-teacher','stand-teacher'])$(id).onchange=()=>{window.workflowConfigChanged?.();window.workflowRender?.();window.renderJointTraining();};
window.renderJointTraining();
