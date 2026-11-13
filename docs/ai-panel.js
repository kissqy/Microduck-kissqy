// Live AI diagnostics. Reply replay stays in this page's RAM and never autoplays.
import {formatError} from './messages.js?v=v260-20261113';
const $=id=>document.getElementById(id);
const API='/api/ai';
const MIC_BARS=Array.from({length:16},(_,i)=>`M${3+i*6},${(23-i*22/15).toFixed(1)}V26`);
const TOOL={express_emotion:'官方表情',perform_skill:'执行动作',sit_down:'坐下',stand_up:'站起',head_expression:'头部表达',head_pose:'调整头部',walk_short:'短距离行走',stop_moving:'停止行走',body_pose:'身体姿态',mouth_pose:'嘴巴动作',stay_silent:'保持安静',inspect_scene:'拍照识图'};
Object.assign(TOOL,{switch_voice:'切换音色',list_voices:'音色列表'});
const SKILL={roulade:'翻滚',kick_left:'左脚踢',kick_right:'右脚踢',play_dead:'装死',ground_pick:'低头捡物',sit_toggle:'起坐切换',roller_stand:'滑轮站立'};
const EVENT={model_progress:'模型执行状态',provider_connecting:'连接豆包',provider_session:'豆包会话',mic_ready:'HAT 麦克风就绪',input_gate:'收音屏蔽状态',speaker_ready:'HAT 扬声器待命',asr_started:'开始语音识别',transcript:'你的语音转写',assistant_text:'豆包文字返回',tool_call:'豆包工具调用',tool_result:'动作执行回执',tool_denied:'动作未执行',ipc_request:'发送机器人指令',ipc_accepted:'机器人接收回执',tool_feedback:'回传豆包工具结果',provider_error:'豆包连接错误',asr_error:'转写错误',mic_error:'HAT 收音错误',speaker_error:'HAT 播放错误',provider_event:'豆包事件',model_turn_finished:'本轮模型结束',speaker_playback_started:'HAT 开始播放',speaker_playback_finished:'HAT 播放结束',model_violation:'发声限制已拦截',catalog:'实机动作清单',voice_state:'发声权限'};
Object.assign(EVENT,{vision_state:'识图状态',camera_profile:'摄像头帧率',camera_exposure:'摄像头曝光',vision_image:'照片亮度处理',vision_result:'豆包视觉结果',vision_preview:'拍照画面',vision_preview_error:'拍照预览错误',vision_context:'视觉上下文',tool_error:'工具错误'});
Object.assign(EVENT,{tof_context:'本次 TOF 测距',expression_audio_state:'官方表情配音',vision_timing:'取帧与识图耗时',vision_preview_timing:'预览异步传输'});
Object.assign(EVENT,{input_turn_wait:'豆包断句 / 回复等待',input_turn_commit:'提交本句',input_turn_committed:'豆包已确认输入'});

class ReplyAudioCache{
  constructor(changed=()=>{},limit=32*1024*1024){this.entries=new Map();this.bytes=0;this.limit=limit;this.changed=changed;this.player=null;this.playing=null;}
  remove(id){
    const entry=this.entries.get(id);if(!entry)return;
    if(this.playing===id)this.stop();
    if(entry.url)URL.revokeObjectURL(entry.url);
    this.bytes-=entry.bytes;this.entries.delete(id);
  }
  trim(){while(this.bytes>this.limit||this.entries.size>200)this.remove(this.entries.keys().next().value);}
  handle(event){
    const id=event.audio_id,seq=event.sequence;
    if(!/^[a-f0-9]{32}$/.test(id||'')||!Number.isInteger(seq)||seq<0)return;
    let entry=this.entries.get(id);
    if(event.phase==='chunk'){
      if(!entry&&seq===0){entry={chunks:[],bytes:0,next:0,ready:false};this.entries.set(id,entry);}
      if(!entry)return;
      if(entry.ready||seq!==entry.next||typeof event.data!=='string'||event.data.length>16384){this.remove(id);this.changed();return;}
      try{
        const raw=atob(event.data);if(!raw.length||raw.length%2)throw Error('invalid PCM');
        const pcm=Uint8Array.from(raw,c=>c.charCodeAt(0));
        entry.chunks.push(pcm);entry.bytes+=pcm.byteLength;entry.next++;this.bytes+=pcm.byteLength;this.trim();
      }catch{this.remove(id);this.changed();}
    }else if(event.phase==='end'&&entry){
      if(entry.ready||seq!==entry.next||!entry.bytes){this.remove(id);this.changed();return;}
      const header=new ArrayBuffer(44),view=new DataView(header);
      const ascii=(offset,value)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(i));};
      ascii(0,'RIFF');view.setUint32(4,36+entry.bytes,true);ascii(8,'WAVE');ascii(12,'fmt ');view.setUint32(16,16,true);
      view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,24000,true);view.setUint32(28,48000,true);
      view.setUint16(32,2,true);view.setUint16(34,16,true);ascii(36,'data');view.setUint32(40,entry.bytes,true);
      entry.blob=new Blob([header,...entry.chunks],{type:'audio/wav'});entry.chunks=[];entry.bytes+=44;this.bytes+=44;
      entry.url=URL.createObjectURL(entry.blob);entry.ready=true;this.trim();this.changed();
    }else if(event.phase==='error'){this.remove(id);this.changed();}
  }
  stop(){
    if(this.player){this.player.pause();try{this.player.currentTime=0;}catch{}}
    this.player=null;this.playing=null;
  }
  async toggle(id){
    const entry=this.entries.get(id);if(!entry?.ready)return;
    if(this.playing===id){this.stop();this.changed();return;}
    this.stop();const player=new Audio(entry.url);this.player=player;this.playing=id;
    player.addEventListener('ended',()=>{if(this.player===player){this.stop();this.changed();}},{once:true});
    try{await player.play();this.changed();}
    catch{if(this.player===player)this.stop();this.changed();throw Error('浏览器未能播放这条回复，请再次点击喇叭');}
  }
  clear(){this.stop();for(const id of [...this.entries.keys()])this.remove(id);this.bytes=0;}
}

