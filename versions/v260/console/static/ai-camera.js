// Reuse the existing fully negotiated receive-only video connection.
// Closing AI releases only the preview it opened, never a manual connection.
export class AICamera {
  constructor(camera,address,problem){this.camera=camera;this.address=address;this.problem=problem;this.active=false;this.attempted=false;this.ownedGeneration=null;}
  manual(){this.ownedGeneration=null;this.attempted=true;}
  update(active){
    active=!!active;
    if(active!==this.active){this.active=active;this.attempted=false;}
    if(!active){
      if(this.ownedGeneration===this.camera.generation)this.camera.disconnect();
      this.ownedGeneration=null;return;
    }
    if(this.attempted)return;
    this.attempted=true;
    if(this.camera.ws)return;
    try{
      const address=this.address();this.camera.connect(address.host,address.port);
      this.ownedGeneration=this.camera.generation;
    }catch(error){this.ownedGeneration=null;this.problem(error.message);}
  }
}
