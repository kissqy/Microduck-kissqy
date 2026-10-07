let configOverridesText="[]";
'use strict';
let studioData=null,studioDraft=null,studioDirty=false,studioTab='servo-mass',studioPage=0,studioBody=null,studioStamp='',studioBusy=false,followStamp='';
const bodyNames={trunk_base:'躯干总成',yaw2roll:'左髋偏航连接件',hip_l:'左髋侧摆连接件',upper_leg_left:'左大腿',leg:'左小腿',ankle_left:'左脚踝与脚掌',neck:'颈部底座',neck_pitch:'颈部连接件',yaw_roll_motion:'头部转向连接件',jaw_soft:'头部与鸭嘴总成',bearing_roll:'右髋偏航连接件',hip_l_2:'右髋侧摆连接件',upper_leg_right:'右大腿',leg_2:'右小腿',ankle_right:'右脚踝与脚掌'};
const jointNames={trunk_base_freejoint:'躯干自由运动',left_hip_yaw:'左髋转向',left_hip_roll:'左髋侧摆',left_hip_pitch:'左髋前后摆',left_knee:'左膝',left_ankle:'左脚踝',right_hip_yaw:'右髋转向',right_hip_roll:'右髋侧摆',right_hip_pitch:'右髋前后摆',right_knee:'右膝',right_ankle:'右脚踝',neck_pitch:'颈部俯仰',head_pitch:'头部俯仰',head_yaw:'头部左右转',head_roll:'头部左右歪',mouth:'鸭嘴开合'};
const bilingual=(name,names)=>`<strong>${esc(names[name]||'模型部件')}</strong><small class="model-name">${esc(name)}</small>`;
function setExpertSettings(enabled){
 document.body.classList.toggle('expert-settings',enabled);
 for(const [id,active] of [['settings-basic',!enabled],['settings-expert',enabled]]){$(id).classList.toggle('selected',active);$(id).setAttribute('aria-pressed',String(active));}
 $('open-advanced-settings').textContent=enabled?'收起高级参数':'打开高级参数';
 $('settings-view-note').textContent=enabled?'高级参数已显示':'';
 draw();
}
const configValue=v=>v===null?'null（未单独设置，见解释）':typeof v==='object'?JSON.stringify(v):String(v);
const sj=v=>JSON.stringify(v);const pretty=v=>JSON.stringify(v,null,2);const val=v=>v===null||v===undefined?'未取得':typeof v==='object'?sj(v):String(v);
let editVersion=0,saveTimer=null,savePromise=null;
let zeroFetchPromise=null,zeroTargetLoaded=false,calibrationEpoch=0;
const repairedDescribeAttempts=new Set();
function syncCalibrationResult(result){
 if(result.calibration){studioDraft.calibration=structuredClone(result.calibration);studioData.recipe.calibration=structuredClone(result.calibration);}
 calibrationEpoch++;studioData.frozen=null;describeAttempts.clear();
 studioData.bundled_calibration_matches=sj(studioDraft.calibration?.data)===sj(studioData.hardware.current_calibration.data);
 if(typeof selectTaskEngine==='function')selectTaskEngine(false);
 renderStudioTables();renderStudioChecks();
}
function repairTaskConfiguration(){
 if(!online||!state||!studioData||window.workflowBusy||zeroFetchPromise)return;
 if(typeof selectTaskEngine==='function')selectTaskEngine(false);
 const failed=state.jobs.find(j=>j.op==='describe'&&j.request?.task===$('task').value);
 if(failed?.status!=='failed'||!failed.message?.includes('训练源码版本已变化')||repairedDescribeAttempts.has(failed.id))return;
 if(state.jobs.some(j=>['describe','probe'].includes(j.op)&&active(j)))return;
 repairedDescribeAttempts.add(failed.id);
 // Retry only the failed read, once. Never start/restart training or a probe.
 describeTask(true).catch(e=>tell(e.message));
}
function markDirty(){studioDirty=true;editVersion++;$('studio-status').textContent='正在同步修改…';clearTimeout(saveTimer);saveTimer=setTimeout(()=>saveStudio(),400);window.workflowConfigChanged?.();window.workflowRender?.();}
function downloadJSON(name,value){const u=URL.createObjectURL(new Blob([pretty(value)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),2000);}
function stablePath(row){return row.path.map(String).join('.');}
function table(headers,rows){return `<table class="studio-table"><thead><tr>${headers.map(x=>`<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table>`;}
function row(cells){return '<tr>'+cells.map(x=>'<td>'+x+'</td>').join('')+'</tr>';}
function cells(items){return items.map(x=>esc(val(x)));}
async function studioLoad(force=false){
 if(studioBusy||zeroFetchPromise)return;studioBusy=true;const loadedVersion=editVersion,loadedCalibrationEpoch=calibrationEpoch;
 try{const r=await fetch('/api/studio');if(!r.ok)throw Error('无法读取参数台账');const data=await r.json();if(zeroFetchPromise||loadedCalibrationEpoch!==calibrationEpoch)return;studioData=data;if(!zeroTargetLoaded){$('zero-target').value=studioData.zero_connection?.target||'';zeroTargetLoaded=true;}if(!studioDraft||(force&&loadedVersion===editVersion&&!studioDirty&&!savePromise)){studioDraft=structuredClone(studioData.recipe);studioDirty=false;const migrate=studioDraft.baseline!=='official_0151';if(migrate){studioDraft.baseline='official_0151';studioDraft.robot={servo_mass_model:'hd1910_820g_v1'};studioDraft.overrides=[];studioDraft.task_overrides={};$('repo').value=studioData.pins.official_0151.repo;}fillStudio();if(migrate)markDirty();}if(!document.activeElement?.closest('#robot-data,#all-config'))renderStudioTables();renderStudioChecks();}
 catch(e){tell(e.message);}finally{studioBusy=false;window.workflowRender?.();}
}
function fillStudio(){

 $('custom-mjcf').value=studioDraft.robot.mjcf_path||'';$('robot-overrides').value=pretty(studioDraft.robot);
 configOverridesText=pretty(studioDraft.task_overrides?.[$('task').value]||($('task').value==='Mjlab-Velocity-Flat-MicroDuck'?studioDraft.overrides:[])||[]);
 $('studio-status').textContent='页面参数已同步';
}
function renderStudioChecks(){
 if(!studioData)return;
 const setupBusy=window.workflowBusy,zeroBusy=!!zeroFetchPromise;
 const c=current();$('download-run').href='/api/report.zip'+(c?'?job='+encodeURIComponent(c.id):'');
 $('calibration-zero').disabled=setupBusy||zeroBusy;
 $('calibration-zero').textContent=zeroBusy?'正在获取…':'从 ZERO 获取';
 $('zero-target').disabled=zeroBusy;$('calibration-file').disabled=setupBusy||zeroBusy;
 $('calibration-bundled').disabled=setupBusy||zeroBusy||studioData.bundled_calibration_matches;
 $('calibration-bundled').textContent=studioData.bundled_calibration_matches?'已使用随包标定':'使用随包标定';
 $('calibration-bundled').classList.toggle('applied',studioData.bundled_calibration_matches);
 const revision=studioData.hardware.current_calibration.revision;
 $('calibration-quick-status').textContent=studioData.bundled_calibration_matches?`随包修订${revision} · 已应用`:'安装包内的历史标定';
 $('calibration-bundled').title='使用安装包自带标定，将替换当前实验标定。';
 
}
function servoMassSupported(){return studioDraft.baseline==='official_0151'&&!studioDraft.robot.mjcf_path;}
function effectiveStudioModel(){
 const m=structuredClone(studioData.baseline.model);if(!m)return null;
 const profile=studioData.servo_mass_profile,closure=studioData.mass_closure_profile,choice=studioDraft.robot.servo_mass_model,enabled=servoMassSupported()&&[profile.key,closure.key].includes(choice);
 for(const b of m.bodies){
  const o=studioDraft.robot.bodies?.[b.name]||{};Object.assign(b,o);
  if(o.mass!==undefined)b.mass_kg=o.mass;
  b.servo_mass_addition_g=enabled&&o.mass===undefined?(profile.body_counts[b.name]||0)*(profile.replacement_g-profile.reference_g):0;
  b.closure_mass_addition_g=enabled&&choice===closure.key&&o.mass===undefined?(closure.body_additions_g[b.name]||0):0;
  const before=b.mass_kg;b.mass_kg+=(b.servo_mass_addition_g+b.closure_mass_addition_g)/1000;
  if((b.servo_mass_addition_g+b.closure_mass_addition_g)&&o.inertia===undefined)b.inertia=b.inertia.map(v=>v*b.mass_kg/before);
  b.mass_g=b.mass_kg*1000;
 }
 m.total_mass_kg=m.bodies.reduce((sum,b)=>sum+b.mass_kg,0);return m;
}
function renderServoMass(m){
 const p=studioData.servo_mass_profile,c=studioData.mass_closure_profile,choice=studioDraft.robot.servo_mass_model,supported=servoMassSupported(),closed=choice===c.key&&supported;
 const total=m.total_mass_kg*1000,gap=c.target_g-total,custom=!!studioDraft.robot.mjcf_path;
 const head=m.bodies.find(b=>b.name==='jaw_soft'),trunk=m.bodies.find(b=>b.name==='trunk_base');
 const exact=closed&&!custom&&Math.abs(gap)<.00001&&!Object.values(studioDraft.robot.bodies||{}).some(v=>v.mass!==undefined);
 const rows=m.bodies.map(b=>{const n=p.body_counts[b.name]||0,manual=studioDraft.robot.bodies?.[b.name]?.mass!==undefined;
  return row([bilingual(b.name,bodyNames),`<strong>${b.mass_g.toFixed(3)}</strong>`,String(n),manual?'手动指定':b.closure_mass_addition_g?'舵机 +'+b.servo_mass_addition_g+'g / 补重 +'+b.closure_mass_addition_g.toFixed(5)+'g':b.servo_mass_addition_g?'舵机 +'+b.servo_mass_addition_g+'g':'沿用模型',`<button class="text-button" data-body="${esc(b.name)}">编辑</button>`]);});
 return `<div class="panel-body servo-mass-panel">
 <div class="mass-values servo-mass-summary"><div><span>当前模型总重</span><strong id="servo-mass-total">${custom?'待编译核对':total.toFixed(2)+' g'}</strong><small id="servo-mass-gap">${custom?'自定义模型以编译为准':Math.abs(gap)<.00001?'与实测820g一致':(gap>0?'距820g还差 ':'比820g重 ')+Math.abs(gap).toFixed(2)+' g'}</small></div><div><span>头部总成</span><strong>${head?.mass_g.toFixed(3)??'—'} g</strong></div><div><span>躯干总成</span><strong>${trunk?.mass_g.toFixed(3)??'—'} g</strong></div></div>
 </div>`+table(['部件 · 中英对照','质量 / g','舵机 / 颗','重量来源','操作'],rows);
}
function renderActuators(m){
 const ref=studioData.servo_references,official=ref?.official_training;
 const number=v=>v===undefined?'未记录':v===null?'未单独设置':`<span title="${esc(configValue(v))}">${esc(typeof v==='number'?Number(v.toPrecision(8)):configValue(v))}</span>`;
 const label=(k,h)=>`<strong>${esc(h?.title||k)}</strong><small lang="en">${esc(h?.english||k)}</small><code class="field-path">${esc(k)}</code>`;
 const run=training(),actual=run?.effective_config?.resolved?.model?.actuators||[];
 const planned=structuredClone(m.actuators[0]||{});
 const edits=studioDraft.task_overrides?.[$('task').value]||[];
 for(const edit of edits){const p=edit.path;if(p?.slice(0,6).join('.')==='env.scene.entities.robot.articulation.actuators'&&Number(p[6])===0&&p.length===8)planned[p[7]]=edit.value;}
 let output='<div class="servo-section-title">训练执行器 / Actuator configuration · 19 项</div>';
 output+=table(['配置项 / Parameter','单位','官方 XL330 基线','本页 HD1910 配置','训练用途'],Object.entries(ref.actuator_fields).map(([k,h])=>row([label(k,h),esc(h.unit),number(official?.actuators?.[0]?.[k]),number(planned[k]),esc(h.explanation)])));
 output+='<p class="servo-source-note">页面编辑用于下次启动；正在运行的任务保留启动时配置。XL330 实物电压上限为 6 V，表中的仿真电压不是实物供电建议。</p>';
 output+='<div class="servo-section-title">实际加载的控制模型 / Loaded controller</div>';
 output+=`<p class="servo-source-note">运行读回：${esc(run?runName(run):'尚无训练记录')}。旧记录未采集的值显示“未记录”。</p>`;
 output+=table(['控制参数 / Parameter','单位','XL330 基线读回','HD1910 基线读回','本次训练读回','用途'],Object.entries(ref.runtime_fields).map(([k,h])=>row([label(k,h),esc(h.unit),number(official?.actuators?.[0]?.runtime_properties?.[k]),number(m.actuators[0]?.runtime_properties?.[k]),number(actual[0]?.runtime_properties?.[k]),esc(h.explanation)])));
 for(const [i,a] of m.actuators.entries()){
  const source=a.parameter_file?.data||{},reference=official?.parameter_file?.data||{};
  output+='<div class="servo-section-title">BAM 辨识参数 / Identified parameters · 20 项</div>';
  output+=table(['参数与用途 / Parameter','单位','官方 XL330','HD1910 基线','本页 HD1910 值','本次训练读回','操作'],[...new Set([...Object.keys(source),...Object.keys(reference)])].map(k=>{
   const v=source[k],h=ref.bam_fields[k]||studioData.baseline.bam_help[k],fitOnly=['q_offset','command_delay'].includes(k);
   return row([label(k,h)+`<small class="servo-usage ${fitOnly?'reference-only':''}">${esc(h?.usage)}</small><small>${esc(h?.explanation)}</small>`,esc(h?.unit||'—'),number(reference[k]),number(v),number(studioDraft.robot.actuator_parameters?.[i]?.[k]??v),number(actual[i]?.runtime_properties?actual[i]?.parameter_file?.data?.[k]:undefined),typeof v==='number'&&!fitOnly?`<button class="text-button" data-bam="${i}" data-key="${esc(k)}">修改</button>`:fitOnly?'仅辨识记录':'来源标识']);
  }));
 }
 if(ref){
  output+=`<p class="servo-source-note">来源：<a href="${esc(official.source.url.replace(/\.git$/,''))}/tree/${esc(official.source.revision)}" target="_blank" rel="noopener">官方训练基线</a> · <a href="${esc(official.parameter_file.url)}" target="_blank" rel="noopener">XL330 BAM M6 原始参数</a>。未提供的字段保留空缺。</p>`;
  output+='<div class="servo-section-title">XL330 / HD1910 厂家性能对照 / Manufacturer specifications</div>';
  const performance=[...ref.performance.map(p=>({...p,name:'XL330-M288'})),...(ref.hd1910_manufacturer?.performance||[]).map(p=>({...p,name:'HD-1910-C001'}))];
  output+=table(['型号 / Model','供电 / V','堵转扭矩 / N·m','堵转电流 / A','空载转速 / rpm','换算 / rad/s','空载时间 / s·60°⁻¹'],performance.map(p=>row(cells([p.name,p.voltage_v,Number(p.stall_torque_nm.toFixed(4)),p.stall_current_a,p.no_load_speed_rpm,Number(p.no_load_speed_rad_s.toFixed(4)),Number(p.no_load_s_per_60deg.toFixed(4))]))));
  if(ref.hd1910_manufacturer)output+=`<p class="servo-source-note">${esc(ref.hd1910_manufacturer.note)} <a href="${esc(ref.hd1910_manufacturer.source_url)}" target="_blank" rel="noopener">HD-1910-C001厂家规格 ${esc(ref.hd1910_manufacturer.edition)}</a></p>`;
  output+=table(['参数 / Parameter','XL330厂家公布值','单位','HD1910 对照（规格/本机）','训练用途'],ref.specifications.map(p=>row(cells([p.label,p.value,p.unit,p.hd1910,p.usage]))));
  const inertia=ref.inertia;
  output+='<div class="servo-section-title">XL330 壳体质量、重心与惯量 / Mass properties</div>';
  output+=table(['项目','厂家参考值','单位'],[row(cells(['单颗质量 / Mass',inertia.mass_g,'g'])),row(cells(['重心 / Center of mass',inertia.com_mm,'mm'])),row(cells(['惯量张量 / Inertia tensor',inertia.tensor_g_mm2,'g·mm²']))]);
  output+=`<p class="servo-source-note">${esc(inertia.note)} ${esc(inertia.unit_conversion)} · <a href="${esc(inertia.source_url)}" target="_blank" rel="noopener">厂家原始惯量 PDF</a></p>`;
  output+='<div class="servo-section-title">XL330 完整控制表 / Control table · 110 项</div><label class="servo-register-search">查寄存器 / Find register <input id="servo-register-search" type="search" placeholder="中文、英文或地址"></label>';
  output+='<div id="servo-register-table">'+table(['地址 / Bytes','寄存器 / Register','区域 / 权限','厂家初值','范围 / 单位','训练关系'],ref.registers.map(p=>row([esc(p.address)+' / '+esc(p.size_bytes),esc(p.label),esc(p.area)+' / '+esc(p.access),number(p.default),esc(p.range)+' / '+esc(p.unit),esc(p.usage)])))+'</div>';
  output+=`<p class="servo-source-note">${ref.notes.map(esc).join('<br>')}<br><a href="${esc(ref.manufacturer_source)}" target="_blank" rel="noopener">ROBOTIS 官方规格与控制表</a> · 核对 ${esc(ref.reviewed_on)} · 参考资料不自动覆盖 HD1910 训练参数。</p>`;
  output+='<div class="servo-section-title">飞特开源方案核对 / Community source audit</div>';
  output+=table(['项目 / Project','配套配置','与本机的关系','验证范围'],(ref.community_comparison||[]).map(p=>row([`<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.name)}</a>`,esc(p.configuration),esc(p.difference),esc(p.evidence)])));
 }
 return output;
}
function renderStudioTables(){
 if(!studioData)return;const m=effectiveStudioModel(),h=studioData.hardware;
 $('body-mass').textContent=m?`实验质量 ${(m.total_mass_kg*1000).toFixed(3)} g`:'等待模型';
 for(const button of document.querySelectorAll('[data-studio-tab]')){const selected=button.dataset.studioTab===studioTab;button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));}
 let output='';
 if(m&&studioTab==='servo-mass')output=renderServoMass(m);
 if(m&&studioTab==='joints')output=table(['关节 · 中英对照','所属刚体','刚体质量 / g','Home / °','模型范围 / rad','关节轴','锚点 / m'],m.joints.map(j=>row([bilingual(j.name,jointNames),bilingual(j.body,bodyNames),...cells([(m.bodies.find(b=>b.name===j.body)?.mass_g??j.body_mass_g).toFixed(4),j.home_deg.toFixed(5),j.limited?j.range:'无限位',j.axis,j.pos])])));
 if(m&&studioTab==='actuators')output=renderActuators(m);
 $('robot-table').classList.toggle('servo-mass-view',studioTab==='servo-mass');
 $('robot-table').innerHTML=output||'<p class="empty">无数据。</p>';
 const imported=studioDraft.calibration,c=imported||h.current_calibration;
 $('calibration-source').textContent=imported?(imported.zero_target?`已从 ${imported.zero_target} 获取 · ${new Date(imported.imported_at*1000).toLocaleString('zh-CN',{hour12:false})} · 15关节 + IMU`:'15关节标定已载入当前实验 · '+imported.source):'尚未载入本实验标定';
 const real=c?.data?.joints;
 $('calibration-table').innerHTML=table(['关节 · 中英对照','ID','方向','零点 / counts','机械限位 / rad'],h.joints.map(j=>{const q=real?.find(x=>x.name===j.name),change=c?.changes?.joints?.find(x=>x.name===j.name);const tr=row([bilingual(j.name,jointNames),...cells([j.id,q?.direction??j.direction_historical]),esc(q?.zero_raw??j.zero_raw_inferred)+(change?.fields.zero_raw?`<small class="calibration-old">原 ${esc(val(change.fields.zero_raw.before))}</small>`:''),esc(val(q?[q.min_rad,q.max_rad]:'历史° '+sj(j.limits_deg_historical)))]);return change?tr.replace('<tr>','<tr class="calibration-changed">'):tr;}));
 $('hardware-summary').innerHTML=`<p><span>IMU安装 · wxyz</span><code>${esc(c?val(c.data.imu_mount_quat):'未取得')}</code></p>`;
 renderConfigTable();
}
function currentConfigRows(){const actual=taskSchema()?.inspection?.rows;return (actual?.every(r=>r.help)?actual:$('task').value==='Mjlab-Velocity-Flat-MicroDuck'?studioData.baseline.rows||[]:[]).map(r=>r.path.join('.')==='agent.save_interval'?{...r,value:1000,editable:false}:r);}
function renderConfigTable(){
 if(!studioData)return;const all=currentConfigRows(),q=$('config-search').value.toLowerCase().trim(),category=$('config-category').value,status=$('config-status').value;
 const filtered=all.map((r,i)=>({r,i})).filter(({r})=>(r.editable||$('config-show-reference').checked)&&stablePath(r).startsWith(category)&&(status==='all'||r.help.status===status)&&(!q||(stablePath(r)+' '+sj(r.value)+' '+sj(r.help)).toLowerCase().includes(q))).sort((a,b)=>(a.r.help.status==='pending'?0:1)-(b.r.help.status==='pending'?0:1)||a.i-b.i);
 const pages=Math.max(1,Math.ceil(filtered.length/70));studioPage=Math.min(studioPage,pages-1);const n={missing:all.filter(r=>r.help.documentation_missing).length,pending_adaptation:all.filter(r=>r.help.status==='pending'&&!r.help.documentation_missing).length,can_keep_source:all.filter(r=>r.help.status==='known').length};
 $('config-count').textContent=`${all.length} 项参数 · 说明待补充 ${n.missing} · 待核对 ${n.pending_adaptation} · 可沿用 ${n.can_keep_source} · 覆盖 ${studioDraft.overrides.length}`;
 $('config-table').innerHTML=table(['中文名称 / 配置路径','作用 / 单位','源码值','确认状态','本实验覆盖','操作'],filtered.slice(studioPage*70,(studioPage+1)*70).map(({r,i})=>{
  const h=r.help,managedScale=stablePath(r)==='env.actions.joint_pos.scale',override=managedScale?{value:1.0}:(studioDraft.task_overrides?.[$('task').value]||($('task').value.endsWith('-HD1910')?studioDraft.overrides:[])||[]).find(p=>sj(p.path)===sj(r.path));
  const links='';
  return row([`<strong>${esc(h.title)}</strong><small class="field-context">${esc(h.context)}</small><code class="field-path">${esc(stablePath(r))}</code>`,`<div class="field-meaning">${esc(h.explanation)}<small>单位：${esc(h.unit)}</small></div>`,`<code>${esc(configValue(r.value))}</code>`,`<span class="field-state ${h.status}">${esc(h.status_label)}</span><small class="field-evidence">${esc(h.evidence)}</small>${links}`,`<code>${esc(override?configValue(override.value):'沿用源码')}</code>`,managedScale?'官方动作映射 1.0':r.editable?`<button class="text-button" data-config="${i}">修改</button>`:'<span class="hint">来源定义</span>']);}));
 if(!filtered.length)$('config-table').innerHTML='<p class="empty">当前筛选没有匹配项；可切换确认状态或清空搜索。</p>';
 $('config-page').textContent=`${studioPage+1} / ${pages} 页 · 匹配 ${filtered.length} 项`;$('config-prev').disabled=!studioPage;$('config-next').disabled=studioPage>=pages-1;
}
function gatherStudio(){
 studioDraft.training_action_scale=1.0;
 studioDraft.name='官方骨架 + HD1910';studioDraft.baseline='official_0151';studioDraft.purpose='sim2real';
 studioDraft.robot=JSON.parse($('robot-overrides').value||'{}');studioDraft.task_overrides??={};studioDraft.task_overrides[$('task').value]=JSON.parse(configOverridesText||'[]');studioDraft.overrides=studioDraft.task_overrides['Mjlab-Velocity-Flat-MicroDuck']||studioDraft.overrides||[];
 if($('custom-mjcf').value.trim())studioDraft.robot.mjcf_path=$('custom-mjcf').value.trim();else delete studioDraft.robot.mjcf_path;
 if(!studioDraft.name)throw Error('请填写实验名称');return studioDraft;
}
async function saveStudio(){
 clearTimeout(saveTimer);
 if(zeroFetchPromise&&!(await zeroFetchPromise))return false;
 if(savePromise){const okay=await savePromise;if(!okay)return false;if(studioDirty)return saveStudio();return true;}
 savePromise=(async()=>{await Promise.resolve();try{
  do {const version=editVersion,snapshot=structuredClone(gatherStudio());await post('/api/recipe',{recipe:snapshot});
   if(version===editVersion){studioDirty=false;studioData.recipe=snapshot;studioData.frozen=null;$('studio-status').textContent='页面参数已同步 · 用于下次启动';}
  } while(studioDirty);
  return true;
 }catch(e){studioDirty=true;$('studio-status').textContent='参数未同步：'+e.message;tell(e.message);return false;}finally{savePromise=null;window.workflowRender?.();}})();
 return savePromise;
}
$('calibration-file').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{if(!(await saveStudio()))return;if(f.size>40*1024*1024)throw Error('文件超过40MB');const result=await post('/api/calibration/import',{name:f.name,text:await f.text()});syncCalibrationResult(result);await studioLoad(true);repairTaskConfiguration();tell('标定已导入并自动同步，可继续训练。');}catch(x){tell(x.message);}e.target.value='';};
async function fetchZeroCalibration(){
 const status=$('calibration-zero-status');status.classList.remove('error');status.textContent='正在读取 ZERO 已保存的标定…';calibrationEpoch++;
 try{
  const result=await post('/api/calibration/zero',{target:$('zero-target').value});
  syncCalibrationResult(result);
  studioData.zero_connection=result.zero_connection;
  studioData.bundled_calibration_matches=sj(result.calibration.data)===sj(studioData.hardware.current_calibration.data);
  $('zero-target').value=result.zero_connection.target;studioData.frozen=null;calibrationEpoch++;
  const names=result.changes.joints.map(j=>`${jointNames[j.name]||j.name}（${j.id}）`);
  status.textContent=`已获取并保存 · ${names.length?names.length+'个关节变化：'+names.join('、'):'关节无变化'} · IMU${result.changes.imu_changed?'已更新':'无变化'} · 相关配置已同步`;
  renderStudioTables();tell('ZERO 最新标定已导入。');return true;
 }catch(error){status.classList.add('error');status.textContent=error.message;tell(error.message);return false;}
}
$('calibration-zero').onclick=async()=>{
 if(zeroFetchPromise||window.workflowBusy)return;
 if(!$('zero-target').value.trim()){$('calibration-zero-status').textContent='请输入 ZERO 的 IP 或 用户名@IP。';$('zero-target').focus();return;}
 if(!(await saveStudio()))return;
 if(zeroFetchPromise)return;
 zeroFetchPromise=fetchZeroCalibration();renderStudioChecks();
 try{await zeroFetchPromise;}finally{zeroFetchPromise=null;renderStudioChecks();repairTaskConfiguration();}
};
$('settings-basic').onclick=()=>setExpertSettings(false);
$('settings-expert').onclick=()=>setExpertSettings(true);
$('open-advanced-settings').onclick=()=>setExpertSettings(!document.body.classList.contains('expert-settings'));
$('config-show-reference').onchange=()=>{studioPage=0;renderConfigTable();};
document.querySelector('nav a[href="#reference-details"]').addEventListener('click',()=>setExpertSettings(true));
$('calibration-bundled').onclick=async()=>{try{if(studioDirty&&!(await saveStudio()))return;const result=await post('/api/calibration/bundled',{});syncCalibrationResult(result);await studioLoad(true);repairTaskConfiguration();tell('随包标定已应用并自动同步，可继续训练。');}catch(error){tell(error.message);}};

for(const id of ['custom-mjcf','robot-overrides'])$(id).addEventListener('input',markDirty);
for(const b of document.querySelectorAll('[data-studio-tab]'))b.onclick=()=>{studioTab=b.dataset.studioTab;renderStudioTables();};
$('config-search').oninput=$('config-category').onchange=$('config-status').onchange=()=>{studioPage=0;renderConfigTable();};
$('config-prev').onclick=()=>{studioPage--;renderConfigTable();};$('config-next').onclick=()=>{studioPage++;renderConfigTable();};
$('config-reset').onclick=()=>{configOverridesText='[]';gatherStudio();markDirty();renderConfigTable();};
$('config-table').onclick=e=>{const b=e.target.closest('[data-config]');if(!b)return;const i=Number(b.dataset.config),r=currentConfigRows()[i],ov=(studioDraft.task_overrides?.[$('task').value]||[]).find(p=>sj(p.path)===sj(r.path));const tr=b.closest('tr');tr.children[4].innerHTML=`<input class="config-edit" value="${esc(sj(ov?ov.value:r.value))}" data-apply="${i}" aria-label="覆盖值">`;};
$('config-table').addEventListener('change',e=>{const b=e.target.closest('[data-apply]');if(!b)return;try{const r=currentConfigRows()[Number(b.dataset.apply)],v=JSON.parse(b.value);b.setCustomValidity('');const overrides=JSON.parse(configOverridesText||'[]').filter(p=>sj(p.path)!==sj(r.path));overrides.push({path:r.path,value:v});configOverridesText=pretty(overrides);gatherStudio();markDirty();renderConfigTable();}catch(x){b.setCustomValidity('JSON格式无效');b.reportValidity();tell('JSON格式无效：'+x.message);}});
$('robot-table').onclick=e=>{
 const bam=e.target.closest('[data-bam]');if(bam){const i=bam.dataset.bam,k=bam.dataset.key;const value=studioDraft.robot.actuator_parameters?.[i]?.[k]??studioData.baseline.model.actuators[i].parameter_file.data[k];bam.closest('tr').children[4].innerHTML=`<input class="config-edit" aria-label="BAM覆盖值" value="${value}" data-bam-apply="${i}" data-key="${esc(k)}">`;return;}const b=e.target.closest('[data-body]');if(!b)return;studioBody=b.dataset.body;const raw=effectiveStudioModel().bodies.find(x=>x.name===studioBody),ov=studioDraft.robot.bodies?.[studioBody]||{};
 $('body-edit-title').textContent='编辑 '+(bodyNames[studioBody]||'刚体')+'（'+studioBody+'） · SI单位';$('body-edit-fields').innerHTML=[['mass','质量 / kg',raw.mass_kg],['ipos','重心 [x,y,z] / m',raw.ipos],['inertia','主惯量 [I1,I2,I3] / kg·m²',raw.inertia],['iquat','惯性旋转 [w,x,y,z]',raw.iquat],['pos','相对父体位置 [x,y,z] / m',raw.pos],['quat','相对父体旋转 [w,x,y,z]',raw.quat]].map(([k,label,v])=>`<label>${esc(label)}<input data-body-field="${k}" value="${esc(sj(ov[k]??v))}"></label>`).join('');$('body-editor').hidden=false;$('body-editor').scrollIntoView({block:'center',behavior:'smooth'});};
$('robot-table').addEventListener('change',e=>{const apply=e.target.closest('[data-bam-apply]');if(!apply)return;const value=Number(apply.value);if(!apply.value.trim()||!Number.isFinite(value)){apply.setCustomValidity('请输入有限数字');apply.reportValidity();return;}apply.setCustomValidity('');studioDraft.robot.actuator_parameters??={};studioDraft.robot.actuator_parameters[apply.dataset.bamApply]??={};studioDraft.robot.actuator_parameters[apply.dataset.bamApply][apply.dataset.key]=value;$('robot-overrides').value=pretty(studioDraft.robot);markDirty();});
$('robot-table').addEventListener('input',e=>{if(e.target.id!=='servo-register-search')return;const q=e.target.value.trim().toLowerCase();for(const tr of document.querySelectorAll('#servo-register-table tbody tr'))tr.hidden=!tr.textContent.toLowerCase().includes(q);});
$('body-edit-fields').addEventListener('change',e=>{const input=e.target.closest('[data-body-field]');if(!input)return;try{const field=input.dataset.bodyField,value=field==='mass'?Number(input.value):JSON.parse(input.value);if(field==='mass'&&(!input.value.trim()||!Number.isFinite(value)||value<=0))throw Error('质量须大于0');studioDraft.robot.bodies??={};studioDraft.robot.bodies[studioBody]??={};studioDraft.robot.bodies[studioBody][field]=value;$('robot-overrides').value=pretty(studioDraft.robot);input.setCustomValidity('');markDirty();renderStudioTables();}catch(error){input.setCustomValidity(error.message);input.reportValidity();}});
$('body-edit-cancel').onclick=()=>{$('body-editor').hidden=true;};
window.studioRender=()=>{
 renderStudioChecks();if(!state)return;
 repairTaskConfiguration();
 const key=state.jobs.slice(0,8).map(j=>j.id+j.status).join('|');if(key!==studioStamp){studioStamp=key;if(!studioDirty&&!savePromise)studioLoad();}
 if($('follow-latest').checked&&!viewerLaunching){
   const train=state.jobs.find(j=>j.op==='train'&&active(j)),cp=train?.checkpoints?.at(-1),v=viewer();
   if(cp&&(!v||v.status==='running'&&v.op==='play'&&v.request.source_job===train.id)){
     const id=train.id+cp.path;
     if(id!==followStamp&&(!v||v.request.checkpoint!==cp.path)){
       followStamp=id;
       startViewer('/api/play',{source_job:train.id,checkpoint:cp.path,eval_pushes:false},true).then(result=>{if(!result&&followStamp===id)followStamp='';});
     }
   }
 }
};
studioLoad(true);

$('train-form').addEventListener('input',()=>{if(studioData?.frozen){studioData.frozen=null;$('studio-status').textContent='使用页面当前参数';}window.renderTrainingQueue?.();});

'use strict';
let contactSettingsStamp='';
const contactGroups=[
 {title:'接触面 / Contact surface',fields:[
  ['足底摩擦随机范围','Foot friction range',['env','events','foot_friction','params','ranges'],'按事件安排抽样的绝对摩擦系数；不是舵机摩擦倍率。'],
  ['足底摩擦抽样时机','Foot friction sampling mode',['env','events','foot_friction','mode'],'startup：创建环境时抽样；reset：每次环境复位时抽样。'],
  ['左右脚共用抽样','Shared foot friction',['env','events','foot_friction','params','shared_random'],'同一环境的两只脚使用同一次抽样。'],
  ['足底接触维度','Foot contact dimension',['env','scene','entities','robot','collisions',0,'condim','^(left|right)_foot_collision$'],'1：法向；3：加入滑动摩擦；4/6：再加入扭转/滚动摩擦。'],
  ['身体接触维度','Body contact dimension',['env','scene','entities','robot','collisions',0,'condim','.*_collision'],'身体的碰撞设置；脚掌采用上面的单独设置。'],
  ['接触软硬与阻尼','Contact solver reference',['env','scene','entities','robot','collisions',0,'solref'],'留空沿用模型的接触响应；编译值见下方足底读回。'],
  ['接触阻抗曲线','Contact solver impedance',['env','scene','entities','robot','collisions',0,'solimp'],'控制接触约束随穿透变化的响应，不是舵机电气阻抗。']
 ]},
 {title:'物理求解与显存 / Physics & GPU buffers',fields:[
  ['接触缓冲上限','Contact capacity · nconmax',['env','sim','nconmax'],'每个环境的接触缓冲容量；越大越占显存，不是动作或摩擦强度。'],
  ['约束缓冲上限','Constraint capacity · njmax',['env','sim','njmax'],'每个环境的约束存储容量，包括接触和关节约束。'],
  ['接触传感器匹配上限','Contact sensor max matches',['env','sim','contact_sensor_maxmatch'],'接触传感器可匹配的接触数量上限。'],
  ['凸碰撞检测迭代上限','CCD iterations',['env','sim','mujoco','ccd_iterations'],'每次碰撞检测的迭代预算；不是训练轮数。'],
  ['物理步长 / 秒','Physics timestep / s',['env','sim','mujoco','timestep'],'每次物理积分的时间；改变它会影响舵机延迟等模型。']
 ]},
 {title:'相关随机化 / Domain randomization',fields:[
  ['舵机摩擦倍率','BAM friction scale range',['env','events','randomize_joint_friction','params','scale_range'],'每次复位随机缩放 BAM 摩擦，和足底接触摩擦分开。'],
  ['转子惯量倍率','Armature scale range',['env','events','randomize_armature','params','ranges'],'每次复位缩放关节转子惯量。'],
  ['编码器零位误差 / rad','Encoder bias range / rad',['env','events','encoder_bias','params','bias_range'],'模拟反馈零位误差；不会修改本机舵机标定。']
 ]}
];
const contactGet=(tree,path)=>path.reduce((v,k)=>v?.[k],tree);
const contactValue=v=>v===undefined?'本动作未设置':v===null?'沿用模型':typeof v==='boolean'?(v?'开启':'关闭'):typeof v==='object'?JSON.stringify(v):String(v);
function renderContactSettings(){
 if(!studioData||!studioDraft)return;
 const task=$('task').value,schema=taskSchema(task)?.inspection;
 const base=schema?.full,planned=base?structuredClone(base):null;
 const overrides=studioDraft.task_overrides?.[task]||(task==='Mjlab-Velocity-Flat-MicroDuck'?studioDraft.overrides:[])||[];
 for(const edit of overrides){
  const parent=contactGet(planned,edit.path.slice(0,-1));
  if(parent&&Object.hasOwn(parent,edit.path.at(-1)))parent[edit.path.at(-1)]=structuredClone(edit.value);
 }
 const run=state?.jobs.find(j=>j.op==='train'&&active(j));
 const actual=run?.effective_config?.resolved;
 const key=JSON.stringify([task,schema?.sha256,overrides,run?.id,actual?.sha256,actual]);
 if(key===contactSettingsStamp)return;
 if(document.activeElement?.matches('[data-contact-input]'))return;
 contactSettingsStamp=key;
 const name=taskCatalog.tasks.find(t=>t.id===task)?.name||task;
 $('contact-settings-source').textContent='待加入方案：'+name+(run?' · 运行读回：'+(run.request.label||taskCatalog.tasks.find(t=>t.id===run.request.task)?.name||run.request.task):'');
 if(!planned){$('contact-settings-table').innerHTML='<p class="hint">正在读取随包任务参数…</p>';return;}
 let html=contactGroups.map(group=>{
  const rows=group.fields.map(([cn,en,path,meaning])=>{
   const source=contactGet(base,path),value=contactGet(planned,path),readback=contactGet(actual?.full,path);
   const editable=schema.rows?.some(r=>r.editable&&sj(r.path)===sj(path));
   const control=editable?'<button type="button" class="text-button" data-contact-edit="'+esc(JSON.stringify(path))+'">修改</button>':'';
   return row(['<strong>'+esc(cn)+'</strong><small lang="en">'+esc(en)+'</small>',
    '<span class="contact-value">'+esc(contactValue(value))+'</span>'+control+'<small>官方默认 '+esc(contactValue(source))+'</small>',
    esc(actual?contactValue(readback):run?'尚未读回':'未启动'),
    esc(meaning)]);
  });
  return '<h4>'+group.title+'</h4>'+table(['参数 / Parameter','下次加入队列的值','正在训练的配置','用途'],rows);
 }).join('');
 const terrains=planned.env?.scene?.terrain?.terrain_generator?.sub_terrains;
 const terrainNames={flat:'平地 / Flat',pyramid_stairs:'台阶 / Stairs',random_grid:'随机凸起 / Random grid',pyramid_slope:'斜坡 / Slope'};
 html+='<h4>地形组成 / Terrain composition</h4>';
 if(!terrains)html+='<p class="form-note">本动作使用平地 / Plane，没有粗糙地形高度课程。</p>';
 else html+=table(['地形 / Terrain','比例','高度 / 坡度范围','用途'],Object.entries(terrains).map(([k,t])=>{
  const range=t.step_height_range||t.grid_height_range||t.slope_range;
  return row([esc(terrainNames[k]||k),esc((t.proportion*100).toFixed(0)+'%'),range?esc(JSON.stringify(range)+(t.slope_range?'（坡度比）':' m')):'0 m','源自所选官方任务配方']);
 }));
 const geoms=actual?.model?.entity_compiled?.geoms;
 html+='<h4>足底编译基线与运行读回 / Compiled foot contacts</h4>';
 const referenceGeoms=schema.model?.entity_compiled?.geoms;
 html+=table(['脚掌 / Foot','摩擦 [滑动, 扭转, 滚动]','维度','solref','solimp'],['left_foot_collision','right_foot_collision'].map(n=>{
  const g=geoms?.find(g=>g.name===n);
  const ref=referenceGeoms?.find(g=>g.name===n);
  return row([esc(n.startsWith('left')?'左脚 / Left':'右脚 / Right'),...['friction','condim','solref','solimp'].map(k=>'<span>'+esc(ref?contactValue(ref[k]):'基线未采集')+'</span><small>运行：'+esc(g?contactValue(g[k]):'未采集')+'</small>')]);
 }));
 html+='<p class="form-note">运行配置显示启动时的范围与模型构建值，不是每只鸭子当前抽到的摩擦值。编辑只影响下一次加入队列，已加入或正在训练的方案保留原值。</p>';
 $('contact-settings-table').innerHTML=html;
}
$('contact-settings-table').onclick=e=>{
 const b=e.target.closest('[data-contact-edit]');if(!b)return;
 const path=JSON.parse(b.dataset.contactEdit),base=taskSchema()?.inspection?.full;
 const existing=(studioDraft.task_overrides?.[$('task').value]||[]).find(p=>sj(p.path)===sj(path));
 const input=document.createElement('input');input.className='config-edit';input.dataset.contactInput=b.dataset.contactEdit;input.value=JSON.stringify(existing?existing.value:contactGet(base,path));input.setAttribute('aria-label',b.closest('tr').cells[0].textContent);
 b.closest('td').replaceChildren(input);input.focus();input.select();
};
$('contact-settings-table').onchange=async e=>{
 const input=e.target.closest('[data-contact-input]');if(!input)return;
 try{
  const path=JSON.parse(input.dataset.contactInput),value=JSON.parse(input.value);
  const original=contactGet(taskSchema()?.inspection?.full,path);
  if(typeof original==='boolean'&&typeof value!=='boolean')throw Error('请输入 true 或 false。');
  if(path.at(-1)==='mode'&&!['startup','reset'].includes(value))throw Error('这里可设 startup 或 reset。');
  if(value!==null&&typeof value==='number'&&(!Number.isFinite(value)||value<=0))throw Error('请输入大于0的数值。');
  if(['nconmax','njmax','contact_sensor_maxmatch','ccd_iterations','condim'].some(k=>path.includes(k))&&(!Number.isInteger(value)||value<1))throw Error('请输入正整数。');
  if(path.includes('condim')&&![1,3,4,6].includes(value))throw Error('接触维度只支持 1、3、4、6。');
  if(path.at(-1)==='ranges'||path.at(-1)==='scale_range'||path.at(-1)==='bias_range'){
   if(!Array.isArray(value)||value.length!==2||!value.every(Number.isFinite)||value[0]>value[1]||(path.at(-1)!=='bias_range'&&value[0]<=0))throw Error('请输入有序范围，例如 [0.7,1.3]。');
  }
  input.setCustomValidity('');
  const overrides=(studioDraft.task_overrides?.[$('task').value]||[]).filter(p=>sj(p.path)!==sj(path));
  overrides.push({path,value});configOverridesText=pretty(overrides);gatherStudio();markDirty();
  input.blur();contactSettingsStamp='';renderContactSettings();renderConfigTable();
 }catch(error){input.setCustomValidity(error.message);input.reportValidity();tell(error.message);}
};
