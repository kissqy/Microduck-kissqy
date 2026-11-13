import assert from 'node:assert/strict';
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import {pathToFileURL} from 'node:url';
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'robotd-first-'));
try {
 const source=path.resolve(process.argv[2]||'static');fs.cpSync(source,path.join(tmp,'static'),{recursive:true});fs.writeFileSync(path.join(tmp,'package.json'),'{"type":"module"}');
 const {ServiceManagement}=await import(pathToFileURL(path.join(tmp,'static/service-management.js')));
 const {TelemetryStore}=await import(pathToFileURL(path.join(tmp,'static/raw-telemetry.js')));
 const ready={steps:Object.fromEntries([1,2,3,4].map(n=>[n,{status:'success',detail:`ready ${n}`}]))};
 const store=new TelemetryStore({mode:'service',ids:[],names:[],labels:[]});store.ingest({channel:'startup',data:ready});store.ingest({channel:'state',data:{old:1}});
 store.ingest({channel:'robotd_stream',data:{preserve_startup:true}});
 assert.deepEqual(store.data.startup,ready);assert.equal(store.data.state,undefined);
 const m=Object.create(ServiceManagement.prototype);let processes=0,models=0;
 Object.assign(m,{cfg:{},panel:{},retryAfter:0,connectionAfter:0,catalog:null,lastJob:'',paint(){},refresh(){models++;},refreshConnection(){processes++;}});
 const snapshot={bus:{build:'1fa8438-feetech-ft6-control.36',mode:'motion'},startup:{steps:{4:{status:'success'}}}};
 m.render(snapshot,{});assert.equal(processes,0);assert.equal(models,0);
 m.render({...snapshot,startup:ready},{});assert.equal(processes,1);assert.equal(models,1);
 const late=Object.create(ServiceManagement.prototype);Object.assign(late,{cfg:{control_token:'test'},panel:{},paint(){},connectionLoading:false,connectionAfter:0,catalog:{models:[]},supported:false});
 const pending=[];globalThis.fetch=(_url,options)=>new Promise(resolve=>pending.push({resolve,signal:options.signal}));
 const old=late.refreshConnection();assert.equal(pending.length,1);late.invalidate();assert.equal(pending[0].signal.aborted,true);
 const current=late.refreshConnection();assert.equal(pending.length,2);
 pending[0].resolve({ok:true,json:async()=>({management_revision:'R17',pid:111})});await old;
 assert.equal(late.connection,null);assert.equal(late.connectionLoading,true,'old completion cannot release the new request');
 pending[1].resolve({ok:true,json:async()=>({management_revision:'R17',pid:222})});await current;
 assert.equal(late.connection.pid,222);assert.equal(late.connectionLoading,false);
 const text=fs.readFileSync(path.join(source,'service-management.js'),'utf8');assert.doesNotMatch(text,/setInterval/);
 console.log('PASS all-four-step query gate, startup preserved at data handoff, retired process response rejected, no readiness polling');
} finally {fs.rmSync(tmp,{recursive:true,force:true});}
