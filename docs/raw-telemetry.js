import {supportsFeature} from './service-builds.js';
import {deriveKinematics} from './raw-kinematics.js';

const TTL={state:1.5,health:5,tof:2,system:7,capabilities:20,bus:1.5,calibration:Infinity};
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const number=v=>finite(v)?v:null;
const counter=v=>finite(v)||(typeof v==='string'&&/^[0-9]+$/.test(v));
const value=(v,i)=>Array.isArray(v)?number(v[i]):null;
const vector=(v,n)=>Array.isArray(v)&&v.length===n&&v.every(finite)?v:null;
const deg=v=>finite(v)?v*180/Math.PI:null;
const copy=v=>structuredClone(v);
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const own=(v,k)=>Object.hasOwn(v,k);
const get=(v,k,fallback=null)=>own(v,k)?v[k]:fallback;
export function mergeMetadata(base,current){
  const result={...base};
  for(const [key,v] of Object.entries(current))Object.defineProperty(result,key,{value:object(v)&&object(base[key])?mergeMetadata(base[key],v):v,enumerable:true,writable:true,configurable:true});
  return result;
}

/** u64/i64 values outside JSON's exact integer range remain decimal strings. */
export function decodeTree(bytes){
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),utf8=new TextDecoder('utf-8',{fatal:true});let p=0;
  const take=n=>{if(n<0||p+n>bytes.length)throw Error('原始遥测帧被截断');const begin=p;p+=n;return begin;};
  const u32=()=>view.getUint32(take(4),true);
  const text=()=>{const size=u32(),at=take(size);return utf8.decode(bytes.subarray(at,at+size));};
  const read=(depth=0)=>{
    if(depth>64)throw Error('原始遥测嵌套过深');const tag=view.getUint8(take(1));
    if(tag<3)return [null,false,true][tag];
    if(tag===3||tag===4){const v=view[tag===3?'getBigInt64':'getBigUint64'](take(8),true);return v>=BigInt(Number.MIN_SAFE_INTEGER)&&v<=BigInt(Number.MAX_SAFE_INTEGER)?Number(v):v.toString();}
    if(tag===5){const v=view.getFloat64(take(8),true);return finite(v)?v:null;}
    if(tag===6)return text();
    if(tag===7||tag===8){const size=u32();if(size>bytes.length-p)throw Error('原始遥测集合长度无效');
      if(tag===7)return Array.from({length:size},()=>read(depth+1));
      const result={};for(let i=0;i<size;i++){const key=text();if(own(result,key))throw Error('原始遥测包含重复字段');Object.defineProperty(result,key,{value:read(depth+1),enumerable:true,writable:true,configurable:true});}return result;
    }throw Error('原始遥测类型无效');
  };
  const result=read();if(p!==bytes.length||!object(result))throw Error('原始遥测根或尾部无效');return result;
}

export function decodeRecord(buffer){
  const bytes=buffer instanceof Uint8Array?buffer:new Uint8Array(buffer);
  if(bytes.length<6||new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength).getUint32(0,true)!==bytes.length-4||bytes.length>8*1024*1024+4)throw Error('原始遥测帧长度无效');
  const kind=bytes[4],payload=bytes.subarray(5);
  if(kind===1||kind===3)return {kind,data:JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(payload))};
  if(kind===2||kind===4)return {kind,data:decodeTree(payload)};
  throw Error('原始遥测帧类型无效');
}

