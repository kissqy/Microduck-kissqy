'use strict';
const $=id=>document.getElementById(id);
const words={starting:'正在启动',running:'运行中',stopping:'正在停止',completed:'已完成',stopped:'已停止',failed:'失败',interrupted:'上次已中断'};
const kinds={setup:'准备环境',preflight:'配置预检',probe:'环境检查',describe:'读取任务配置',train:'训练',preview:'初始仿真',play:'检查点评估',onnx:'ONNX 验证',export:'模型导出',delete_model:'删除模型',prune_models:'清理低轮数模型'};
const labels={expert_bc:'双教师模仿损失',expert_bc_fallen_frac:'倒地样本占比',expert_bc_anchor_frac:'行走老师样本占比',reward:'平均奖励',episode_length:'平均回合长度',value_loss:'价值损失',policy_loss:'策略损失',fps:'采样速度 / steps/s'};
const numericFields=[['learning_rate','learning-rate'],['seed','seed'],['gamma','gamma'],['entropy','entropy'],['clip','clip']];
let token='',state=null,selected=null,configView=false,online=true,profileLoaded=false;
let fullLog=null;
let viewerStop=null,viewerLaunching=false,watchTraining=false,watchedTrainingId=null;
let frameJob=null,frameDetach=null;
let renderedTasks='',renderedModels='',renderedRuns='',renderedPresets='',renderedSchema='',renderedCompare='';
const rewardDrafts={};
const actionScaleDrafts={};
let firmwarePDraft=3; // Nearest writable HD1910 P to the theoretical 2.69.
const rewardNames={"track_linear_velocity": "平移速度跟踪", "track_angular_velocity": "转向速度跟踪", "upright": "保持直立", "pose": "关节姿态约束", "body_ang_vel": "抑制机身晃动", "angular_momentum": "抑制角动量", "dof_pos_limits": "避免关节越界", "action_rate_l2": "动作连续性", "air_time": "抬脚节奏", "foot_clearance": "脚离地间隙", "foot_swing_height": "摆动脚高度", "foot_slip": "避免打滑", "self_collisions": "避免自碰撞", "head_pose_tracking": "头部跟随", "body_pose_tracking": "身体姿态跟随", "head_pose_bias": "抑制头部长期偏差", "expert_bc": "双教师模仿损失", "stand_height": "站立高度", "head_height": "头部高度", "orientation": "机身朝向", "joint_pos": "关节姿态", "feet_air_time": "足部腾空时间", "termination": "回合终止", "stand_still": "静止站立", "tracking_lin_vel": "线速度跟踪", "tracking_ang_vel": "角速度跟踪", "joint_torques": "关节扭矩", "joint_acc": "关节加速度", "feet_slip": "足部打滑", "roulade_progress": "翻滚进度", "roulade_overspeed": "翻滚超速惩罚", "roulade_head_pivot": "翻滚头部支点", "roulade_landing_composite": "翻滚落地综合表现", "roulade_upright_after_roll": "翻滚后恢复直立", "roulade_height_after_roll": "翻滚后恢复高度", "roulade_landing_sharp": "翻滚精确落地", "roulade_stand_tax": "翻滚中的站立惩罚", "roulade_rise_velocity": "翻滚起身速度", "roulade_sagittal": "翻滚偏离矢状面惩罚", "roulade_lateral_vel": "翻滚侧向速度惩罚", "roulade_flatness": "翻滚平躺惩罚", "joint_torque_rate_l2": "扭矩变化惩罚", "arrival_damping": "达到高度后抑制晃动", "gentle_landing": "落地冲击惩罚", "ball_forward_velocity": "球向前运动", "ball_speed_overshoot": "球速超调惩罚", "support_foot_grounded": "支撑脚着地", "pose_stand_legs": "站立腿部姿态", "pose_stand_neck": "站立颈部姿态", "height_stand": "站立目标高度", "crouch_glide_pose": "下蹲滑行姿态", "crouch_glide_pose_l1": "下蹲滑行姿态偏差", "forward_speed": "前向速度", "crouch_forward_lean": "下蹲前倾", "feet_flat": "脚掌平放偏差", "neck_action_rate_l2": "颈部动作变化惩罚", "joint_torques_l2": "关节扭矩惩罚", "pose_stand_l1": "站姿偏差惩罚", "height_stand_sharp": "精确站立高度", "height_stand_l1": "站立高度偏差", "com_upward_velocity": "重心向上速度", "gentle_rise": "起身冲击惩罚", "upright_linear": "机身直立程度", "upright_sharp": "精确直立姿态", "standing_composite": "站立综合表现", "posture_pose_legs": "目标腿部姿态", "posture_pose_l1": "目标姿态偏差", "posture_height": "目标姿态高度", "posture_height_sharp": "精确姿态高度", "posture_height_l1": "姿态高度偏差", "rise_bootstrap": "起身动作引导", "descent_speed": "下降速度惩罚", "rise_speed": "上升速度惩罚", "gentle_motion": "垂直冲击惩罚", "upright_while_tall": "高位保持直立", "posture_stillness": "姿态静止程度", "posture_composite": "姿态综合表现", "com_height_target": "重心目标高度", "neck_joint_pos_l2": "颈部关节位置惩罚", "action_over_limit": "动作越界惩罚", "hip_roll_neutral": "髋侧倾中立偏差", "wheel_speed": "轮子速度", "braking": "制动表现", "skating_air_time": "轮滑腾空节奏", "glide": "滑行表现", "single_support": "单脚支撑", "gait_symmetry": "步态不对称惩罚", "forward_lean": "机身前倾", "heading_hold": "保持航向", "leg_symmetry": "双腿对称", "grounded": "着地状态", "heading_tracking": "目标航向跟踪", "mouth_ground_proximity": "鸭嘴接近地面", "mouth_perpendicular_to_ground": "鸭嘴垂直地面", "ground_pick_return_pose_legs": "拾取后腿部姿态恢复", "ground_pick_return_pose_neck": "拾取后颈部姿态恢复", "return_upright": "拾取后恢复直立", "neck_vel_descent": "下降阶段颈部速度惩罚", "mouth_payload_force": "鸭嘴负载力", "feet_grounded": "双脚着地", "head_impact_penalty": "头部碰撞惩罚", "upright_progress": "直立恢复进度", "height_progress": "高度恢复进度", "fallen_tax": "倒地状态惩罚", "recovery_success": "成功恢复站立", "spin_rate_track": "旋转速度跟踪", "spin_rate_l1": "旋转速度偏差", "spin_stay_in_place": "保持原地旋转", "spin_wheel_differential": "旋转轮速差", "leg_antisymmetry": "双腿反向对称", "spin_grounded": "旋转时保持着地", "alive": "回合存活", "wheel_glide": "轮子滑行"};
const rewardTitle=name=>`<strong>${esc(rewardNames[name]||"任务奖励")}</strong><small lang="en">${esc(name)}</small>`;
const describeAttempts=new Set();
const taskReferences=new Map(), referenceLoads=new Map();
function taskSchema(task=$('task').value){return state?.environment?.configs?.[task]||taskReferences.get(task);}
async function loadTaskReference(task=$('task').value){
  if(!task||taskReferences.has(task)||referenceLoads.has(task))return;
  const pending=(async()=>{
    try{
      const response=await fetch('/api/task-reference?task='+encodeURIComponent(task));
      if(!response.ok)throw Error('读取随包官方配置失败。');
      taskReferences.set(task,await response.json());
      if($('task').value===task){renderTaskConfig(true);renderCurriculum();if(studioData)renderConfigTable();window.renderContactSettings?.();}
    }catch(error){tell(error.message);}finally{referenceLoads.delete(task);}
  })();
  referenceLoads.set(task,pending);
}
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const active=j=>['starting','running','stopping'].includes(j.status);
const isViewer=j=>['preview','play','onnx'].includes(j.op);
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const fmt=v=>finite(v)?Number(v.toFixed(4)).toLocaleString('zh-CN'):'—';
const stamp=t=>finite(t)?new Date(t*1000).toLocaleString('zh-CN',{hour12:false}):'—';
const runName=j=>j?.request?.label|| (j?((taskCatalog.tasks.find(t=>t.id===(j.resolved_task||j.request?.task))?.name||'训练')+' · '+stamp(j.created)):'尚未选择');
function recoverySelection(pick){
  const job=state?.jobs.find(j=>j.id===(pick.export_job||pick.source_job));
  return !!taskCatalog.tasks.find(t=>t.id===(job?.resolved_task||job?.request?.task)&&t.role==='stand');
}
const seconds=v=>finite(v)?`${Math.floor(v/3600)}h ${Math.floor(v%3600/60)}m ${Math.floor(v%60)}s`:'—';
const metric=j=>j?.metrics?.at(-1)||j?.latest_metric;
function tell(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(tell.timer);tell.timer=setTimeout(()=>$('toast').hidden=true,6500);}
async function post(path,data,options={}){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Training-Token':token},body:JSON.stringify(data),...options});
  const value=await r.json();if(!r.ok){const error=Error(value.error||'请求失败');error.status=r.status;throw error;}return value;
}
function profile(){return {mode:$('engine-mode').value,distro:$('distro').value,repo:$('repo').value};}
function current(){return state?.jobs.find(j=>j.id===selected)||state?.jobs[0]||null;}
function liveLogText(job){
  if(!job)return '尚未选择任务。';
  return [`${kinds[job.op]||job.op} / ${job.id} / ${words[job.status]||job.status}`,job.message||'',
    job.worker_exit_code===undefined?'':`工作进程退出码：${job.worker_exit_code}`,
    ...(job.logs||[])].filter(Boolean).join('\n');
}
function displayedLogText(job){
  if(!fullLog||!job||fullLog.jobId!==job.id)return liveLogText(job);
  if(fullLog.loading)return liveLogText(job)+'\n\n正在读取完整日志…';
  if(fullLog.error)return liveLogText(job)+'\n\n'+fullLog.error;
  return fullLog.text;
}
async function showFullLog(id=current()?.id){
  if(!id){tell('尚未选择任务。');return;}
  selected=id;configView=false;
  const request={jobId:id,loading:true,text:'',error:''};fullLog=request;
  render();window.openSection?.('logs');
  try{
    const r=await fetch('/api/log?job='+encodeURIComponent(id),{signal:AbortSignal.timeout(15000)});
    if(!r.ok){const error=await r.json();throw Error(error.error||'读取完整日志失败。');}
    request.text=await r.text();
  }catch(error){request.error='完整日志读取失败：'+error.message+'。可使用“导出运行记录”保留任务资料。';}
  finally{request.loading=false;if(fullLog===request){render();$('job-log').scrollTop=0;}}
}
function training(){const live=state?.jobs.find(j=>j.op==='train'&&active(j));if(live)return live;const j=current();return j?.op==='train'?j:state?.jobs.find(r=>r.op==='train'&&r.id===j?.request?.source_job)||state?.jobs.find(r=>r.op==='train');}
function viewer(){if(watchTraining)return null;return state?.jobs.find(j=>isViewer(j)&&active(j)&&j.status!=='stopping')||state?.jobs.find(j=>isViewer(j)&&active(j));}
function chosen(id){try{return JSON.parse($(id).value)||{};}catch{return {};}}
function setOptions(id,html){const old=$(id).value;$(id).innerHTML=html;if([...$(id).options].some(o=>o.value===old))$(id).value=old;}
function comparisonIds(){return [];}
function chartRuns(){const base=training();return base?[base,...comparisonIds().map(id=>state.jobs.find(j=>j.id===id)).filter(j=>j&&j.id!==base.id&&j.request.task===base.request.task)]:[];}

