import * as T from './vendor/three.module.min.js';
import {OrbitControls} from './vendor/OrbitControls.js';
import {parseDuck,rootQuaternion,displayRootQuaternion} from './pose.js';
import {servoPartMap} from './joint-map.js';

export class DuckView {
  constructor(){this.headingReference=null;this.displayYaw=null;}
  async init(container,home,onSelect) {
    this.home=home; this.onSelect=onSelect; this.container=container;
    this.initialView='front';
    this.scene=new T.Scene();this.scene.background=new T.Color('#101619');
    this.camera=new T.PerspectiveCamera(37,1,.005,20);this.camera.up.set(0,0,1);
    this.camera.position.set(.56,0,.23);
    this.renderer=new T.WebGLRenderer({antialias:true,alpha:false});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));
    this.renderer.outputColorSpace=T.SRGBColorSpace;
    this.renderer.toneMapping=T.ACESFilmicToneMapping;
    container.append(this.renderer.domElement);
    this.controls=new OrbitControls(this.camera,this.renderer.domElement);
    this.controls.target.set(0,0,.145);this.controls.enableDamping=false;
    this.controls.minDistance=.065;this.controls.maxDistance=1.8;
    this.controls.addEventListener('start',()=>{this.focus=null;this.initialView=null;});
    this.scene.add(new T.HemisphereLight(0xf0f5ff,0x50565b,2));
    const key=new T.DirectionalLight(0xffffff,2.2);key.position.set(.3,-.4,.8);this.scene.add(key);
    const rim=new T.DirectionalLight(0xe3edff,.8);rim.position.set(-.5,.4,.25);this.scene.add(rim);
    const grid=new T.GridHelper(1.6,32,0x415147,0x23302d);grid.rotation.x=Math.PI/2;grid.position.z=-.001;this.scene.add(grid);
    const axes=new T.AxesHelper(.09);axes.position.set(0,0,.004);this.scene.add(axes);
    const modelResponse=await fetch('./assets/duck-visual.bin');if(!modelResponse.ok)throw Error('官方完整视觉模型读取失败');
    this.model=parseDuck(await modelResponse.arrayBuffer());
    // Share immutable GPU geometry between measured and target poses.
    this.geometry=this.model.meshes.map(m=>{
      const g=new T.BufferGeometry();g.setAttribute('position',new T.BufferAttribute(m.vertices,3));
      g.setAttribute('normal',new T.BufferAttribute(m.normals,3));g.setIndex(new T.BufferAttribute(m.indices,1));
      g.computeBoundingBox();g.computeBoundingSphere();return g;
    });
    this.actual=this.build(false);this.ghost=this.build(true);
    this.scene.add(this.actual.root,this.ghost.root);this.ghost.root.visible=false;
    this.ray=new T.Raycaster();let start=null;
    this.renderer.domElement.addEventListener('pointerdown',e=>{start=e.isPrimary&&e.button===0?{x:e.clientX,y:e.clientY,id:e.pointerId}:null;});
    this.renderer.domElement.addEventListener('pointercancel',()=>{start=null;});
    this.renderer.domElement.addEventListener('pointerup',e=>{
      const down=start;start=null;
      if(!down||down.id!==e.pointerId||Math.hypot(e.clientX-down.x,e.clientY-down.y)>5)return;
      const b=this.renderer.domElement.getBoundingClientRect();
      this.ray.setFromCamera(new T.Vector2((e.clientX-b.left)/b.width*2-1,1-(e.clientY-b.top)/b.height*2),this.camera);
      // Transparent covers/bearings must not consume a servo click.
      const hit=this.ray.intersectObjects(this.actual.servos,false)[0];if(hit)onSelect(hit.object.userData.joint);
    });
    this.observer=new ResizeObserver(()=>{const w=container.clientWidth,h=container.clientHeight;if(w&&h){this.camera.aspect=w/h;this.camera.updateProjectionMatrix();this.renderer.setSize(w,h);}});
    this.observer.observe(container);this.pose(this.actual,home,[0,0,-1],0);this.frame();
    return this;
  }
  build(ghost) {
    const root=new T.Group(), bodies=[],parts=[],servos=[],mapping=servoPartMap(this.model);
    for(const b of this.model.bodies){
      const group=new T.Group();group.position.fromArray(b.pos);
      group.quaternion.set(b.quat[1],b.quat[2],b.quat[3],b.quat[0]).normalize();
      group.userData.rest=group.quaternion.clone();group.userData.axis=new T.Vector3(...b.axis).normalize();
      (b.parent<0?root:bodies[b.parent]).add(group);bodies.push(group);
    }
    for(const [part,p] of this.model.parts.entries()){
      const color=new T.Color(`rgb(${p.rgb.join(',')})`);
      const material=ghost?new T.MeshBasicMaterial({color:0xbef264,wireframe:true,transparent:true,opacity:.16,depthWrite:false,side:T.DoubleSide}):new T.MeshStandardMaterial({color,roughness:.68,metalness:.03,flatShading:false,side:T.DoubleSide});
      const mesh=new T.Mesh(this.geometry[p.mesh],material);mesh.position.fromArray(p.pos);
      mesh.quaternion.set(p.quat[1],p.quat[2],p.quat[3],p.quat[0]).normalize();
      mesh.userData.joint=mapping.get(part)??-1;mesh.userData.baseColor=color.clone();
      if(mesh.userData.joint>=0)servos[mesh.userData.joint]=mesh;
      bodies[p.body].add(mesh);parts.push(mesh);
    }
    return {root,bodies,parts,servos,box:new T.Box3(),rotation:new T.Quaternion()};
  }
  pose(instance,joints,gravity,yaw) {
    const root=instance.root;root.position.set(0,0,0);
    const q=(this.reversePitch?displayRootQuaternion(gravity,yaw):rootQuaternion(gravity,yaw))||[1,0,0,0];
    root.quaternion.set(q[1],q[2],q[3],q[0]);
    this.model.bodies.forEach((b,i)=>{
      const g=instance.bodies[i];g.quaternion.copy(g.userData.rest);
      if(b.joint>=0)g.quaternion.multiply(instance.rotation.setFromAxisAngle(g.userData.axis,Number.isFinite(joints[b.joint])?joints[b.joint]:this.home[b.joint]));
    });
    root.updateMatrixWorld(true);
    // Same display-only floor convention as robotctl: not a measured body height.
    const box=instance.box.setFromObject(root);if(Number.isFinite(box.min.z))root.position.z=-box.min.z;
  }
  update(snapshot) {
    if(!this.actual)return;
    const service=snapshot.mode==='service';
    this.reversePitch=service;
    const rows=snapshot.servos.slice(0,15);
    const joints=service?rows.map(r=>r.status==='live'&&Number.isFinite(r.angle_deg)?r.angle_deg*Math.PI/180:null):snapshot.state.joints;
    const live=service?snapshot.service_sample_fresh&&snapshot.pose_calibrated:snapshot.channels.state.status==='live';
    const complete=Array.isArray(joints)&&joints.length===15&&joints.every(Number.isFinite);
    if(live && complete){
      if(snapshot.imu.status==='live'&&Array.isArray(snapshot.imu.gravity)&&(!service||snapshot.imu.mount_verified))this.lastGravity=snapshot.imu.gravity;
      // A stale IMU does not magically make the real robot upright. Hold its last
      // known tilt while the UI explicitly labels tilt as unknown/stale.
      // A local display origin, never an IMU mounting correction. Keep the
      // grid and camera fixed; only later heading changes rotate the duck.
      const yaw=snapshot.state.odom?.yaw;
      if(snapshot.channels.state.status==='live'&&Number.isFinite(yaw)){
        if(!Number.isFinite(this.headingReference))this.headingReference=yaw;
        const delta=yaw-this.headingReference;
        this.displayYaw=Math.atan2(Math.sin(delta),Math.cos(delta));
      }
      this.pose(this.actual,joints,this.lastGravity,this.displayYaw??0);
      if(this.showGhost)this.pose(this.ghost,snapshot.state.targets||joints,this.lastGravity,this.displayYaw??0);
      // Apply the startup view once. Later samples must not undo orbit/zoom.
      if(!this.hasPose&&this.initialView)this.view(this.initialView);
      this.initialView=null;
      this.hasPose=true;
    }
    this.ghost.root.visible=!!(this.showGhost && live && complete && snapshot.state.targets?.length===15);
    this.actual.parts.forEach(m=>{
      const i=m.userData.joint,row=rows[i];
      m.material.color.copy(m.userData.baseColor);
      m.material.emissive.setHex(0);m.material.emissiveIntensity=0;
      if(this.heat && row && Number.isFinite(row.temperature_c) && row.status==='live')m.material.color.setHSL(.33-Math.min(1,Math.max(0,(row.temperature_c-25)/40))*.33,.8,.5);
      const chosen=i>=0&&i===this.selected;
      if(chosen){m.material.emissive.setHex(0xc8ff6b);m.material.emissiveIntensity=.55;}
      m.material.transparent=!live;m.material.opacity=chosen||live?1:.36;
      m.renderOrder=chosen?1:0;m.material.depthTest=!chosen;m.material.depthWrite=!chosen&&live;
    });
  }
  focusJoint(joint){
    const servo=this.actual?.servos[joint];if(!servo)return;
    this.initialView=null;
    this.actual.root.updateMatrixWorld(true);
    const box=new T.Box3().setFromObject(servo),target=box.getCenter(new T.Vector3());
    const local=target.clone();this.actual.root.worldToLocal(local);
    // View legs from their outer side, head from the front/side, with context.
    const side=joint<5?1:joint>=10?-1:Math.abs(local.y)>.018?Math.sign(local.y):-1;
    const direction=new T.Vector3(.65,side,.35).normalize().applyQuaternion(this.actual.root.quaternion);
    const radius=box.getSize(new T.Vector3()).length()/2;
    const distance=Math.max(.12,radius/Math.sin(T.MathUtils.degToRad(this.camera.fov/2))*1.45);
    this.focus={start:performance.now(),from:this.camera.position.clone(),fromTarget:this.controls.target.clone(),to:target.clone().addScaledVector(direction,distance),target};
  }
  advanceFocus(now){
    const f=this.focus;if(!f)return;
    const t=Math.min(1,Math.max(0,(now-f.start)/380)),ease=t*t*(3-2*t);
    this.camera.position.lerpVectors(f.from,f.to,ease);this.controls.target.lerpVectors(f.fromTarget,f.target,ease);
    if(t===1)this.focus=null;
  }
  resetHeading(){this.headingReference=null;this.displayYaw=null;}
  view(name) {
    this.focus=null;
    const positions={front:[.56,0,.23],side:[0,-.56,.23],top:[.001,0,.7],home:[.56,0,.23]};
    name=Object.hasOwn(positions,name)?name:'home';
    if(!this.hasPose)this.initialView=name;
    // All presets share the fixed display axes. Re-selecting a view must not
    // cancel a real turn or rotate the ground relative to the display origin.
    this.camera.position.fromArray(positions[name]);
    this.controls.target.set(0,0,.145);this.controls.update();
  }
  frame(){this.advanceFocus(performance.now());this.controls.update();this.renderer.render(this.scene,this.camera);requestAnimationFrame(()=>this.frame());}
}
