// R1.5.21-CalibUI1: run ORIGINAL dashboard rendering code against realistic ZERO changes.
// No external npm dependencies, no network/robot/training worker.
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'training/static/studio.js'),'utf8');
const css=fs.readFileSync(path.join(root,'training/static/workflow.css'),'utf8');
const hardware=JSON.parse(fs.readFileSync(path.join(root,'data/hardware.json'),'utf8'));
function sliceBetween(a,b){const i=source.indexOf(a),j=source.indexOf(b);assert(i>=0&&j>i,[a,b]);return source.slice(i,j);}
const helperCode=sliceBetween('const jointNames=','function setExpertSettings(');
const functionCode=sliceBetween('function renderStudioTables(){','function currentConfigRows()');
const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const ui={};const el=id=>ui[id]??={classList:{toggle(){}},textContent:'',innerHTML:''};
const context={
 console,
 esc,studioData:{hardware},studioDraft:{calibration:structuredClone(hardware.current_calibration)},
 studioTab:'none',bodyNames:{trunk_base:'躯干总成'},
 $:el,document:{querySelectorAll:()=>[]},
 effectiveStudioModel:()=>({total_mass_kg:0.82,bodies:[],joints:[]}),
 renderConfigTable:()=>{},
};
vm.createContext(context);
vm.runInContext(`const val=v=>v===null||v===undefined?'未取得':typeof v==='object'?JSON.stringify(v):String(v);\nconst row=cells=>'<tr>'+cells.map(v=>'<td>'+v+'</td>').join('')+'</tr>';
const cells=values=>values.map(v=>esc(v));\nconst table=(headers,rows)=>'<table class="studio-table"><thead><tr>'+headers.map(h=>'<th>'+h+'</th>').join('')+'</tr></thead><tbody>'+rows.join('')+'</tbody></table>';\n${helperCode}\n${functionCode}`,context);
const render=()=>vm.runInContext('renderStudioTables()',context);
function setDiff(mods){
 const before=structuredClone(hardware.current_calibration);
 const changes=[];
 for(const joint of before.data.joints){
  if(!mods[joint.name])continue;
  const fields={};for(const [field,after] of Object.entries(mods[joint.name])){
   fields[field]={before:joint[field],after};assert.notEqual(joint[field],after);joint[field]=after;
  }
  changes.push({name:joint.name,id:joint.id,fields});
 }
 before.changes={joints:changes,imu_changed:false};context.studioDraft.calibration=before;render();return el('calibration-table').innerHTML;
}
const rowHtml=(html,name)=>{
 const rows=html.match(/<tr>[\s\S]*?<\/tr>/g)||[];
 return rows.find(x=>x.includes(`<small class="model-name">${name}</small>`))||'';
};
const changedFields=html=>[...html.matchAll(/class="calibration-value calibration-value-changed" data-calibration-field="([^"]+)"/g)].map(m=>m[1]);
assert.equal(hardware.joints.length,15);
let html=setDiff({});assert.equal(changedFields(html).length,0);
assert.match(rowHtml(html,'left_hip_yaw'),/左髋旋转/);assert.match(rowHtml(html,'left_hip_yaw'),/（ID <span/);
assert.match(rowHtml(html,'right_hip_yaw'),/右髋旋转/);
assert.match(rowHtml(html,'head_yaw'),/头部转向/);
assert.match(rowHtml(html,'head_roll'),/头部侧倾/);
assert.match(html,/机械下限 \/ °/);assert.match(html,/机械上限 \/ °/);
assert.match(rowHtml(html,'left_hip_yaw'),/−25°/);assert.match(rowHtml(html,'left_hip_yaw'),/\+30°/);
assert.doesNotMatch(rowHtml(html,'left_hip_yaw'),/−0\.436332|0\.523599/);
const cases=[
 ['direction_only',{left_hip_yaw:{direction:-1}},['direction'],'left_hip_yaw',/原 <span[^>]*>\+1<\/span>/],
 ['zero_only',{left_hip_yaw:{zero_raw:2077}},['zero_raw'],'left_hip_yaw',/原 <span[^>]*>2035<\/span>/],
 ['min_only',{right_hip_yaw:{min_rad:-.4}},['min_rad'],'right_hip_yaw',/原 <span/],
 ['max_only',{right_hip_yaw:{max_rad:.4}},['max_rad'],'right_hip_yaw',/原 <span/],
 ['id_only',{head_yaw:{id:132}},['id'],'head_yaw',/原 <span[^>]*>32<\/span>/],
 ['calibrated_only',{head_roll:{calibrated:false}},['calibrated'],'head_roll',/原 <span[^>]*>已标定<\/span>/],
 ['mixed',{left_hip_yaw:{direction:-1},right_hip_yaw:{zero_raw:2012},head_yaw:{max_rad:1.5}},['direction','zero_raw','max_rad'],null,null],
];
for(const [name,changes,expect,sourceRow,previous] of cases){
 html=setDiff(changes);
 assert.deepEqual(changedFields(html).sort(),expect.slice().sort(),name);
 if(sourceRow){
  const row=rowHtml(html,sourceRow);assert(previous.test(row),name+' missing previous value');
  assert.equal((row.match(/calibration-value-changed/g)||[]).length,1,name+' wrong field changed');
 }
 if(name==='min_only'){
  assert.match(rowHtml(html,sourceRow),/−22\.92°/);
  assert.match(rowHtml(html,sourceRow),/原 <span[^>]*>−30°<\/span>/);
 }
 if(name==='max_only'){
  assert.match(rowHtml(html,sourceRow),/\+22\.92°/);
  assert.match(rowHtml(html,sourceRow),/原 <span[^>]*>\+25°<\/span>/);
 }
 assert.equal((html.match(/class="calibration-old"/g)||[]).length,expect.length,name);
 assert(!html.includes('class="calibration-changed"'),name+' highlighted whole row');
 assert(html.includes(`${expect.length} 项字段不同`),name);
 console.log('PASS',name,changedFields(html).join(','));
}
assert(!css.includes('#calibration-table tr.calibration-changed td:nth-child(4)'),'old zero-only rule still exists');
assert(!css.includes('#calibration-table tr.calibration-changed{'),'old full-row styling still exists');
assert.match(css,/#calibration-table \.calibration-value-changed/);
const robotView=vm.runInContext(`studioTab='joints';effectiveStudioModel=()=>({total_mass_kg:0.82,bodies:[],joints:[{name:'left_hip_yaw',body:'trunk_base',body_mass_g:400,home_deg:0,limited:true,range:[-.4,.5],axis:[0,0,1],pos:[0,0,0]}]});renderStudioTables();$('robot-table').innerHTML;`,context);
assert.match(robotView,/左髋旋转/);assert.match(robotView,/ID 20/);assert.match(robotView,/left_hip_yaw/);
assert.match(robotView,/模型范围 \/ °/);assert.match(robotView,/−22\.92° ～ \+28\.65°/);
assert.doesNotMatch(robotView,/−0\.4,0\.5/);
console.log('CALIBRATION_UI_OK: 15 servo IDs; 7 diff cases; min/max degrees including old/new; model degree ranges; backend untouched');
