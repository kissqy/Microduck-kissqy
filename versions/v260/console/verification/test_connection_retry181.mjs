import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-173-'));
try{
  const source=path.resolve(process.argv[2]||'console/static');
  fs.cpSync(source,path.join(temp,'static'),{recursive:true});
  fs.writeFileSync(path.join(temp,'package.json'),'{"type":"module"}');
  const load=n=>import(pathToFileURL(path.join(temp,'static',n)));
  const {ConnectionRetry}=await load('connection-retry.js');
  let now=0;const retry=new ConnectionRetry(()=>now);
  for(let i=0;i<4;i++){
    assert.equal(retry.ready,true);retry.connected();now+=1;retry.failed();
    now+=9999;assert.equal(retry.ready,false);now+=1;
  }
  now+=1000000;assert.equal(retry.ready,false);assert.equal(retry.exhausted,true);
  const {ControlPanel}=await load('control.js');
  const pad=Object.create(ControlPanel.prototype);let calls=0;
  Object.assign(pad,{reconnect:new ConnectionRetry(()=>now),connecting:false,linkEpoch:0,
    sessionUsed:false,servicePaused:()=>false,paint(){},s:{},feedback:{textContent:'',classList:{remove(){},add(){},toggle(){}},setAttribute(){}},
    socket:{close(){},async open(){}},async post(){calls++;throw Error('SSH refused');}});
  for(let i=0;i<4;i++){
    await pad.connect();await pad.connect();assert.equal(calls,i+1);now+=10000;
  }
  for(let i=0;i<100;i++){now+=10000;await pad.connect();}
  assert.equal(calls,4,'UI stops after three retries');
  pad.resetConnectionRetry();await pad.connect();assert.equal(calls,5,'explicit reconnect starts a new budget');


  const stable=new ConnectionRetry(()=>now);stable.failed();now+=10000;stable.connected();now+=30000;stable.failed();assert.equal(stable.failures,1);
  const {ServiceManagement}=await load('service-management.js');
  let fetches=0;globalThis.fetch=async()=>{fetches++;throw Error('SSH offline');};
  const el={textContent:'',classList:{remove(){},add(){},toggle(){}},setAttribute(){}};
  const panel=Object.create(ServiceManagement.prototype);
  Object.assign(panel,{cfg:{control_token:'fixture'},supported:true,loading:false,connectionLoading:false,
    queryRetry:new ConnectionRetry(()=>now),processRetry:new ConnectionRetry(()=>now),paint(){},$:()=>el});
  for(let i=0;i<4;i++){
    await panel.refresh(true);await panel.refresh(true);await panel.refreshConnection();await panel.refreshConnection();
    assert.equal(fetches,2*(i+1));now+=10000;
  }
  await panel.refresh(true);await panel.refreshConnection();assert.equal(fetches,8);
  panel.invalidate();await panel.refresh(true);await panel.refreshConnection();assert.equal(fetches,10);
  console.log(JSON.stringify({frontend_retry:'passed',management_query_retry:'passed',flapping_limit:'passed',stable_reset:'passed',manual_reset:'passed'}));
}finally{fs.rmSync(temp,{recursive:true,force:true});}
