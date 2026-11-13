import assert from 'node:assert/strict';
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import {pathToFileURL} from 'node:url';
const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-pad-repair-ui-'));
try{
  fs.cpSync(path.resolve(process.argv[2]||'static'),path.join(temporary,'static'),{recursive:true});
  fs.writeFileSync(path.join(temporary,'package.json'),'{"type":"module"}');
  const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
  class Element{
    constructor(){this.value='';this.checked=false;this.disabled=false;this.textContent='';this.classList={add(){},toggle(){}};}
    set innerHTML(value){this.html=value;for(const id of value.matchAll(/id="([^"]+)"/g))get(id[1]);}
    querySelector(selector){return get(selector.replace(/^#/,''));}setAttribute(){}append(node){this.child=node;}after(node){this.sibling=node;}
  }
  globalThis.document={createElement:()=>new Element(),querySelector:get,hidden:false};
  const {GamepadRepair}=await import(pathToFileURL(path.join(temporary,'static/gamepad-repair.js')));
  const {ServicePanel}=await import(pathToFileURL(path.join(temporary,'static/service.js')));
  const panel=Object.create(ServicePanel.prototype);
  Object.assign(panel,{cfg:{service_enabled:true,control_token:'token'},options:{},s:{bus:{},service_sample_fresh:false},
    lastSample:performance.now()-100000,client:'gamepad-ui-test',seq:0,posting:false,$:get,paint:()=>repair.render()});
  const repair=new GamepadRepair(panel);
  panel.s.connection={active:false};repair.render();assert.equal(get('gamepad-repair-start').disabled,true);
  panel.s.connection={active:true,connected:false};
  repair.render();assert.equal(repair.root.hidden,true);assert.equal(get('gamepad-repair-start').disabled,false);
  repair.button.onclick();assert.equal(repair.root.hidden,false);
  assert.equal(get('gamepad-repair-start').disabled,false,'IMU telemetry is not a Bluetooth recovery gate');
  const sent=[];globalThis.fetch=async(url,options)=>{sent.push({url,payload:JSON.parse(options.body)});return {ok:true,json:async()=>({accepted:true,message:'已提交'})};};
  get('service-sudo-password').value='secret';get('gamepad-repair-address').value='53:81:7f:20:ae:ab';
  await repair.start();assert.equal(sent.length,1);assert.equal(sent[0].url,'/api/service');
  assert.deepEqual(sent[0].payload.command,{action:'repair-gamepad',supported:true,address:'53:81:7F:20:AE:AB',operation:'repair',sudo_password:'secret'});
  get('gamepad-repair-supported').checked=true;get('gamepad-repair-supported').onchange();
  assert.equal(get('gamepad-repair-start').textContent,'开始配对');
  await repair.start();assert.equal(sent.length,2);assert.equal(sent[1].payload.command.operation,'pair');
  assert.ok(!get('gamepad-repair-status').textContent.includes('secret'));
  get('gamepad-repair-address').value='invalid';await repair.start();assert.equal(sent.length,2);
  assert.match(get('gamepad-repair-status').textContent,/MAC/);
  for(const option of ['offline','replay']){
    panel.options={[option]:true};repair.render();assert.equal(get('gamepad-repair-start').disabled,true);
    await repair.start();assert.equal(sent.length,2);
  }
  panel.options={};panel.s.service_control={busy:true,job:{at:1,action:'repair-gamepad',status:'running',phase:'scanning',message:'正在扫描'}};
  repair.render();assert.equal(get('gamepad-repair-start').disabled,true);assert.match(get('gamepad-repair-status').textContent,/扫描/);
  panel.s.service_control.job.message='正在配对';repair.render();assert.match(get('gamepad-repair-status').textContent,/配对/);
  panel.s.service_control={job:{at:1,action:'repair-gamepad',status:'error',phase:'connect_failed',error:'旧配对已保留',result:{virtual:false,padd_active:true,padd_open:false},pad_steps:{bluetooth:{status:'failed',message:'旧配对连接失败'},physical:{status:'waiting',message:'等待设备'}}}};
  repair.render();assert.match(get('gamepad-repair-status').textContent,/旧配对已保留/);assert.match(get('gamepad-repair-evidence').textContent,/Xbox 桥接 未就绪/);
  assert.match(get('gamepad-repair-steps').textContent,/蓝牙连接 · 失败/);assert.doesNotMatch(get('gamepad-repair-steps').textContent,/等待设备/);
  panel.s.service_sample_fresh=true;panel.s.bus={mode:'motion',homed:false};panel.s.control={webpad:{event_authoritative:true,real_connected:true}};
  panel.s.service_control={job:{at:2,action:'repair-gamepad',status:'completed',result:{phase:'ready',message:'手柄连接已确认',bluetooth_connected:true,physical:true,virtual:true,padd_active:true,bridge_active:true,padd_open:true,warnings:['btd 恢复失败']}}};
  repair.render();assert.match(get('gamepad-repair-status').textContent,/手柄连接已确认/);assert.match(get('gamepad-repair-evidence').textContent,/padd 打开 Xbox 已确认/);
  assert.match(get('gamepad-repair-evidence').textContent,/机器人 未 HOME/);
  assert.equal(get('gamepad-repair-supported').checked,false,'successful pairing resets destructive choice');
  panel.s.control.webpad.real_connected=false;repair.render();assert.match(get('gamepad-repair-evidence').textContent,/上次核对.*当前手柄输入 已断开/);
  get('gamepad-repair-close').onclick();assert.equal(repair.root.hidden,true);
  const html=fs.readFileSync(path.join(temporary,'static/index.html'),'utf8');assert.ok(html.includes('id="control-panel"'));
  const source=fs.readFileSync(path.join(temporary,'static/gamepad-repair.js'),'utf8');assert.ok(!/setInterval|fetch\(/.test(source),'no additional polling or standalone transport');
  assert.ok(!source.includes('gamepad-repair-phone')&&!source.includes('gamepad-repair-reboot'));
  console.log('PASS normal vs explicit pairing, SSH/IMU boundaries, old bond preservation, named step history, current disconnect vs last check, robot HOME state, no polling/reboot/phone enable controls');
}finally{fs.rmSync(temporary,{recursive:true,force:true});}
