'use strict';
let remoteState=null,remoteFieldsLoaded=false,remoteUiBusy=false,remoteWasBusy=false;
const remoteFields=['host','user','port','identity','workspace','auth'];
function remoteConnection(){const value={...remoteState?.connection};for(const key of remoteFields)value[key]=$('ssh-'+key).value.trim();value.port=Number(value.port);return value;}
function renderRemote(){
 if(!remoteState)return;
 if(!remoteFieldsLoaded){for(const key of remoteFields)$('ssh-'+key).value=remoteState.connection?.[key]??(key==='auth'?'password':'');$('wsl-test-distro').value=remoteState.wsl_distro||'Ubuntu';remoteFieldsLoaded=true;}
 const busy=remoteUiBusy||remoteState.busy,connected=remoteState.status==='connected',passwordMode=$('ssh-auth').value==='password';
 $('ssh-password-row').hidden=!passwordMode;
 $('ssh-password-note').hidden=!passwordMode;
 $('ssh-password').disabled=busy;
 $('ssh-password').placeholder=remoteState.password_available?'已输入，留空沿用本次密码':'输入服务器登录密码';
 $('ssh-identity').closest('label').hidden=passwordMode;
 $('ssh-host-verification').hidden=!remoteState.pending_host;
 $('ssh-host-fingerprint').textContent=remoteState.pending_host?remoteState.pending_host.hostname+' · '+remoteState.pending_host.key_type+'\n'+remoteState.pending_host.fingerprint:'';
 $('ssh-trust-host').disabled=busy;

 $('training-target').value=remoteState.target;
 $('ssh-status').textContent=remoteState.message;
 $('ssh-status').classList.toggle('remote-failed',remoteState.status==='failed');
 $('ssh-gpu').textContent=remoteState.info?.gpu||'连接后显示服务器 GPU、显存和驱动。';
 for(const id of ['ssh-save','ssh-deploy','ssh-connect','training-target'])$(id).disabled=busy;
 for(const key of remoteFields)$('ssh-'+key).disabled=busy;
 $('wsl-test').disabled=busy||!remoteState.wsl_test_supported;
 $('wsl-test-distro').disabled=busy||!remoteState.wsl_test_supported;
 $('ssh-restore').hidden=!remoteState.has_server_backup;
 $('ssh-restore').disabled=busy;
 $('wsl-test').textContent=remoteState.busy&&remoteState.wsl_test_supported?'正在测试…':'本机 WSL 测试';
 $('wsl-test-note').textContent=remoteState.wsl_test_supported?'用 SSH 测试服务器通道；原本机 / WSL 训练继续使用原通道。':'WSL测试入口需在Windows中启动中控；当前可使用Linux本机或SSH服务器。';
 $('ssh-disconnect').disabled=busy||!connected;
 $('server-model-upload').disabled=busy||remoteState.target!=='ssh'||!connected;
 $('ssh-deploy').textContent=remoteState.status==='deploying'?'正在部署…':'部署并准备环境';
 $('ssh-connect').textContent=remoteState.status==='connecting'?'正在连接…':'连接 / 重连';
 $('ssh-section').hidden=remoteState.target!=='ssh';
 $('execution-location').textContent=remoteState.target==='ssh'?`${remoteState.connection?.wsl_distro?'WSL · '+remoteState.connection.wsl_distro:'服务器 · '+(remoteState.connection?.host||'待配置')} · ${connected?'已连接':'未连接'}`:'本机 / WSL';
 $('execution-location').classList.toggle('remote-failed',remoteState.target==='ssh'&&!connected);
 const c=remoteConnection(),key=c.identity?' -i "'+c.identity.replace(/"/g,'')+'"':'';
 $('ssh-login-command').textContent=`ssh -p ${c.port||22}${key} ${c.user||'ubuntu'}@${c.host||'服务器IP'}`;
}
async function pollRemote(){
 try{const response=await fetch('/api/remote/state',{signal:AbortSignal.timeout(4000)});if(response.ok){const previous=remoteState;remoteState=await response.json();renderRemote();if(remoteWasBusy&&!remoteState.busy&&remoteState.status==='connected'){remoteWasBusy=false;location.reload();return;}remoteWasBusy=remoteWasBusy||remoteState.busy;}}
 catch{ /* Main state polling owns the dashboard connectivity banner. */ }
 setTimeout(pollRemote,2000);
}
async function remoteAction(action,save=true){
 if(remoteUiBusy)return;
 remoteUiBusy=true;renderRemote();
 try{
  if(save){remoteState=await post('/api/remote/configure',{connection:remoteConnection(),password:$('ssh-password').value});$('ssh-password').value='';}
  if(action)remoteState=await post('/api/remote/'+action,{});
  if(action==='deploy'||action==='connect')remoteWasBusy=true;
  tell(remoteState.message||'服务器连接已保存。');
 }catch(error){tell(error.message);}
 finally{remoteUiBusy=false;renderRemote();}
}
$('training-target').onchange=async()=>{
 const target=$('training-target').value;
 if(typeof launchFlow!=='undefined'&&launchFlow.busy){tell('请等待当前训练启动流程完成后再切换位置。');renderRemote();return;}
 remoteUiBusy=true;renderRemote();
 try{await post('/api/remote/select',{target});location.reload();}catch(error){tell(error.message);remoteUiBusy=false;renderRemote();}
};
$('ssh-save').onclick=()=>remoteAction(null);
$('ssh-deploy').onclick=()=>remoteAction('deploy');
$('ssh-connect').onclick=()=>remoteAction('connect');
$('ssh-trust-host').onclick=async()=>{
 if(remoteUiBusy||!remoteState.pending_host)return;
 remoteUiBusy=true;renderRemote();
 try{remoteState=await post('/api/remote/trust-host',{fingerprint:remoteState.pending_host.fingerprint});remoteWasBusy=true;tell(remoteState.message);}
 catch(error){tell(error.message);}
 finally{remoteUiBusy=false;renderRemote();}
};
$('ssh-disconnect').onclick=async()=>{await remoteAction('disconnect',false);await loadState();};
$('wsl-test').onclick=async()=>{
 if(remoteUiBusy)return;
 if(typeof launchFlow!=='undefined'&&launchFlow.busy){tell('请等待当前训练启动流程完成后再测试。');return;}
 remoteUiBusy=true;renderRemote();
 try{remoteState=await post('/api/remote/wsl-test',{distro:$('wsl-test-distro').value.trim()});remoteWasBusy=true;tell(remoteState.message);}
 catch(error){tell(error.message);}
 finally{remoteUiBusy=false;renderRemote();}
};
$('ssh-restore').onclick=async()=>{await remoteAction('server-restore',false);remoteFieldsLoaded=false;renderRemote();await loadState();};
for(const key of remoteFields)$('ssh-'+key).oninput=renderRemote;
$('ssh-auth').onchange=renderRemote;
$('server-model-upload').onchange=async event=>{
 const file=event.target.files[0];if(!file)return;
 try{
  if(file.size>30*1024*1024)throw Error('请上传30MB以内的完整老师/续训模型ZIP。');
  $('server-model-upload').disabled=true;$('model-transfer-status').textContent='正在上传模型，训练来源和动作配置会保留…';
  const bytes=new Uint8Array(await file.arrayBuffer());let binary='';
  for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
  const result=await post('/api/models/import',{name:file.name,data:btoa(binary)},{signal:AbortSignal.timeout(180000)});
  selected=result.job_id;await loadState();
  $('model-transfer-status').textContent=result.resume_supported===false?'老师已上传；旧包缺少原训练并行数，可作老师，续训需原训练快照。':'模型已上传，可在老师选择或续训来源中选择。';tell('模型已上传，原倍率、滤波和P已保留。');
 }catch(error){$('model-transfer-status').textContent=error.message;tell(error.message);}
 finally{event.target.value='';renderRemote();}
};
pollRemote();
