/* Public offline preview adapter: no outgoing API or hardware commands. */
(()=>{
"use strict";
const VERSION="R17 v1.0.146 · Fake Robot";
const ids=[20,21,22,23,24,10,11,12,13,14,30,31,32,33,34];
const names=["左髋Yaw","左髋Roll","左髋Pitch","左膝","左踝","右髋Yaw","右髋Roll","右髋Pitch","右膝","右踝","颈Yaw","颈Pitch","头","嘴","颈"];
const homeDeg=[0,-5,-26.24,-0.28,25.95,0,5,26.24,0.28,-25.95,20,20,0,0,0];
const config={
 version:"1.0.146",baseline:"1fa84386f07884e27866411bc1ba166977bced95",mode:"service",
 service_enabled:true,control_enabled:false,connection_ui:false,raw_telemetry:false,
 control_token:"",ssh_target:"",camera_host:"duck-demo.invalid",camera_port:8443,
 hz:50,ids,labels:names,home:homeDeg.map(x=>x*Math.PI/180)
};
const start=Date.now();
const channel=()=>({status:"live",age_ms:20,error:null});
const fakeModel={name:"Demo-Walk-10000",task:"Mjlab-Velocity-Flat-MicroDuck-V2-HD1910",sha256:"0b8f0447".padEnd(64,"0"),available:true,active:true};
function snapshot(){
  const seconds=(Date.now()-start)/1000,now=Date.now()/1000;
  const joints=homeDeg.map((v,i)=>(v+2.2*Math.sin(seconds*1.25+i*.61))*Math.PI/180);
  const targets=homeDeg.map(v=>v*Math.PI/180);
  const servos=ids.map((id,i)=>{
    const angle=joints[i]*180/Math.PI,goal=homeDeg[i];
    return {id,name:names[i],label:names[i],status:"live",source:"Fake Robot",
      position_raw:Math.round(2048+angle*4096/360),goal_position_raw:Math.round(2048+goal*4096/360),
      angle_deg:angle,target_deg:goal,error_deg:goal-angle,calibrated:true,
      voltage_v:7.28+.07*Math.sin(seconds+i*.4),temperature_c:36+i%5+Math.sin(seconds*.6+i),
      current_ma:130,current_raw:86,speed_raw:3,load_raw:28,velocity_rpm:.4,
      torque_enabled:true,moving:false,model_number:1910,
      p_gain:5,i_gain:0,d_gain:20,hardware_error:0,
      calibration:{calibrated:true,zero_raw:2048,direction:i%3===0?-1:1,min_rad:-1.57,max_rad:1.57}
    };
  });
  const motorTemps=servos.map(x=>x.temperature_c);
  const roll=1.4*Math.sin(seconds*.33),pitch=1.2*Math.sin(seconds*.27);
  const bus={mode:"motion",phase:"control",build:"1fa8438-feetech-ft6-control.29",
    management_capabilities:{supported:true,management:true,motion:true,webpad:false,live_pad_settings:false,coast:true},
    torque_state:"on",policy_enabled:false,homed:true,scale_use:"walking",
    action_scale:.7,head_lowpass:.5,legs_lowpass:.7,voltage_adapt:true,
    nominal_voltage:7.3,voltage_scale_mult:1,active_action_scale:.7,
    loaded_models:{walk:fakeModel,sitstand:{...fakeModel,task:"Mjlab-SitStand-Flat-MicroDuck"},stand_test:{...fakeModel,task:"Mjlab-StandUp-Rough-Backlash-MicroDuck"}},
    home_start_guard:{ready:true,max_joint_error_deg:2.1,tilt_deg:1.2,reason:"Demo"},
    total_cycles:Math.floor(seconds*50),cycle:Math.floor(seconds*50),
    total_communication_failures:0,session:"demo",target_hz:50,
    native:{torque_state_confirmed:true,command_clamps_total:0,
      sync:{address:56,length:15,request_sent:true,missing_ids:[],elapsed_us:2400}},
    diagnostics:{missing_by_id:{}},error:""
  };
  const health={healthy:true,degraded:false,reason:"",
    control_loop:{target_hz:50,hz:50+.2*Math.sin(seconds),last_tick_age_ms:10,missed:0},
    battery:{volts:7.25},motors:{max_c:Math.max(...motorTemps),mean_c:motorTemps.reduce((a,b)=>a+b,0)/15,hottest:"ID 20"},
    bus:{consecutive_errors:0,startup_failures:0},imu:{ready:true,stale_blocks:0,consecutive_stale_blocks:0}
  };
  const system={hostname:"duck-demo",cpu_percent:15+Math.sin(seconds)*4,
    cpu_temp_c:62+Math.sin(seconds*.2)*2,memory_total:2147483648,
    memory_available:1258291200,uptime_s:5400+seconds,
    identities:{robotd:{revision:"1fa84386f07884e27866411bc1ba166977bced95"}},
    camera:{fps:30,targetFps:30,width:1280,height:720,format:"NV12",dropped:0,consumers:0},
    camera_age_ms:20
  };
  return {schema:"microduck-console/v1",mode:"service",version:"1.0.146",baseline:config.baseline,at:now,uptime:seconds,
    read_only:true,service_sample_fresh:true,pose_calibrated:true,service_compatible:true,
    service_operation:false,connection_paused:false,extended:false,
    channels:{state:channel(),health:channel(),system:channel(),tof:channel(),
      bus:channel(),calibration:channel(),capabilities:channel()},
    state:{joints,targets,odom:{yaw:.1*Math.sin(seconds*.1),position:[.02*Math.sin(seconds*.1),0,0]},
      move:{requested:[0,0,0],applied:[0,0,0],limited_by:[]},
      safety:{fallen:false,gain:5},loop:{missed:0},policy:"Demo Walk"},
    bus,health,system,servos,
    capabilities:{walk:"Demo-Walk-10000",sitstand:"Demo-SitStand-10000"},
    control:{connected:false,audio:{volume:72},webpad:{available:false,real_connected:false,
      settings:{mouth_percent:50,head_rad:1},error:"在线只读展示"}},
    imu:{status:"live",ready:true,mount_verified:true,source:"Fake IMU",
      gravity:[Math.sin(roll*Math.PI/180),Math.sin(pitch*Math.PI/180),-.999],
      gyro:[.02*Math.sin(seconds),.01,0],quat:[1,0,0,0],roll_deg:roll,pitch_deg:pitch},
    tof:{rows:8,cols:8,seq:Math.floor(seconds*8),distance_mm:Array.from({length:64},(_,i)=>350+30*(i%8)+Math.round(12*Math.sin(seconds+i))),status:Array(64).fill(5)},
    calibration:{calibration_path:"Fake calibration · DEMO",calibration:{imu_mount_quat:[1,0,0,0],imu_mount_verified:true}},
    calibrated_count:15,saved_calibrated_count:15,service_control:{busy:false,stopping:false,job:null,sudo_password_saved:false},
    connection:{active:false},events:[]};
}
function jsonResponse(data,status=200){return new Response(JSON.stringify(data),{
 status,headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"}});}
const nativeFetch=window.fetch.bind(window);
window.fetch=(resource,init)=>{
 const url=new URL(typeof resource==="string"?resource:resource.url,location.href);
 if(url.origin===location.origin && url.pathname.startsWith("/api/")){
   const path=url.pathname,method=(init?.method||resource?.method||"GET").toUpperCase();
   if(method==="GET"){
     if(path==="/api/config")return Promise.resolve(jsonResponse(config));
     if(path==="/api/snapshot")return Promise.resolve(jsonResponse(snapshot()));
     if(path==="/api/system-log")return Promise.resolve(jsonResponse({entries:[
       {seq:1,at:Date.now()/1000,message:"[DEMO] Fake Robot 已连接，无真实设备"}],cursor:1}));
     return Promise.resolve(jsonResponse({error:"Online Demo / 只读展示"},404));
   }
   if(path==="/api/service/models")return Promise.resolve(jsonResponse({
     models:[{...fakeModel,slot:"walk"},{...fakeModel,slot:"sitstand",task:"Mjlab-SitStand-Flat-MicroDuck"}],
     slots:[{slot:"walk",model:fakeModel},{slot:"sitstand",model:{...fakeModel,task:"Mjlab-SitStand-Flat-MicroDuck"}}],
     manual_recovery:{path:"Demo-StandUp",action_scale:1,model:{name:"Demo-StandUp",id:"demo",available:true}}
   }));
   if(path==="/api/service/connection")return Promise.resolve(jsonResponse({
     management_revision:"R17",process_matches:true,running:true,actual_port:"/dev/ttyS2",
     pid:1042,actual_mode:"motion",motion_ready:true}));
   if(path==="/api/service/firmware")return Promise.resolve(jsonResponse({verified:false,error:"Fake Robot：无可刷写固件"}));
   return Promise.resolve(jsonResponse({error:"在线演示禁止任何写操作 / No device commands in demo",accepted:false},403));
 }
 return nativeFetch(resource,init);
};
// Safeguard: Pages may never initiate the real camera, USB or SSH.
document.addEventListener("DOMContentLoaded",()=>{
  document.body.classList.add("pages-demo");
  const banner=document.createElement("div");
  banner.setAttribute("role","status");
  banner.style.cssText="position:relative;z-index:30;background:#253323;color:#d8fbaa;border:1px solid #557548;border-radius:8px;padding:9px 14px;margin:10px 0;font-size:13px;font-weight:600";
  banner.textContent="ONLINE DEMO / Fake Robot · 使用原 R17 中控界面和官方 3D 模型 · 数据均为模拟值，不能控制真实设备";
  document.querySelector("main .page-heading")?.before(banner);
  const switchTab=document.createElement("a");switchTab.href="./training/";
  switchTab.textContent="打开训练中控预览 →";
  switchTab.style.cssText="color:#c1f577;padding-left:16px";
  banner.append(switchTab);
  const dangerSelectors=[
    "#ssh-connect","#camera-connect","#service-quick-stop","#service-reboot",
    "#service-shutdown","#service-mode-motion","#service-mode-calibrate",
    "#management-import","#management-reconnect","#firmware-choose","#firmware-flash",
    "#service-capture","#service-move","#service-center","#service-verify-imu"
  ];
  for(const selector of dangerSelectors){const el=document.querySelector(selector);
    if(el){el.addEventListener("click",event=>{event.preventDefault();event.stopImmediatePropagation();},true);el.title="Fake Robot：该操作已禁用";el.disabled=true;}
  }
  const bodyLog=document.querySelector("#camera-message");
  if(bodyLog)bodyLog.textContent="在线 Demo，不连接摄像头";
  setInterval(()=>{const chip=document.getElementById("mode-chip");if(chip)chip.textContent="DEMO · FAKE ROBOT";},400);
});
window.__microduckDemo={snapshot,config};
})();