function drawChart(id,field){
  // The wrapper owns layout. Canvas backing dimensions must never resize the
  // element observed by ResizeObserver (especially on high-DPI displays).
  const canvas=$(id),box=canvas.parentElement.getBoundingClientRect(),dpr=Math.min(window.devicePixelRatio||1,2),w=box.width,h=box.height;
  if(!w||!h)return;
  const width=Math.round(w*dpr),height=Math.round(h*dpr);
  if(canvas.width!==width)canvas.width=width;
  if(canvas.height!==height)canvas.height=height;
  const ctx=canvas.getContext('2d');if(!ctx)return;
  const theme=getComputedStyle(document.body);
  const colors=['--green','--blue','--warm'].map(name=>theme.getPropertyValue(name).trim());
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
  const runs=chartRuns(),all=runs.flatMap(j=>(j.metrics||[]).filter(p=>finite(p[field])));
  if(id==='training-chart')$('chart-empty').hidden=all.length>0;
  const l=70,r=20,t=17,b=36,cw=w-l-r,ch=h-t-b;if(cw<40||ch<20)return;
  let low=all.length?Math.min(...all.map(p=>p[field])):0,high=all.length?Math.max(...all.map(p=>p[field])):1;
  const pad=Math.max((high-low)*.12,Math.abs(high)*.02,.01);low-=pad;high+=pad;
  const xmin=all.length?Math.min(...all.map(p=>p.iteration)):0,xmax=Math.max(xmin+1,...all.map(p=>p.iteration));
  ctx.font='13px ui-monospace,monospace';ctx.lineWidth=1;
  for(let i=0;i<=4;i++){const y=t+i*ch/4,v=high-(high-low)*i/4;ctx.strokeStyle=theme.getPropertyValue('--line').trim();ctx.beginPath();ctx.moveTo(l,y);ctx.lineTo(w-r,y);ctx.stroke();ctx.fillStyle=theme.getPropertyValue('--muted').trim();ctx.textAlign='right';ctx.fillText(Math.abs(v)>=10000?v.toExponential(1):v.toFixed(high-low<2?2:0),l-9,y+4);}
  ctx.textAlign='left';ctx.fillText(String(xmin),l,h-10);ctx.textAlign='right';ctx.fillText(String(xmax),w-r,h-10);
  runs.forEach((j,index)=>{
    const points=j.metrics||[];
    const line=(smooth,alpha)=>{let started=false,ema=null;ctx.beginPath();ctx.strokeStyle=colors[index];ctx.globalAlpha=alpha;ctx.lineWidth=smooth?2.2:1.6;
      for(const p of points){if(!finite(p[field])){started=false;ema=null;continue;}ema=ema===null?p[field]:.2*p[field]+.8*ema;const value=smooth?ema:p[field];const x=l+(p.iteration-xmin)/(xmax-xmin)*cw,y=t+(high-value)/(high-low)*ch;if(started)ctx.lineTo(x,y);else ctx.moveTo(x,y);started=true;}
      ctx.stroke();ctx.globalAlpha=1;
    };
    line(false,$('chart-smooth').checked?.32:1);if($('chart-smooth').checked)line(true,1);
    const last=points.filter(p=>finite(p[field])).at(-1);if(last){ctx.fillStyle=colors[index];ctx.beginPath();ctx.arc(l+(last.iteration-xmin)/(xmax-xmin)*cw,t+(high-last[field])/(high-low)*ch,2.7,0,Math.PI*2);ctx.fill();}
  });
}
let chartFrame=null;
function draw(){
  if(chartFrame!==null)return;
  chartFrame=requestAnimationFrame(()=>{
    chartFrame=null;
    drawChart('training-chart','reward');drawChart('detail-chart',$('chart-series').value);
  });
}

