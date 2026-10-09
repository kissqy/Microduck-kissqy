/** One browser socket for input; no polling, reconnect replay, or idle motor frames. */
export class ControlSocket {
  constructor(token,disconnected){this.token=token;this.disconnected=disconnected;this.ws=null;this.pending=new Map();this.id=0;}
  async open(){
    this.close();
    const ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/control/socket`,['r17-control','r17-auth.'+this.token]);this.ws=ws;
    return new Promise((resolve,reject)=>{
      let opened=false;
      const timer=setTimeout(()=>{this.close();reject(Error('手柄长连接建立超时'));},2500);
      ws.onopen=()=>{opened=true;clearTimeout(timer);resolve();};
      ws.onmessage=e=>{
        try{
          const row=JSON.parse(e.data),entry=this.pending.get(row.id);if(!entry)return;
          this.pending.delete(row.id);clearTimeout(entry.timer);
          if(row.error)entry.reject(Error(row.error));
          else entry.resolve({...row.result,browser_rtt_ms:performance.now()-entry.at,dispatch_ms:row.elapsed_ms});
        }catch{this.close();this.disconnected('手柄长连接回执无效；动作不重发');}
      };
      ws.onerror=()=>ws.close();
      ws.onclose=()=>{
        clearTimeout(timer);if(this.ws!==ws)return;this.ws=null;
        this.rejectPending('手柄长连接已断开；动作不重发');
        if(opened)this.disconnected('手柄长连接已断开，网页输入已暂停');
        else reject(Error('无法建立手柄长连接，请查看系统日志'));
      };
    });
  }
  request(payload){
    if(this.ws?.readyState!==WebSocket.OPEN)return Promise.reject(Error('手柄长连接尚未就绪'));
    return new Promise((resolve,reject)=>{
      const id=++this.id,at=performance.now();
      const timer=setTimeout(()=>{this.close();this.disconnected('手柄回执超时；动作不重发');},1500);
      this.pending.set(id,{resolve,reject,timer,at});
      try{this.ws.send(JSON.stringify({id,payload}));}
      catch(e){this.pending.delete(id);clearTimeout(timer);reject(e);}
    });
  }
  rejectPending(reason){for(const entry of this.pending.values()){clearTimeout(entry.timer);entry.reject(Error(reason));}this.pending.clear();}
  close(){const ws=this.ws;this.ws=null;this.rejectPending('手柄连接已关闭；动作不重发');if(ws)ws.close();}
}
