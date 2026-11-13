const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const nodes=new Map(),calls=[];
 const el=id=>{if(!nodes.has(id)){const node={hidden:false,disabled:false,textContent:'',classList:{toggle(){}},closest(){return this;}};let value='';Object.defineProperty(node,'value',{get:()=>value,set:v=>{value=String(v);}});nodes.set(id,node);}return nodes.get(id);};
 const initial={target:'ssh',connection:{host:'seoul.example.org',user:'ubuntu',port:2222,identity:'',workspace:'~/microduck-training-ssh',auth:'password'},busy:false,status:'disconnected',info:{},wsl_test_supported:false,message:'test'};
 const context=vm.createContext({console,Number,String,Uint8Array,AbortSignal,setTimeout(){},fetch:async()=>({ok:true,json:async()=>initial}),$:el,tell(){},loadState:async()=>{},location:{reload(){}},post:async(route,value)=>{
  calls.push({route,value});
  return {...initial,password_available:true,busy:route.endsWith('/connect')||route.endsWith('/trust-host')};
 }});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../training/static/remote.js'),'utf8'),context);await new Promise(resolve=>setImmediate(resolve));
 assert.equal(el('ssh-password-row').hidden,false);assert.equal(el('ssh-identity').hidden,true);
 const secret='fixture %& 中文';el('ssh-password').value=secret;await el('ssh-connect').onclick();
 assert.equal(calls[0].route,'/api/remote/configure');assert.equal(calls[0].value.password,secret);assert.equal(calls[0].value.connection.auth,'password');
 assert.equal(calls[1].route,'/api/remote/connect');assert.equal(el('ssh-password').value,'');
 assert(!el('ssh-status').textContent.includes(secret));assert(!el('ssh-login-command').textContent.includes(secret));
 vm.runInContext("remoteState.busy=false;remoteState.status='failed';remoteState.pending_host={hostname:'server',key_type:'ssh-ed25519',fingerprint:'SHA256:fixture'};renderRemote();",context);
 assert.equal(el('ssh-host-verification').hidden,false);assert.match(el('ssh-host-fingerprint').textContent,/SHA256:fixture/);
 await el('ssh-trust-host').onclick();assert.equal(calls[2].route,'/api/remote/trust-host');assert.equal(calls[2].value.fingerprint,'SHA256:fixture');
 vm.runInContext('remoteState.busy=false;renderRemote();',context);el('ssh-auth').value='key';el('ssh-auth').onchange();assert.equal(el('ssh-password-row').hidden,true);assert.equal(el('ssh-identity').hidden,false);
 assert(calls.every(call=>!['/api/train','/api/setup','/api/queue/control'].includes(call.route)));
 console.log('PASSWORD_UI_OK: real handlers submit password + blank field after save + no secret display + fingerprint confirmation + key mode preserved + no automatic training');
})().catch(error=>{console.error(error);process.exitCode=1;});