function modelRecords(){
  return (state?.jobs||[]).flatMap(j=>j.op==='train'?(j.checkpoints||[]).map(c=>({kind:'PT',job:j,iteration:c.iteration,name:c.name||c.path.split('/').at(-1),path:c.path,value:{source_job:j.id,checkpoint:c.path},created:c.modified||j.created,timeLabel:c.modified?'保存于':'运行于'})):
    j.op==='export'&&j.status==='completed'&&j.artifact?[{kind:'ONNX',job:j,iteration:j.request.source_iteration,name:j.artifact.split('/').at(-1),path:j.artifact,value:{export_job:j.id},created:j.ended||j.created,usable:!!j.artifact_sha256}]:[]);
}
function recordLabel(c){return `${c.kind} · ${c.kind==='PT'?runName(c.job):c.job.request.source_label||'模型导出'} · ${Number.isFinite(c.iteration)?c.iteration+1:'—'} 轮${c.job.compatibility_label?' · '+c.job.compatibility_label:''} · ${filterLabel(c.kind==='PT'?(c.job.effective_config?.action_filter??c.job.request.action_filter):c.job.request.policy_parameters?.action_filter)}`;}
function renderModels(){
  const records=modelRecords(),key=$('task').value+JSON.stringify(records.map(c=>[c.kind,c.job.id,c.path,c.created,c.usable,c.job.request.label,c.job.target_compatible,c.job.resume_compatible,c.job.compatibility_label]));
  if(key!==renderedModels){
    const options=records.filter(c=>c.usable!==false&&c.job.target_compatible).map(c=>`<option value="${esc(JSON.stringify(c.value))}">${esc(recordLabel(c))}</option>`).join('');
    setOptions('checkpoint','<option value="">请选择模型存档或 ONNX</option>'+options);
    setOptions('resume','<option value="">新建训练</option>'+records.filter(c=>c.kind==='PT'&&c.job.resume_compatible&&c.job.request.task===$('task').value).map(c=>`<option value="${esc(JSON.stringify(c.value))}">${esc(recordLabel(c))}</option>`).join(''));
    const latest=new Map();for(const c of records){const k=c.kind+':'+c.job.id;if(!latest.has(k)||c.iteration>latest.get(k).iteration)latest.set(k,c);}
    $('model-table').innerHTML=latest.size?[...latest.values()].map(c=>`<tr><td><span class="pill muted">${c.kind}</span><strong>${esc(c.kind==='PT'?runName(c.job):c.job.request.source_label||'模型导出')}</strong><small>${esc(taskCatalog.tasks.find(t=>t.id===(c.job.resolved_task||c.job.request.task))?.name||c.job.request.task||'训练动作')}${c.job.compatibility_label?' · '+esc(c.job.compatibility_label):''}</small></td><td><strong class="result-iterations">${Number.isFinite(c.iteration)?c.iteration+1:'—'}<small>轮</small></strong><button class="text-button danger" type="button" data-delete-model="${esc(JSON.stringify(c.value))}">删除模型</button></td><td>${esc(stamp(c.created))}</td><td><details class="model-provenance"><summary>${esc(c.name)}</summary><p>检查点编号 ${c.iteration??'—'}</p><code>${esc(c.path)}</code><p>${esc(c.job.id)}</p></details></td><td><button class="train-button action-blue" type="button" data-model="${esc(JSON.stringify(c.value))}" ${c.usable===false||!c.job.target_compatible?'disabled':''}>${!c.job.target_compatible?'历史模型':c.usable===false?'需要重新导出':'选入仿真'}</button>${c.kind==='ONNX'?`<button class="train-button action-teal" type="button" data-download-model="${c.job.id}">下载模型包</button>`:''}</td></tr>`).join(''):'<tr><td colspan="5" class="empty">训练保存检查点后，模型会出现在这里。</td></tr>';
    renderedModels=key;
  }
  const picked=JSON.stringify(chosen('checkpoint')),record=records.find(c=>JSON.stringify(c.value)===picked);
  const scale=record?.kind==='PT'?(record.job.effective_config?.training_action_scale??record.job.request.training_action_scale):record?.job.request.policy_parameters?.training_action_scale;
  $('selected-action-scale').textContent=[finite(scale)?`所选模型动作系数 ${scale} · 仿真与导出沿用此值`:'',record?filterLabel(record.kind==='PT'?(record.job.effective_config?.action_filter??record.job.request.action_filter):record.job.request.policy_parameters?.action_filter):'',record?.job.compatibility_label||''].filter(Boolean).join(' · ');
  if(window.renderJointTraining)window.renderJointTraining();
  $('model-count').textContent=records.length?`${records.filter(c=>c.kind==='PT').length} 个检查点 · ${records.filter(c=>c.kind==='ONNX').length} 个 ONNX`:'尚无模型';
}
function jointDiagnostics(run){
  if(!run?.request?.task?.includes('VelStand'))return '';
  const point=metric(run)||{},percent=v=>finite(v)?(v*100).toFixed(1)+'%':'未上报';
  const items=[
    ['行走老师覆盖','Walk anchor · ≤25°',percent(point.expert_bc_anchor_frac)],
    ['起身老师覆盖','Recovery expert · >35°',percent(point.expert_bc_fallen_frac)],
    ['模仿损失','Expert BC loss',finite(point.expert_bc)?fmt(point.expert_bc):'未上报'],
    ['速度跟踪奖励','Velocity tracking',fmt(point.rewards?.track_linear_velocity)],
    ['晃动惩罚','Angular velocity penalty',fmt(point.rewards?.body_ang_vel)],
  ];
  return `<div class="joint-diagnostics">${items.map(([zh,en,v])=>`<div><small>${esc(zh)}</small><strong>${esc(v)}</strong><small lang="en">${esc(en)}</small></div>`).join('')}</div><p class="joint-diagnostic-note">覆盖为姿态门控比例，不是成功率；倒地样本不足时会跳过起身模仿。训练画面包含探索与扰动，总奖励跨课程下降时需同时核对行走保持和倒地恢复。</p>`;
}
function renderComparison(){
  const run=training(),p={...run?.request,...run?.effective_config};
  $('chart-run-label').textContent=runName(run);
  $('chart-legend').innerHTML=jointDiagnostics(run);
  $('run-config-summary').textContent=run?`${p.num_envs??'—'} 环境 · 动作系数 ${fmt(p.training_action_scale??p.resolved?.full?.env?.actions?.joint_pos?.scale)} · ${filterLabel(p.action_filter)} · 学习率 ${p.learning_rate??'官方默认'} · 种子 ${p.seed??'官方默认'} · 策略网络 ${p.actor_dims?.join(' / ')||'官方默认'} · 推扰 ${p.pushes==='off'?'关闭':'官方设置'}`:'等待训练参数';
}
function renderTaskConfig(force=false){
  const task=$('task').value,schema=taskSchema(task),key=JSON.stringify([task,schema]);
  if(!schema)loadTaskReference(task);
  if(!force&&key===renderedSchema)return;renderedSchema=key;
  for(const [name,id] of numericFields)$(id).placeholder=schema&&finite(schema[name])?'默认 '+schema[name]:'官方默认';
  for(const [name,id] of [['actor_dims','actor-dims'],['critic_dims','critic-dims']])$(id).placeholder=schema?.[name]?.join(', ')||'官方默认';
  $('activation').options[0].textContent=schema?'沿用官方 · '+schema.activation:'沿用官方';
  const draft=rewardDrafts[task]||{};
  $('reward-fields').innerHTML=schema?(schema.rewards||[]).map(r=>`<label><span>${rewardTitle(r.name)}<small>${r.editable?'官方默认 '+r.weight:'官方课程调度 · 初始 '+r.weight}</small></span><input type="number" min="-1000" max="1000" step="any" data-reward="${esc(r.name)}" value="${esc(draft[r.name]??'')}" placeholder="${esc(r.weight)}" ${r.editable?'':'disabled'}></label>`).join(''):'';
}
function curriculumPlan(full,alignment){
  if(!full?.env)return null;
  const match=Object.entries(full.env.curriculum||{}).find(([name,t])=>['set_ground_state','random_prone_init','set_roulade_state'].includes(t?.params?.event_name)&&Array.isArray(t.params.param_stages));
  const term=match?.[1];
  if(!term)return null;
  const event=term.params.event_name,steps=full.agent?.num_steps_per_env;
  const base=full.env.events?.[event]?.params||{};
  const stages=term.params.param_stages.filter(s=>finite(s?.step)&&s.params).slice().sort((a,b)=>a.step-b.step);
  let merged={...base};
  const reference=alignment?.stages?.filter(s=>s.term===match[0]&&s.key==='param_stages');
  return {event,steps:finite(steps)&&steps>0?steps:null,episode:full.env.episode_length_s,
    stages:stages.map((s,i)=>({step:s.step,reference_step:reference?.[i]?.reference_step,params:merged={...merged,...s.params}}))};
}
function poseMix(event,p){
  const val=k=>finite(p?.[k])?p[k]:0;
  const pct=n=>(n*100).toFixed(Number.isInteger(Math.round(n*1000)/10)?0:1)+'%';
  if(event==='set_roulade_state'){
    const total=val('standing_prob')+val('midroll_prob');
    return total>0?'站姿起翻 '+pct(val('standing_prob')/total)+' · 翻滚中途姿态 '+pct(val('midroll_prob')/total):'未读到有效比例';
  }
  if(event==='set_ground_state'){
    const pairs=[['face_down_prob','趴地'],['face_up_prob','仰躺/侧倾'],['sitting_prob','坐姿'],['standing_prob','站姿']];
    const total=pairs.reduce((n,[k])=>n+val(k),0);
    return total>0?pairs.map(([k,label])=>label+' '+pct(val(k)/total)).join(' · '):'未读到有效比例';
  }
  return '倒地 '+pct(val('prone_prob'))+' · 半蹲 '+pct(val('crouch_prob'))+' · 正常站立 '+pct(Math.max(0,1-val('prone_prob')-val('crouch_prob')));
}
const curriculumNames={
  action_rate_weight:['动作平滑','Action smoothness','逐步加强动作变化惩罚，减少突变和抖动。'],
  standing_envs:['原地站立比例','Standing commands','增加零速度指令的抽样比例，练习停下保持；不是倒地复位比例。'],
  head_pose_range:['头部姿态范围','Head pose range','逐步扩大相对默认姿态的头部目标范围，同时学习平衡。'],
  body_pose_range:['躯干姿态范围','Body pose range','限定躯干位置和角度目标；只有一个阶段时保持固定。'],
  com_range:['躯干重心扰动','Body CoM randomization','扩大仿真重心偏移范围，适应配重误差。'],
  head_com_range:['头部重心扰动','Head CoM randomization','扩大头部重心偏移范围，适应头部配重误差。'],
  head_pose_bias_weight:['头部姿态约束','Head pose bias weight','逐步调整头部姿态偏置项的奖励权重。']
};
function otherCurricula(full){
  return Object.entries(full?.env?.curriculum||{}).flatMap(([name,term])=>{
    const params=term?.params||{};
    if(['set_ground_state','random_prone_init','set_roulade_state'].includes(params.event_name)&&Array.isArray(params.param_stages))return [];
    const groups=Object.entries(params).filter(([key,value])=>key.endsWith('_stages')&&Array.isArray(value));
    const strict=sampleAlignment.strict(term);
    return groups.map(([key,values])=>({name,key,params,strict,stages:values.filter(s=>s&&finite(s.step)&&s.step>=0).slice().sort((a,b)=>a.step-b.step)})).filter(c=>c.stages.length);
  });
}
function courseValue(course,stage){
  const number=n=>Number(n.toFixed(3)).toString();
  if(finite(stage.weight))return '权重 '+number(stage.weight);
  if(finite(stage.rel_standing_envs))return number(stage.rel_standing_envs*100)+'%';
  if(finite(stage.range)&&['randomize_com','randomize_head_com'].includes(course.params.event_name))return '±'+number(stage.range*1000)+' mm';
  if(Array.isArray(stage.ranges)){
    const head=course.params.command_name==='head_pose'&&stage.ranges.length===4;
    const body=course.params.command_name==='body_pose'&&stage.ranges.length===6;
    const labels=head?['颈俯仰','头俯仰','头转向','头侧倾']:body?['前后 X','左右 Y','上下 Z','侧倾 Roll','俯仰 Pitch','转向 Yaw']:[];
    return stage.ranges.map((range,i)=>{
      if(!Array.isArray(range)||range.length!==2||!range.every(finite))return JSON.stringify(range);
      const position=body&&i<3,mult=position?1000:1,unit=position?' mm':head||body?' rad':'';
      const value=range[0]===-range[1]?'±'+number(range[1]*mult):number(range[0]*mult)+'～'+number(range[1]*mult);
      return (labels[i]?labels[i]+' ':'')+value+unit;
    }).join(' · ');
  }
  return JSON.stringify(Object.fromEntries(Object.entries(stage).filter(([key])=>key!=='step')));
}
function renderOtherCurricula(full,sample,running,hasPose,alignment){
  const courses=otherCurricula(full),container=$('curriculum-other');
  container.hidden=courses.length===0;
  $('curriculum-rows').closest('.curriculum-table-wrap').hidden=!!courses.length&&!hasPose;
  if(!courses.length){container.replaceChildren();return;}
  const steps=full?.agent?.num_steps_per_env,step=finite(sample?.step)?sample.step:null;
  const fresh=!!(running&&online&&step!==null&&Date.now()/1000-(sample.received||sample.captured_at)<5);
  const round=s=>finite(steps)&&steps>0?Number((s/steps).toFixed(2))+' 轮':s+' 步';
  const progress=step===null?'尚未读回运行步数 · 显示初始计划':(fresh?'当前运行进度':'上次读回进度')+' '+round(step);
  if(!hasPose){
    $('curriculum-live').textContent=courses.length+' 项课程配置 · '+progress;
    $('curriculum-note').textContent='按运行步数定位计划阶段，以下参数尚未逐项读回；单阶段项保持固定。';
  }
  container.innerHTML=(hasPose?'<p class="course-progress">其他课程 · '+esc(progress)+'；以下为计划值，非逐项运行读回。</p>':'')+
    '<table class="course-list"><thead><tr><th>课程 / Curriculum</th><th>阶段计划值 / Planned value</th><th>完整阶段 / Schedule</th></tr></thead><tbody>'+courses.map(course=>{
      const info=curriculumNames[course.name]||['任务课程',course.name,'按本次任务配置分阶段调整。'];
      // Reward/standing/CoM use >; official pose-range schedules use >=.
      const index=step===null?-1:course.stages.reduce((last,s,i)=>(course.strict?step>s.step:step>=s.step)||s.step===0?i:last,-1);
      const value=courseValue(course,course.stages[Math.max(index,0)]);
      const status=course.stages.length===1?'固定计划值':index<0?'初始计划':fresh?'当前阶段 · 计划值':'上次阶段 · 计划值';
      return '<tr data-course="'+esc(course.name)+'"><td><strong>'+esc(info[0])+'</strong><small lang="en">'+esc(info[1])+'</small><p>'+esc(info[2])+'</p></td><td><span class="course-status">'+status+'</span><b>'+esc(value)+'</b></td><td><div class="course-stages">'+course.stages.map((s,i)=>
        '<span class="course-stage'+(i===index?' current':'')+'"><strong>'+esc(s.step===0?'初始':round(s.step)+(course.strict?'后':'起'))+'</strong> '+esc(courseValue(course,s))+
        (s.step>0&&alignment?'<small>4096基准 '+esc(round(alignment.stages.find(v=>v.term===course.name&&v.key===course.key&&v.index===i)?.reference_step??s.step))+'</small>':'')+'</span>'
      ).join('')+'</div></td></tr>';
    }).join('')+'</tbody></table>';
}

