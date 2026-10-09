/* Training Studio R1.5.17 — isolated, read-only GitHub Pages preview. */
(()=>{"use strict";
const task="Mjlab-VelStand-Rough-Backlash-MicroDuck";
const now=()=>Date.now()/1000;
const points=Array.from({length:43},(_,i)=>{
 const iteration=i*240,progress=i/42,noise=Math.sin(i*1.4)*5;
 return {iteration,total:10000,reward:25+100*(1-Math.exp(-progress*3.5))+noise,
   fps:58000+Math.sin(i*.48)*6000,episode_length:360+progress*190,
   value_loss:.41*Math.exp(-progress*2)+.08,policy_loss:-.006*(1-progress),
   rewards:{track_linear_velocity:14+progress*24,track_angular_velocity:3+progress*5,
     upright:6+progress*10,expert_bc:.8-progress*.32},expert_bc:.85-progress*.3,
   expert_bc_anchor_frac:.62,expert_bc_fallen_frac:.27};
});
const job={
 id:"dem0abcd00000001",op:"train",status:"completed",created:now()-86400,ended:now()-43000,
 message:"示例训练已完成 · 页面所有曲线与记录均为 Demo 数据",profile:{mode:"wsl",distro:"Ubuntu",repo:"~/microduck-training-studio/engines/official_0151"},
 request:{task,label:"[DEMO] 行走与倒地起身",num_envs:4096,iterations:10000,
   training_action_scale:.9,training_firmware_p:5,
   learning_rate:0.0003,seed:42,actor_dims:[256,128,64],action_filter:{enabled:true,head_alpha:.5,legs_alpha:.7}},
 effective_config:{num_envs:4096,iterations:10000,training_action_scale:.9,
    training_firmware_p:5,action_filter:{enabled:true,head_alpha:.5,legs_alpha:.7}},
 resolved_task:task,target_compatible:true,resume_compatible:true,
 progress:{done:10000,total:10000,percent:100,elapsed_seconds:24800,eta_seconds:0},
 metrics:points,latest_metric:points.at(-1),logs:[
   "[DEMO] 独立训练中控 R1.5.17","[DEMO] GPU: RTX 4080 SUPER 16GB",
   "[DEMO] 4096 environments · 10000 iterations",
   "[DEMO] Export ready (sample only; no actual ONNX)"
 ],checkpoints:[{path:"/demo/model_9999.pt",name:"model_9999.pt",iteration:9999,modified:now()-43000}],
 compatibility_label:"Demo · HD1910",message_long:""
};
const profile=job.profile;
function currentState(){
 return {profile,computer_verified:true,
  environment:{ready:true,status:"ready",reused:true,engine:"official_0151",
   message:"[DEMO] 训练环境为模拟状态，不运行 CUDA / WSL / 训练程序",
   revision:"8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec",
   gpu:{gpus:[{name:"RTX 4080 SUPER · DEMO",memory_gb:16}]},
   configs:{},tasks:[task]},
  jobs:[job],
  resources:{received:now(),devices:[{name:"RTX 4080 SUPER · DEMO",utilization:81,
    used_mb:11260,total_mb:16384,temperature:65}]},
  presets:[],training_queue:{enabled:false,entries:[{
    id:"demo-queue",status:"completed",job_id:job.id,request:job.request,
    progress:job.progress,recipe_sha256:"demo0000",message:"示例任务已完成"}],
    failure_policy:"stop",message:"[DEMO] 训练队列为静态示例，不能启动新任务"},
  };
}
const config={token:"DEMO-READONLY",version:"Studio R1.5.17 · ONLINE DEMO",
 platform:"linux",release:"R1.5.17",remote_workspace:""};
const respond=(data,status=200)=>new Response(JSON.stringify(data),{
 status,headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"}});
const native=window.fetch.bind(window);
window.fetch=(input,opts)=>{
 const url=new URL(typeof input==="string"?input:input.url,location.href);
 if(url.origin===location.origin&&url.pathname.startsWith("/api/")){
   const method=(opts?.method||input?.method||"GET").toUpperCase();
   if(method!=="GET")return Promise.resolve(respond({error:"在线演示仅供查看，禁止提交训练、导出、连接 SSH 或修改设置。"},403));
   if(url.pathname==="/api/config")return Promise.resolve(respond(config));
   if(url.pathname==="/api/state")return Promise.resolve(respond(currentState()));
   if(url.pathname==="/api/task-reference")return Promise.resolve(respond({
     task:url.searchParams.get("task"),learning_rate:0.0003,seed:42,gamma:.99,
     activation:"elu",actor_dims:[256,128,64],critic_dims:[256,128,64],
     rewards:[{name:"track_linear_velocity",weight:2,editable:true},
       {name:"upright",weight:1,editable:true}],
     inspection:{full:null,rows:[]}
   }));
   if(url.pathname==="/api/remote/state")return Promise.resolve(respond({
     target:"local",status:"ready",message:"[DEMO] 仅展示，不连接 SSH",selected:"local",
     connected:false,connection:{host:"",port:22,user:""} }));
   if(url.pathname==="/api/studio")return Promise.resolve(respond({
     recipe:{schema:"microduck-training-recipe/v1",version:1,name:"官方骨架 + HD1910",
       baseline:"official_0151",purpose:"sim2real",training_action_scale:.9,
       robot:{servo_mass_model:"hd1910_820g_v1"},overrides:[],task_overrides:{},
       calibration:null},
     zero_connection:{target:""},pins:{official_0151:{repo:profile.repo,
        revision:"8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec"}},
     baseline:{model:null,rows:[]},checks:[],frozen:null,archives:[],
     hardware:{current_calibration:{revision:"DEMO",data:{joints:[],imu_mount_quat:[1,0,0,0]}},
       joints:[]},servo_references:[],
     servo_mass_profile:{key:"hd1910_820g_v1",body_counts:{},replacement_g:23,reference_g:18},
     mass_closure_profile:{key:"hd1910_820g_v1",target_g:820,body_additions_g:{}},
     bundled_calibration_matches:false,readiness:{items:[]},target_runtime:"0.15.1"
   }));
   if(url.pathname==="/api/log")return Promise.resolve(new Response(job.logs.join("\n"),{
     headers:{"Content-Type":"text/plain; charset=utf-8"}}));
   return Promise.resolve(respond({error:"该功能在在线 Demo 中不可用"},404));
 }
 return native(input,opts);
};
document.addEventListener("DOMContentLoaded",()=>{
  document.body.classList.add("pages-training-demo");
  const banner=document.createElement("div");
  banner.setAttribute("role","status");
  banner.className="notice";
  banner.style.cssText="margin:12px 0;border:1px solid #6b844d;background:#1d3022;color:#d9ffa6;font-weight:600";
  banner.innerHTML="ONLINE DEMO / Fake Training · R1.5.17 原始训练界面，奖励曲线与 GPU 数值均为示例。不能启动 CUDA、提交训练或连接 SSH。 <a href='../' style='color:#c1f577;margin-left:12px'>← 返回机器人中控预览</a>";
  document.querySelector(".train-top")?.after(banner);
  const disableDanger=[
    "#train-start","#train-stop","#queue-add","#queue-clear","#environment-setup",
    "#probe","#preview-start","#play-start","#recovery-eval-start",
    "#export-model","#calibration-zero","#calibration-bundled",
    "#ssh-connect","#wsl-test","#delete-model"
  ];
  for(const selector of disableDanger){
    const b=document.querySelector(selector);
    if(b){b.disabled=true;b.title="Online Demo：仅供查看";b.addEventListener("click",e=>{e.stopImmediatePropagation();e.preventDefault();},true);}
  }
  document.addEventListener("submit",e=>{e.preventDefault();e.stopImmediatePropagation();},true);
  document.addEventListener("click",e=>{
    const b=e.target.closest("button[data-delete-model],button[data-download-model],[data-queue-action]");
    if(b){e.preventDefault();e.stopImmediatePropagation();} 
  },true);
});
window.__trainingDemo={state:currentState,config};
})();