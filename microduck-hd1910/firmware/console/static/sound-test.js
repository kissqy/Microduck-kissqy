// Voice test: play the robot's own sounds through the official intent and say
// what the daemon answered. There is no direct aplayer here on purpose — a click
// that bypassed `robot.sound` would prove the speaker works while the path the
// duck actually uses stays broken.
const REFUSALS=[
  [/read-only/i,'当前 robotd 处于标定模式，官方接口拒绝发声'],
  [/audio.*enabled|enabled.*audio/i,'robotd.toml 里 [audio] enabled = false'],
  [/bank|音库/i,'音库没有渲染出 wav'],
];

export function refusalText(reason,detail){
  const message=String(reason||detail?.message||'');
  for(const [pattern,text] of REFUSALS)if(pattern.test(message))return text;
  return message||'robotd 没有说明拒绝原因';
}

// Only the commissioning refusal has an action attached to it; the others are
// configuration the operator has to change elsewhere. The reason may already be
// translated by the board helper, so both spellings are recognised.
export function refusalHint(reason,detail){
  const message=String(reason||detail?.message||'');
  if(!/read-only|标定模式/i.test(message))return '';
  return '到「机器人服务模式」切到运动模式后再试';
}

export function playableState({online,replay,busy,catalog,serviceEnabled=true}){
  if(replay)return {disabled:true,reason:'历史回放时不发声'};
  if(!online)return {disabled:true,reason:'尚未连接 Zero'};
  if(!serviceEnabled)return {disabled:true,reason:'声音测试需要 --feetech 服务模式'};
  if(busy)return {disabled:true,reason:'正在提交上一次播放'};
  if(catalog&&catalog.can_play===false)return {disabled:true,reason:catalog.reason};
  return {disabled:false,reason:''};
}

export class SoundPanel{
  constructor(cfg){
    this.cfg=cfg;this.root=document.getElementById('sound-panel');
    if(!this.root)return;
    this.$=id=>document.getElementById(id);
    this.tags=(cfg.sound?.tags||[]).map(row=>row.tag);
    this.names=cfg.sound?.names||{};
    this.catalog=null;this.busy=false;this.online=false;this.replay=false;this.posting=0;
    this.build();
  }

  client(){
    this.owner=this.owner||crypto.randomUUID().replaceAll('-','');
    return this.owner;
  }

  build(){
    const list=this.$('sound-buttons');
    list.replaceChildren(...this.tags.map(tag=>{
      const button=document.createElement('button');
      button.type='button';button.className='button';button.dataset.tag=tag;
      button.textContent=this.names[tag]||tag;
      button.title=`robot.sound · tag ${tag}`;
      button.onclick=()=>this.play(tag,button);
      return button;
    }));
    const refresh=this.$('sound-refresh');
    if(refresh)refresh.onclick=()=>this.loadCatalog();
  }

  async post(command,button){
    this.busy=true;this.paint(button);
    try{
      const response=await fetch('/api/control',{method:'POST',
        headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},
        body:JSON.stringify({...command,client:this.client(),seq:++this.posting}),
        signal:AbortSignal.timeout(15000)});
      const data=await response.json();
      if(!response.ok)throw Error(data.error||'控制接口拒绝了请求');
      return data;
    }finally{
      this.busy=false;this.paint(button);
    }
  }

  async loadCatalog(){
    if(!this.online||this.busy||this.replay)return;
    try{
      const data=await this.post({action:'sound_list'});
      if(data&&Array.isArray(data.tags)){this.catalog=data;this.showCatalog();}
    }catch(e){
      this.feedback(e.message,'error');
    }
  }

  async play(tag,button){
    if(this.busy||this.replay)return;
    this.feedback(`${this.names[tag]||tag} 正在提交…`,'running');
    try{
      const data=await this.post({action:'play_sound',tag},button);
      if(data?.accepted===true){
        this.feedback(`${this.names[tag]||tag} 已提交 · via robotd（${tag}）`,'completed');
      }else{
        const reason=refusalText(data?.reason,data?.detail);
        const hint=refusalHint(data?.reason,data?.detail);
        this.feedback(hint?`${reason} · ${hint}`:reason,'error');
      }
    }catch(e){
      this.feedback(e.name==='TimeoutError'||e.name==='AbortError'
        ?'播放请求超时；未确认成功，请查看系统日志':e.message,'error');
    }
  }

  showCatalog(){
    const catalog=this.catalog;
    this.$('sound-bank').textContent=catalog.bank?`音库 ${catalog.bank}`:'音库未配置';
    for(const button of this.$('sound-buttons').children){
      const row=catalog.tags.find(item=>item.tag===button.dataset.tag);
      if(row)button.title=`robot.sound · tag ${row.tag} · ${row.wavs} 个 wav`;
    }
    if(catalog.can_play===false)this.feedback(catalog.reason,'error');
  }

  feedback(message,tone){
    const el=this.$('sound-feedback');if(!el)return;
    el.textContent=message||'';
    el.className='panel-note service-job '+(tone||'');
  }

  render(s,options={}){
    if(!this.root)return;
    this.replay=!!options.replay;
    const connection=s?.connection;
    this.online=!options.offline&&(!this.cfg.connection_ui||connection?.active===true);
    // The board-side helper needs the service transport, which only exists in
    // --feetech mode; otherwise the click would fail with a 503 instead.
    this.serviceEnabled=this.cfg.service_enabled!==false;
    const volume=s?.control?.audio?.volume;
    this.$('sound-volume').textContent=Number.isInteger(volume)?`音量 ${volume}%`:'音量未回读';
    const state=playableState({online:this.online,replay:this.replay,busy:this.busy,catalog:this.catalog,serviceEnabled:this.serviceEnabled});
    for(const button of this.$('sound-buttons').children)button.disabled=state.disabled;
    if(this.$('sound-refresh'))this.$('sound-refresh').disabled=state.disabled;
    this.$('sound-status').textContent=state.reason||'点击试听；实际发声由 robotd 走官方意图';
    // The bank listing needs one round trip through the board; do it once.
    if(!state.disabled&&!this.catalog&&!this.catalogTried){this.catalogTried=true;this.loadCatalog();}
    if(state.disabled)this.catalogTried=false;
  }

  paint(button){
    const state=playableState({online:this.online,replay:this.replay,busy:this.busy,catalog:this.catalog,serviceEnabled:this.serviceEnabled});
    for(const item of this.$('sound-buttons').children)item.disabled=state.disabled;
    if(button)button.textContent=this.busy?'播放中…':(this.names[button.dataset.tag]||button.dataset.tag);
  }
}
