// Exercise the real remote UI handlers without a browser or a live WSL.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const nodes=new Map(),calls=[];
 const el=id=>{if(!nodes.has(id)){const node={hidden:false,disabled:false,textContent:'',classList:{toggle(){}},closest(){return this;}};let value='';Object.defineProperty(node,'value',{get:()=>value,set:v=>{value=String(v);}});nodes.set(id,node);}return nodes.get(id);};
 const server={host:'seoul.example.org',user:'ubuntu',port:2222,identity:'',workspace:'~/microduck-training-ssh',known_hosts:'',wsl_distro:'',auth:'key'};
 const initial={target:'local',connection:{...server},status:'disconnected',busy:false,message:'local',info:{},wsl_test_supported:true,wsl_distro:'Ubuntu',has_server_backup:false};
 const context=vm.createContext({console,Number,String,Uint8Array,AbortSignal,setTimeout(){},fetch:async()=>({ok:true,json:async()=>initial}),$:el,tell(){},loadState:async()=>{},location:{reload(){}},post:async(route,value)=>{
  calls.push({route,value});
  if(route==='/api/remote/wsl-test')return {...initial,target:'ssh',busy:true,status:'deploying',has_server_backup:true};
  if(route==='/api/remote/server-restore')return {...initial,target:'ssh',has_server_backup:true};
  return initial;
 }});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../training/static/remote.js'),'utf8'),context);
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(el('wsl-test').disabled,false);assert.equal(el('ssh-section').hidden,true);
 assert.equal(el('wsl-test-distro').value,'Ubuntu');
 el('wsl-test-distro').value='Ubuntu-24.04';await el('wsl-test').onclick();
 assert.equal(calls.length,1);assert.equal(calls[0].route,'/api/remote/wsl-test');assert.equal(calls[0].value.distro,'Ubuntu-24.04');
 assert.equal(el('training-target').value,'ssh');assert.equal(el('wsl-test').disabled,true);assert.equal(el('ssh-restore').hidden,false);
 vm.runInContext("remoteState.busy=false;remoteState.status='failed';renderRemote();",context);
 await el('ssh-restore').onclick();assert.equal(calls[1].route,'/api/remote/server-restore');assert.equal(el('ssh-host').value,'seoul.example.org');
 vm.runInContext("remoteState.wsl_test_supported=false;renderRemote();",context);assert.equal(el('wsl-test').disabled,true);
 assert.match(el('wsl-test-note').textContent,/Windows/);
 assert(calls.every(c=>!['/api/train','/api/setup','/api/queue/control'].includes(c.route)));
 console.log('WSL_UI_OK: existing local mode + distro selection + direct test action + busy blocking + restore server fields + platform guard + no automatic train/setup');
})().catch(error=>{console.error(error);process.exitCode=1;});
