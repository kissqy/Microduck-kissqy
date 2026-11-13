import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-hotspot-ui44-'));
try{
  const source=path.resolve(process.argv[2]||'static');
  fs.cpSync(source,path.join(temporary,'static'),{recursive:true});
  fs.writeFileSync(path.join(temporary,'package.json'),'{"type":"module"}');
  const {FirmwarePanel}=await import(pathToFileURL(path.join(temporary,'static/firmware.js')));
  const {ServicePanel}=await import(pathToFileURL(path.join(temporary,'static/service.js')));
  // The feature tests exercise the existing service transport methods; the
  // unrelated firmware SHA verification is not a network prerequisite.
  FirmwarePanel.prototype.verify=function(){};
  const makeFixture=()=>{
    const nodes=new Map();
    const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
    class Element{
      constructor(){this.value='';this.disabled=false;this.textContent='';this.hidden=false;this.classList={add(){},toggle(){}};this.parentElement=this;this.children=[];}
      set innerHTML(value){this.html=value;for(const id of value.matchAll(/id="([^"]+)"/g))get(id[1]);}
      querySelector(selector){return get(selector.replace(/^#/,''));}
      closest(selector){return selector==='.service-power'?get('legacy-power'):this;}
      append(...nodes){for(const node of nodes){node.remove();this.children.push(node);node.parentElement=this;}}
      after(node){const parent=this.parentElement;node.remove();parent.children.splice(parent.children.indexOf(this)+1,0,node);node.parentElement=parent;}
      remove(){const parent=this.parentElement;if(parent!==this){const at=parent.children.indexOf(this);if(at>=0)parent.children.splice(at,1);}this.parentElement=this;}
      setAttribute(){}
    }
    globalThis.document={createElement:()=>new Element(),getElementById:get,hidden:false};
    const panel=Object.create(ServicePanel.prototype);
    const state={connection:{active:true,connected:true},bus:{},service_sample_fresh:false,service_control:{}};
    Object.assign(panel,{cfg:{service_enabled:true,control_token:'token'},options:{},s:state,
      lastSample:performance.now()-100000,blocked:true,client:'hotspot-ui-test',seq:0,posting:false,$:get});
    const powerRow=new Element();get('service-power-actions').append(powerRow);powerRow.append(get('service-reboot'),get('service-shutdown'),get('service-resume'));
    const firmware=new FirmwarePanel(panel);panel.firmware=firmware;
    panel.paint=()=>firmware.paint();
    const render=(s=state,options={})=>{panel.s=s;panel.options=options;firmware.render(s,options);};
    render();get('service-sudo-password').value='private-password';
    const sent=[];let confirmCount=0;
    globalThis.fetch=async(url,options)=>{sent.push({url,body:JSON.parse(options.body)});return {ok:true,json:async()=>({accepted:true,message:'指令已提交'})};};
    globalThis.confirm=message=>{confirmCount++;assert.ok(message.includes('清除已保存的 Wi‑Fi 连接信息（保留配网热点）'));assert.match(message,/停止动作并放稳机器人/);assert.match(message,/断开.*中控/);assert.match(message,/重新联网/);assert.match(message,/设置 Zero 登录密码/);return true;};
    return {panel,firmware,state,get,render,sent,confirms:()=>confirmCount};
  };

  {
    const f=makeFixture();
    assert.ok(f.firmware.root.html.indexOf('id="firmware-hotspot"')>f.firmware.root.html.indexOf('class="firmware-power"'),'hotspot starts in the lower power area rather than the upgrade toolbar');
    const row=f.get('service-resume').parentElement;
    assert.equal(f.get('firmware-hotspot').parentElement,row);
    assert.equal(row.children[row.children.indexOf(f.get('service-resume'))+1],f.get('firmware-hotspot'),'hotspot follows resume in the lower action row');
    assert.equal(f.get('firmware-hotspot').disabled,false,'authenticated SSH is sufficient even without IMU telemetry');
    globalThis.confirm=()=>false;
    await f.get('firmware-hotspot').onclick();
    assert.equal(f.sent.length,0,'cancel cannot submit the reset');
    assert.equal(f.get('firmware-hotspot-help').textContent,'');
  }
  {
    const f=makeFixture();
    await f.firmware.enableHotspot();
    assert.equal(f.confirms(),1);
    assert.equal(f.sent.length,1);
    assert.deepEqual(f.sent[0],{url:'/api/service',body:{client:'hotspot-ui-test',seq:1,command:{action:'enable-hotspot',supported:true,confirmed:true,sudo_password:'private-password'}}});
    assert.match(f.get('firmware-hotspot-status').textContent,/请求已提交/);
    assert.match(f.get('firmware-hotspot-status').textContent,/尚未确认热点已开启/);
    assert.ok(!f.get('firmware-hotspot-status').textContent.includes('private-password'));
    await f.firmware.enableHotspot();assert.equal(f.sent.length,1,'no second reset while the accepted request is pending');
    f.state.service_control={job:{action:'enable-hotspot',at:10,status:'completed',result:{accepted:true,queued:true,delay_seconds:5}}};
    f.state.connection={active:false,connected:false};f.state.connection_paused=true;f.render(f.state,{offline:true});
    assert.match(f.get('firmware-hotspot-status').textContent,/任务已调度/);
    assert.match(f.get('firmware-hotspot-status').textContent,/尚未确认热点已开启/);
    assert.equal(f.get('firmware-hotspot-help').hidden,false);
    assert.match(f.get('firmware-hotspot-help').textContent,/Microduck-kissqy.*12345678.*10\.42\.0\.1:8088/);
    assert.match(f.get('firmware-hotspot-help').textContent,/新 IP 和该密码/);
    assert.equal(f.sent.length,1,'offline render cannot retry networking');
    f.state.connection={active:true,connected:false};f.state.connection_paused=false;f.render();
    assert.equal(f.get('firmware-hotspot').disabled,true,'an unfinished SSH authentication cannot rearm the button');
    f.state.connection.connected=true;f.render();
    assert.equal(f.get('firmware-hotspot').disabled,false,'authenticated reconnection rearms this page without a refresh');
    assert.match(f.get('firmware-hotspot-status').textContent,/Zero 已重新连接/);
    f.render();f.render();
    assert.equal(f.get('firmware-hotspot').disabled,false,'the retained completion receipt cannot relock a reconnected page');
    assert.equal(f.sent.length,1,'connection recovery only rearms and never retries the reset');
    await f.firmware.enableHotspot();
    assert.equal(f.sent.length,2,'a later explicit click and confirmation can start a new reset');
    f.render();assert.equal(f.get('firmware-hotspot').disabled,true,'the previous queued receipt cannot count as the new request');
    assert.equal(f.firmware.hotspotQueued,false);
  }
  {
    const f=makeFixture();let resolve;
    globalThis.fetch=(url,options)=>{f.sent.push({url,body:JSON.parse(options.body)});return new Promise(done=>{resolve=done;});};
    const first=f.firmware.enableHotspot();
    assert.equal(f.sent.length,1);assert.equal(f.get('firmware-hotspot').disabled,true);
    await f.firmware.enableHotspot();assert.equal(f.sent.length,1);
    resolve({ok:true,json:async()=>({accepted:true,message:'已接收'})});await first;
  }
  {
    const f=makeFixture();
    for(const change of [
      ()=>f.state.connection={active:false,connected:false},
      ()=>f.state.connection={active:true,connected:false},
      ()=>f.state.connection_paused=true,
      ()=>f.state.service_control={busy:true},
      ()=>f.state.service_control={stopping:true},
      ()=>f.state.service_operation=true,
      ()=>f.panel.posting=true,
      ()=>f.panel.options={offline:true},
      ()=>f.panel.options={replay:true},
    ]){
      f.state.connection={active:true,connected:true};f.state.connection_paused=false;f.state.service_control={};f.state.service_operation=false;f.panel.posting=false;f.panel.options={};
      change();f.render(f.state,f.panel.options);
      assert.equal(f.get('firmware-hotspot').disabled,true);
      await f.firmware.enableHotspot();
      assert.equal(f.sent.length,0,'disabled network maintenance cannot submit');
    }
    // A direct call still checks a changed connection with a stale enabled DOM.
    f.get('firmware-hotspot').disabled=false;f.panel.options={};f.state.connection.connected=false;
    await f.panel.post({action:'enable-hotspot',supported:true,confirmed:true});assert.equal(f.sent.length,0);
  }
  {
    const f=makeFixture();
    globalThis.fetch=async()=>({ok:false,json:async()=>({accepted:false,error:'R5 配网脚本未安装'})});
    await f.firmware.enableHotspot();
    assert.match(f.get('firmware-hotspot-status').textContent,/请求未提交.*R5 配网脚本未安装/);
    assert.equal(f.get('firmware-hotspot').disabled,false,'a rejected request can be corrected and submitted manually');
    globalThis.fetch=async()=>{throw Error('connection lost');};
    await f.firmware.enableHotspot();
    assert.match(f.get('firmware-hotspot-status').textContent,/提交结果未确认.*先检查热点.*不会自动重试/);
    assert.equal(f.get('firmware-hotspot-help').hidden,false);
  }
  {
    const f=makeFixture();
    f.state.service_control={job:{action:'enable-hotspot',at:1,status:'error',error:'上次密码错误'}};f.render();
    assert.match(f.get('firmware-hotspot-status').textContent,/上次请求/);
    await f.firmware.enableHotspot();
    assert.match(f.get('firmware-hotspot-status').textContent,/请求已提交/,'an older error cannot overwrite a new accepted request');
    f.state.service_control={job:{action:'enable-hotspot',at:2,status:'error',error:'本次脚本校验失败'}};f.render();
    assert.match(f.get('firmware-hotspot-status').textContent,/本次脚本校验失败/);
    assert.equal(f.get('firmware-hotspot').disabled,false);
    // Live job completion may beat the HTTP receipt; the final state still uses
    // the verified job result rather than regressing to a generic accepted note.
    globalThis.fetch=async()=>{f.state.service_control={job:{action:'enable-hotspot',at:3,status:'completed',result:{hotspot:{queued:true}}}};f.render();return {ok:true,json:async()=>({accepted:true,message:'已接收'})};};
    await f.firmware.enableHotspot();assert.match(f.get('firmware-hotspot-status').textContent,/任务已调度/);
  }
  console.log('PASS hotspot confirmation/cancel, authenticated SSH without IMU, sudo submission once, busy/offline/replay gates, queued-vs-live wording, retained reconnect instructions, authenticated connection-cycle rearm without retry, rejection/unknown receipt and stale-job races');
}finally{
  fs.rmSync(temporary,{recursive:true,force:true});
}
