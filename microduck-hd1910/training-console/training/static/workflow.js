
let previousTask=taskCatalog.default_task,catalogStamp='';
const taskVariantDrafts={};
let taskVariantsStamp='';
function taskEngine(id=$('task').value){return taskCatalog.tasks.find(t=>t.id===id)?.engine||'official_0151';}
function selectedEnginePin(){return studioData?.pins[taskEngine()];}
function executionProfileForTask(){
 const target=profile(),pin=selectedEnginePin();if(!pin)return target;
 const marker='microduck-training-studio/engines/',repo=target.repo.replace(/\/+$/,'');
 for(const p of Object.values(studioData.pins)){
  const tail=marker+p.repo.split(marker)[1];
  if(repo===p.repo||repo.includes(marker)){target.repo=repo.includes(marker)?repo.split(marker)[0]+marker+pin.repo.split(marker)[1]:pin.repo;break;}
 }
 return target;
}
function profileForTask(){return {...executionProfileForTask(),task:$('task').value};}
function selectTaskEngine(force=true){const pin=selectedEnginePin();if(pin)$('repo').value=force?pin.repo:executionProfileForTask().repo;}
function actionProfile(task=$('task').value){
 const role=taskCatalog.tasks.find(t=>t.id===task)?.role;
 return taskCatalog.profiles.find(p=>p.role===role);
}
function ensureTaskVisible(task){
 const info=taskCatalog.tasks.find(t=>t.id===task),p=actionProfile(task);
 if(!p||!info?.enabled)return false;
 taskVariantDrafts[p.role]=task;renderTaskCatalog(task);return true;
}
function renderTaskCatalog(selectedTask){
 let value=selectedTask||$('task').value||previousTask||taskCatalog.default_task;
 if(!taskCatalog.tasks.find(t=>t.id===value)?.enabled)value=taskCatalog.default_task;
 const info=taskCatalog.tasks.find(t=>t.id===value),p=actionProfile(value);
 if(p&&info?.enabled)taskVariantDrafts[p.role]=value;
 const stamp=JSON.stringify([value,taskVariantDrafts]);
 if(catalogStamp===stamp){renderTaskVariants();renderTaskProgress();return;}
 catalogStamp=stamp;
 const groups=[...new Set(taskCatalog.profiles.map(p=>p.group))];
 $('task').innerHTML=groups.map(group=>`<optgroup label="${esc(group)}">${taskCatalog.profiles.filter(p=>p.group===group).map(p=>`<option value="${esc(taskVariantDrafts[p.role]||p.default_task)}">${esc(p.name)}</option>`).join('')}</optgroup>`).join('');
 $('task').value=info?.enabled?value:taskCatalog.default_task;
 renderTaskVariants();renderTaskProgress();
}
function renderTaskVariants(){
 const task=$('task').value,p=actionProfile(task),info=taskCatalog.tasks.find(t=>t.id===task);if(!p||!info)return;
 const resume=!!chosen('resume').source_job,stamp=JSON.stringify([task,resume]);
 if(taskVariantsStamp===stamp)return;
 taskVariantsStamp=stamp;
 const all=p.variants.map(id=>taskCatalog.tasks.find(t=>t.id===id));
 const terrains=[...new Set(all.map(t=>t.terrain))];
 $('task-terrain').innerHTML=terrains.map(t=>`<option value="${t}">${t==='Rough'?'粗糙地形 / Rough':'平地 / Flat'}</option>`).join('');$('task-terrain').value=info.terrain;
 const plays=[...new Set(all.filter(t=>t.terrain===info.terrain).map(t=>t.backlash))];
 $('task-backlash').innerHTML=plays.map(v=>`<option value="${v?'on':'off'}">${v?'±1° · 总间隙2° / Backlash':'不模拟齿隙 / No backlash'}</option>`).join('');$('task-backlash').value=info.backlash?'on':'off';
 $('task-terrain').disabled=resume||terrains.length===1;$('task-backlash').disabled=resume||plays.length===1;
 $('task-physics-note').textContent=info.backlash?'14个关节 · 电机角＋齿隙角作为编码器反馈 · 训练、仿真和导出一致':info.role==='roulade'?'官方前滚翻当前仅有平地普通版本。':info.hardware==='rollers'?'滑轮模型：需安装滑轮。官方成品运行动作系数0.8；新训练按页面动作系数执行。':'沿用所选官方动作配方；训练、仿真和导出记录实际配置。';
}
async function changeTaskVariant(){
 if(window.workflowBusy){renderTaskVariants();return;}
 const p=actionProfile(),next=p?.variants.find(id=>{const t=taskCatalog.tasks.find(t=>t.id===id);return t.terrain===$('task-terrain').value&&t.backlash===($('task-backlash').value==='on');});
 if(!next||next===$('task').value)return;
 if((studioDirty||savePromise)&&!(await saveStudio())){renderTaskVariants();return;}
 ensureTaskVisible(next);changeTask();
}
$('task-terrain').onchange=changeTaskVariant;$('task-backlash').onchange=changeTaskVariant;
$('resume').addEventListener('change',renderTaskVariants);
function renderTaskProgress(){
 const task=$('task').value,t=taskCatalog.tasks.find(t=>t.id===task);if(!t)return;
 $('task-description').textContent=t.description;
 const n=Number($('num-envs').value),rounds=Number($('iterations').value),valid=Number.isInteger(n)&&n>=1&&n<=8192;
 $('task-budget').textContent=valid?`4096 基准：源码上限 ${t.iterations.toLocaleString()} 轮 → ${n} 环境默认 ${sampleAlignment.budget(t.iterations,n).toLocaleString()} 实际轮。可修改，不是必须训满。`:'请填写有效并行环境数。';
 $('sample-alignment-note').textContent=valid?`课程按累计采样量对齐 4096 · 本次 ${rounds.toLocaleString()} 实际轮 ≈ ${(rounds*n/4096).toLocaleString('zh-CN',{maximumFractionDigits:2})} 基准轮 · 保存间隔为1000实际轮`:'课程与预算随并行环境数自动换算。';
}
let budgetSamples=Number($('iterations').value)*Number($('num-envs').value);
window.rememberTrainingBudget=()=>{const n=Number($('num-envs').value),r=Number($('iterations').value);if(n>0&&r>0)budgetSamples=n*r;};
window.alignTrainingBudget=()=>{
 const n=Number($('num-envs').value);if(!Number.isInteger(n)||n<1||n>8192)return;
 $('iterations').value=Math.ceil(budgetSamples/n);
};
function changeTask(){
 const task=$('task').value,t=taskCatalog.tasks.find(t=>t.id===task);if(!t)return;
 previousTask=task;renderTaskVariants();selectTaskEngine();$('resume').value='';$('iterations').value=sampleAlignment.budget(t.iterations,Number($('num-envs').value)||4096);window.rememberTrainingBudget();$('run-label').value=t.name;
 if(studioDraft){configOverridesText=JSON.stringify(studioDraft.task_overrides?.[task]||(task==='Mjlab-Velocity-Flat-MicroDuck'?studioDraft.overrides:[])||[],null,2);renderConfigTable();}
 // Different action families can have different PPO/network defaults.
 for(const id of ['learning-rate','seed','gamma','entropy','clip','activation','actor-dims','critic-dims'])$(id).value='';
 $('training-pushes').value='default';loadTaskReference(task);renderTaskConfig(true);renderTaskProgress();render();
}
renderTaskCatalog();
'use strict';
// Only a deliberate button press starts this sequence. A refresh never queues training.
let launchFlow={busy:false,cancelled:false,job:null,message:''};
window.workflowBusy=false;
function openSection(id){
  const target=$(id);if(!target)return;
  if(target.closest('.expert-only'))setExpertSettings(true);
  for(let node=target;node;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;
  target.scrollIntoView({behavior:'smooth',block:'start'});
}
window.openSection=openSection;
document.addEventListener('click',e=>{
  const a=e.target.closest('a[href^="#"]');
  if(a&&a.hash.length>1&&$(a.hash.slice(1))){e.preventDefault();openSection(a.hash.slice(1));}
});
const waitTick=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function canonical(value){
  if(value&&typeof value==='object'&&!Array.isArray(value))return Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])]));
  return Array.isArray(value)?value.map(canonical):value;
}
function matchingPreflight(){
  if(!studioData?.frozen||studioDirty)return false;
  try{const value=readParameters();delete value.label;return JSON.stringify(canonical(value))===JSON.stringify(canonical(studioData.frozen.start_parameters));}catch{return false;}
}
function environmentMatches(){
  return !!(online&&state?.environment?.ready&&JSON.stringify(profile())===JSON.stringify(state.profile)
    &&state.environment.revision===selectedEnginePin()?.revision);
}
function setFlowMessage(message){launchFlow.message=message;window.workflowRender();}
function assertContinue(){
  if(launchFlow.cancelled)throw Error('已取消启动；不会继续启动训练。');
  if(!online)throw Error('后台连接中断，已停止后续启动步骤。连接恢复后请重新点击开始。');
}
async function waitForJob(id){
  launchFlow.job=id;
  for(;;){
    assertContinue();await loadState();assertContinue();
    const job=state.jobs.find(j=>j.id===id);
    if(!job)throw Error('找不到当前任务记录，请查看运行日志。');
    if(!active(job)&&job.ended){
      if(job.status!=='completed')throw Error(job.message||'任务未完成，已停止后续步骤。');
      launchFlow.job=null;return job;
    }
    await waitTick(450);
  }
}
async function runStep(op,value,message){
  assertContinue();setFlowMessage(message);
  const result=await post('/api/'+op,value);
  launchFlow.job=result.job_id;selected=result.job_id;configView=false;
  if(launchFlow.cancelled){await post('/api/stop',{job_id:result.job_id});assertContinue();}
  return waitForJob(result.job_id);
}
function validateTrainForm(){
  const form=$('train-form');
  if(!form.checkValidity()){openSection('parameters');form.reportValidity();return false;}
  return true;
}
async function runWorkflow(kind){
  if(kind!=='prepare')return;
  if(launchFlow.busy||!state||!studioData)return;
  if(document.querySelector('#robot-data input:invalid,#all-config input:invalid')){tell('请修正尚未完成的参数输入。');return;}
  launchFlow={busy:true,cancelled:false,job:null,message:'正在确认本次启动设置…'};window.workflowBusy=true;
  $('training-settings').inert=true;$('reference-details').inert=true;
  window.workflowRender();
  try{
    await loadState();assertContinue();
    // Configuration inspection is allowed to finish; it is never repeated as a manual gate.
    for(const job of state.jobs.filter(active)){
      if(job.op==='describe')await waitForJob(job.id);
      else throw Error('已有任务正在运行，请等待完成或停止后再安装环境。');
    }
    while(studioBusy)await waitTick(100);
    if(!(await saveStudio()))throw Error('参数未同步，请检查页面输入。');
    assertContinue();
    await runStep('setup',profileForTask(),'准备冻结源码和依赖，日志持续更新…');
    for(const [id,key] of [['engine-mode','mode'],['distro','distro'],['repo','repo']])$(id).value=state.profile[key];
    setFlowMessage('安装结束。选择参数 → 加入队列 → 开始训练。');
    await studioLoad(true);
  }catch(error){
    setFlowMessage(error.message);tell(error.message);
  }finally{
    launchFlow.busy=false;launchFlow.job=null;window.workflowBusy=false;
    $('training-settings').inert=false;$('reference-details').inert=false;
    render();window.workflowRender();
  }
}

