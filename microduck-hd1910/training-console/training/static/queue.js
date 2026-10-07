'use strict';
let queueSending=false,queueAddRequest=null,queueListStamp='',queueLiveJob=null;
const queueWords={waiting:'等待 / Waiting',starting:'启动中 / Starting',running:'训练中 / Running',stopping:'停止中',completed:'完成 / Done',failed:'失败 / Failed',stopped:'已停止 / Stopped',cancelled:'已取消'};
function queueName(entry){return entry.request.label||taskCatalog.tasks.find(t=>t.id===entry.request.task)?.name||entry.request.task;}
function queueTeacherText(entry){
 return ['walk','stand'].flatMap(role=>{
  const p=entry.request[role+'_teacher'];if(!p)return [];
  const prior=state.training_queue.entries.find(e=>e.id===p.queue_entry);
  return [(role==='walk'?'行走老师：':'起身老师：')+(prior?'队列 · '+queueName(prior):(p.checkpoint?.split('/').at(-1)||'原模型'))];
 }).join(' · ');
}
window.renderTrainingQueue=()=>{
 const q=state?.training_queue;if(!q)return;
 const entries=q.entries||[],live=entries.find(e=>['starting','running','stopping'].includes(e.status));
 if(live?.job_id&&live.job_id!==queueLiveJob){
  if(!selected||selected===queueLiveJob){selected=live.job_id;configView=false;}
  queueLiveJob=live.job_id;
 }
 const running=state.jobs.find(j=>j.op==='train'&&active(j));
 const next=entries.find(e=>e.status==='waiting'),plan=running?.request||next?.request;
 const info=taskCatalog.tasks.find(t=>t.id===(plan?.task||$('task').value));
 $('selected-action').textContent=(running?'当前训练 · ':next?'待训练 · ':'待加入 · ')+(plan?.label||info?.name||'选择动作');
 const effective=running?.effective_config;
 const envs=effective?.num_envs??plan?.num_envs??Number($('num-envs').value),rounds=effective?.iterations??plan?.iterations??Number($('iterations').value);
 const servoP=effective?.training_firmware_p??plan?.training_firmware_p??currentTrainingFirmwareP();
 $('training-summary').textContent=`P ${servoP} · ${envs.toLocaleString()} 环境 · ${rounds.toLocaleString()} 轮 · 每1000轮保存`;
 const waiting=entries.filter(e=>e.status==='waiting').length,done=entries.filter(e=>e.status==='completed').length,failed=entries.filter(e=>['failed','stopped'].includes(e.status)).length;
 $('queue-summary').textContent=`${q.enabled?'自动执行中':running?.status==='stopping'?'正在停止':running?'后续未启动':'未执行'} · 等待 ${waiting} · 完成 ${done}${failed?' · 异常 '+failed:''}`;
 $('queue-message').textContent=(q.message||'选择参数 → 加入队列 → 开始训练。').split('\n')[0].replaceAll('开始队列','开始训练');
 $('queue-failure-policy').value=q.failure_policy;$('queue-failure-policy').disabled=!online||queueSending;
 $('train-start').disabled=!online||!token||queueSending||q.enabled||!!window.workflowBusy||(!waiting&&!live)||running?.status==='stopping';
 const environmentBusy=state.jobs.find(j=>['setup','probe'].includes(j.op)&&active(j));
 $('train-start').textContent=q.enabled?(running?'训练运行中':environmentBusy?'等待环境就绪':waiting?'队列已启动':'正在收尾'):'开始训练 ▶';
 $('train-stop').disabled=!online||!token||queueSending||(!q.enabled&&!running)||(!q.enabled&&running?.status==='stopping');
 $('train-stop').textContent=running?.status==='stopping'?'正在停止…':'停止训练';
 $('queue-clear').disabled=!online||queueSending||!entries.some(e=>['completed','failed','stopped','cancelled'].includes(e.status));
 $('queue-add').disabled=!online||!token||queueSending||!!window.workflowBusy;$('queue-add').textContent=queueSending?'正在处理…':'＋ 加入队列';
 const key=JSON.stringify([online,queueSending,entries]);if(key===queueListStamp)return;queueListStamp=key;
 $('queue-list').innerHTML=entries.length?entries.map((e,i)=>{
  const p=e.request,t=taskCatalog.tasks.find(t=>t.id===p.task),progress=e.progress,f=p.action_filter;
  const metadata=`${p.num_envs.toLocaleString()} 环境 · ${p.iterations.toLocaleString()} 轮 · ${t?.terrain==='Rough'?'粗糙':'平地'} · ${t?.backlash?'齿隙 ±1°':'无齿隙'} · 动作 ${p.training_action_scale} · ${f?.enabled?'滤波 '+f.head_alpha+'/'+f.legs_alpha:'滤波关闭'}`;
  const off=!online||queueSending,mutable=e.status==='waiting';
  return `<article class="queue-row ${e.status}"><b class="queue-index">${i+1}</b><div class="queue-info"><strong>${esc(queueName(e))}</strong><small>${esc(metadata)}</small>${queueTeacherText(e)?`<small>${esc(queueTeacherText(e))}</small>`:''}${e.status==='failed'||e.status==='stopped'?`<p class="queue-error">${esc((e.message||'').split('\n')[0])}</p>`:''}</div><div class="queue-state"><strong>${esc(queueWords[e.status]||e.status)}</strong><small>${progress?progress.done.toLocaleString()+' / '+progress.total.toLocaleString()+' 轮 · '+Math.floor(progress.percent)+'%':'机器人/标定快照 '+esc(e.recipe_sha256?.slice(0,8))}</small></div><div class="queue-row-controls">${e.job_id?`<button type="button" data-queue-view="${esc(e.job_id)}" class="text-button">查看训练</button>`:''}${mutable?`<button type="button" data-queue-action="move" data-entry="${e.id}" data-queue-direction="-1" ${off||i===0||entries[i-1].status!=='waiting'?'disabled':''} aria-label="上移任务">↑</button><button type="button" data-queue-action="move" data-entry="${e.id}" data-queue-direction="1" ${off||i===entries.length-1||entries[i+1].status!=='waiting'?'disabled':''} aria-label="下移任务">↓</button>`:''}${['failed','stopped'].includes(e.status)?`<button type="button" data-queue-action="retry" data-entry="${e.id}" ${off?'disabled':''}>重新训练</button>`:''}${!['starting','running','stopping'].includes(e.status)?`<button type="button" class="text-button danger" data-queue-action="remove" data-entry="${e.id}" ${off?'disabled':''}>移除</button>`:''}</div></article>`;
 }).join(''):'<p class="hint queue-empty">在“本次训练参数”中选择参数，点击“加入队列”，再点击“开始训练”。单个任务也使用此流程。</p>';
};
async function queueOperation(value){
 if(queueSending)return;queueSending=true;window.renderTrainingQueue();
 try{await post('/api/queue/control',value);await loadState();}
 catch(e){tell(e.message);}finally{queueSending=false;window.renderTrainingQueue();}
}
$('queue-add').onclick=async()=>{
 if(queueSending||!validateTrainForm())return;
 if(document.querySelector('#robot-data input:invalid,#all-config input:invalid')){tell('请修正尚未完成的参数输入。');return;}
 queueSending=true;window.renderTrainingQueue();
 try{
  while(studioBusy)await new Promise(resolve=>setTimeout(resolve,100));
  if(!(await saveStudio()))throw Error('参数未同步，请检查页面输入。');
  const parameters=readParameters(true);
  queueAddRequest=queueAddRequest||crypto.randomUUID();
  await post('/api/queue/add',{...parameters,execution_profile:executionProfileForTask(),client_id:queueAddRequest});
  queueAddRequest=null;await loadState();tell('已加入队列，按添加时参数训练。');
 }catch(e){tell(e.message);if(e.status)queueAddRequest=null;}
 finally{queueSending=false;window.renderTrainingQueue();}
};
$('train-form').onsubmit=e=>{e.preventDefault();tell('请先加入队列，再点击开始训练。');};
$('train-start').onclick=()=>queueOperation({action:'start'});
$('train-stop').onclick=async()=>{
 if(queueSending)return;
 // Static-only updates can keep an older desktop backend and its GPU owner alive.
 if(state.training_queue.stop_supported)return queueOperation({action:'stop'});
 queueSending=true;window.renderTrainingQueue();
 try{
  await post('/api/queue/control',{action:'pause'});await loadState();
  for(const job of state.jobs.filter(j=>j.op==='train'&&active(j)&&j.status!=='stopping'))await post('/api/stop',{job_id:job.id});
  await loadState();
 }catch(e){tell(e.message);}finally{queueSending=false;window.renderTrainingQueue();}
};
$('queue-clear').onclick=()=>queueOperation({action:'clear'});
$('queue-failure-policy').onchange=()=>queueOperation({action:'policy',failure_policy:$('queue-failure-policy').value});
$('queue-list').onclick=e=>{
 const view=e.target.closest('[data-queue-view]');if(view){selected=view.dataset.queueView;configView=false;loadState();return;}
 const b=e.target.closest('[data-queue-action]');if(b&&!b.disabled)queueOperation({action:b.dataset.queueAction,entry_id:b.dataset.entry,direction:Number(b.dataset.queueDirection)});
};
window.renderTrainingQueue();
for(const event of ['input','change'])$('train-form').addEventListener(event,()=>window.renderTrainingQueue());