export function adaptService(result,report,calibration,sampleElapsed){
  const channels=result.channels,active=channels.bus.status==='live',commissioning=report.mode==='commissioning';
  const sample=report.last_sample||{},diagnostic=report.native||report;
  const source=commissioning?sample.servos||[]:diagnostic.joints||[];
  let rows=new Map(source.filter(object).map(r=>[r.id,r]));if(rows.size!==source.length)rows=new Map();
  let serverAge=diagnostic.sample_age_ms;
  if(commissioning)serverAge=finite(report.updated_at_us)&&finite(sample.at_us)?Math.max(0,(report.updated_at_us-sample.at_us)/1000):null;
  const age=finite(serverAge)?Math.max(sampleElapsed||0,serverAge+(channels.bus.age_ms||0)):null;
  let fresh=active&&age!==null&&age<500&&!['configuration_error','waiting_for_bus','read_error','configuring_uart'].includes(report.phase);
  if(!commissioning&&report.fresh_sample===false)fresh=false;
  const continuable=active&&finite(sampleElapsed)&&sampleElapsed<500&&supportsFeature(report,'coast')&&report.mode==='motion'&&report.phase==='control'&&['fresh','coasting','holding'].includes(report.read_recovery)&&report.policy_enabled===true&&report.homed===true&&!report.torque_off_pending&&diagnostic.torque_state_confirmed===true;
  const mapping=new Map((calibration.calibration?.joints||[]).filter(object).map(r=>[r.id,r]));
  const saved=[...mapping.values()].filter(r=>r.calibrated===true&&r.name===result.servos.find(s=>s.id===r.id)?.name).length;
  const motion=report.motion||{},torque=report.torque_state;
  for(const row of result.servos){
    const raw=rows.get(row.id)||{},cal=mapping.get(row.id)||{},pos=get(raw,'position_raw');
    const valid=Number.isInteger(pos)&&pos>=-32767&&pos<=32767&&(raw.joint||raw.name)===row.name;
    Object.assign(row,{source:'robot.busStatus',status:fresh&&valid&&(commissioning||raw.feedback_fresh!==false)?'live':valid?'stale':'unavailable',calibrated:false,position_raw:pos,speed_raw:get(raw,'speed_raw'),load_raw:get(raw,'load_raw'),current_raw:get(raw,'current_raw'),voltage_v:get(raw,'voltage_v',get(raw,'volts')),temperature_c:get(raw,'temperature_c'),current_source:'飞特原始计数；未经电流单位标定',encoder_deg:valid?(pos-2048)*360/4096:null,calibration:Object.keys(cal).length?cal:null,sample_age_ms:age,moving:get(raw,'moving'),current_ma:commissioning?null:get(raw,'current_ma')});
    if(commissioning){
      Object.assign(row,{angle_deg:null,target_deg:null,error_deg:null,velocity_rpm:null});
      const okay=valid&&raw.calibrated===true&&cal.calibrated===true&&cal.name===row.name&&Number.isInteger(cal.zero_raw)&&cal.zero_raw>=0&&cal.zero_raw<=4095&&Number.isInteger(cal.direction)&&[-1,1].includes(cal.direction)&&finite(cal.min_rad)&&finite(cal.max_rad)&&cal.min_rad<cal.max_rad;
      if(okay){row.angle_deg=(pos-cal.zero_raw)*360/4096*cal.direction;row.calibrated=true;}
      const goal=motion.id===row.id?get(motion,'target_raw'):null;row.goal_position_raw=goal;
      if(okay&&finite(goal)){row.target_deg=(goal-cal.zero_raw)*360/4096*cal.direction;row.error_deg=row.angle_deg-row.target_deg;}
      row.torque_enabled=active?(torque==='off'?false:torque==='single_joint_enabled'?row.id===motion.id:null):null;
    }else{
      Object.assign(row,{calibrated:raw.calibrated===true,angle_deg:null,target_deg:null,error_deg:null});
      if(finite(raw.position_rad))row.angle_deg=deg(raw.position_rad);
      if(finite(raw.velocity_rad_s))row.velocity_rpm=raw.velocity_rad_s*30/Math.PI;
      row.torque_enabled=active?get(diagnostic,'torque_state_confirmed'):null;
      const targets=result.state.targets||[];
      if(channels.state.status==='live'){
        if(targets.length===15&&finite(targets[row.index]))row.target_deg=deg(targets[row.index]);
        if(finite(row.angle_deg)&&finite(row.target_deg))row.error_deg=row.angle_deg-row.target_deg;
      }
    }
  }
  if(commissioning){
    const imu=sample.imu||{},g=vector(imu.gravity,3);
    Object.assign(result.imu,{gravity:g,gyro:get(imu,'gyro_rad_s'),quat:get(imu,'quaternion_wxyz'),ready:get(imu,'ready'),sequence:get(imu,'sequence'),age_ms:get(imu,'age_ms'),age_upper_bound_ms:get(imu,'age_upper_bound_ms'),firmware_status:get(imu,'status'),mount_verified:report.imu_mount_verified===true,status:fresh&&g&&imu.valid===true?'live':g?'stale':'unavailable',source:'robotd / FT6 / 当前安装变换',reason:fresh?null:'等待新鲜的整链样本',roll_deg:g?deg(Math.atan2(-g[1],-g[2])):null,pitch_deg:g?deg(Math.atan2(g[0],Math.hypot(g[1],g[2]))):null});
  }else Object.assign(result.imu,{mount_verified:diagnostic.imu_mount_verified===true,age_upper_bound_ms:get(diagnostic,'imu_age_upper_bound_ms'),firmware_status:get(diagnostic,'imu_status')});
  const count=result.servos.filter(r=>r.calibrated).length;
  return Object.assign(result,{bus:report,calibration,service_sample_fresh:fresh,service_sample_age_ms:age,service_walk_continuable:continuable,calibrated_count:count,saved_calibrated_count:saved,pose_calibrated:count===15,read_only:false,service_compatible:supportsFeature(report,'supported')});
}