window.runTrainingPreparation=()=>runWorkflow('prepare');
$('environment-setup').onclick=()=>runWorkflow('prepare');
$('workflow-cancel').onclick=async()=>{
  launchFlow.cancelled=true;setFlowMessage('正在取消；不会继续启动训练。');
  if(launchFlow.job)try{await post('/api/stop',{job_id:launchFlow.job});}catch(e){tell(e.message);}
};
// A manual recheck exists only as an optional diagnostic in the lower settings.
$('env-form').onsubmit=async e=>{e.preventDefault();if(!launchFlow.busy)await action('/api/probe',profileForTask());};
$('copy-log').onclick=async()=>{
  const value=displayedLogText(current());
  try{await navigator.clipboard.writeText(value);tell('已复制任务状态、错误和日志。');}
  catch{const area=document.createElement('textarea');area.value=value;document.body.append(area);area.select();const okay=document.execCommand('copy');area.remove();tell(okay?'已复制日志。':'浏览器不允许复制；请使用“导出运行记录”。');}
};
for(const event of ['input','change'])$('train-form').addEventListener(event,()=>{launchFlow.message='';window.workflowRender();});
for(const event of ['input','change'])$('env-form').addEventListener(event,()=>{launchFlow.message='';window.workflowRender();});
window.workflowConfigChanged=()=>{launchFlow.message='';};
window.addEventListener('beforeunload',event=>{if(launchFlow.busy){event.preventDefault();event.returnValue='';}});

