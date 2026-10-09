const initial=()=>({lx:0,ly:0,rx:0,ry:0,lt:0,rt:0,dx:0,dy:0});
export class PadControls {
  constructor(panel){
    this.panel=panel;this.root=panel.root.querySelector('.official-pad');this.axes=initial();this.buttons=new Set();this.inputs=new Map();
    for(const stick of this.root.querySelectorAll('[data-stick]')){
      stick.addEventListener('pointerdown',e=>{if(e.button||panel.disabled)return;e.preventDefault();stick.setPointerCapture(e.pointerId);this.inputs.set(e.pointerId,{stick});this.drag(stick,e);});
      stick.addEventListener('pointermove',e=>{if(this.inputs.get(e.pointerId)?.stick===stick)this.drag(stick,e);});
      stick.addEventListener('lostpointercapture',e=>this.release(e.pointerId));stick.addEventListener('contextmenu',e=>e.preventDefault());
    }
    for(const button of this.root.querySelectorAll('[data-button],[data-dpad],[data-trigger]')){
      button.addEventListener('pointerdown',e=>{if(e.button||button.disabled||panel.disabled)return;e.preventDefault();button.setPointerCapture(e.pointerId);this.inputs.set(e.pointerId,{button});this.applyButton(button,true);});
      button.addEventListener('lostpointercapture',e=>this.release(e.pointerId));
      button.addEventListener('keydown',e=>{if(['Space','Enter'].includes(e.code)&&!e.repeat&&!button.disabled&&!panel.disabled){e.preventDefault();this.applyButton(button,true);}});
      button.addEventListener('keyup',e=>{if(['Space','Enter'].includes(e.code)){e.preventDefault();this.applyButton(button,false);}});
      button.addEventListener('blur',()=>{if(button.classList.contains('held'))this.applyButton(button,false);});
    }
    for(const trigger of this.root.querySelectorAll('[data-axis]')){
      trigger.addEventListener('input',()=>{this.axes[trigger.dataset.axis]=Number(trigger.value);panel.change();});
      for(const event of ['pointerup','pointercancel','blur'])trigger.addEventListener(event,()=>{trigger.value=0;this.axes[trigger.dataset.axis]=0;panel.change(false);});
    }
    window.addEventListener('pointerup',e=>this.release(e.pointerId));window.addEventListener('pointercancel',e=>this.release(e.pointerId));
    this.root.querySelector('[data-pad-center]').onclick=()=>{this.reset();panel.change(false);};
  }
  applyButton(button,pressed){
    if(button.dataset.trigger){this.axes[button.dataset.trigger]=pressed?1:0;}
    else if(button.dataset.button){if(pressed)this.buttons.add(button.dataset.button);else this.buttons.delete(button.dataset.button);}
    else {const [axis,value]=button.dataset.dpad.split(':');this.axes[axis]=pressed?Number(value):0;}
    button.classList.toggle('held',pressed);button.setAttribute('aria-pressed',String(pressed));this.panel.change(pressed);
  }
  drag(stick,e){
    const r=stick.getBoundingClientRect(),x=Math.max(-1,Math.min(1,(e.clientX-r.left-r.width/2)/(r.width/2))),y=Math.max(-1,Math.min(1,(e.clientY-r.top-r.height/2)/(r.height/2)));
    const prefix=stick.dataset.stick;this.axes[prefix+'x']=x;this.axes[prefix+'y']=y;
    stick.querySelector('i').style.transform=`translate(${x*35}px,${y*35}px)`;this.panel.change();
  }
  release(id){
    const input=this.inputs.get(id);if(!input)return;this.inputs.delete(id);
    if(input.button)this.applyButton(input.button,false);
    if(input.stick){const p=input.stick.dataset.stick;this.axes[p+'x']=this.axes[p+'y']=0;input.stick.querySelector('i').style.transform='translate(0,0)';this.panel.change(false);}
  }
  active(){return this.buttons.size>0||Object.values(this.axes).some(v=>v!==0);}
  frame(){return {axes:{...this.axes},buttons:[...this.buttons]};}
  reset(){
    this.inputs.clear();this.axes=initial();this.buttons.clear();
    for(const dot of this.root.querySelectorAll('[data-stick] i'))dot.style.transform='translate(0,0)';
    for(const b of this.root.querySelectorAll('.held')){b.classList.remove('held');b.setAttribute('aria-pressed','false');}
    for(const input of this.root.querySelectorAll('[data-axis]'))input.value=0;
  }
  paint(){
    for(const button of this.root.querySelectorAll('button'))button.disabled=this.panel.disabled||button.dataset.unavailable==='true';
    for(const input of this.root.querySelectorAll('input'))input.disabled=this.panel.disabled;
    for(const stick of this.root.querySelectorAll('[data-stick]'))stick.setAttribute('aria-disabled',String(this.panel.disabled));
  }
}
