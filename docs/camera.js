// Receive-only signalling shapes from official 0.15.1 mediad/webclient.
// No motion JSON-RPC, audio capture or computer-camera permission is requested.
export class Camera {
  constructor(video,onStatus,onStats){this.video=video;this.onStatus=onStatus;this.onStats=onStats;this.generation=0;}
  connect(host,port){
    this.disconnect();const generation=++this.generation;
    if(!/^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/.test(host)||!Number.isInteger(port)||port<1||port>65535)throw Error('请输入有效的摄像头主机和端口');
    if(location.protocol==='https:')throw Error('局域网 ws 信令不能从 HTTPS 页面连接；请使用本地 http://127.0.0.1:8090');
    const ws=this.ws=new WebSocket(`ws://${host}:${port}`);let queue=Promise.resolve();
    this.onStatus('connecting','正在连接官方 mediad…');
    this.deadline=setTimeout(()=>{if(this.pc?.connectionState!=='connected')this.fail('连接超时：检查 mediad、信令端口及两端局域网 UDP。');},20000);
    ws.onmessage=e=>{queue=queue.then(async()=>{if(generation===this.generation)await this.message(JSON.parse(e.data));}).catch(err=>{if(generation===this.generation)this.fail(err.message);});};
    ws.onerror=()=>{if(generation===this.generation)this.fail('摄像头信令无法连接；检查地址、8443 端口和 mediad 状态。');};
    ws.onclose=()=>{if(generation===this.generation)this.fail('摄像头连接已关闭');};
  }
  send(msg){if(this.ws?.readyState===WebSocket.OPEN)this.ws.send(JSON.stringify(msg));}
  async message(msg){
    if(msg.type==='welcome')this.send({type:'list'});
    else if(msg.type==='list'){
      if(this.sessionRequested||this.sessionId)return;
      const producer=msg.producers?.[0];if(!producer)throw Error('mediad 没有视频生产者，请检查 IMX219 和视频管线');
      this.sessionRequested=true;
      this.send({type:'startSession',peerId:producer.id});
    }else if(msg.type==='sessionStarted'){
      this.sessionId=msg.sessionId;const pc=this.pc=new RTCPeerConnection({iceServers:[]});this.pendingICE=[];
      const gen=this.generation;
      pc.onicecandidate=e=>{if(e.candidate)this.send({type:'peer',sessionId:this.sessionId,ice:{candidate:e.candidate.candidate,sdpMLineIndex:e.candidate.sdpMLineIndex}});};
      pc.ontrack=e=>{if(e.track.kind==='video'){this.video.srcObject=e.streams[0]||new MediaStream([e.track]);this.video.play().catch(()=>{});}};
      pc.ondatachannel=e=>{e.channel.onmessage=()=>{};}; // No control methods, including on disconnect.
      pc.onconnectionstatechange=()=>{
        if(gen!==this.generation)return;
        if(pc.connectionState==='connected'){clearTimeout(this.deadline);this.onStatus('live','摄像头已连接');}
        else if(['failed','disconnected'].includes(pc.connectionState))this.fail('视频链路中断，请检查网络后重连');
      };
      this.statsTimer=setInterval(()=>this.stats().catch(()=>{}),1000);
    }else if(msg.type==='peer'){
      if(!this.pc||msg.sessionId!==this.sessionId)return;
      if(msg.sdp){
        await this.pc.setRemoteDescription(msg.sdp);
        for(const ice of this.pendingICE)await this.pc.addIceCandidate(ice);this.pendingICE=[];
        if(msg.sdp.type==='offer'){
          const answer=await this.pc.createAnswer();await this.pc.setLocalDescription(answer);
          this.send({type:'peer',sessionId:this.sessionId,sdp:{type:'answer',sdp:answer.sdp}});
        }
      }else if(msg.ice){
        const ice={candidate:msg.ice.candidate,sdpMLineIndex:msg.ice.sdpMLineIndex};
        if(this.pc.remoteDescription)await this.pc.addIceCandidate(ice);else this.pendingICE.push(ice);
      }
    }else if(msg.type==='error')throw Error(msg.details||'mediad 信令返回错误');
    else if(msg.type==='endSession')this.fail('mediad 已结束视频会话');
  }
  async stats(){
    if(!this.pc)return;const stats=await this.pc.getStats();
    for(const s of stats.values())if(s.type==='inbound-rtp'&&(s.kind==='video'||s.mediaType==='video')){
      const prev=this.previous;this.previous={at:s.timestamp,bytes:s.bytesReceived,frames:s.framesDecoded};
      const dt=prev?(s.timestamp-prev.at)/1000:0;
      this.onStats({fps:s.framesPerSecond??(dt>0?(s.framesDecoded-prev.frames)/dt:null),mbps:dt>0?(s.bytesReceived-prev.bytes)*8/dt/1e6:null,loss:s.packetsLost});
    }
  }
  fail(message){this.disconnect(false);this.onStatus('error',message);}
  disconnect(report=true){
    this.generation++;clearTimeout(this.deadline);clearInterval(this.statsTimer);
    if(this.sessionId)this.send({type:'endSession',sessionId:this.sessionId});
    if(this.pc){this.pc.onconnectionstatechange=null;this.pc.close();this.pc=null;}
    if(this.ws){this.ws.onclose=null;this.ws.onerror=null;this.ws.close();this.ws=null;}
    this.video.srcObject=null;this.sessionId=null;this.sessionRequested=false;this.previous=null;this.pendingICE=[];
    if(report)this.onStatus('idle','通过官方 mediad 接入局域网视频流');
  }
}