export class TelemetryStore{
  constructor(config,clock=()=>performance.now()/1000,wall=()=>Date.now()/1000){this.config=config;this.clock=clock;this.wall=wall;this.started=clock();this.reset();}
  reset(){
    this.data={};this.base={};this.model=null;this.kinematics=null;this.events=[];this.history=[];this.lastRecord=-1;this.busSampleKey=null;this.busSampleAt=null;
    this.aux={connection_paused:true,service_operation:false,inspection_active:this.config.mode!=='service',gait_capture:false,service_commands:[]};
    this.channels=Object.fromEntries(Object.keys(TTL).map(k=>[k,{status:'waiting',at:null,error:'',seq:0}]));
  }
  disconnect(){
    for(const channel of Object.keys(TTL))this.ingest({channel,error:'SSH 连接已暂停'});
    this.aux={...this.aux,connection_paused:true,connection:{...this.aux.connection,active:false,connected:false}};
  }
  ingest(event){
    const channel=event?.channel,c=this.channels[channel];if(!c)return;
    const previous=[c.status,c.error].join('\0'),now=this.clock(),data=event.data;
    if(channel==='tof'&&!own(event,'error')&&object(data?.subscription)){
      const first=!this.data.tof?.subscription;this.data.tof={...this.data.tof,subscription:copy(data.subscription)};
      c.status=c.at===null?'waiting':now-c.at>TTL.tof?'stale':'live';c.error='';
      if(first||previous!==[c.status,c.error].join('\0'))this.event(channel,c.status,'测距服务已连接，等待有效测距数据');return;
    }
    if(own(event,'error')){c.status='error';c.error=String(event.error).slice(0,500);}
    else if(object(data)){
      this.data[channel]=data;
      if(channel==='bus'){
        const sample=data.last_sample||{},key=JSON.stringify([get(sample,'at_us'),get(sample,'cycle',get(data,'cycle')),get(data,'mode')]);
        if(key!==this.busSampleKey){this.busSampleKey=key;this.busSampleAt=now;}
      }
      Object.assign(c,{status:'live',error:'',at:now,seq:c.seq+1});
    }else return;
    if(previous!==[c.status,c.error].join('\0'))this.event(channel,c.status,c.error||'数据连接已恢复');
  }
  event(channel,level,message){this.events.push({at:this.wall(),channel,level,message});if(this.events.length>150)this.events.shift();}
  accept(buffer){
    const {kind,data}=decodeRecord(buffer);
    if(kind===1){
      if(data.schema!=='r17.raw.v1'||!object(data.channels))throw Error('原始遥测协议版本不符');
      this.base=data.channels;this.model=data.model;this.kinematics=data.kinematics;
      for(const channel of ['calibration','capabilities'])if(object(data[channel]))this.ingest({channel,data:data[channel]});return;
    }
    if(kind===3){
      if(data.id===1&&object(data.result)&&data.result.accepted===true)this.ingest({channel:'tof',data:{subscription:data.result}});
      else if(data.method==='tof.frame'&&object(data.params))this.ingest({channel:'tof',data:data.params});return;
    }
    for(const [channel,raw] of Object.entries(data))if(this.channels[channel]&&object(raw)){
      const value=mergeMetadata(this.base[channel]||{},raw);
      if(channel==='state'&&this.kinematics){
        if(Array.isArray(value.joints)&&value.joints.every(Number.isFinite))Object.assign(value,deriveKinematics(this.kinematics,this.config.names,value.joints));
        else Object.assign(value,{frames:null,skeleton:[]});
      }
      this.ingest({channel,data:value});
    }
  }
  auxiliary(data){
    if(data.inspection_active&&!this.aux.inspection_active)this.history=[];
    if(data.gait_capture&&!this.aux.gait_capture&&!data.inspection_active){this.history=[];this.lastRecord=-1;}
    this.aux={...this.aux,...data};
    if(object(data.calibration))this.ingest({channel:'calibration',data:data.calibration});
  }
  snapshot(record=true){
    const now=this.clock(),channels=copy(this.channels);
    for(const [name,c] of Object.entries(channels)){const at=c.at;delete c.at;c.age_ms=at===null?null:Math.round((now-at)*1000);if(c.status==='live'&&now-at>TTL[name])c.status='stale';}
    const state=copy(this.data.state||{}),health=copy(this.data.health||{}),extension=state.diagnostics||{},slow=extension.slow||{},slowAge=number(slow.age_ms),tempsFresh=slowAge!==null&&slowAge<=5000;
    const servos=this.config.ids.map((id,index)=>{
      const name=this.config.names[index],angle=value(state.joints,index),target=value(state.targets,index);
      const row={id,name,label:this.config.labels[index],index,group:index<5?'left':index<10?'head':'right',angle_deg:deg(angle),target_deg:deg(target),error_deg:angle!==null&&target!==null?deg(angle-target):null,velocity_rpm:null,current_ma:value(extension.currents_ma,index),temperature_c:tempsFresh?value(slow.temps_c,index):null,voltage_v:null,pwm_percent:null,current_ratio_percent:null,torque_enabled:null,hardware_error:null,status:angle!==null?channels.state.status:'unavailable',source:'robot.state',temperature_age_ms:slowAge,current_source:Object.keys(extension).length?'robot.state.diagnostics / 绝对值':'未导出'};
      const velocity=value(extension.velocities,index);if(velocity!==null)row.velocity_rpm=velocity*30/Math.PI;
      if(!Object.keys(extension).length&&health.motors?.hottest===name){row.temperature_c=channels.health.status==='live'?number(health.motors.max_c):null;row.temperature_source='robot.health / 仅最高温关节';}return row;
    });
    const gravity=vector(state.safety?.gravity,3),validGravity=gravity&&gravity.reduce((s,x)=>s+x*x,0)>=.01;
    const roll=validGravity?deg(Math.atan2(-gravity[1],-gravity[2])):null,pitch=validGravity?deg(Math.atan2(gravity[0],Math.hypot(gravity[1],gravity[2]))):null;
    const rawImu=extension.imu||{};let imuStatus=channels.state.status,imuReason=rawImu.reason||rawImu.error||null;
    if(imuStatus==='live'){
      if(roll===null||pitch===null){imuStatus='unavailable';imuReason='没有有效重力方向';}
      else if(channels.health.status==='live'){
        if(finite(health.imu?.consecutive_stale_blocks)&&health.imu.consecutive_stale_blocks>=25){imuStatus='stale';imuReason='官方报告 IMU 连续旧样本达到 25，不能当作新姿态';}
        else if(health.imu?.ready===false){imuStatus='waiting';imuReason='官方 SFLP 融合尚未就绪';}
      }
    }
    const imu={gravity,roll_deg:roll,pitch_deg:pitch,gyro:vector(rawImu.gyro,3),quat:vector(rawImu.quat,4),source:Object.keys(rawImu).length?'robot.state.diagnostics':'robot.state.safety.gravity',health:get(health,'imu'),status:imuStatus,reason:imuReason,ready:get(rawImu,'ready'),sequence:get(rawImu,'sequence'),age_ms:get(rawImu,'age_ms')};
    const result={schema:'microduck-console/v1',service_operation:!!this.aux.service_operation,connection_paused:!!this.aux.connection_paused,version:this.config.version,baseline:this.config.baseline,mode:this.config.mode,read_only:!this.config.control_enabled,at:this.wall(),uptime:now-this.started,channels,state,health,imu,capabilities:copy(this.data.capabilities||{}),tof:copy(this.data.tof||{}),servos,system:copy(this.data.system||{}),events:copy(this.events),extended:extension.schema==='microduck-observer/v1',pose_calibrated:true};
    if(this.config.mode==='service')adaptService(result,copy(this.data.bus||{}),copy(this.data.calibration||{}),this.busSampleAt===null?null:(now-this.busSampleAt)*1000);
    const bus=result.bus||{},loop=this.config.mode==='service'&&bus.mode==='motion'&&counter(bus.cycle)&&channels.bus.status==='live';
    if(record&&(this.aux.inspection_active||loop||this.aux.gait_capture)&&now-this.lastRecord>=.095){
      const frame=copy(result);delete frame.events;if(frame.bus){delete frame.bus.last_failure;delete frame.bus.diagnostics;}
      this.history.push(frame);if(this.history.length>1200)this.history.shift();this.lastRecord=now;
    }
    return {...result,control:this.aux.control||{available:false,connected:false},service_control:this.aux.service_control||{available:false},connection:this.aux.connection||null};
  }
  recording(){return {schema:'microduck-console-recording/v1',baseline:this.config.baseline,mode:this.config.mode,created_at:this.wall(),frames:this.history.length?copy(this.history):[this.snapshot()],service_commands:copy(this.aux.service_commands||[]),last_failure:copy(this.data.bus?.last_failure??null)};}
}