export class AIPanel{
  constructor(cfg){
    this.cfg=cfg;this.cursor=0;this.es=null;this.status=null;this.rowCount=0;
    this.micLevel=null;this.micReceived=0;
    this.chatMessages=new Map();this.chatRevision=-1;this.chatPhase='stopped';this.chatFollow=true;this.chatPhotos=new Map();
    this.replyAudio=new ReplyAudioCache(()=>this.paintChat());
    this.formLoaded=false;this.configWarning='';
    this.visionPosting=false;this.previewCaptureId=null;
    this.noticeKind='';this.speechPosting=false;this.speechDesired=false;
    this.cameraPosting=false;this.cameraDesired=false;this.cameraDraftDirty=false;this.cameraEpoch=0;
    const click=(id,fn)=>$(id).addEventListener('click',()=>fn.call(this));
    click('ai-save',this.save);click('ai-start',this.start);click('ai-stop',this.stop);
    click('ai-voice-use',this.useVoice);click('ai-voice-add',this.addVoice);click('ai-voice-remove',this.removeVoice);
    click('ai-voice-manage',this.openVoiceManager);click('ai-voice-close',this.closeVoiceManager);
    $('ai-voice-id').addEventListener('change',()=>this.paintVoices());
    click('ai-refresh',this.refreshSkills);
    click('ai-clear',this.clearView);
    click('ai-commit',this.commitInput);click('ai-chat-latest',this.latestChat);
    click('ai-vision-capture',this.captureVision);
    $('ai-speech-enabled').addEventListener('change',()=>this.setSpeech());
    $('ai-vision-enabled').addEventListener('change',()=>this.setCameraMode());
    $('ai-dialogue').addEventListener('scroll',()=>{this.chatFollow=this.chatAtEnd();if(this.chatFollow)$('ai-chat-latest').hidden=true;},{passive:true});
    $('ai-follow').addEventListener('change',()=>{});
    this.load().then(()=>this.events()).catch(e=>this.problem(e));
    this.statusInterval=setInterval(()=>this.load().catch(()=>{}),5000);
    this.micTimer=setInterval(()=>this.paintMic(),300);
    globalThis.addEventListener?.('pagehide',()=>{this.replyAudio.clear();this.es?.close();clearInterval(this.statusInterval);clearInterval(this.micTimer);});
    globalThis.addEventListener?.('pageshow',event=>{if(event.persisted){this.events();this.statusInterval=setInterval(()=>this.load().catch(()=>{}),5000);this.micTimer=setInterval(()=>this.paintMic(),300);this.paintChat();}});
  }
  async get(path){const r=await fetch(API+path,{cache:'no-store'});const o=await r.json();if(!r.ok)throw Error(o.error||'请求失败');return o;}
  async post(path,body={}){
    const r=await fetch(API+path,{method:'POST',headers:{'Content-Type':'application/json',
      'X-Control-Token':this.cfg.control_token},body:JSON.stringify(body)});
    const o=await r.json();if(!r.ok)throw Error(o.error||'请求失败');return o;
  }
  problem(e){this.noticeKind='error';$('ai-message').textContent=formatError(e);$('ai-message').dataset.error='true';$('ai-message').hidden=false;}
  note(s,kind='action'){this.noticeKind=s?kind:'';$('ai-message').textContent=s;$('ai-message').dataset.error='false';$('ai-message').hidden=!s;}
  paintConnection(){
    const s=this.status||{};
    $('ai-connected').textContent=s.provider_ready?'● 豆包已连接':s.running?'◌ 豆包连接中':'○ 豆包未运行';
    $('ai-connected').className='badge '+(s.running?'':'neutral');
    if(s.provider_ready&&this.noticeKind==='connection')this.note('');
  }
  acceptStatus(next,cameraEpoch=this.cameraEpoch){
    const previous=this.status;
    if(previous&&(previous.voice_state_revision??-1)>(next.voice_state_revision??-1)){
      for(const key of ['voices','voice_id','voice_revision','voice_selection','voice_state_revision'])next[key]=previous[key];
    }
    if(previous&&next.speech_session===previous.speech_session&&(previous.voice_revision??-1)>(next.voice_revision??-1)){
      for(const key of ['voice_id','voice_revision','voice_selection'])next[key]=previous[key];
    }
    if(previous&&next.speech_session===previous.speech_session&&Number.isInteger(previous.speech_revision)&&previous.speech_revision>(next.speech_revision??-1)){
      for(const key of ['voice_unlocked','speech_revision','speech'])next[key]=previous[key];
    }
    if(previous&&(cameraEpoch!==this.cameraEpoch||Number.isInteger(previous.camera_revision)&&previous.camera_revision>(next.camera_revision??-1))){
      next.camera_revision=previous.camera_revision;next.camera_profile=previous.camera_profile;
      next.vision={...next.vision,enabled:previous.vision?.enabled};
    }
    this.status=next;
  }
  async load(){
    const before=this.status?.head_limits;
    const cameraEpoch=this.cameraEpoch;
    this.acceptStatus(await this.get('/status'),cameraEpoch);this.paint();
    if(before&&this.status.running&&this.status.provider_ready&&!this.catalogSyncing&&JSON.stringify(before)!==JSON.stringify(this.status.head_limits)){
      this.catalogSyncing=true;
      try{await this.post('/skills');}catch(e){this.problem(e);}finally{this.catalogSyncing=false;}
    }
  }
  paint(){
    const s=this.status||{};
    this.paintConnection();
    this.paintVoice();
    $('ai-skill-count').textContent=String(s.skills?.length||0);
    const skills=$('ai-skills');skills.replaceChildren();
    for(const name of s.skills||[]){const chip=document.createElement('span');chip.className='ai-skill-chip';chip.title=name;chip.textContent=SKILL[name]||TOOL[name]||'自定义动作';skills.append(chip);}
    if(!s.skills?.length)skills.textContent='尚未读取';
    $('ai-expression-count').textContent=String(s.expressions?.length||0);
    const expressions=$('ai-expressions');expressions.replaceChildren();
    for(const row of s.expressions||[]){const chip=document.createElement('span');chip.className='ai-skill-chip';chip.title=row.meaning+' · '+row.seconds+'秒';chip.textContent=row.label;expressions.append(chip);}
    if(!s.expressions?.length)expressions.textContent='需升级配套固件后刷新';
    const axisLabels={neck_pitch:'脖子',head_pitch:'抬低头',head_yaw:'转头',head_roll:'歪头'};
    $('ai-head-ranges').textContent=Object.entries(s.head_limits||{}).map(([axis,span])=>axisLabels[axis]+' '+span.map(v=>Math.round(v*180/Math.PI)+'°').join('～')).join(' · ')||'头部范围尚未读取';
    $('ai-key-state').textContent=s.credentials_present?(s.configuration_saved?'已保存到本机':'已填写'):'尚未保存';
    $('ai-api-key').placeholder=s.credentials_present?'已保存，留空继续使用；填写新密钥可替换':'填写豆包实时语音密钥';
    if(!this.formLoaded){
      if(s.voice_id)$('ai-voice-id').value=s.voice_id;
      if(s.persona)$('ai-persona').value=s.persona;
      if(s.vision?.model)$('ai-vision-model').value=s.vision.model;
      this.formLoaded=true;
    }
    if(s.configuration_error&&s.configuration_error!==this.configWarning){this.configWarning=s.configuration_error;this.problem(new Error(s.configuration_error));}
    $('ai-start').disabled=!!s.running;
    $('ai-stop').disabled=!s.running;
    $('ai-persona').disabled=!!s.running;
    for(const id of ['ai-api-key','ai-vision-api-key','ai-vision-model','ai-save'])$(id).disabled=!!s.running;
    this.paintVoices();
    if(s.mic_level)this.mic(s.mic_level,s.mic_level.received_at_ms);
    this.mergeChat(s.conversation,true);
    this.paintCommit();
    this.paintMic();
    this.paintVision();
    if(s.error)this.problem(new Error(s.error));
  }
  async save(){
    try{
      const args={voice_id:$('ai-voice-id').value.trim(),persona:$('ai-persona').value.trim(),
        vision_model:$('ai-vision-model').value.trim(),vision_enabled:!!$('ai-vision-enabled').checked};
      const key=$('ai-api-key').value.trim();if(key)args.api_key=key;
      const visualKey=$('ai-vision-api-key').value.trim();if(visualKey)args.vision_api_key=visualKey;
      this.acceptStatus(await this.post('/configure',args));this.cameraDraftDirty=false;$('ai-api-key').value='';
      $('ai-vision-api-key').value='';
      this.paint();this.note('语音、视觉和角色配置已保存');return true;
    }catch(e){this.problem(e);return false}
  }
  paintVoices(){
    const s=this.status||{},select=$('ai-voice-id');
    const rows=s.voices||[{name:'当前音色',id:s.voice_id||select.value}];
    const signature=JSON.stringify(rows);
    if(signature!==this.voiceCatalogSignature){
      const keep=select.value;select.replaceChildren();
      for(const row of rows){const option=document.createElement('option');option.value=row.id;option.textContent=row.name+' · '+row.id;select.append(option);}
      select.value=rows.some(row=>row.id===keep)?keep:s.voice_id||rows[0]?.id||'';
      this.voiceCatalogSignature=signature;
    }
    const stamp=(s.speech_session||'')+':'+(s.voice_id||'');
    if(this.voiceStamp!==stamp&&s.voice_id){select.value=s.voice_id;this.voiceStamp=stamp;}
    const pending=!!(s.running&&['pending','unconfirmed'].includes(s.voice_selection?.phase)),busy=!!this.voicePosting||pending;
    select.disabled=busy;
    $('ai-voice-use').disabled=busy||!!s.running&&!s.provider_ready;
    $('ai-voice-add').disabled=busy;
    $('ai-voice-remove').disabled=busy||rows.length<=1||select.value===s.voice_id;
    const active=rows.find(row=>row.id===s.voice_id);
    const state=$('ai-voice-state'),message=(active?'当前：'+active.name+' · '+active.id+'。':'')+(s.voice_selection?.message||'切换确认后，后续生成的回复使用新音色');
    state.textContent=pending?'等待确认':s.voice_selection?.phase==='error'?'切换失败':'当前';state.title=message;select.title=message;
    const listStamp=signature+':'+(s.voice_id||'')+':'+select.value+':'+busy;
    if(this.voiceListStamp!==listStamp){
      const list=$('ai-voice-list'),scroll=list.scrollTop;list.replaceChildren();
      for(const row of rows){
        const item=document.createElement('div'),button=document.createElement('button'),name=document.createElement('strong'),id=document.createElement('small');
        item.setAttribute('role','listitem');button.type='button';button.className='ai-voice-list-row';button.disabled=busy;
        button.setAttribute('aria-pressed',String(select.value===row.id));name.textContent=row.name+(row.id===s.voice_id?' · 当前':'');id.textContent=row.id;
        button.append(name,id);button.addEventListener('click',()=>{select.value=row.id;this.paintVoices();});item.append(button);list.append(item);
      }
      list.scrollTop=scroll;this.voiceListStamp=listStamp;
    }
  }
  openVoiceManager(){this.paintVoices();const dialog=$('ai-voice-manager');if(!dialog.open)dialog.showModal();}
  closeVoiceManager(){$('ai-voice-manager').close();}
  async voicePost(path,body){
    if(this.voicePosting)return;
    this.voicePosting=true;this.paintVoices();
    try{this.acceptStatus(await this.post(path,body));this.paint();return true;}
    catch(e){this.problem(e);return false;}finally{this.voicePosting=false;this.paintVoices();}
  }
  async useVoice(){await this.voicePost('/voice',{voice_id:$('ai-voice-id').value});}
  async addVoice(){
    const rows=[...(this.status?.voices||[{name:'当前音色',id:this.status?.voice_id||$('ai-voice-id').value}]),{name:$('ai-voice-name').value.trim(),id:$('ai-voice-new-id').value.trim()}];
    if(await this.voicePost('/voices',{voices:rows})){$('ai-voice-name').value='';$('ai-voice-new-id').value='';this.note('音色已添加，可下拉选择或在对话中要求切换');}
  }
  async removeVoice(){
    const id=$('ai-voice-id').value;
    await this.voicePost('/voices',{voices:(this.status?.voices||[]).filter(row=>row.id!==id)});
  }
  async start(){try{if(!await this.save())return;this.micLevel=null;this.micReceived=0;this.note('正在连接豆包…','connection');this.acceptStatus(await this.post('/start'));this.paint();}catch(e){this.problem(e)}}
  async stop(){try{this.acceptStatus(await this.post('/stop'));this.paint();this.note('已停止，聊天记录保留');}catch(e){this.problem(e)}}
  async commitInput(){try{await this.post('/commit');this.note('已提交本句');}catch(e){this.problem(e)}}
  async setSpeech(){
    if(this.speechPosting)return;
    this.speechDesired=!!$('ai-speech-enabled').checked;this.speechPosting=true;this.paintVoice();
    try{this.acceptStatus(await this.post('/speech',{enabled:this.speechDesired}));}
    catch(e){this.problem(e)}finally{this.speechPosting=false;this.paintVoice();}
  }
  paintVoice(){
    const s=this.status||{};
    const enabled=!!s.running&&s.voice_unlocked===true,busy=this.speechPosting||s.speech?.phase==='pending';
    $('ai-speech-enabled').checked=enabled;
    $('ai-speech-enabled').disabled=busy||!s.running||!s.provider_ready;
    $('ai-lock').textContent=busy?((this.speechPosting?this.speechDesired:s.speech?.enabled)?'正在启用说话…':'正在关闭说话…'):s.speech?.phase==='error'?'设置未确认 · 显示上次状态':!s.running?'豆包未运行':enabled?'豆包说话已启用':'豆包说话未启用 · 鸭叫保留';
    $('ai-lock').dataset.unlocked=String(enabled);
  }
  async setCameraMode(){
    if(this.cameraPosting)return;
    if(!this.status?.running){this.cameraDraftDirty=true;return;}
    this.cameraDesired=!!$('ai-vision-enabled').checked;
    this.cameraPosting=true;this.cameraEpoch++;this.paintVision();
    try{this.acceptStatus(await this.post('/camera-mode',{enabled:this.cameraDesired}));this.cameraDraftDirty=false;}
    catch(e){this.problem(e)}finally{this.cameraPosting=false;this.cameraEpoch++;this.paintVision();}
  }
  async captureVision(){
    if(this.visionPosting)return;
    this.visionPosting=true;this.paintVision();
    try{this.acceptStatus(await this.post('/vision',{question:$('ai-vision-question').value.trim()||'眼前是什么？'}));this.paint();this.note('已请求 Zero 拍照，照片和结果会留在对应对话里');}
    catch(e){this.problem(e)}finally{this.visionPosting=false;this.paintVision()}
  }
  paintVision(){
    const s=this.status||{},v=s.vision||{};
    const profile=s.camera_profile||{};
    const continuous=!!(s.running&&s.provider_ready&&v.enabled&&profile.phase==='ready');
    this.cfg.onVisionCamera?.(continuous);
    const checkbox=$('ai-vision-enabled');checkbox.disabled=this.cameraPosting;
    if((s.running||!this.cameraDraftDirty)&&typeof v.enabled==='boolean')checkbox.checked=v.enabled;
    $('ai-camera-state').textContent=this.cameraPosting?(this.cameraDesired?'正在开启常开取景…':'正在关闭常开取景…'):
      !s.running&&this.cameraDraftDirty?(checkbox.checked?'已选择常开 · 保存后生效':'已选择按需拍照 · 保存后生效'):
      !v.enabled?'按需拍照 · 常开已关闭':!s.running?'启动 AI 后常开取景 · 15 帧':
      profile.message||(s.provider_ready?'等待摄像头就绪':'等待 AI 连接后常开取景');
    $('ai-camera-state').dataset.warning=String(profile.phase==='warning');
    $('ai-camera-state').title=profile.warning||'实测帧率与温度可在摄像头和系统卡片查看';
    const busy=['queued','waiting_motion','capturing','recognizing'].includes(v.phase);
    $('ai-vision-key-state').textContent=v.credentials_present?'已保存到本机':'火山方舟 · 与语音 KEY 不同';
    $('ai-vision-api-key').placeholder=v.credentials_present?'已保存，留空继续使用':'填写火山方舟 API Key';
    $('ai-vision-capture').disabled=!!(this.visionPosting||busy||!s.running||!s.provider_ready||!v.credentials_present);
    const state=$('ai-vision-state');state.dataset.error=String(!!v.error);
    state.dataset.warning=String(!!(v.exposure_warning||v.image_warning)&&!v.error);
    state.title=[v.exposure_warning,v.image_warning].filter(Boolean).join('；');
    state.textContent=formatError(v.error)||(!v.credentials_present?'填写视觉 KEY 后保存并启动 AI':v.message||'尚未拍照');
    if(Number.isFinite(v.mean_luma))state.textContent+=' · 原始均值 '+v.mean_luma.toFixed(0)+'/255';
    if(v.lift_applied)state.textContent+=' · 逆光已提亮';
    const timing=[];
    if(Number.isFinite(v.read_ms))timing.push('取图 '+v.read_ms+' ms');
    if(Number.isFinite(v.image_ms))timing.push('原图检查 '+v.image_ms+' ms');
    if(Number.isFinite(v.api_ms))timing.push('视觉 '+(v.api_ms/1000).toFixed(1)+' s');
    $('ai-vision-timing').textContent=timing.join(' · ');$('ai-vision-timing').hidden=!timing.length;
    const time=Number.isFinite(v.captured_at_ms)?new Date(v.captured_at_ms).toLocaleTimeString('zh-CN',{hour12:false}):'';
    if(v.capture_id&&/^[a-f0-9]{32}$/.test(v.capture_id)){
      if(this.previewCaptureId!==v.capture_id){
        const url=API+'/vision/frame?id='+v.capture_id;
        $('ai-vision-frame').src=url;$('ai-vision-open').href=url;
        this.previewCaptureId=v.capture_id;
      }
      $('ai-vision-open').hidden=false;
      if(time)state.textContent+=' · '+time;
    }else{$('ai-vision-open').hidden=true;this.previewCaptureId=null;}
    $('ai-vision-result').textContent=v.observation||'';
    $('ai-vision-display').hidden=!v.observation&&$('ai-vision-open').hidden;
  }
  paintCommit(){$('ai-commit').disabled=!(this.status?.running&&this.status?.provider_ready&&this.chatPhase==='transcribing');}
  chatAtEnd(){const box=$('ai-dialogue');return box.scrollHeight-box.clientHeight-box.scrollTop<60;}
  latestChat(){this.chatFollow=true;const box=$('ai-dialogue');box.scrollTop=box.scrollHeight;$('ai-chat-latest').hidden=true;}
  mergeChat(update,replace=false){
    if(!update||!Number.isInteger(update.revision)||update.revision<this.chatRevision)return;
    this.chatRevision=update.revision;this.chatPhase=update.phase||this.chatPhase;
    $('ai-chat-state').textContent=update.note||'';
    const messages=update.messages||[];
    if(replace)this.chatMessages.clear();
    if(update.oldest_id)for(const id of this.chatMessages.keys())if(id<update.oldest_id)this.chatMessages.delete(id);
    for(const message of messages)if(Number.isInteger(message.id)&&!message.type?.startsWith('task')&&(message.type!=='action'||message.name in TOOL))this.chatMessages.set(message.id,message);
    if(replace||messages.length)this.paintChat();
    this.paintCommit();
  }
  paintChat(){
    const box=$('ai-dialogue'),follow=this.chatAtEnd(),top=box.scrollTop;
    box.replaceChildren();
    const chronological=[...this.chatMessages.values()].sort((a,b)=>a.id-b.id);
    const retained=new Set(chronological.map(message=>message.capture_id));
    for(const id of this.chatPhotos.keys())if(!retained.has(id))this.chatPhotos.delete(id);
    const children=new Map();
    for(const message of chronological)if(message.type==='vision'&&this.chatMessages.has(message.parent_id)){
      if(!children.has(message.parent_id))children.set(message.parent_id,[]);
      children.get(message.parent_id).push(message);
    }
    const ordered=[];
    for(const message of chronological){
      if(message.type==='vision'&&this.chatMessages.has(message.parent_id))continue;
      ordered.push(message,...(children.get(message.id)||[]));
    }
    for(const message of ordered){
      const row=document.createElement('div');row.className='ai-chat-line '+message.role;
      row.dataset.messageId=message.id;row.dataset.type=message.type||'text';
      const visual=message.type==='vision';
      const avatar=document.createElement('span');avatar.className='ai-chat-avatar';avatar.textContent=visual?'视觉':message.role==='user'?'你':message.role==='system'?'提示':'豆包';
      const body=document.createElement('div');body.className='ai-chat-body';
      const meta=document.createElement('div');meta.className='ai-chat-meta';
      meta.textContent=`${visual?'本次拍照':message.role==='user'?'你':message.role==='system'?'会话提示':'豆包'} · ${(message.at||'').split('T').at(-1)||''}${message.final===false?' · 识别中':''}${message.blocked?' · 仅中控文字':''}`;
      const text=document.createElement('p');
      if(message.type==='action'){
        const r=message.result||{};
        const action=(TOOL[message.name]||message.name)+(message.arguments?.emotion?' · '+(r.label||this.status?.expressions?.find(x=>x.name===message.arguments.emotion)?.label||message.arguments.emotion):'')+(message.arguments?.skill?' · '+(SKILL[message.arguments.skill]||message.arguments.skill):'');
        text.textContent=action+'\n'+(r.accepted?(r.status==='silence_no_action'?'本轮保持安静，未执行动作。':r.status==='completed'?(message.name==='express_emotion'||message.name==='head_expression'?'官方表情已播放完成。':'模型动作已结束。'):'机器人已接收／处理此请求，动作是否完成请看实机。'):'未执行：'+(formatError(r.reason)||'未获得有效回执'));
      }else text.textContent=message.text||'';
      body.append(meta);
      if(visual){
        if(message.question&&!message.parent_id){const q=document.createElement('div');q.className='ai-chat-photo-question';q.textContent=message.question;body.append(q);}
        if(message.image_available&&/^[a-f0-9]{32}$/.test(message.capture_id||'')){
          let link=this.chatPhotos.get(message.capture_id);
          if(!link){link=document.createElement('a');link.className='ai-chat-photo';link.href=API+'/vision/frame?id='+message.capture_id;link.target='_blank';link.rel='noopener';
          const photo=document.createElement('img');photo.alt='这次提问拍到的画面';photo.loading='lazy';photo.width=message.width||640;photo.height=message.height||360;
          photo.addEventListener('load',()=>{if(this.chatFollow)this.latestChat();},{once:true});
          photo.addEventListener('error',()=>{photo.hidden=true;const tip=document.createElement('span');tip.textContent='本张照片已从会话缓存释放';link.replaceChildren(tip);},{once:true});
          photo.src=link.href;link.append(photo);this.chatPhotos.set(message.capture_id,link);}
          body.append(link);
        }
        if(message.image_error){const tip=document.createElement('div');tip.className='ai-chat-distance';tip.textContent=formatError(message.image_error);body.append(tip);}
        const d=message.distance;
        if(d){const line=document.createElement('div');line.className='ai-chat-distance';line.textContent=d.available?(Number.isFinite(d.center_m)?'TOF 前方中心约 '+d.center_m.toFixed(2)+' 米':'TOF 中心暂无有效距离')+' · '+(d.valid_zones||0)+'/64 区有效':'TOF：'+(d.reason||'暂无新鲜测距');line.title=d.note||'';body.append(line);}
      }
      if(message.role==='assistant'&&message.type==='text'&&/^[a-f0-9]{32}$/.test(message.audio_id||'')){
        const replay=document.createElement('button'),clip=this.replyAudio.entries.get(message.audio_id);
        replay.type='button';replay.className='ai-replay';replay.textContent=this.replyAudio.playing===message.audio_id?'⏹':'🔊';
        replay.disabled=!clip?.ready;replay.title=clip?.ready?'在中控回听这条豆包回复；再次点击停止':clip?'正在接收回复音频':'本窗口没有这条音频；刷新或关闭页面后会清空';
        replay.setAttribute('aria-label','回听这条豆包回复');
        replay.addEventListener('click',()=>this.replyAudio.toggle(message.audio_id).catch(e=>this.problem(e)));
        text.append(replay);
      }
      body.append(text);row.append(avatar,body);box.append(row);
    }
    if(!this.chatMessages.size){const empty=document.createElement('div');empty.className='ai-chat-empty';empty.textContent='对着 HAT 说话，识别文字、豆包回复和动作结果会留在这里。';box.append(empty);}
    if(follow)this.latestChat();else{box.scrollTop=top;$('ai-chat-latest').hidden=false;}
  }
  async refreshSkills(){try{await this.post('/skills');this.acceptStatus(await this.get('/status'));this.paint();this.note('动作清单已更新');}catch(e){this.problem(e)}}
  clearView(){$('ai-trace').replaceChildren();this.rowCount=0;this.note('日志显示已清空');}
  mic(level,received=Date.now()){
    if(!Number.isFinite(level?.dbfs)||!Number.isFinite(received)||received<=this.micReceived)return;
    this.micLevel=level;this.micReceived=received;
    this.paintMic();
  }
  paintMic(){
    const active=!!this.status?.running,now=Date.now();
    const fresh=!!(active&&this.micLevel&&now-this.micReceived<1500);
    const db=fresh?this.micLevel.dbfs:-96;
    const blocked=!!(fresh&&this.micLevel.input_blocked);
    // Low-to-high level ladder; only actual recent dBFS lights up its bars.
    const bars=fresh?Math.ceil(Math.max(0,Math.min(1,(db+60)/54))*MIC_BARS.length):0;
    $('ai-mic-wave-line').setAttribute('d',MIC_BARS.join(''));
    $('ai-mic-wave-active').setAttribute('d',MIC_BARS.slice(0,bars).join(''));
    $('ai-mic-state').textContent=!active?'未启动':!fresh?'等待收音':blocked?(this.micLevel.block_reason==='tail'?'余音 · 屏蔽':'播放 · 屏蔽'):db<=-90?'近静音':'收音中';
    $('ai-mic-monitor').dataset.live=String(fresh);
    $('ai-mic-monitor').dataset.blocked=String(blocked);
    $('ai-mic-db').textContent=fresh?`${db.toFixed(1)} dBFS`:'— dBFS';
    $('ai-mic-sent').textContent=`已上传 ${Number(this.micLevel?.uploaded_seconds||0).toFixed(1)} 秒`;
    $('ai-mic-monitor').title=!active?'HAT 麦克风尚未启动':!fresh?'尚未收到最近的 HAT 音量数据':
      `HAT 实时音量 ${db.toFixed(1)} dBFS · 已上传 ${Number(this.micLevel.uploaded_seconds||0).toFixed(1)} 秒`+(blocked?' · 播放期间不上传真实录音，音量仍显示实际收音':'');
  }
  events(){
    this.es?.close();
    this.es=new EventSource(API+'/stream?after='+this.cursor);
    this.es.addEventListener('audio',message=>{try{this.replyAudio.handle(JSON.parse(message.data));}catch{}});
    this.es.addEventListener('message',message=>{
      try{const e=JSON.parse(message.data);if(!Number.isInteger(e.id)||e.id<=this.cursor)return;this.cursor=e.id;this.add(e);}catch(err){this.problem(err)}
    });
    this.es.addEventListener('error',()=>{$('ai-stream-state').textContent='日志连接中断，正在恢复显示…';});
    this.es.addEventListener('open',()=>{$('ai-stream-state').textContent='实时事件长连接已接入';});
  }
  add(e){
    if(e.kind==='voice_selection'){this.load().catch(()=>{});}
    if(e.kind?.startsWith('task')||['tool_call','tool_result','tool_feedback','tool_denied'].includes(e.kind)&&e.name&&!(e.name in TOOL))return;
    if(e.kind==='voice_state'){
      this.status=this.status||{};const s=this.status;
      if(e.speech_session&&s.speech_session&&e.speech_session!==s.speech_session&&s.running)return;
      if(Number.isInteger(e.speech_revision)&&e.speech_revision<=(s.speech_revision??-1))return;
      s.voice_unlocked=!!e.unlocked;
      if(e.speech_session)s.speech_session=e.speech_session;
      if(Number.isInteger(e.speech_revision))s.speech_revision=e.speech_revision;
      if(e.speech)s.speech=e.speech;
      this.paintVoice();
    }
    if(e.kind==='speech_control'){this.status=this.status||{};this.status.speech={...this.status.speech,...e};this.paintVoice();}
    if(e.kind==='audio_state'){this.status=this.status||{};this.status.muted=!!e.muted;this.paintVoice();}
    if(e.conversation_update)this.mergeChat(e.conversation_update);
    if(e.kind==='camera_profile'){
      this.status=this.status||{};
      const revision=this.status.camera_revision??-1;
      if(Number.isInteger(e.camera_revision)&&e.camera_revision<revision)return;
      if(e.camera_revision===revision&&this.status.camera_profile?.phase==='ready'&&e.phase==='preparing')return;
      if(Number.isInteger(e.camera_revision))this.status.camera_revision=e.camera_revision;
      if(e.phase!=='preparing'&&typeof e.enabled==='boolean')this.status.vision={...this.status.vision,enabled:e.enabled};
      this.status.camera_profile={...e};this.paintVision();
    }
    if(e.kind==='provider_session'&&e.event==='session.created'){
      this.status=this.status||{};this.status.provider_ready=true;this.paintConnection();this.paintCommit();this.paintVision();
    }
    if(['vision_state','vision_preview','camera_exposure','vision_image','vision_timing'].includes(e.kind)&&!(e.kind==='vision_preview'&&e.preview_current===false)){
      this.status=this.status||{};this.status.vision=this.status.vision||{};
      const v=this.status.vision;
      if(['queued','waiting_motion','capturing'].includes(e.phase))for(const key of ['capture_id','width','height','captured_at_ms','mean_luma','exposure_ready','exposure_warning','wait_seconds','sample_count','lift_applied','photo_gamma','image_warning','read_ms','image_ms','capture_ms','api_ms','total_ms','capture_backend','image_bytes','direct_frame'])delete v[key];
      for(const key of ['phase','message','observation','error','capture_id','width','height','captured_at_ms','mean_luma','exposure_ready','exposure_warning','wait_seconds','sample_count','lift_applied','photo_gamma','image_warning','read_ms','image_ms','capture_ms','api_ms','total_ms','capture_backend','image_bytes','direct_frame'])if(key in e){
        if(key==='message'&&(e.kind==='vision_timing'||e.kind==='vision_preview'&&['done','error'].includes(v.phase)))continue;
        v[key]=e[key];
      }
      this.paintVision();
    }
    if(e.kind==='input_gate'&&this.micLevel){this.micLevel={...this.micLevel,input_blocked:!!e.blocked,block_reason:e.reason||''};this.paintMic();}
    if(e.kind==='mic_level'){
      const parsed=Date.parse(e.at);this.mic(e,Number.isFinite(parsed)?parsed:Date.now());return;
    }
    if((e.kind==='transcript'||e.kind==='assistant_text')&&!e.final)return;
    const root=$('ai-trace'),item=document.createElement('div');item.className='ai-trace-row';
    const meta=document.createElement('div');meta.className='ai-trace-meta';
    const tag=e.kind||'event';
    item.dataset.kind=tag;
    meta.textContent=`${(e.at||'').split('T').at(-1)||''}  ·  ${EVENT[tag]||tag}`;item.append(meta);
    let prominent=e.text||e.message||e.reason||e.name||e.method||e.event||'';
    if(tag==='transcript')prominent=(e.final?'你说：':'你说（识别中）：')+(e.text||'');
    if(tag==='assistant_text')prominent='豆包回复'+(e.blocked?'（仅中控文字）':'')+'：'+(e.text||'');
    if(tag==='tool_call')prominent=`${TOOL[e.name]||e.name}${e.arguments?.skill?' · '+(SKILL[e.arguments.skill]||e.arguments.skill):''}\n参数：${JSON.stringify(e.arguments||{})}`;
    if(tag==='tool_result'||tag==='tool_feedback')prominent=`${TOOL[e.name]||e.name} · ${JSON.stringify(e.result||{})}`;
    if(tag==='ipc_request')prominent=`${e.method}\n参数：${JSON.stringify(e.params||{})}`;
    if(tag==='ipc_accepted')prominent=`${e.method} · 已接收指令，尚不代表动作完成。`;
    if(tag.endsWith('_error')||tag==='tool_denied')prominent=formatError(prominent);
    if(['tool_result','tool_feedback'].includes(tag)&&e.result?.accepted===false&&e.result.reason)prominent=(TOOL[e.name]||e.name||'动作')+' · '+formatError(e.result.reason);
    if(prominent){const body=document.createElement('div');body.className='ai-trace-main';
      body.textContent=String(prominent).slice(0,1200);item.append(body);}
    if(['tool_call','tool_result','tool_denied','ipc_request','ipc_accepted','provider_error','provider_protocol_error','provider_event','asr_error','catalog','model_violation','tool_feedback'].includes(tag)){
      const more=document.createElement('details'),sum=document.createElement('summary');sum.textContent='调用参数 / 原始事件';
      const pre=document.createElement('pre');pre.textContent=JSON.stringify(e,null,2);
      more.append(sum,pre);item.append(more);
    }
    root.append(item);
    if(++this.rowCount>450){root.firstChild?.remove();this.rowCount--;}
    if($('ai-follow').checked)root.scrollTop=root.scrollHeight;
  }
}
