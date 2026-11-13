import assert from 'node:assert/strict';
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import {pathToFileURL} from 'node:url';
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'duck-install-'));
try{
 const source=path.resolve(process.argv[2]||'static');fs.cpSync(source,path.join(tmp,'static'),{recursive:true});fs.writeFileSync(path.join(tmp,'package.json'),' {"type":"module"}');
 const {FirmwarePanel}=await import(pathToFileURL(path.join(tmp,'static/firmware.js')));
 const nodes=new Map();const get=id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',hidden:false,value:0,classList:{add(){},toggle(){}}});return nodes.get(id);};
 const panel=Object.create(FirmwarePanel.prototype);Object.assign(panel,{$:get,paint(){}});
 panel.render({service_control:{job:{action:'upgrade-service',status:'running',message:'上传固件 · 进行中',transfer_progress:{step:'上传固件',percent:40,bytes:4*1048576,total:10*1048576,detail:'等待 Zero 写入与校验'}}}},{});
 assert.equal(get('transfer').hidden,false);assert.equal(get('progress').value,40);assert.match(get('progress-text').textContent,/40%.*4.0 \/ 10.0 MiB/);assert.match(get('status').textContent,/上传固件/);
 panel.render({service_control:{job:{action:'upgrade-service',status:'running',message:'解压固件 · 开始',transfer_progress:{step:'校验上传',percent:100,bytes:10,total:10,detail:'SHA256 一致'}}}},{});
 assert.equal(get('progress').value,100);assert.equal(get('status').textContent,'解压固件 · 开始');
 panel.render({service_control:{job:{action:'upgrade-service',status:'error',error:'固件解压失败：damaged archive',transfer_progress:{step:'校验上传',percent:100,bytes:10,total:10,detail:'SHA256 一致'}}}},{});
 assert.match(get('status').textContent,/damaged archive/);assert.doesNotMatch(get('status').textContent,/已完成/);
 panel.render({service_control:{job:{action:'upgrade-service',status:'completed',result:{input:{status:'error'}}}}},{});
 assert.match(get('status').textContent,/已完成.*手动重新连接/);
 panel.render({service_control:{job:{action:'reconnect-service',status:'running'}}},{});assert.equal(get('transfer').hidden,true);
 const js=fs.readFileSync(path.join(source,'firmware.js'),'utf8');assert.match(js,/<progress id="firmware-progress"/);assert.doesNotMatch(js,/setInterval|setTimeout\(/);
 console.log('PASS actual byte progress, retained completed transfer, per-stage status, original failure reason, manual connection recovery, no added UI polling');
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