function renderCurriculum(){
  const currentRun=training(),running=currentRun&&active(currentRun);
  const task=running?currentRun.request.task:$('task').value;
  // Idle pages preview the NEXT run; never display a completed run's old stages
  // as if they were the newly edited parallel-count settings.
  const run=running?currentRun:null;
  const recorded=run?.effective_config?.resolved?.full;
  const base=taskSchema(task)?.inspection?.full;
  const preview=recorded?{full:recorded,alignment:run.effective_config.curriculum_alignment}:
    run&&!run.request.sample_alignment_version?{full:base,alignment:null}:sampleAlignment.preview(base,Number(run?.request.num_envs??$('num-envs').value));
  const {full,alignment}=preview;
  const plan=curriculumPlan(full,alignment),sample=run?.training_curriculum_state;
  const fresh=!!(running&&online&&sample&&Date.now()/1000-(sample.received||sample.captured_at)<5);
  const actual=!!(plan&&sample&&sample.reset_event===plan.event);
  const step=actual?sample.step:null;
  const activeStage=finite(step)&&plan?plan.stages.reduce((last,s,i)=>step>=s.step?i:last,-1):-1;
  const taskName=taskCatalog.tasks.find(t=>t.id===task)?.name||task||'等待训练任务';
  $('curriculum-task').textContent=taskName;
  $('curriculum-source').textContent=(run?.effective_config?'本次训练实际配置':'下次训练计划')+(alignment?' · 已对齐4096采样量':' · 原运行课程');
  $('curriculum-alignment').textContent=alignment?`${alignment.num_envs} 环境 · 轮数倍率 ×${Number(alignment.iteration_factor.toFixed(4))} · 实际课程步数随累计采样量换算；不保证不同并行数的训练结果相同。`:'';
  const live=$('curriculum-live');live.dataset.state='pending';
  if(actual){
    const params=sample.reset_params||{},expected=plan.stages[activeStage]?.params;
    const matches=expected&&Object.keys(params).every(k=>Math.abs((expected[k]??0)-params[k])<1e-6);
    live.dataset.state=fresh?(matches?'verified':'mismatch'):'pending';
    live.textContent=(fresh?'运行读回：':'上次读回（非实时）：')+poseMix(sample.reset_event,params)+
      (fresh?(matches?'。与当前计划阶段一致。':'。与当前计划阶段不同，以运行读回为准。'):'');
  }else live.textContent=!plan?(full?'此任务没有起始姿态分阶段课程，可直接训练。':'课程配置尚未读取，不影响开始训练。'):running?'等待训练进程回传当前生效比例；尚未核实，不按默认值冒充。':'开训后显示实际生效比例。';
  const episode=actual?sample.episode_limit_s:plan?.episode;
  $('curriculum-note').textContent=!plan?'':(finite(episode)?'每回合最长 '+episode+' 秒。':'')+(plan?.event==='set_roulade_state'?'翻滚中途姿态用于练习后半程及落地；比例指开局抽样。':'比例指回合开局，不是画面中的姿态占比。')+(actual&&plan.steps?'课程进度 '+Math.floor(step/plan.steps)+' 本机等效轮'+(finite(sample.reference_iterations)?' / '+fmt(sample.reference_iterations)+' 轮（4096基准）':'')+'。':'');
  $('curriculum-rows').innerHTML=plan?.stages.length?plan.stages.map((s,i)=>{
    const next=plan.stages[i+1];
    const range=plan.steps?Math.ceil(s.step/plan.steps)+(next?'～'+(Math.ceil(next.step/plan.steps)-1):' 以后')+' 轮':s.step+(next?'～'+(next.step-1):' 以后')+' 步';
    const reference=finite(s.reference_step)?Math.ceil(s.reference_step/24)+(next?'～'+(Math.ceil(next.reference_step/24)-1):' 以后')+' 轮':'—';
    const label=i===activeStage?(fresh?(live.dataset.state==='verified'?'当前生效阶段':'当前进度 · 待核对'):'上次读回阶段'):activeStage<0?'计划':i<activeStage?'已过':'后续';
    return `<tr class="${i===activeStage?'current':''}"><td>${esc(range)}</td><td>${esc(reference)}</td><td>${esc(poseMix(plan.event,s.params))}</td><td>${label}</td></tr>`;
  }).join(''):'<tr><td colspan="4">'+(full?'此任务没有上述起始姿态分阶段课程。':'尚未收到该任务的课程配置；无需因此执行环境检查。')+'</td></tr>';
  renderOtherCurricula(full,sample,running,!!plan,alignment);
}
function renderResources(){
  const res=state.resources,stale=!online||!res?.received||Date.now()/1000-res.received>10,gpu=res?.devices?.[0];
  $('gpu-live').textContent='GPU 占用 '+(finite(gpu?.utilization)?fmt(gpu.utilization)+'%':'—');
  $('gpu-used').textContent='显存使用 '+(finite(gpu?.used_mb)&&finite(gpu?.total_mb)?`${(gpu.used_mb/1024).toFixed(1)} / ${(gpu.total_mb/1024).toFixed(1)} GB`:'—');
  $('gpu-temp').textContent='GPU 温度 '+(finite(gpu?.temperature)?fmt(gpu.temperature)+' °C':'—');
  $('gpu-stamp').textContent=res?.received?(stale?'上次采样 · ':'每 3 秒采样 · ')+stamp(res.received):'运行任务时每 3 秒采样';
}
// Use a different loopback site from the dashboard: Chrome can isolate the
// WebGL renderer from the controls even though both servers are local.
function isolatedViewerUrl(url){
  if(!/^http:\/\/127\.0\.0\.1:\d{4,5}$/.test(url||''))return '';
  return url.replace('127.0.0.1',location.hostname==='localhost'?'127.0.0.1':'localhost');
}
function mountViewerFrame(url,id,kind){
  clearTimeout(frameDetach);frameDetach=null;
  let frame=$('viewer-frame');
  const src=isolatedViewerUrl(url)+'/?darkMode&'+kind+'='+encodeURIComponent(id);
  if(frame.hasAttribute('src')&&frame.getAttribute('src')!==src){
    const fresh=frame.cloneNode(false);fresh.removeAttribute('src');
    frame.replaceWith(fresh);frame=fresh;
  }
  frameJob=id;frame.hidden=false;frame.style.visibility='';
  if(frame.getAttribute('src')!==src)frame.setAttribute('src',src);
}
function retireViewerFrame(){
  const frame=$('viewer-frame');
  if(!frame.hasAttribute('src')||frameDetach!==null)return;
  // Keep the live document's viewport dimensions until it is detached. Hiding
  // with display:none first sends a zero-size resize through the WebGL scene.
  frame.style.visibility='hidden';frame.style.pointerEvents='none';
  frameDetach=setTimeout(()=>{
    frameDetach=null;
    if($('viewer-frame')!==frame)return;
    const fresh=frame.cloneNode(false);fresh.removeAttribute('src');
    fresh.hidden=true;fresh.style.visibility='';fresh.style.pointerEvents='';
    frame.replaceWith(fresh);frameJob=null;
  },60);
}
function renderSimulation(){
  if(watchTraining){renderTrainingLive();return;}
  const play=viewer(),latest=play||state.jobs.find(isViewer),frame=$('viewer-frame');
  if(viewerStop&&!state.jobs.some(j=>j.id===viewerStop.id&&active(j)))viewerStop=null;
  const switching=!!(play?.wait_for_viewers&&!play.viewer_url);
  const stopping=play&&(play.status==='stopping'||viewerStop?.id===play.id);
  const url=online&&!stopping&&play?.status==='running'&&/^http:\/\/127\.0\.0\.1:\d{4,5}$/.test(play.viewer_url||'')?play.viewer_url:'';
  const model=play?.viewer_checkpoint||play?.request.checkpoint?.split('/').at(-1)||play?.request.onnx_path?.split('/').at(-1)||'';
  const iteration=play?.viewer_iteration??play?.request.source_iteration??Number(model.match(/^model_(\d+)\.pt$/)?.[1]);
  $('viewer-state').textContent=latest?`${kinds[latest.op]} · ${words[latest.status]} · ${latest.message}`:'尚未启动物理仿真。';
  $('sim-mode').textContent=!online?'后台已断开':play?play.op==='preview'?'初始模型 · 未训练':play.op==='onnx'?'ONNX 成品验证':'检查点策略':'尚未启动';
  $('sim-source').textContent=!online?'画面已断开':play?play.op==='preview'?`${play.request.task} · 零动作输入`:`${play.request.source_label||play.request.task} · ${model}${finite(iteration)?' · 第 '+iteration+' 轮':''} · ${play.request.recovery_evaluation?'翻身检查 · 平地':'推扰'+(play.request.eval_pushes?'开启':'关闭')}`:'尚未加载';
  $('sim-empty-title').textContent=!online?'训练台后台已断开':play?'正在准备物理仿真…':'等待加载仿真';
  $('sim-empty-note').textContent=!online?'请检查独立启动窗口。':play?play.status==='stopping'?'正在结束当前仿真进程。':'等待物理环境和策略加载完成。首次编译 GPU 内核的进度可在日志查看。':'查看初始模型，或选择检查点 / ONNX 进行仿真验证。';
  const retained=frame.hasAttribute('src')&&(!online||state.jobs.some(j=>isViewer(j)&&j.id===frameJob&&active(j)));
  if(!frame.hasAttribute('src'))frame.hidden=true;
  frame.style.pointerEvents=stopping||switching?'none':'';
  $('sim-empty').hidden=!!(url||retained)&&!stopping&&!switching;
  $('sim-empty').classList.toggle('stopping-overlay',!!stopping||switching);
  $('viewer-fullscreen').disabled=!url||!!stopping;
  if(url)mountViewerFrame(url,play.id,'studioJob');
  else if(!retained)retireViewerFrame();
  $('viewer-link').hidden=!url;if(url)$('viewer-link').href=isolatedViewerUrl(url);else $('viewer-link').removeAttribute('href');
  $('eval-pushes').disabled=viewerLaunching;
  if(stopping){
    const slow=viewerStop&&Date.now()-viewerStop.started>15000;
    $('sim-mode').textContent='正在停止';$('sim-empty-title').textContent=viewerStop?.error?'停止请求未确认':slow?'仿真仍在退出':'正在停止仿真…';
    $('sim-empty-note').textContent=viewerStop?.error|| (slow?'停止耗时较长，可查看该仿真的完整日志；尚未确认进程退出。':'正在关闭仿真并释放资源；退出完成后移除画面。');
    $('viewer-state').textContent=$('sim-empty-note').textContent;
  }
  if(switching&&!stopping){$('sim-empty-title').textContent='正在切换模型…';$('sim-empty-note').textContent='旧仿真退出后自动加载所选模型。';}
  renderSimTelemetry();
}
function renderTrainingLive(){
  const job=state.jobs.find(j=>j.id===watchedTrainingId),frame=$('viewer-frame');
  const url=online&&job&&active(job)&&/^http:\/\/127\.0\.0\.1:\d{4,5}$/.test(job.training_view_url||'')?job.training_view_url:'';
  const sample=job?.training_view_state;
  $('sim-mode').textContent='训练现场 · Live';
  $('sim-source').textContent=job?`${runName(job)} · 实际训练环境${sample?' · 鸭子 '+(sample.env_indices?.length>1?(sample.env_indices[0]+1)+'–'+(sample.env_indices.at(-1)+1):sample.env_index+1)+' / '+sample.num_envs+' · 训练步 '+sample.step:''}`:'没有正在运行的训练';
  $('viewer-state').textContent=job?.training_view_error||(url?'画面来自正在训练的环境。默认同时显示最多9只，可在画面中切换编号组。':job&&!active(job)?'该次训练已结束。':'等待训练现场画面…');
  $('sim-empty-title').textContent=job?.training_view_error?'训练画面不可用':job&&!active(job)?'该次训练已结束':'正在准备训练现场…';
  $('sim-empty-note').textContent=job?.training_view_error||'训练现场随训练启动；已启动的旧版任务需要保存检查点后续训，才能接入。';
  $('sim-empty').hidden=!!url;$('sim-empty').classList.remove('stopping-overlay');
  frame.style.pointerEvents='';
  if(url)mountViewerFrame(url,job.id,'trainingJob');
  else retireViewerFrame();
  $('viewer-link').hidden=!url;if(url)$('viewer-link').href=isolatedViewerUrl(url);else $('viewer-link').removeAttribute('href');
  $('viewer-fullscreen').disabled=!url;$('eval-pushes').disabled=true;
  renderSimTelemetry();$('drive-status').textContent='训练现场仅观看；遥控用于独立模型验证。';
}
function simFresh(){const j=viewer();return online&&j?.status==='running'&&j.sim_state&&Date.now()/1000-j.sim_state.received<2;}
function driveReady(){const j=viewer();return viewerStop?.id!==j?.id&&simFresh()&&j?.sim_controls?.movement&&!j.sim_state.paused&&!j.sim_state.error;}
function renderSimTelemetry(){
  const j=viewer(),fresh=simFresh()&&viewerStop?.id!==j?.id,data=fresh?j.sim_state:null,available=!!(fresh&&j.sim_controls),canMove=!!driveReady();
  document.querySelectorAll('[data-direction]').forEach(b=>b.disabled=!canMove);$('sim-zero').disabled=!available;
  $('sim-pause').disabled=!available;$('sim-reset').disabled=!available;$('sim-pause').textContent=data?.paused?'继续仿真':'暂停仿真';
  $('drive-status').textContent=!j?'加载行走策略后启用遥控。':!fresh?'等待仿真实时反馈…':data.error||(!j.sim_controls?.movement?'该任务可暂停与重置，未启用行走遥控。':data.paused?'仿真已暂停。':'按住方向键移动，松开后目标速度归零。');
  const vector=v=>Array.isArray(v)?v.map(x=>finite(x)?x.toFixed(2):'—').join(' / '):'— / — / —';
  $('sim-command').textContent=vector(data?.command);$('sim-actual').textContent=vector(data?.actual);
  $('sim-tilt').textContent=data?`${fmt(data.roll)}° / ${fmt(data.pitch)}°`:'— / —';
  $('sim-outcome').textContent=data?`${fmt(data.upright_seconds)} s / ${fmt(data.terminations)} 次`:'— / —';
  $('sim-performance').hidden=!data;$('sim-performance').textContent=data?`仿真循环 ${fmt(data.loop_fps)} FPS · 物理时间 ${fmt(data.sim_seconds)} s`:'';
  if(!canMove&&held.size)clearMotion();
  renderDriveFeedback();
}
function keyboardReady(){return $('sim-drive').contains(document.activeElement)&&!document.activeElement.closest('input,select,textarea,[contenteditable="true"]');}
function renderDriveFeedback(){
  const ready=!!driveReady(),focused=keyboardReady(),data=simFresh()?viewer().sim_state:null;
  const ranges=driveRanges();
  $('drive-speed-note').textContent=`任务指令范围：前后 ${Math.max(...ranges[0].map(Math.abs)).toFixed(2)} m/s · 左右 ${Math.max(...ranges[1].map(Math.abs)).toFixed(2)} m/s · 转向 ${Math.max(...ranges[2].map(Math.abs)).toFixed(2)} rad/s`;
  const feedback=$('drive-feedback'),requested=movement(),moving=requested.some(x=>x!==0),command=data?.command;
  const values=requested.map(x=>x.toFixed(2)).join(' / ');
  const received=ready&&moving&&Array.isArray(command)&&command.every((v,i)=>finite(v)&&Math.abs(v-requested[i])<.001);
  const info=data?.control,ownAck=info?.client===clientId&&info.sequence>=moveSequence;
  let message=!ready?'等待可用的仿真控制连接。':moving?received?'仿真已收到；看实际速度和动作判断策略表现。':ownAck&&info.expired?'上一条指令已过期，正在发送最新按键状态。':controlError||'等待仿真收到指令；未收到不能归因于训练轮数。':Array.isArray(command)&&command.some(x=>Math.abs(x)>.001)?'正在等待仿真目标归零…':'未按住方向 · 目标归零，策略仍在运行。';
  if(controlError&&!moving)message=controlError;
  feedback.textContent=`按键请求 ${values} · ${message}`;
  feedback.dataset.state=received?'received':moving||controlError?'waiting':'idle';
}
function render(){
  if(!state)return;
  const env=state.environment,jobs=state.jobs,job=current(),run=training(),liveTrain=jobs.find(j=>j.op==='train'&&active(j)),play=viewer(),probe=jobs.find(j=>j.op==='probe'&&active(j)),setup=jobs.find(j=>j.op==='setup'&&active(j));
  if(!profileLoaded){for(const [id,key] of [['engine-mode','mode'],['distro','distro'],['repo','repo']])$(id).value=state.profile[key];profileLoaded=true;}
  $('distro').disabled=$('engine-mode').value!=='wsl';
  const changed=JSON.stringify(profile())!==JSON.stringify(state.profile),ready=online&&env.ready&&!changed&&!probe;
  $('env-badge').textContent=changed?'执行目录已选择':env.ready?(env.reused||env.evidence_job?'环境记录已复用':'CUDA 已验证'):setup?'正在准备环境':env.status==='checking'?'正在检查环境':'直接启动';$('env-badge').className='pill '+(ready?'':'muted');$('env-message').textContent=env.message;
  $('gpu-name').textContent=env.gpu?.gpus?.map(g=>g.name).join(' / ')||'—';$('gpu-memory').textContent=env.gpu?.gpus?.map(g=>g.memory_gb+' GB').join(' / ')||'—';$('engine-revision').textContent=env.revision?.slice(0,12)||'—';
  $('probe').disabled=!online||jobs.some(active)||state.computer_verified===true;$('probe').textContent=state.computer_verified?'训练机器已检查 · 所有项目共用':probe?'正在检查训练机器…':'首次检查训练机器';
  renderTaskCatalog();
  renderTaskConfig();renderModels();renderComparison();renderResources();
  const picked=chosen('checkpoint');$('delete-model').disabled=!online||(!picked.checkpoint&&!picked.export_job)||jobs.some(j=>j.op==='delete_model'&&active(j));$('play-start').disabled=!online||(!picked.checkpoint&&!picked.export_job)||viewerLaunching||!!play?.wait_for_viewers&&!play?.viewer_url;$('play-start').textContent=viewerLaunching?'正在提交…':play?'切换到所选模型':picked.export_job?'验证 ONNX 模型':'查看所选策略';
  $('recovery-eval-start').disabled=$('play-start').disabled||!recoverySelection(picked);
  $('recovery-eval-note').hidden=!recoverySelection(picked);
  $('export-model').disabled=!online||!picked.checkpoint||jobs.some(j=>j.op==='export'&&active(j));$('play-stop').disabled=!play||!online;$('preview-start').disabled=!online||viewerLaunching||!!play?.wait_for_viewers&&!play?.viewer_url;
  $('play-stop').disabled=!play||!online||!!viewerStop?.sending||(play?.status==='stopping'&&!viewerStop?.error);
  $('play-stop').textContent=viewerStop?.error?'重试停止仿真':viewerStop||play?.status==='stopping'?'正在停止…':'停止仿真';
  $('training-live').disabled=!online||!liveTrain;
  $('training-live').textContent=watchTraining?'正在观看训练':'观看当前训练';
  if(watchTraining){$('play-stop').disabled=false;$('play-stop').textContent='关闭观看';}
  $('task-config-refresh').disabled=!online||jobs.some(j=>j.op==='describe'&&active(j));

  renderActionFilter();
  const resuming=!!chosen('resume').checkpoint;for(const id of ['actor-dims','critic-dims','activation'])$(id).disabled=resuming;
  $('run-state').textContent=run?words[run.status]:'尚未开始';$('run-name').textContent=run?runName(run)+' · '+run.request.task:'等待选择训练任务';
  const m=metric(run),p=run?.progress;
  $('run-iteration').textContent=p?`${p.done} / ${p.total}`:'— / —';$('raw-iteration').textContent=m?`实际日志编号 ${m.iteration} / ${m.total}（从 0 开始）`:'尚无迭代记录';
  if(run?.request.sample_alignment_version){
    const ref=run.training_curriculum_state?.reference_iterations??run.sample_clock?.reference_iterations;
    if(finite(ref))$('raw-iteration').textContent+=' · 累计折合4096：'+fmt(ref)+'轮';
    else if(p)$('raw-iteration').textContent+=' · 本次折合4096：'+fmt(p.done*run.request.num_envs/4096)+'轮';
  }
  $('run-reward').textContent=fmt(m?.reward);$('run-fps').innerHTML=fmt(m?.fps)+' <em>steps/s</em>';
  $('run-time').textContent='运行时间 '+seconds(p?.elapsed_seconds);$('run-progress').value=p?.percent||0;
  $('progress-text').textContent=run?`${words[run.status]} · ${p?Math.floor(p.percent)+'%':'等待迭代记录'}${active(run)&&p?.done===p?.total&&p?.total?' · 正在收尾':''}`:'等待训练开始';
  $('run-eta').textContent='预计剩余 '+seconds(p?.eta_seconds)+(finite(p?.eta_seconds)&&active(run)?' · 按最近迭代估算':'');
  const terms=Object.entries(m?.rewards||{});$('reward-terms').innerHTML=terms.length?terms.map(([name,v])=>`<div class="reward-term"><span>${rewardTitle(name)}</span><b>${fmt(v)}</b></div>`).join(''):'<span class="hint">当前日志尚无分项奖励。</span>';
  renderSimulation();renderPanel('训练课程',renderCurriculum);
  const history=jobs.filter(j=>j.op==='train'&&!j.history_retired).slice(0,10);
  const listKey=history.map(j=>j.id+':'+j.status).join('|')+'|'+selected;if(listKey!==renderedRuns){$('run-list').innerHTML=history.length?history.map(j=>`<button type="button" data-job="${j.id}" class="${j.id===job?.id?'selected':''}"><span>${kinds[j.op]} · ${words[j.status]||j.status}</span><span>↗</span><small>${esc(j.op==='train'?runName(j):j.request?.source_label||j.request?.task||j.profile.repo)}</small><small>${stamp(j.created)}</small></button>`).join(''):'<p class="empty">尚无运行记录。</p>';renderedRuns=listKey;}
  $('job-message').textContent=job?.message||'等待任务。';$('show-config').textContent=configView?'查看日志':'查看配置';
  const full=!!job&&fullLog?.jobId===job.id;
  $('log-title').textContent=configView?'本次配置':full?'完整日志 · 手动刷新':'实时日志 · 最近160行';
  $('show-full-log').disabled=!job||(full&&fullLog.loading);$('show-full-log').textContent=full?'刷新完整日志':'查看完整日志';
  $('show-live-log').hidden=!full;
  const out=$('job-log'),atBottom=out.scrollHeight-out.scrollTop-out.clientHeight<40;
  out.textContent=configView?JSON.stringify({request:job?.request,effective_config:job?.effective_config,revision:job?.revision,argv:job?.argv,cwd:job?.cwd,artifact_sha256:job?.artifact_sha256},null,2):displayedLogText(job);if(atBottom&&!configView&&!full)out.scrollTop=out.scrollHeight;draw();window.studioRender?.();window.workflowRender?.();window.renderTrainingQueue?.();
}
// Display failures must never change connectivity or stop state polling.
const renderErrors=new Map();
function renderPanel(name,callback){
  try{callback();renderErrors.delete(name);}
  catch(error){renderErrors.set(name,error?.message||String(error));}
  const notice=$('render-error');
  notice.hidden=renderErrors.size===0;
  notice.textContent=[...renderErrors].map(([name,message])=>name+'显示异常：'+message).join('；');
}
let loading=null;
async function loadState(){
  if(loading)return loading;
  loading=(async()=>{
    try{
      try{
        const query=new URLSearchParams();if(selected)query.set('selected',selected);
        if(comparisonIds().length)query.set('compare',comparisonIds().join(','));
        const r=await fetch('/api/state?'+query,{signal:AbortSignal.timeout(4000)});
        if(!r.ok)throw Error('后台无法读取');
        state=await r.json();online=true;$('connection-error').hidden=true;
      }catch{
        online=false;$('connection-error').hidden=false;clearMotion();
      }
      renderPanel('页面',render);
    }finally{loading=null;}
  })();
  return loading;
}
async function refresh(){try{await loadState();}finally{setTimeout(refresh,1000);}}
async function action(path,value,selectJob=true){try{const result=await post(path,value);if(result.job_id&&selectJob){selected=result.job_id;configView=false;}await loadState();return result;}catch(e){tell(e.message);return null;}}
async function startViewer(path,value,automatic=false){
  if(viewerLaunching)return null;
  viewerLaunching=true;watchTraining=false;
  if(!automatic)$('follow-latest').checked=false;
  clearMotion(false);controlActions=[];
  render();
  try{return await action(path,value,false);}
  finally{viewerLaunching=false;render();}
}
async function stopViewer(){
  if(watchTraining){watchTraining=false;render();return;}
  const j=viewer();if(!j||viewerStop?.sending)return;
  const request={id:j.id,sending:true,error:'',started:Date.now()};viewerStop=request;
  // Dispatch before any layout or WebGL iframe teardown can occupy this tab.
  const pending=post('/api/stop',{job_id:j.id},{signal:AbortSignal.timeout(4000)});
  $('follow-latest').checked=false;
  clearMotion(false);controlActions=[];
  $('play-stop').disabled=true;$('play-stop').textContent='正在停止…';
  renderSimulation();
  try{await pending;}
  catch(e){if(viewerStop===request){request.error='停止请求未确认：'+e.message+'。可点击“重试停止仿真”，任务尚未标为已停止。';tell(request.error);}}
  finally{request.sending=false;render();await loadState();}
}
function filterLabel(value){
  return value?.enabled?`头颈滤波 ${value.head_alpha} / 腿部 ${value.legs_alpha}`:'头腿滤波直通 1.0';
}
function currentTrainingScale(){
  const source=state?.jobs.find(j=>j.id===chosen('resume').source_job);
  if(source)return source.effective_config?.training_action_scale??source.request.training_action_scale??1.0;
  const info=taskCatalog.tasks.find(t=>t.id===$('task').value);
  if(info?.role==='sitstand')return 1.0; // daemon 0.15.1 pins the sit/rise scale.
  if(finite(actionScaleDrafts[$('task').value]))return actionScaleDrafts[$('task').value];
  return info?.training_action_scale??(['walk','stand','joint'].includes(info?.role)?0.9:1.0);
}
function currentTrainingFirmwareP(){
  const source=state?.jobs.find(j=>j.id===chosen('resume').source_job);
  if(!source)return firmwarePDraft;
  const resolved=source.effective_config?.resolved||source.effective_config?.inspection;
  const saved=source.effective_config?.training_firmware_p??source.request.training_firmware_p??resolved?.model?.actuators?.[0]?.kp_fw;
  if(saved!=null)return saved;
  const edits=source.request.studio_recipe?.task_overrides?.[source.request.task]||[];
  const override=edits.find(p=>p.path?.at(-1)==='kp_fw');
  return override?.value??5; // Preserve historical HD1910 defaults.
}
function readActionFilter(){return {enabled:$('action-filter-enabled').checked,head_alpha:Number($('head-filter-alpha').value),legs_alpha:Number($('legs-filter-alpha').value),version:1};}
function applyActionFilter(value){
  $('action-filter-enabled').checked=!!value?.enabled;
  $('head-filter-alpha').value=value?.head_alpha??0.5;
  $('legs-filter-alpha').value=value?.legs_alpha??0.7;
}
function renderActionFilter(){
  const resuming=!!chosen('resume').checkpoint;
  $('action-filter-enabled').disabled=resuming;
  for(const id of ['head-filter-alpha','legs-filter-alpha'])$(id).disabled=resuming||!$('action-filter-enabled').checked;
  const scale=currentTrainingScale(),scaleField=$('training-action-scale');
  if(![...scaleField.options].some(o=>Number(o.value)===scale))scaleField.add(new Option(String(scale),String(scale)));
  scaleField.value=[...scaleField.options].find(o=>Number(o.value)===scale).value;
  const fixedScale=taskCatalog.tasks.find(t=>t.id===$('task').value)?.role==='sitstand';
  scaleField.disabled=resuming||fixedScale;
  if(resuming||document.activeElement!==$('training-firmware-p'))$('training-firmware-p').value=currentTrainingFirmwareP();
  $('training-firmware-p').disabled=resuming;
  $('runtime-alignment').textContent=`舵机 P ${currentTrainingFirmwareP()} · 动作系数 ${currentTrainingScale()} · ${filterLabel(readActionFilter())} · ${resuming?'续训沿用原模型配置':'本次训练配置'}`;
  $('action-filter-note').textContent=resuming?'续训沿用原模型动作系数与滤波；修改请选新建训练。':fixedScale?'坐站固件分支固定动作系数1.0 · 头腿滤波可调 · 仿真与导出沿用训练记录。':'动作系数作用于相对 Home 的偏移 · 滤波每 50Hz 更新 · 仿真与导出沿用训练记录。';
}
function readParameters(allowQueue=false){
  const value={task:$('task').value,label:$('run-label').value.trim(),num_envs:Number($('num-envs').value),iterations:Number($('iterations').value),save_interval:1000,training_action_scale:currentTrainingScale(),action_filter:readActionFilter(),activation:$('activation').value||null,pushes:$('training-pushes').value,reward_weights:{...rewardDrafts[$('task').value]},...chosen('resume')};
  value.training_firmware_p=Number(currentTrainingFirmwareP());
  if(!Number.isInteger(value.training_firmware_p)||value.training_firmware_p<1||value.training_firmware_p>32)throw Error('HD1910舵机P必须是1至32的整数；理论2.69可用最接近的3试训。');
  for(const [key,id] of numericFields)value[key]=$(id).value===''?null:Number($(id).value);
  for(const [key,id] of [['actor_dims','actor-dims'],['critic_dims','critic-dims']]){const raw=$(id).value.trim();if(raw&&!/^[\d,，\s]+$/.test(raw))throw Error('隐藏层请输入逗号分隔的整数。');value[key]=raw?raw.split(/[,，\s]+/).filter(Boolean).map(Number):null;}
  if(window.jointTrainingParameters)Object.assign(value,window.jointTrainingParameters(value,allowQueue));
  return value;
}
async function describeTask(force=false){
  const task=$('task').value,target=typeof executionProfileForTask==='function'?executionProfileForTask():profile(),key=JSON.stringify([target,selectedEnginePin()?.revision,task]);
  if(!online||state.jobs.some(j=>['probe','describe'].includes(j.op)&&active(j)))return;
  if(!force&&(state.environment.configs?.[task]||describeAttempts.has(key)))return;
  describeAttempts.add(key);await action('/api/describe',{task,execution_profile:target},false);
}
function applyParameters(p){
  if(typeof ensureTaskVisible==='function')ensureTaskVisible(p.task);
  if(![...$('task').options].some(o=>o.value===p.task)){tell('当前环境没有这份配置对应的任务。');return false;}
  $('task').value=p.task;previousTask=p.task;if(typeof selectTaskEngine==='function')selectTaskEngine();if(studioDraft)configOverridesText=JSON.stringify(studioDraft.task_overrides?.[p.task]||(p.task==='Mjlab-Velocity-Flat-MicroDuck'?studioDraft.overrides:[])||[],null,2);$('run-label').value=p.label||'';$('num-envs').value=p.num_envs??4096;$('iterations').value=p.iterations??50000;
  for(const [key,id] of numericFields)$(id).value=p[key]??'';
  $('actor-dims').value=p.actor_dims?.join(', ')||'';$('critic-dims').value=p.critic_dims?.join(', ')||'';$('activation').value=p.activation||'';$('training-pushes').value=p.pushes||'default';
  applyActionFilter(p.action_filter);
  if(!chosen('resume').checkpoint&&finite(p.training_action_scale))actionScaleDrafts[p.task]=p.training_action_scale;
  if(!chosen('resume').checkpoint&&finite(p.training_firmware_p))firmwarePDraft=p.training_firmware_p;
  rewardDrafts[p.task]={...p.reward_weights};window.rememberTrainingBudget?.();renderTaskConfig(true);render();return true;
}