export class RawTelemetry{
  constructor(config,onSnapshot,onError){this.config=config;this.store=new TelemetryStore(config);this.onSnapshot=onSnapshot;this.onError=onError;this.closed=false;this.generation=null;this.connect();this.timer=setInterval(()=>{if(this.ready)this.onSnapshot(this.store.snapshot());},100);}
  connect(){
    const socket=this.socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/telemetry/socket`,['r17-telemetry','r17-auth.'+this.config.control_token]);socket.binaryType='arraybuffer';
    socket.onmessage=event=>{
      try{
        if(typeof event.data==='string'){
          const message=JSON.parse(event.data);
          if(own(message,'reset')){if(this.generation!==message.reset){if(message.preserve)this.store.disconnect();else this.store.reset();this.generation=message.reset;}this.ready=true;}
          if(message.event)this.store.ingest(message.event);
          if(message.aux&&message.generation===this.generation){this.store.auxiliary(message.aux);this.ready=true;}
        }else this.store.accept(event.data);
      }catch(error){this.onError(error);socket.close();}
    };
    socket.onclose=()=>{this.ready=false;for(const channel of Object.keys(TTL))this.store.ingest({channel,error:'本地遥测连接已断开'});if(!this.closed){this.onError(Error('本地遥测连接已断开'));this.retry=setTimeout(()=>this.connect(),1000);}};
    socket.onerror=()=>socket.close();
  }
  close(){this.closed=true;clearInterval(this.timer);clearTimeout(this.retry);this.socket?.close();}
}
