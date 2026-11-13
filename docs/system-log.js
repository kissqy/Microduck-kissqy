/** Important events and summarized repeats; the backend keeps bounded recent logs. */
import {formatError} from './messages.js?v=v260-20261113';
export class SystemLogPanel {
  constructor(){
    this.cursor=0;this.lines=[];this.stopped=false;this.retry=0;
    this.root=document.getElementById('system-log');this.pre=document.getElementById('system-log-output');
    document.getElementById('system-log-follow').checked=true;
    document.getElementById('system-log-copy').onclick=async()=>{
      try{await navigator.clipboard.writeText(this.pre.textContent);this.status('已复制当前显示；下载包含关键事件和重复次数。');}
      catch{this.status('可选中日志文字复制，或下载系统日志。');}
    };
    window.addEventListener('pagehide',()=>{this.stopped=true;clearTimeout(this.timer);});
    this.poll();
  }
  status(text){document.getElementById('system-log-status').textContent=text;}
  async poll(){
    let again=false;
    try{
      if(document.hidden)return;
      const response=await fetch('/api/system-log?after='+this.cursor+'&limit=200',{signal:AbortSignal.timeout(5000)});
      if(!response.ok)throw Error('HTTP '+response.status);
      const data=await response.json();
      if(!Array.isArray(data.entries))throw Error('日志响应无效');
      if(data.gap)this.lines.push('··· 页面仅显示最近记录；下载系统日志查看之前的记录 ···');
      for(const row of data.entries){
        const time=new Date(row.at*1000).toLocaleTimeString('zh-CN',{hour12:false});
        const displayed=/错误|异常|失败|stderr/i.test(row.source||'')?formatError(row.text):row.text;
        this.lines.push(`[${time}] [${row.source}] ${displayed}`);
      }
      this.cursor=data.cursor;
      if(this.lines.length>1500)this.lines.splice(0,this.lines.length-1500);
      let chars=this.lines.reduce((sum,line)=>sum+line.length+1,0);
      while(chars>256*1024&&this.lines.length>1)chars-=this.lines.shift().length+1;
      if(this.lines[0]?.length>256*1024)this.lines[0]='··· 本行页面显示末尾，过长内容仅保留摘要 ···\n'+this.lines[0].slice(-256*1024);
      if(data.entries.length){this.pre.textContent=this.lines.join('\n');if(document.getElementById('system-log-follow').checked)this.pre.scrollTop=this.pre.scrollHeight;}
      this.status(data.error?'系统日志保存异常：'+formatError(data.error):'保留启动、操作与异常；相同连接消息合并计数，日志保留最近约 4 MiB。');
      again=data.has_more;
    }catch(e){this.status('系统日志读取中断：'+formatError(e)+'；稍后重新读取。');}
    finally{if(!this.stopped)this.timer=setTimeout(()=>this.poll(),again?50:1000);}
  }
}