// Commands are independent of the one-second history poll. One in-flight
// request, a short server lease, and sequence numbers prevent stale movement.
const held=new Set(),clientId=globalThis.crypto?.randomUUID?.()||('browser_'+Math.random().toString(36).slice(2));
let sequence=0,moveSequence=0,controlSending=false,pendingMove=null,controlActions=[],driveJob=null,controlError='';
function driveRanges(){
  // The official walking tasks use these command ranges.
  // The running adapter publishes its actual ranges when overrides are present.
  const defaults=[[-.4,.4],[-.3,.3],[-1,1]],live=viewer()?.sim_controls?.velocity_ranges;
  return defaults.map((fallback,i)=>{const r=live?.[i],limit=[.4,.3,1][i];return Array.isArray(r)&&r.length===2&&r.every(finite)&&r[0]<=0&&r[1]>=0?[Math.max(-limit,r[0]),Math.min(limit,r[1])]:fallback;});
}
function movement(){const ranges=driveRanges();return [['forward','back'],['left','right'],['turn_left','turn_right']].map(([positive,negative],i)=>held.has(positive)===held.has(negative)?0:held.has(positive)?ranges[i][1]:ranges[i][0]);}
function queueControl(action){const j=viewer();if(!j||!online||!j.sim_controls||viewerStop?.id===j.id)return;const message={job_id:j.id,action,velocity:action==='move'?movement():undefined};if(action==='move'){pendingMove=message;driveJob=j.id;}else{pendingMove=null;controlActions.push(message);controlActions=controlActions.slice(-8);}pumpControl();}
async function pumpControl(){
  if(controlSending)return;const msg=controlActions.shift()||pendingMove;if(!msg)return;if(msg===pendingMove)pendingMove=null;controlSending=true;
  const sentSequence=++sequence;if(msg.action==='move'&&!moveSequence)moveSequence=sentSequence;
  try{
    await post('/api/sim/control',{...msg,client:clientId,sequence:sentSequence},{signal:AbortSignal.timeout(2000)});
    if(viewer()?.id===msg.job_id)controlError='';
  }catch(e){
    if(viewer()?.id===msg.job_id&&viewerStop?.id!==msg.job_id){
      const transient=['TimeoutError','AbortError','TypeError'].includes(e.name)||e.status>=500;
      if(transient){
        // Retain physical key state. The heartbeat sends a fresh command, never
        // the timed-out movement. The adapter's 0.7s lease still returns to zero.
        controlError='遥控连接暂时延迟，正在重试；超时期间仿真自动归零';
        if(msg.action==='zero'&&!held.size&&!pendingMove&&!controlActions.length&&(msg.retry||0)<2){
          controlActions.push({...msg,retry:(msg.retry||0)+1});
        }
      }else{
        held.clear();pendingMove=null;controlActions=[];
        controlError='指令发送失败：'+(e.message||'仿真控制中断');paintHeld();tell(controlError);
      }
    }
  }finally{controlSending=false;renderDriveFeedback();if(controlActions.length||pendingMove)pumpControl();}

}
function paintHeld(){document.querySelectorAll('[data-direction]').forEach(b=>b.classList.toggle('pressed',held.has(b.dataset.direction)));renderDriveFeedback();}
function clearMotion(send=true){const moving=held.size>0||pendingMove;held.clear();pendingMove=null;paintHeld();if(send&&moving)queueControl('zero');}
function beginDirection(name){if(!driveReady())return;if(!held.size)moveSequence=0;controlError='';held.add(name);paintHeld();queueControl('move');}
function endDirection(name){if(!held.delete(name))return;paintHeld();queueControl(held.size?'move':'zero');}
for(const button of document.querySelectorAll('[data-direction]')){
  button.addEventListener('pointerdown',e=>{if(e.button!==0||button.disabled)return;e.preventDefault();$('sim-drive').focus();button.setPointerCapture?.(e.pointerId);beginDirection(button.dataset.direction);});
  for(const event of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(event,()=>endDirection(button.dataset.direction));
}
const keyDirections={KeyW:'forward',ArrowUp:'forward',KeyS:'back',ArrowDown:'back',KeyA:'left',ArrowLeft:'left',KeyD:'right',ArrowRight:'right',KeyQ:'turn_left',KeyE:'turn_right'};
document.addEventListener('keydown',e=>{if(!keyboardReady()||e.ctrlKey||e.altKey||e.metaKey)return;if(e.code==='Space'){e.preventDefault();clearMotion();queueControl('zero');return;}if(keyDirections[e.code]){e.preventDefault();if(!e.repeat)beginDirection(keyDirections[e.code]);}});
document.addEventListener('keyup',e=>{if(keyDirections[e.code])endDirection(keyDirections[e.code]);});
document.addEventListener('focusin',()=>{if(!keyboardReady())clearMotion();renderDriveFeedback();});
$('sim-drive').addEventListener('focusout',()=>queueMicrotask(()=>{if(!keyboardReady())clearMotion();renderDriveFeedback();}));
window.addEventListener('blur',()=>clearMotion());document.addEventListener('visibilitychange',()=>{if(document.hidden)clearMotion();});
window.addEventListener('pagehide',()=>{clearMotion(false);const j=viewer();if(j?.sim_controls)post('/api/sim/control',{job_id:j.id,action:'zero',client:clientId,sequence:++sequence},{keepalive:true}).catch(()=>{});});
setInterval(()=>{if(held.size){if(!driveReady()||driveJob!==viewer()?.id)clearMotion();else queueControl('move');}},150);
async function refreshSimulation(){
  const j=viewer();if(online&&j?.status==='running'&&viewerStop?.id!==j.id&&j.sim_controls){try{const r=await fetch('/api/sim/state?job_id='+encodeURIComponent(j.id),{signal:AbortSignal.timeout(1000)});if(!r.ok)throw Error();const data=await r.json();if(viewer()?.id===j.id){j.sim_state=data;renderSimTelemetry();}}catch{renderSimTelemetry();}}
  setTimeout(refreshSimulation,250);
}

$('env-form').onsubmit=e=>{e.preventDefault();action('/api/probe',profile());};
$('engine-mode').onchange=render;$('distro').oninput=render;$('repo').oninput=render;
$('num-envs').oninput=()=>{window.alignTrainingBudget?.();render();};
$('iterations').oninput=()=>{window.rememberTrainingBudget?.();render();};
$('task').onchange=async()=>{
 const next=$('task').value;if(window.workflowBusy){$('task').value=previousTask;return;}
 $('task').value=previousTask;if((studioDirty||savePromise)&&!(await saveStudio()))return;$('task').value=next;changeTask();

};
$('task-config-refresh').onclick=()=>describeTask(true);
$('reward-fields').oninput=e=>{const name=e.target.dataset.reward;if(!name)return;const draft=rewardDrafts[$('task').value]||=( {} );if(e.target.value==='')delete draft[name];else draft[name]=Number(e.target.value);};
$('resume').onchange=()=>{const chosenValue=chosen('resume'),source=state?.jobs.find(j=>j.id===chosenValue.source_job);if(source){applyParameters({...source.request,...source.effective_config,label:runName(source)+' · 续训'});}else{applyActionFilter({enabled:true,head_alpha:0.5,legs_alpha:0.7});}render();};
for(const id of ['action-filter-enabled','head-filter-alpha','legs-filter-alpha'])$(id).oninput=renderActionFilter;
$('training-action-scale').onchange=()=>{actionScaleDrafts[$('task').value]=Number($('training-action-scale').value);renderActionFilter();};
$('training-firmware-p').onchange=()=>{firmwarePDraft=Number($('training-firmware-p').value);renderActionFilter();};
$('training-firmware-p').oninput=()=>{firmwarePDraft=Number($('training-firmware-p').value);renderActionFilter();};
$('checkpoint').onchange=render;
$('preview-start').onclick=async()=>{if(await saveStudio())return startViewer('/api/preview',{task:$('task').value,execution_profile:executionProfileForTask(),eval_pushes:$('eval-pushes').checked,training_action_scale:currentTrainingScale(),training_firmware_p:currentTrainingFirmwareP(),action_filter:readActionFilter()});};
$('play-start').onclick=()=>{const value=chosen('checkpoint');startViewer(value.export_job?'/api/onnx':'/api/play',{...value,eval_pushes:$('eval-pushes').checked});};
$('recovery-eval-start').onclick=()=>{const value=chosen('checkpoint');startViewer(value.export_job?'/api/onnx':'/api/play',{...value,recovery_evaluation:true,eval_pushes:false});};
$('export-model').onclick=()=>action('/api/export',chosen('checkpoint'));
$('play-stop').onclick=stopViewer;
$('training-live').onclick=()=>{const j=state.jobs.find(j=>j.op==='train'&&active(j));if(!j)return;clearMotion(false);controlActions=[];$('follow-latest').checked=false;watchedTrainingId=j.id;watchTraining=true;render();};
$('sim-zero').onclick=()=>{clearMotion();queueControl('zero');};
$('sim-pause').onclick=()=>{clearMotion();queueControl(viewer()?.sim_state?.paused?'resume':'pause');};
$('sim-reset').onclick=()=>{clearMotion();queueControl('reset');};
$('viewer-fullscreen').onclick=()=>{const stage=$('sim-stage');if(stage.requestFullscreen)stage.requestFullscreen().catch(()=>tell('当前浏览器无法进入全屏，可使用「单独打开」。'));};
$('model-table').onclick=e=>{const b=e.target.closest('[data-model]');if(b){$('checkpoint').value=b.dataset.model;render();$('models').scrollIntoView?.({behavior:'smooth',block:'start'});}};
$('run-list').onclick=e=>{const b=e.target.closest('[data-job]');if(b){selected=b.dataset.job;configView=false;loadState();}};
$('show-config').onclick=()=>{configView=!configView;render();};$('chart-series').onchange=draw;$('chart-smooth').onchange=draw;
$('show-full-log').onclick=()=>showFullLog();
$('show-live-log').onclick=()=>{fullLog=null;configView=false;render();loadState();};
const chartObserver=new ResizeObserver(draw);
for(const id of ['training-chart','detail-chart'])chartObserver.observe($(id).parentElement);
async function startTrainingUi(){try{const r=await fetch('/api/config');if(!r.ok)throw Error('无法读取训练台配置');const cfg=await r.json();token=cfg.token;$('version').textContent=cfg.version+(cfg.version.includes($('version').dataset.uiRevision)?'':' · 界面 '+$('version').dataset.uiRevision);refresh();refreshSimulation();}catch(e){online=false;$('connection-error').hidden=false;tell(e.message);}}
if(document.readyState==='complete')setTimeout(startTrainingUi,0);else document.addEventListener('DOMContentLoaded',startTrainingUi,{once:true});

async function removeModel(value){
  if(!value.checkpoint&&!value.export_job)return;
  const record=modelRecords().find(r=>JSON.stringify(r.value)===JSON.stringify(value));
  if(!window.confirm(`删除 ${record?recordLabel(record):'所选模型'}？\n文件移入训练目录的回收文件夹，正在使用的模型不能删除。`))return;
  await action('/api/models/delete',value);
}
$('delete-model').onclick=()=>removeModel(chosen('checkpoint'));
$('model-table').addEventListener('click',event=>{const button=event.target.closest('[data-delete-model]');if(button)removeModel(JSON.parse(button.dataset.deleteModel));});

async function downloadModel(id,button){
  if(button.disabled)return;
  const original=button.textContent;button.disabled=true;
  const filename='Microduck-Policy-'+id+'.zip';let writable;
  try{
    // Open during the click gesture, before waiting for the server to build the ZIP.
    let handle;
    if(typeof window.showSaveFilePicker==='function'){
      button.textContent='选择保存位置…';
      try{handle=await window.showSaveFilePicker({suggestedName:filename,types:[{description:'模型包 ZIP',accept:{'application/zip':['.zip']}}]});}
      catch(error){if(error.name==='AbortError'){tell('已取消保存模型包。');return;}throw error;}
    }
    button.textContent='正在打包…';
    // Transfer ordinary authenticated JSON, not an attachment/ZIP response.
    // Download managers can intercept the network response even with a file picker.
    const payload=await post('/api/model/content',{job_id:id},{signal:AbortSignal.timeout(150000)});
    if(payload.encoding!=='base64'||typeof payload.data!=='string'||!Number.isSafeInteger(payload.size)||payload.size<4)
      throw Error('服务器未返回有效模型包数据');
    const raw=atob(payload.data),bytes=Uint8Array.from(raw,c=>c.charCodeAt(0));
    if(bytes.length!==payload.size||bytes.slice(0,4).join(',')!=='80,75,3,4')
      throw Error('模型包内容不完整或不是有效 ZIP，请重新下载。');
    const digest=await crypto.subtle.digest('SHA-256',bytes);
    const sha256=Array.from(new Uint8Array(digest),n=>n.toString(16).padStart(2,'0')).join('');
    if(sha256!==payload.sha256)throw Error('模型包校验失败，请重新下载。');
    const blob=new Blob([bytes],{type:'application/zip'});
    if(handle){
      button.textContent='正在保存…';writable=await handle.createWritable();
      await writable.write(blob);await writable.close();writable=null;
      tell('模型包已保存：'+filename);
    }else{
      const url=URL.createObjectURL(blob),link=document.createElement('a');
      link.href=url;link.download=filename;document.body.append(link);link.click();link.remove();
      setTimeout(()=>URL.revokeObjectURL(url),60000);tell('模型包已校验，已交给浏览器保存。');
    }
  }catch(error){if(writable)try{await writable.abort();}catch(_){}tell('模型下载失败：'+error.message);}
  finally{button.disabled=false;button.textContent=original;}
}
$('model-table').addEventListener('click',event=>{const button=event.target.closest('[data-download-model]');if(button)downloadModel(button.dataset.downloadModel,button);});
