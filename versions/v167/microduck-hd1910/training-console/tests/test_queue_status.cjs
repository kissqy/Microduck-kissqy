const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const elements=new Map();
function el(id){if(!elements.has(id))elements.set(id,{value:id==='num-envs'?'2048':id==='iterations'?'2000':'walk',textContent:'',innerHTML:'',addEventListener(){}});return elements.get(id);}
const entry={id:'waiting',status:'waiting',request:{task:'walk',label:'行走老师',num_envs:2048,iterations:2000,training_action_scale:.7,training_firmware_p:3},recipe_sha256:'fixture'};
const state={jobs:[{id:'install',op:'setup',status:'running'}],training_queue:{enabled:true,failure_policy:'pause',entries:[entry]}};
const context=vm.createContext({window:{},state,console,Number,JSON,online:true,token:'fixture',selected:null,configView:false,
 taskCatalog:{tasks:[{id:'walk',name:'行走老师',terrain:'Flat'}]},$:el,active:j=>['starting','running','stopping'].includes(j.status),
 currentTrainingFirmwareP:()=>3,esc:x=>String(x??''),post:()=>{throw Error('render must not start training');}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../training/static/queue.js'),'utf8'),context);
assert.equal(el('train-start').textContent,'等待环境就绪');
assert.equal(el('train-stop').disabled,false);
assert.equal(el('train-start').disabled,true);
state.jobs=[];context.window.renderTrainingQueue();
assert.equal(el('train-start').textContent,'队列已启动');
state.jobs=[{id:'training',op:'train',status:'running',request:entry.request}];entry.status='running';entry.job_id='training';context.window.renderTrainingQueue();
assert.equal(el('train-start').textContent,'训练运行中');
state.jobs=[];state.training_queue.enabled=false;entry.status='failed';entry.message='当前训练机器尚未确认环境就绪';context.window.renderTrainingQueue();
assert.equal(el('train-start').textContent,'开始训练 ▶');
assert.match(el('queue-list').innerHTML,/重新训练/);
console.log('QUEUE_STATUS_OK: setup waits + queue enabled distinct from actual training + failed entry retains retry; no automatic POST');
