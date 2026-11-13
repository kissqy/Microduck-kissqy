'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
const html=read('training/static/index.html'),js=read('training/static/training.js');
assert(html.includes('data-ui-revision="R1.5.27"'));
for(const id of ['target-limit-card','target-limit-start','target-limit-recorded-start','target-limit-file','recovery-eval-start','recovery-eval-note','target-limit-note']){
 assert(!html.includes('id="'+id+'"'),id+' remains in DOM');
 assert(!js.includes("$('"+id+"')"),id+' still has handler');
}
for(const id of ['sim-command-unit','official-policy-references','official-reference-detail'])assert(html.includes('id="'+id+'"'),id);
assert(js.includes('roller_crouch.onnx')&&js.includes('roller.onnx'));
const a=js.indexOf('function isRollerViewer(){'),b=js.indexOf('function renderSimTelemetry(){',a);
const d=js.indexOf('function driveRanges(){'),e=js.indexOf('function queueControl(',d);
assert(a>0&&b>a&&d>b&&e>d);
function ranges(id,live){
 const ctx=vm.createContext({j:{request:{task:id},sim_controls:{velocity_ranges:live}},taskCatalog:{tasks:[{id:'roller',role:'roller'},{id:'walk',role:'walk'},]},finite:v=>typeof v==='number'&&Number.isFinite(v)});
 vm.runInContext('function viewer(){return j;}\n'+js.slice(a,b)+'\n'+js.slice(d,e)+'\nthis.result=driveRanges();this.isRoller=isRollerViewer();',ctx);
 return {ranges:JSON.parse(JSON.stringify(ctx.result)),roller:ctx.isRoller};
}
assert.deepEqual(ranges('roller',[[-.5,.6],[0,0],[0,0]]),{ranges:[[-.5,.6],[0,0],[0,0]],roller:true});
assert.deepEqual(ranges('roller',[[-1,1],[-1,1],[-1,1]]),{ranges:[[-.5,.6],[0,0],[0,0]],roller:true});
assert.deepEqual(ranges('walk',[[-1,1],[-2,2],[-2,2]]),{ranges:[[-.4,.4],[-.3,.3],[-1,1]],roller:false});
assert(!js.includes('targetLimitJobId'));
console.log('R1524_UI_OK: specialist checks; roller [-0.5,+0.6]/0/0 and ordinary walk unchanged; official refs read-only');
