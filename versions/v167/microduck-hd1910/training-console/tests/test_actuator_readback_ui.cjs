'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const text=fs.readFileSync(path.join(root,'training/static/studio.js'),'utf8');
const i=text.indexOf('function renderActuators(m){'),j=text.indexOf('function renderStudioTables(){',i);
assert(i!==-1&&j>i,'Could not locate real actuator renderer');
const ref=JSON.parse(fs.readFileSync(path.join(root,'data/servo_references.json'),'utf8'));
const baseline=JSON.parse(fs.readFileSync(path.join(root,'data/baseline_official0151.json'),'utf8'));
const task='Mjlab-Velocity-Flat-MicroDuck';
const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
let selected=task,job=null;
const ctx={
 studioData:{servo_references:ref,baseline},
 studioDraft:{task_overrides:{},robot:{}},
 training:()=>job,
 runName:()=> '测试任务',
 $:()=>({value:selected}),
 esc,structuredClone,
};
vm.createContext(ctx);
vm.runInContext(`const configValue=v=>v===null?'null':typeof v==='object'?JSON.stringify(v):String(v);
const val=v=>v==null?'未取得':typeof v==='object'?JSON.stringify(v):String(v);
const table=(heads,rows)=>'<table><thead>'+heads.map(s=>'<th>'+esc(s)+'</th>').join('')+'</thead><tbody>'+rows.join('')+'</tbody></table>';
const row=cols=>'<tr>'+cols.map(s=>'<td>'+s+'</td>').join('')+'</tr>';
const cells=items=>items.map(s=>esc(val(s)));
${text.slice(i,j)}`,ctx);
const html=()=>vm.runInContext('renderActuators(studioData.baseline.model)',ctx);
const readback={model:{actuators:[structuredClone(baseline.model.actuators[0])]}};
readback.model.actuators[0].runtime_properties.implementation='HD1910Actuator';
function run(t,config){return {op:'train',request:{task:t},effective_config:config?{resolved:config}:undefined};}
job=null;
let out=html();
assert.doesNotMatch(out,/<th>本次训练读回<\/th>/);
assert.doesNotMatch(out,/旧记录未采集的值显示/);
assert.doesNotMatch(out,/训练仿真配置读回/);
assert.match(out,/XL330 与 HD1910 使用不同的仿真控制参数/);
job=run(task);out=html();
assert.doesNotMatch(out,/<th>本次训练读回<\/th>/,'uninitialized task must not show empty readback');
job=run('Mjlab-StandUp-Flat-MicroDuck',readback);out=html();
assert.doesNotMatch(out,/<th>本次训练读回<\/th>/,'must not leak readback from another active task');
job=run(task,readback);out=html();
assert.equal((out.match(/<th>本次训练读回<\/th>/g)||[]).length,2,'show recorded columns in controller and M6 tables');
assert.match(out,/训练仿真配置读回：测试任务（来自该任务的启动记录，非真机读数）/);
assert.match(out,/HD1910Actuator/);
assert.match(out,/0\.623/); // actual model and M6 values from the frozen sample
selected='Mjlab-Velocity-Flat-MicroDuck-Rollers';out=html();
assert.doesNotMatch(out,/<th>本次训练读回<\/th>/,'task switching must not show stale values');
console.log('ACTUATOR_READBACK_UI_OK: no run; uninitialized; unrelated run; matching snapshot; task switch; legacy UI text');
