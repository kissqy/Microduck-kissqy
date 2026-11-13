/* Public offline preview adapter: no outgoing API or hardware commands. */
(()=>{
"use strict";

const ids=[20,21,22,23,24,10,11,12,13,14,30,31,32,33,34];
const names=["左髋Yaw","左髋Roll","左髋Pitch","左膝","左踝","右髋Yaw","右髋Roll","右髋Pitch","右膝","右踝","颈Pitch","头Pitch","头Yaw","头Roll","嘴"];
const homeDeg=[0,-5,-26.24,-0.28,25.95,0,5,26.24,0.28,-25.95,20,20,0,0,0];
const config={
 version:"1.0.260",baseline:"1fa84386f07884e27866411bc1ba166977bced95",mode:"service",
 service_enabled:true,control_enabled:false,connection_ui:false,raw_telemetry:false,
 control_token:"",ssh_target:"",camera_host:"duck-demo.invalid",camera_port:8443,
 hz:50,ids,labels:names,home:homeDeg.map(x=>x*Math.PI/180)
};
const start=Date.now();
const channel=()=>({status:"live",age_ms:20,error:null});
const models=[{"id": "1cbf8730eadd75a5704332c9f3c10f60", "name": "行走＋倒地联合 9600 轮", "slot": "walk", "task": "Mjlab-VelStand-Rough-Backlash-MicroDuck", "sha256": "1cbf8730eadd75a5704332c9f3c10f60bfa9412135b907831c9dbd731ce1795f", "available": true, "active": true, "demo": true, "runtime_execution_profile": {"schema": "microduck-runtime-execution/v1", "model_sha256": "1cbf8730eadd75a5704332c9f3c10f60bfa9412135b907831c9dbd731ce1795f", "mode": "uniform", "action_scale": 1, "head_lowpass": 0.5, "legs_lowpass": 0.7}}, {"id": "1c94934c6421ec72ed48079cea749668", "name": "坐下／站起 10000 轮", "slot": "sitstand", "task": "Mjlab-SitStand-Flat-MicroDuck", "sha256": "1c94934c6421ec72ed48079cea74966868a7a59f7d732e0207d0f7bdaeed3c50", "available": true, "active": true, "demo": true}, {"id": "b14e3a8b56ddbb8d2d831e727774a168", "name": "低头捡取 10000 轮 · 无缩放滤波", "slot": "ground_pick", "task": "Mjlab-GroundPick-Flat-Backlash-MicroDuck", "sha256": "b14e3a8b56ddbb8d2d831e727774a168c8f5b00194e3e431ae7593a840498c69", "available": true, "active": true, "demo": true}, {"id": "59e15d7b04d0c40e9b11b8a70bdecae6", "name": "前滚翻 10000 轮 · 无缩放滤波", "slot": "roulade", "task": "Mjlab-Roulade-Flat-MicroDuck", "sha256": "59e15d7b04d0c40e9b11b8a70bdecae6da87a5e096efc204fb58eea304fcbbac", "available": true, "active": true, "demo": true}, {"id": "67ad09d82f4865d222a7ae06f250cf9f", "name": "右脚踢球 10000 轮 · 无缩放滤波", "slot": "kick_right", "task": "Mjlab-BallKick-Flat-MicroDuck", "sha256": "67ad09d82f4865d222a7ae06f250cf9f77f08c27e4f019ee3f7e431a764419fd", "available": true, "active": true, "demo": true}, {"id": "ee0376c927044cdece056ba1d3e6eac7", "name": "左脚踢球 10000 轮 · 无缩放滤波", "slot": "kick_left", "task": "Mjlab-BallKickLeft-Flat-Backlash-MicroDuck", "sha256": "ee0376c927044cdece056ba1d3e6eac77b3e02ee3f701f1feb437c183ed39a6d", "available": true, "active": true, "demo": true}, {"id": "9203bb8f5df15cffaa29f5315a722835", "name": "装死 3000 轮 · V8 / STS3215 旧 M6", "slot": "play_dead", "sha256": "9203bb8f5df15cffaa29f5315a722835c1bd718b940b14330f97556ccab83065", "task": "Mjlab-PlayDead-Flat-MicroDuck", "available": true, "active": true, "demo": true}];
const loadedModels=Object.fromEntries(models.map(row=>[row.slot,row]));
function snapshot(){
  const seconds=(Date.now()-start)/1000,now=Date.now()/1000;
  const joints=homeDeg.map((v,i)=>(v+2.2*Math.sin(seconds*1.25+i*.61))*Math.PI/180);
  if(ai.motion?.type==='yes'&&ai.motion.until>Date.now())joints[11]+=0.15*Math.sin(seconds*8);
  const targets=homeDeg.map(v=>v*Math.PI/180);
  const servos=ids.map((id,i)=>{
    const angle=joints[i]*180/Math.PI,goal=homeDeg[i];
    return {id,name:names[i],label:names[i],status:"live",source:"Fake Robot",
      position_raw:Math.round(2048+angle*4096/360),goal_position_raw:Math.round(2048+goal*4096/360),
      angle_deg:angle,target_deg:goal,error_deg:goal-angle,calibrated:true,
      voltage_v:7.28+.07*Math.sin(seconds+i*.4),temperature_c:36+i%5+Math.sin(seconds*.6+i),
      current_ma:130,current_raw:86,speed_raw:3,load_raw:28,velocity_rpm:.4,
      torque_enabled:true,moving:false,model_number:1910,
      p_gain:5,i_gain:0,d_gain:0,hardware_error:0,
      calibration:{calibrated:true,zero_raw:2048,direction:i%3===0?-1:1,min_rad:-1.57,max_rad:1.57}
    };
  });
  const motorTemps=servos.map(x=>x.temperature_c);
  const roll=1.4*Math.sin(seconds*.33),pitch=1.2*Math.sin(seconds*.27);
  const bus={mode:"motion",phase:"control",build:"1fa8438-feetech-ft6-control.102",
    management_capabilities:{supported:true,management:true,motion:true,webpad:false,live_pad_settings:false,coast:true},
    torque_state:"on",policy_enabled:false,homed:true,scale_use:"walking",
    action_scale:1,head_lowpass:.5,legs_lowpass:.7,voltage_adapt:true,
    nominal_voltage:7.3,voltage_scale_mult:1,active_action_scale:1,
    loaded_models:loadedModels,
    home_start_guard:{ready:true,max_joint_error_deg:2.1,tilt_deg:1.2,reason:"Demo"},
    total_cycles:Math.floor(seconds*50),cycle:Math.floor(seconds*50),achieved_hz:50+.2*Math.sin(seconds),
    total_communication_failures:0,session:"demo",target_hz:50,
    native:{imu_ready:true,torque_state_confirmed:true,command_clamps_total:0,
      sync:{address:56,length:15,request_sent:true,missing_ids:[],elapsed_us:2400}},
    diagnostics:{missing_by_id:{}},error:""
  };
  const health={healthy:true,degraded:false,reason:"",
    control_loop:{target_hz:50,hz:50+.2*Math.sin(seconds),achieved_hz:50+.2*Math.sin(seconds),last_tick_age_ms:10,missed:0},
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
  return {schema:"microduck-console/v1",mode:"service",version:"1.0.260",baseline:config.baseline,at:now,uptime:seconds,
    read_only:true,service_sample_fresh:true,pose_calibrated:true,service_compatible:true,
    service_operation:false,connection_paused:false,extended:false,
    channels:{state:channel(),health:channel(),system:channel(),tof:channel(),
      bus:channel(),calibration:channel(),capabilities:channel(),startup:channel()},
    startup:{steps:Object.fromEntries([1,2,3,4].map(n=>[n,{status:"success",detail:"DEMO"}]))},
    state:{joints,targets,odom:{yaw:.1*Math.sin(seconds*.1),position:[.02*Math.sin(seconds*.1),0,0]},
      move:{requested:[0,0,0],applied:[0,0,0],limited_by:[]},
      safety:{fallen:false,gain:5},loop:{missed:0,hz:50+.2*Math.sin(seconds)},policy:"Demo · 联合行走／起身"},
    bus,health,system,servos,
    capabilities:{walk:loadedModels.walk.name,sitstand:loadedModels.sitstand.name,ground_pick:loadedModels.ground_pick.name,skills:["roulade","kick_right","kick_left","play_dead"]},
    control:{connected:false,audio:{volume:72},webpad:{available:false,real_connected:false,
      settings:{mouth_percent:100,head_rad:2.5},error:"在线只读展示"}},
    imu:{status:"live",ready:true,mount_verified:true,source:"Fake IMU",
      gravity:[Math.sin(roll*Math.PI/180),Math.sin(pitch*Math.PI/180),-.999],
      gyro:[.02*Math.sin(seconds),.01,0],quat:[1,0,0,0],roll_deg:roll,pitch_deg:pitch},
    tof:{rows:8,cols:8,seq:Math.floor(seconds*8),distance_mm:Array.from({length:64},(_,i)=>350+30*(i%8)+Math.round(12*Math.sin(seconds+i))),status:Array(64).fill(5)},
    calibration:{calibration_path:"Fake calibration · DEMO",calibration:{imu_mount_quat:[1,0,0,0],imu_mount_verified:true}},
    calibrated_count:15,saved_calibrated_count:15,service_control:{busy:false,stopping:false,job:null,sudo_password_saved:false},
    connection:{active:true,connected:true,target:"DEMO"},events:[]};
}
const D=window.MicroduckDemo;
const rollerNames={swizzle:'滑轮对称滑',crouch:'滑轮蹲下',spin:'滑轮原地转',standup:'滑轮倒地起身'};
const rollerModels=[{"id": "swizzle", "name": "滑轮对称滑", "sha256": "14195135fcaa60cc45c36181d31542e76f07d873261ecae41dca72c0b795fcc8", "available": true, "demo": true, "action_scale": 1.0, "head_lowpass": 1, "legs_lowpass": 1}, {"id": "crouch", "name": "滑轮蹲下", "sha256": "82be20b115d925ab5adfd20c12188364dd841a2c533eba3bfd64fb9212fe4aa4", "available": true, "demo": true, "action_scale": 0.8, "head_lowpass": 1, "legs_lowpass": 1}, {"id": "spin", "name": "滑轮原地转", "sha256": "621fe9f3ae3463089033c76354f8290e23457898af7e3e78de008af4a7180569", "available": true, "demo": true, "action_scale": 1.0, "head_lowpass": 1, "legs_lowpass": 1}, {"id": "standup", "name": "滑轮倒地起身", "sha256": "2575b5894bcd8e3fdbe005b1a7b90d9491085726df32000c26cf5b92b7a10ebb", "available": true, "demo": true, "action_scale": 1.0, "head_lowpass": 1, "legs_lowpass": 1}];
const catalog={models,slots:models.map(model=>({slot:model.slot,model})),
  roller_models:rollerModels,
  management_actions:[],action_scale:1,default_action_scale:.7,default_joint_action_scale:1};
const recordings=[];
const expressions=[
  ['sad','难过','伤心低落'],['devastated','伤心欲绝','非常难过'],['curious','好奇','好奇观察'],
  ['mmh','思考','犹豫思考'],['yes','点头','肯定'],['yes_fast','快速点头','积极肯定'],
  ['no','摇头','否定'],['angry','生气','愤怒'],['excited','兴奋','开心兴奋'],
  ['laugh','大笑','开怀大笑'],['mock','调皮','开玩笑'],['defiant','不服','不服气'],['impatient','不耐烦','有点着急']
].map(([name,label,meaning])=>({name,label,meaning,seconds:2,silent:true,skill:'emotion_silent_'+name,silent_skill:'emotion_silent_'+name}));
const ai={running:false,voice_id:'zh_female_vv_jupiter_bigtts',voice_revision:0,voice_state_revision:0,
  voices:[{name:'活泼小鸭',id:'zh_female_vv_jupiter_bigtts'},{name:'温柔小鸭',id:'zh_female_xiaohe_uranus_bigtts'},{name:'阳光小鸭',id:'zh_male_m191_uranus_bigtts'}],
  persona:'你是桌面小鸭 Microduck，简短自然地回应，配合表情和动作。',
  vision_model:'doubao-seed-2-0-mini-260428',speech:false,speech_revision:0,
  revision:0,messages:[],phase:'stopped',motion:null};
const sampleDefinitions={
  nod:{text:'你能听懂我讲话吗？',reply:'当然！看，我在点头呢。',name:'express_emotion',arguments:{emotion:'yes'},motion:'yes'},
  sit:{text:'坐下吧，我有话跟你讲。',reply:'坐好啦，慢慢说，我听着呢。',name:'sit_down',arguments:{},motion:'sit'},
  voice:{text:'换成温柔小鸭的声音。',reply:'好呀，现在用温柔的声音陪你。',name:'switch_voice',arguments:{voice_id:'zh_female_xiaohe_uranus_bigtts'}}
};
const skills=['roulade','kick_left','kick_right','play_dead','ground_pick','sit_toggle','roller_stand'];
const conversation=()=>({revision:ai.revision,phase:ai.phase,note:ai.running?'演示已启动 · 点击示例查看对话与调用过程':'演示未启动 · 无需填写密钥',messages:ai.messages.map(row=>({...row})),oldest_id:ai.messages[0]?.id});
function aiStatus(){return {
  demo:true,running:ai.running,provider_ready:ai.running,credentials_present:false,configuration_saved:false,
  voice_id:ai.voice_id,voices:ai.voices.map(row=>({...row})),voice_revision:ai.voice_revision,voice_state_revision:ai.voice_state_revision,
  voice_selection:{phase:'confirmed',message:'演示音色仅在当前页面切换'},
  speech_session:'v260-static-demo',voice_unlocked:ai.speech,speech_revision:ai.speech_revision,
  speech:{phase:'confirmed',enabled:ai.speech},persona:ai.persona,
  skills,expressions,head_limits:{neck_pitch:[-1.571,1.047],head_pitch:[-1.571,1.571],head_yaw:[-1.571,1.571],head_roll:[-1.571,1.571]},
  vision:{enabled:false,credentials_present:false,model:ai.vision_model,phase:'idle',message:'在线演示不采集摄像头画面'},
  camera_profile:{phase:'disabled',message:'演示模式不连接摄像头'},conversation:conversation()
};}
function chat(role,text,extra={}){
  const message={id:ai.messages.length?ai.messages.at(-1).id+1:1,role,type:'text',text,final:true,at:new Date().toISOString(),...extra};
  ai.messages.push(message);if(ai.messages.length>60)ai.messages.shift();ai.revision++;return message;
}
function event(kind,fields={}){return D.emit({kind,demo:true,...fields});}
function chatUpdate(){event('conversation',{conversation_update:conversation()});}
function voice(id){
  if(!ai.voices.some(row=>row.id===id))return false;
  ai.voice_id=id;ai.voice_revision++;ai.voice_state_revision++;event('voice_selection',{voice_id:id,message:'模拟音色已切换'});return true;
}
function sample(id){
  if(!ai.running)return D.json({accepted:false,error:'先点击“启动 AI”开始演示。'},409);
  const row=sampleDefinitions[id];if(!row)return D.json({accepted:false,error:'未知演示指令'},400);
  ai.phase='thinking';chat('user',row.text);event('transcript',{text:row.text,final:true,conversation_update:conversation()});
  event('tool_call',{name:row.name,arguments:row.arguments});
  if(id==='voice')voice(row.arguments.voice_id);
  ai.motion={type:row.motion,until:Date.now()+2200};
  const result={accepted:true,status:'completed',demo:true,label:row.motion==='yes'?'点头':undefined};
  chat('assistant','',{type:'action',name:row.name,arguments:row.arguments,result});
  event('tool_result',{name:row.name,result});
  chat('assistant',row.reply);ai.phase='listening';ai.revision++;
  event('assistant_text',{text:row.reply,final:true,blocked:true,conversation_update:conversation()});
  return D.json({accepted:true,demo:true});
}
const wifiNetworks=[
  {ssid:'Microduck-Demo-5G',uuid:'demo-home',saved:true,connected:true,in_range:true,signal:92,security:'WPA2',can_forget:false},
  {ssid:'Studio-Demo',uuid:'demo-studio',saved:true,connected:false,in_range:true,signal:68,security:'WPA2',can_forget:false}
];
const wifi=()=>({accepted:true,demo:true,networks:wifiNetworks,saved_network_count:2,connected_ssid:wifiNetworks[0].ssid,ipv4_addresses:['192.168.6.151']});
D.transport((url,method,options)=>{
  const path=url.pathname;
  let body={};try{if(typeof options?.body==='string')body=JSON.parse(options.body);}catch{return D.json({error:'无效演示请求'},400);}
  if(method==='GET'){
    if(path==='/api/config')return D.json(config);
    if(path==='/api/snapshot'){
      const frame=snapshot();recordings.push(frame);if(recordings.length>600)recordings.shift();return D.json(frame);
    }
    if(path==='/api/system-log')return D.json({entries:Number(url.searchParams.get('after'))?[]:[{seq:1,at:start/1000,source:'DEMO',text:'R17 V260 / control.102 · 11 个运行模型 · 数据仅在当前页面模拟'}],cursor:1,has_more:false});
    if(path==='/api/ai/status')return D.json(aiStatus());
    if(path==='/api/recording')return D.json({schema:'microduck-console-recording/v1',demo:true,frames:recordings.length?recordings:[snapshot()]});
  }
  if(method!=='POST')return;
  if(path==='/api/service/models')return D.json(catalog);
  if(path==='/api/service/connection')return D.json({management_revision:'R17',process_matches:true,running:true,actual_port:'/dev/ttyS2 · DEMO',pid:1042,actual_mode:'motion',motion_ready:true});
  if(path==='/api/service/firmware')return D.json({verified:false,error:'在线演示不读取或安装固件；正式版内含 control.102。'});
  if(path==='/api/service/wifi'&&['status','scan'].includes(body.action))return D.json(wifi());
  if(path==='/api/demo/sample')return sample(body.sample);
  if(path==='/api/ai/configure'){
    ai.persona=String(body.persona||ai.persona).slice(0,4000);ai.vision_model=String(body.vision_model||ai.vision_model).slice(0,200);
    if(body.voice_id)voice(body.voice_id);return D.json(aiStatus());
  }
  if(path==='/api/ai/start'){
    ai.running=true;ai.phase='listening';ai.revision++;
    event('provider_session',{event:'session.created',message:'V260 页面演示已启动，无网络语音服务连接',conversation_update:conversation()});
    event('catalog',{skills,expressions});return D.json(aiStatus());
  }
  if(path==='/api/ai/stop'){
    ai.running=false;ai.speech=false;ai.speech_revision++;ai.phase='stopped';ai.revision++;
    event('provider_event',{message:'演示已停止，当前页面的对话保留',conversation_update:conversation()});return D.json(aiStatus());
  }
  if(path==='/api/ai/skills')return D.json(aiStatus());
  if(path==='/api/ai/voice')return voice(body.voice_id)?D.json(aiStatus()):D.json({error:'请选择演示中的音色'},400);
  if(path==='/api/ai/voices'){
    if(!Array.isArray(body.voices)||body.voices.length<1||body.voices.length>20)return D.json({error:'请保留至少一个音色'},400);
    const rows=body.voices.filter(row=>typeof row.name==='string'&&typeof row.id==='string'&&row.name.trim()&&row.id.trim()).map(row=>({name:row.name.trim().slice(0,40),id:row.id.trim().slice(0,200)}));
    if(rows.length!==body.voices.length||!rows.some(row=>row.id===ai.voice_id))return D.json({error:'请保留当前音色，并填写名称和 ID'},400);
    ai.voices=rows;ai.voice_state_revision++;return D.json(aiStatus());
  }
  if(path==='/api/ai/speech'){
    ai.speech=ai.running&&body.enabled===true;ai.speech_revision++;
    event('voice_state',{unlocked:ai.speech,speech_session:'v260-static-demo',speech_revision:ai.speech_revision,speech:{phase:'confirmed',enabled:ai.speech}});return D.json(aiStatus());
  }
  if(path==='/api/ai/camera-mode'){return D.json({...aiStatus(),demo:true});}
  if(path==='/api/ai/commit'){return D.json({accepted:true,demo:true});}
});
document.addEventListener('DOMContentLoaded',()=>{
  document.body.classList.add('pages-demo');
  D.banner('main .page-heading','V260 / control.102 在线演示 · 读数、对话与动作回执均为模拟；不连接实机。','./training/','训练中控演示 →');
  D.lock('#ssh-connect,#ssh-disconnect,#ssh-target,#service-sudo-password,#service-sudo-forget,#camera-connect,#camera-disconnect,#camera-save,#service-mode-calibrate,#service-mode-motion,#service-minus,#service-plus,#service-move,#service-capture,#service-center,#service-verify-imu,#service-init,#service-quick-stop,#service-reboot,#service-shutdown,#service-resume,#management-reconnect,#management-scale-apply,#firmware-choose,#firmware-file,#firmware-flash,#inspection-start,#inspection-stop,#gamepad-repair-start,#chorale-prepare,#chorale-start,#chorale-stop,#ai-api-key,#ai-vision-api-key,#ai-vision-model,#ai-vision-enabled,#ai-vision-capture,#wifi-password,#wifi-connect,#wifi-forget');
  document.getElementById('camera-message').textContent='在线演示不连接摄像头';
  const examples=document.createElement('div');examples.className='ai-actions';examples.id='ai-demo-examples';
  const label=document.createElement('span');label.textContent='模拟指令';examples.append(label);
  for(const [id,text] of [['nod','你听得懂吗？'],['sit','坐下聊一聊'],['voice','切换温柔音色']]){
    const button=document.createElement('button');button.type='button';button.className='button';button.textContent=text;
    button.addEventListener('click',async()=>{
      const result=await fetch('/api/demo/sample',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sample:id})});
      const data=await result.json();if(!result.ok){const message=document.getElementById('ai-message');message.textContent=data.error;message.dataset.error='false';message.hidden=false;}
    });examples.append(button);
  }
  document.querySelector('.ai-chat-footer').before(examples);
  const note=document.createElement('p');note.className='tiny muted';note.textContent='无需填写密钥。启动后点击模拟指令，查看对话、音色切换和工具调用过程。';examples.before(note);
  document.addEventListener('click',event=>{
    const link=event.target.closest('a[href^="/api/"]');if(!link)return;
    event.preventDefault();event.stopImmediatePropagation();
    if(link.pathname==='/api/servos.csv'){
      const rows=snapshot().servos.map(r=>[r.id,r.name,r.angle_deg,r.voltage_v,r.temperature_c]);
      D.download('id,name,angle_deg,voltage_v,temperature_c\n'+rows.map(r=>r.join(',')).join('\n'),'microduck-v260-demo-servos.csv','text/csv');
    }else if(link.pathname==='/api/system-log/download')D.download('[DEMO] R17 V260 / control.102 — simulated robot data only.','microduck-v260-demo-log.txt','text/plain');
    else if(link.pathname==='/api/ai/log/download')D.download(D.history.map(row=>JSON.stringify(row)).join('\n'),'microduck-v260-demo-ai-log.jsonl','application/x-ndjson');
    else if(link.pathname==='/api/recording')downloadRecording();
  },true);
});
function downloadRecording(){D.download(JSON.stringify({schema:'microduck-console-recording/v1',demo:true,frames:recordings.length?recordings:[snapshot()]}),'microduck-v260-demo-recording.json');}
window.__microduckDemo={snapshot,config,catalog,aiStatus,sample};
})();