window.workflowRender=()=>{
  if(!state||!studioData||!studioDraft)return;
  const jobs=state.jobs,env=environmentMatches(),busy=jobs.find(j=>active(j)&&!['preview','play','onnx','describe'].includes(j.op));
  const task=$('task').value,taskInfo=taskCatalog.tasks.find(t=>t.id===task);
  const live=jobs.find(j=>j.op==='train'&&active(j));
  const frozen=matchingPreflight(),exp=jobs.find(j=>j.op==='export'&&j.status==='completed'&&j.request.studio_recipe_hash===studioData.recipe_hash);
  const pin=selectedEnginePin(),rounds=Number($('iterations').value);
  $('workspace-name').textContent='官方骨架 + HD1910';
  $('workflow-cancel').hidden=!launchFlow.busy;
  const phases=[['训练',jobs.some(j=>j.op==='train'&&j.status==='completed'&&j.request.iterations>0&&j.request.task===task&&j.request.studio_recipe_hash===studioData.recipe_hash)],['验证与导出',!!exp]];
  const currentIndex=phases.findIndex(x=>!x[1]);
  $('workflow-steps').innerHTML=phases.map(([name,done],i)=>`<li class="${done?'done':i===currentIndex?'current':''}"><b>${done?'✓':i+1}</b>${name}</li>`).join('');
  $('workflow-message').textContent=live?'正在训练':launchFlow.busy?'正在安装环境':'选择参数 → 加入队列 → 开始训练';
  renderTaskVariants();renderTaskProgress();if(window.renderJointTraining)window.renderJointTraining();window.renderContactSettings?.();
  const relevant=jobs.find(j=>!['describe'].includes(j.op));
  $('run-alert').hidden=relevant?.status!=='failed';
  if(relevant?.status==='failed'){
    $('run-alert-title').textContent=`${kinds[relevant.op]||'任务'}失败`;
    $('run-alert-message').textContent=relevant.message||'请查看该任务的完整日志。';
    $('run-alert').querySelector('a').onclick=e=>{e.preventDefault();showFullLog(relevant.id);};
  }


};
window.workflowRender();
