/** Page connection settings share the original SSH channels and sudo credential. */
export class SSHConnection {
  constructor(cfg,beforeChange,changed){
    this.cfg=cfg;this.beforeChange=beforeChange;this.changed=changed;this.working=false;
    this.$=id=>document.getElementById(id);
    this.$('ssh-target').value=cfg.ssh_target||'';
    this.$('ssh-target').disabled=!cfg.connection_ui;
    this.$('ssh-form').onsubmit=e=>{e.preventDefault();this.submit('connect');};
    this.$('ssh-disconnect').onclick=()=>this.submit('disconnect');
    const notices=this.$('connection-notices'),service=document.querySelector('.service-status');
    if(service)notices.prepend(service);
    const gait=document.querySelector('.service-gait-preflight');
    if(gait)notices.append(gait);
    this.paint();
  }
  async submit(action){
    if(this.working||!this.cfg.connection_ui)return;
    this.working=true;this.paint();this.beforeChange();
    try{
      const response=await fetch('/api/connection',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},
        body:JSON.stringify({action,target:this.$('ssh-target').value,password:this.$('service-sudo-password').value})});
      const data=await response.json();if(!response.ok||!data.accepted)throw Error(data.error||'连接设置未完成');
      this.cfg.ssh_target=data.target;this.cfg.camera_host=data.camera_host;
      this.$('ssh-target').value=data.target;this.state=data;this.changed(data);
      this.$('ssh-status').textContent=action==='connect'?'正在连接，等待 Zero 实时数据…':'连接已暂停';
    }catch(e){this.$('ssh-status').textContent=e.message;}
    finally{this.working=false;this.paint();}
  }
  render(snapshot){
    if(!snapshot.connection||this.working)return;
    this.state=snapshot.connection;
    this.$('ssh-status').textContent=this.state.connected?'SSH 已连接':this.state.active?this.state.error||'正在连接，等待 Zero 实时数据…':'未连接，填写地址和密码后连接';
    this.paint();
  }
  paint(){
    this.$('ssh-connect').disabled=this.working||!this.cfg.connection_ui;
    this.$('ssh-connect').textContent=this.working?'连接中…':this.state?.active?'重连':'连接';
    this.$('ssh-disconnect').disabled=this.working||!this.state?.active;
  }
}
