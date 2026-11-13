import {messageZh} from './messages.js';

export function startupFailure(s){
  if(s?.connection_paused||s?.connection?.active===false)return '';
  if(s?.channels?.startup?.status==='live'){
    const failed=Object.entries(s.startup?.steps||{}).find(([,row])=>row.status==='failed');
    if(failed)return `启动第 ${failed[0]}/4 步失败：${failed[1].detail||'请导出启动诊断'}`;
  }
  const bus=s?.bus||{};
  // A failed startup emits one bus report; the live health heartbeat keeps it
  // authoritative even though there can never be a fresh motion sample.
  if(bus.phase==='configuration_error'&&s.channels?.health?.status==='live')
    return `总线启动失败：${bus.error||s.health?.reason||'请导出启动诊断'}`;
  return '';
}

/** Connection progress is not evidence of a sensor or service fault. */
export function connectionNotice(s,{connectionUI=false}={}){
  const quiet={hidden:true,tone:'neutral',message:''};
  if(s?.connection_paused||(connectionUI&&s?.connection?.active!==true))return quiet;
  const channels=s?.channels||{},service=s?.mode==='service';
  const channel=channels[service?'bus':'state']||{};
  // Native feedback can arrive before the next auxiliary SSH status update.
  const connected=s?.connection?.connected===true||['state','bus','health','system'].some(name=>channels[name]?.status==='live');
  const failed=startupFailure(s);
  if(failed)return {hidden:false,tone:'warning',message:failed};
  const error=channel.status==='error'?channel.error:channels.state?.status==='error'?channels.state.error:'';
  if(error)return {hidden:false,tone:'warning',message:`${connected?'机器人服务连接异常':'连接异常'}：${messageZh(error)}`};
  if(channels.startup?.status==='live'){
    const pending=Object.entries(s.startup?.steps||{}).find(([,row])=>['starting','waiting'].includes(row.status));
    if(pending)return {hidden:false,tone:'neutral',message:`启动第 ${pending[0]}/4 步：${pending[1].detail||'等待完成'}`};
  }
  // robot.health explicitly calls its unfinished first cycle unhealthy; that
  // startup phase belongs with the first-feedback wait, not a failure banner.
  const health=s?.health||{};
  if(channels.health?.status==='live'&&health.healthy===false&&health.reason&&health.reason!=='control loop has not completed a cycle yet')
    return {hidden:false,tone:'warning',message:`机器人服务报告异常：${messageZh(health.reason)}`};
  if(service?s?.service_sample_fresh===true:channel.status==='live')return quiet;
  if(channel.status==='stale'||channels.state?.status==='stale')
    return {hidden:false,tone:'warning',message:'机器人状态已停止更新，当前为旧反馈；等待实时反馈恢复。'};
  return {hidden:false,tone:'neutral',message:connected?'SSH 已连接，等待机器人首次完整反馈…':'正在连接 Zero，等待 SSH 会话建立…'};
}
