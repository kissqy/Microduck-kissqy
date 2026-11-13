import assert from 'node:assert/strict';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const source=path.resolve(process.argv[2]||'static');
const {ServicePanel}=await import(pathToFileURL(path.join(source,'service.js')));
const command={action:'center',unassembled:true,duration_ms:2000};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
class Dialog extends EventTarget {
  constructor(){super();this.nodes=new Map();this.open=false;this.removed=false;}
  querySelector(id){if(!this.nodes.has(id))this.nodes.set(id,new EventTarget());return this.nodes.get(id);}
  showModal(){this.open=true;}
  close(){this.open=false;this.dispatchEvent(new Event('close'));}
  remove(){this.removed=true;}
  setAttribute(){}
  click(id){this.querySelector(id).dispatchEvent(new Event('click'));}
}
let panel,calls,dialogs,nativeConfirms;
function setup(){
  calls=[];dialogs=[];nativeConfirms=0;
  const nodes=new Map();
  globalThis.document={hidden:false,body:{append(node){dialogs.push(node);}},createElement(name){assert.equal(name,'dialog');return new Dialog();}};
  globalThis.fetch=async(url,options)=>{calls.push(JSON.parse(options.body).command.action);return {ok:true,json:async()=>({accepted:true,message:'accepted'})};};
  // Windows native dialogs can enqueue a window blur after confirm returns.
  // The old listener then cancels the newly submitted center job.
  globalThis.confirm=()=>{nativeConfirms++;queueMicrotask(()=>panel.suspend());return true;};
  panel=Object.assign(Object.create(ServicePanel.prototype),{
    cfg:{service_enabled:true,control_token:'test'},options:{},client:'center185test',seq:0,
    blocked:false,posting:false,ownsMotion:false,lastSample:performance.now(),
    $(id){if(!nodes.has(id))nodes.set(id,{checked:true,disabled:false,value:''});return nodes.get(id);},
    paint(){},feedback(){},
  });
}
async function start(){const pending=panel.post({...command});await flush();return {pending};}
function finish(){dialogs.at(-1)?.click('[data-center-confirm]');}

setup();
let {pending}=await start();finish();await pending;await flush();
assert.deepEqual(calls,['center'],'confirmation must not send an automatic relax immediately after center');
assert.equal(nativeConfirms,0,'center must use an in-page confirmation');
assert.equal(panel.ownsMotion,true);
panel.suspend();await flush();assert.deepEqual(calls,['center','relax'],'real loss of page control must still stop motion');
panel.suspend();await flush();assert.equal(calls.length,2,'repeated suspend must not send duplicate stops');

setup();({pending}=await start());assert.equal(calls.length,0);
dialogs[0].click('[data-center-cancel]');await pending;assert.deepEqual(calls,[]);assert.equal(dialogs[0].removed,true);

setup();({pending}=await start());dialogs[0].dispatchEvent(new Event('cancel',{cancelable:true}));await pending;assert.deepEqual(calls,[]);

setup();({pending}=await start());panel.suspend();await pending;finish();await flush();assert.deepEqual(calls,[],'leaving during confirmation must cancel without starting later');

setup();({pending}=await start());await panel.post({...command});assert.equal(dialogs.length,1,'double click must not open a second dialog');
finish();await pending;assert.deepEqual(calls,['center']);

for(const invalid of ['offline','stale','unchecked','hidden','busy']){
  setup();({pending}=await start());
  if(invalid==='offline'){panel.options.offline=true;panel.blocked=true;}
  if(invalid==='stale')panel.lastSample=performance.now()-3000;
  if(invalid==='unchecked')panel.$('service-unassembled').checked=false;
  if(invalid==='hidden')document.hidden=true;
  if(invalid==='busy')panel.posting=true;
  finish();await pending;assert.deepEqual(calls,[],`changed ${invalid} state must be rechecked before submission`);
}

setup();({pending}=await start());await panel.post({action:'relax'});await pending;finish();await flush();assert.deepEqual(calls,['relax'],'explicit stop during confirmation must prevent a later center');
console.log(JSON.stringify({state_recheck_cases:5,confirmation_does_not_stop_its_own_center:true,cancel_escape_and_page_exit_send_no_center:true,duplicate_submit_blocked:true,fresh_state_rechecked:true,explicit_and_lifecycle_stop_preserved:true}));
