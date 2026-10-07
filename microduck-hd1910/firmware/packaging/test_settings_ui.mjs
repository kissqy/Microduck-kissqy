import assert from 'node:assert/strict';
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import {pathToFileURL} from 'node:url';
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'microduck-settings-ui-'));
try{
 fs.cpSync(process.argv[2],path.join(temp,'static'),{recursive:true});fs.writeFileSync(path.join(temp,'package.json'),'{"type":"module"}');
 const sent=[];globalThis.window={dispatchEvent:e=>sent.push(e.detail)};globalThis.CustomEvent=class{constructor(name,data){this.detail=data.detail;}};
 const nodes=new Map();class Element{constructor(){this.value='';this.textContent='';this.dataset={};this.classList={toggle(){}};}setAttribute(){}}
 const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
 const heads=[.5,1,2.5].map(v=>{const el=new Element();el.dataset.headAmplitude=String(v);return el;});
 const root={querySelector:get,querySelectorAll:q=>q==='[data-head-amplitude]'?heads:[]};
 const {ControlPanel}=await import(pathToFileURL(path.join(temp,'static/control.js')));
 const panel=Object.create(ControlPanel.prototype);Object.assign(panel,{root,cfg:{service_enabled:true},connected:true,options:{},feedback:new Element(),pad:{paint(){},reset(){}},volumeDirty:false,mouthDirty:false,volumeBusy:false});
 const snapshot=(volume,mouth,head)=>({service_sample_fresh:true,bus:{build:'1fa8438-feetech-ft6-control.14',mode:'motion',phase:'control',head_lowpass:.5,legs_lowpass:.7},control:{connected:true,audio:{volume},webpad:{available:true,settings:mouth===null?null:{mouth_percent:mouth,head_rad:head}}},service_control:{}});
 // A stale receipt must never hide a newer device snapshot.
 panel.audio={volume:85};panel.render(snapshot(17,60,.5));assert.equal(get('#control-volume').value,17);assert.equal(get('#control-volume-value').textContent,'17%');
 get('#control-mouth').value='30';panel.applyPadSettings();assert.deepEqual(sent.at(-1),{mouth_percent:30,head_rad:.5});
 panel.render(snapshot(23,55,1));assert.equal(get('#control-volume').value,23);assert.equal(get('#control-mouth').value,55);
 get('#control-mouth').value='20';panel.applyPadSettings();assert.deepEqual(sent.at(-1),{mouth_percent:20,head_rad:1});
 // Unavailable data stays visibly unknown; the page does not invent defaults.
 panel.render(snapshot(undefined,null,undefined));assert.equal(get('#control-volume-value').textContent,'—');assert.equal(get('#control-mouth-value').textContent,'—');assert.equal(get('#control-volume').disabled,true);assert.equal(get('#control-mouth').disabled,true);
 console.log('PASS newer device settings replace receipts; mouth updates preserve saved head amplitude; missing values stay unknown');
}finally{fs.rmSync(temp,{recursive:true});}
