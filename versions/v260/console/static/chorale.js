const parts={bass:'低音',tenor:'男高音',alto:'中音',soprano:'高音'};

export function choraleView(s,options={}){
  const job=s.service_control?.job;
  const live=!options.replay&&!options.offline&&!s.connection_paused&&s.channels?.state?.status==='live';
  const online=live&&s.service_sample_fresh&&s.service_compatible;
  const busy=!!(s.service_control?.busy||s.service_control?.stopping||job?.status==='running');
  const bus=s.bus||{},native=bus.native||bus;
  const off=!bus.torque_off_pending&&(bus.mode==='commissioning'?bus.torque_state==='off':native.torque_state_confirmed===false);
  const c=live?s.state?.chorale:null;
  let text=options.replay?'历史回放 · 合唱操作不可用':!live?'等待机器人实时状态':!c?'未开始合唱':c.part?`正在合唱 · ${parts[c.part]||c.part} · ${c.voices} 个声部`:c.joining?'找到伙伴，正在同步节拍…':`等待另一只鸭子 · 当前 ${c.voices??1} 个声部`;
  if(c?.part&&Number.isFinite(c.beats))text+=` · 第 ${Math.floor(c.beats/4)+1} 小节`;
  return {text,prepare:online&&!busy&&off,start:online&&!busy&&bus.mode==='motion'&&!c,stop:live&&!busy};
}

export class ChoralePanel{
  constructor(panel){
    this.panel=panel;
    for(const operation of ['prepare','start','stop']){
      panel.$('chorale-'+operation).onclick=()=>panel.post({action:'chorale-'+operation,...(operation==='prepare'?{supported:true}:{})});
    }
  }
  render(s,options){
    const view=choraleView(s,options);
    this.panel.$('chorale-state').textContent=view.text;
    for(const operation of ['prepare','start','stop'])this.panel.$('chorale-'+operation).disabled=!view[operation]||this.panel.posting||!!this.panel.centerConfirmation;
  }
}
