import * as T from './vendor/three.module.min.js?demo=20261013';
import {DuckView} from './duck.js?demo=20261013';
import {REFERENCE_IDS,REFERENCE_LABELS} from './calibration-reference.js?demo=20261013';
import {officialStandingDegrees,referenceAngle} from './joint-reference.js?demo=20261013';
import {attachElectronics} from './assembly-electronics.js?v=20261030-harness';
import {COMPONENTS,CONNECTIONS,WIRING_NOTE} from './assembly-components.js?v=20261030-harness';

const groups={
  all:{title:'整只小鸭',description:'先看整体连接关系，再选择腿部或头颈放大查看。',indexes:REFERENCE_IDS.map((_,i)=>i)},
  left:{title:'左腿 · 20–24',description:'从髋部到脚踝依次为 20、21、22、23、24。这里的左侧以鸭子自身为准。',indexes:[0,1,2,3,4]},
  right:{title:'右腿 · 10–14',description:'从髋部到脚踝依次为 10、11、12、13、14。可切到背面或外侧核对连接朝向。',indexes:[10,11,12,13,14]},
  head:{title:'头颈 · 30–34',description:'颈部俯仰、头部俯仰、转向、侧摆与嘴部。转到侧面查看各层关节的连接关系。',indexes:[5,6,7,8,9]},
};
const $=id=>document.getElementById(id);
let scope='all',selected=null,pose='zero',view,electronics,componentId='hat',activeComponent=null,exploded=false;

class AssemblyView extends DuckView{
  async init(container,onSelect){
    await super.init(container,officialStandingDegrees,onSelect);
    this.selected=-1;
    this.scene.background=new T.Color('#101619');
    this.scene.children.filter(item=>item.type==='GridHelper').forEach(item=>{item.material.transparent=true;item.material.opacity=.65;});
    this.bodyAxes.visible=false;
    this.controls.enablePan=true;
    this.renderer.domElement.setAttribute('aria-label','小鸭三维模型；拖动旋转，双指或滚轮缩放');
    this.bodyJointScopes=this.model.bodies.map((body,index)=>{
      const chain=[];let current=index;
      while(current>=0){const entry=this.model.bodies[current];if(entry.joint>=0)chain.push(entry.joint);current=entry.parent;}
      return chain;
    });
    this.setReference('zero');
    return this;
  }
  matches(part,index){
    if(scope==='all')return true;
    const indexes=groups[scope].indexes;
    return indexes.includes(this.actual.parts[index].userData.joint)||this.bodyJointScopes?.[part.body].some(joint=>indexes.includes(joint));
  }
  update(snapshot){
    super.update(snapshot);
    if(!this.actual||!this.bodyJointScopes)return;
    const fade=$('fade-others').checked&&scope!=='all';
    this.actual.parts.forEach((mesh,index)=>{
      const relevant=this.matches(this.model.parts[index],index);
      mesh.material.transparent=fade&&!relevant;
      mesh.material.opacity=fade&&!relevant ? .13 : 1;
      mesh.material.depthWrite=!fade||relevant;
      mesh.material.depthTest=true;
      mesh.renderOrder=relevant?1:0;
      if(mesh.userData.joint===this.selected){mesh.material.emissive.setHex(0xc1f577);mesh.material.emissiveIntensity=.65;}
    });
  }
  focusScope(){
    if(scope==='all'){this.view('front');return;}
    this.actual.root.updateMatrixWorld(true);
    const box=new T.Box3();
    this.actual.parts.forEach((mesh,index)=>{if(this.matches(this.model.parts[index],index))box.expandByObject(mesh);});
    if(box.isEmpty())return;
    const target=box.getCenter(new T.Vector3());
    const direction=new T.Vector3(.72,scope==='left'?1:-1,.28).normalize();
    const radius=box.getBoundingSphere(new T.Sphere()).radius;
    const vertical=T.MathUtils.degToRad(this.camera.fov),horizontal=2*Math.atan(Math.tan(vertical/2)*this.camera.aspect);
    const distance=Math.max(.16,radius/Math.sin(Math.min(vertical,horizontal)/2)*1.12);
    this.initialView=null;this.overviewName=null;
    this.focus={start:performance.now(),from:this.camera.position.clone(),fromTarget:this.controls.target.clone(),to:target.clone().addScaledVector(direction,distance),target};
  }
}

function drawInspector(){
  $('part-title').textContent=groups[scope].title;
  $('part-description').textContent=groups[scope].description;
  document.querySelectorAll('[data-group]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.group===scope)));
  $('joint-list').replaceChildren(...groups[scope].indexes.map(index=>{
    const button=document.createElement('button');button.type='button';button.className='joint-button';
    button.setAttribute('aria-pressed',String(index===selected));
    button.setAttribute('aria-label',`${REFERENCE_LABELS[index]}，舵机 ID ${REFERENCE_IDS[index]}`);
    const id=document.createElement('b');id.textContent=REFERENCE_IDS[index];
    const name=document.createElement('span');name.textContent=REFERENCE_LABELS[index];
    button.append(id,name);button.addEventListener('click',()=>selectJoint(index));button.disabled=!view;
    return button;
  }));
  const detail=$('joint-detail');detail.replaceChildren();
  if(selected===null){detail.textContent='点选舵机外壳或上方关节，查看对应 ID。';return;}
  const id=REFERENCE_IDS[selected],title=document.createElement('strong');title.textContent=`${REFERENCE_LABELS[selected]} · ID ${id}`;
  const description=document.createElement('span');description.textContent=id===34?'嘴部在此模型中为固定外观，可核对位置，不能演示开合。':`当前模型参考角度：${pose==='home'?referenceAngle(officialStandingDegrees[id],2):'0'}°。高亮位置表示舵机外壳；请旋转模型核对其连接方向。`;
  detail.append(title,description);
}
function selectJoint(index){
  if(!view)return;
  clearComponent();setInspector('joints');
  selected=index;
  if(scope!=='all'&&!groups[scope].indexes.includes(index))scope=index<5?'left':index<10?'head':'right';
  view.selectJoint(index);view.focusJoint(index);electronics?.setWireFocus($('fade-others').checked?'servo'+REFERENCE_IDS[index]:null);drawInspector();
}
function setScope(next){
  if(!view)return;
  clearComponent();setInspector('joints');
  scope=next;selected=null;view.selected=-1;view.update({});view.focusScope();electronics?.setWireFocus($('fade-others').checked?next:null);drawInspector();
}
function setPose(next){
  if(!view)return;
  pose=next;view.setReference(next);
  if(selected!==null)view.focusJoint(selected);else view.focusScope();
  $('pose-label').textContent=next==='zero'?'模型零位 · 0°':'HOME · 官方站姿参考';
  document.querySelectorAll('[data-pose]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.pose===next)));
  drawInspector();
}
document.querySelectorAll('[data-group]').forEach(button=>button.addEventListener('click',()=>setScope(button.dataset.group)));
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>view?.view(button.dataset.view)));
document.querySelectorAll('[data-pose]').forEach(button=>button.addEventListener('click',()=>setPose(button.dataset.pose)));
$('fade-others').addEventListener('change',()=>{view?.update({});electronics?.setWireFocus($('fade-others').checked?(activeComponent||(selected!==null?'servo'+REFERENCE_IDS[selected]:scope)):null);});
$('reset-view').addEventListener('click',()=>setScope('all'));
$('retry').addEventListener('click',()=>location.reload());
function setInspector(name){
  $('joints-panel').hidden=name!=='joints';$('electronics-panel').hidden=name!=='electronics';
  document.querySelector('.inspector').setAttribute('aria-labelledby',name==='joints'?'part-title':'component-title');
  document.querySelectorAll('[data-inspect]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.inspect===name)));
}
function clearComponent(){
  activeComponent=null;electronics?.setWireFocus(null);electronics?.clearSelection();$('component-quick').hidden=true;
  document.querySelectorAll('[data-component]').forEach(button=>button.setAttribute('aria-pressed','false'));
}
function drawComponent(){
  const component=COMPONENTS[componentId];
  $('component-title').textContent=component.label;$('component-description').textContent=component.description;
  $('component-location').textContent=component.locationNote;
  $('component-facts').replaceChildren(...component.facts.map(text=>{const item=document.createElement('li');item.textContent=text;return item;}));
  const connections=CONNECTIONS.filter(item=>item.from===componentId||item.to===componentId);
  const container=$('component-wires');container.replaceChildren();
  if(connections.length){const heading=document.createElement('h3');heading.textContent='这块板接到哪里';container.append(heading);}
  connections.forEach(item=>{const row=document.createElement('div');row.className='component-wire';const title=document.createElement('strong');title.textContent=item.label;const detail=document.createElement('span');detail.textContent=item.detail;row.append(title,detail);container.append(row);});
  for(const id of ['component-purchase','component-quick-buy']){const link=$(id);link.href=component.purchase.url;link.textContent=component.purchase.label+' ↗';}
  $('component-source').href=component.source.url;$('component-source').textContent=component.source.label+' ↗';
  $('component-sources').replaceChildren(...(component.extraSources||[]).map(source=>{const link=document.createElement('a');link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=source.label+' ↗';return link;}));
  if(component.sourceNote){const note=document.createElement('p');note.textContent=component.sourceNote;$('component-sources').append(note);}
  $('component-quick-name').textContent=component.shortLabel||component.label;
  document.querySelectorAll('[data-component]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.component===activeComponent)));
}
function selectComponent(id){
  if(!COMPONENTS[id])return;
  componentId=id;activeComponent=id;selected=null;scope='all';
  if(view){view.selected=-1;view.update({});drawInspector();}
  if(electronics){
    $('show-components').checked=true;Object.keys(COMPONENTS).forEach(key=>electronics.setVisible(key,true));
    if(id==='imu'){$('show-battery').checked=true;electronics.setBatteryVisible(true);}
    electronics.select(id);if(id==='hat'||id==='zero')$('open-cover').checked=true;
    $('component-quick').hidden=false;
  }
  electronics?.setWireFocus($('fade-others').checked?id:null);drawComponent();setInspector('electronics');
}
document.querySelectorAll('[data-component]').forEach(button=>button.addEventListener('click',()=>selectComponent(button.dataset.component)));
document.querySelectorAll('[data-inspect]').forEach(button=>button.addEventListener('click',()=>{setInspector(button.dataset.inspect);if(button.dataset.inspect==='electronics')drawComponent();}));
$('open-cover').addEventListener('change',()=>{electronics?.setCoverOpen($('open-cover').checked);if($('open-cover').checked)electronics?.focus('head');});
$('show-components').addEventListener('change',()=>{Object.keys(COMPONENTS).forEach(id=>electronics?.setVisible(id,$('show-components').checked));if(!$('show-components').checked)$('component-quick').hidden=true;});
$('show-wires').addEventListener('change',()=>electronics?.setWiringVisible($('show-wires').checked));
$('show-battery').addEventListener('change',()=>electronics?.setBatteryVisible($('show-battery').checked));
$('focus-battery').addEventListener('click',()=>{if(!electronics)return;$('show-battery').checked=true;electronics.setBatteryVisible(true);electronics.focus('battery');});
$('show-servo-ids').addEventListener('change',()=>electronics?.setServoIdsVisible($('show-servo-ids').checked));
$('toggle-explosion').addEventListener('click',()=>{
  if(!electronics)return;
  exploded=!exploded;
  if(exploded)setScope('all');
  electronics.setExploded(exploded);
  $('toggle-explosion').setAttribute('aria-pressed',String(exploded));
  $('toggle-explosion').textContent=exploded?'收起复原':'爆炸展开';
  $('explosion-status').textContent=exploded?'打印件已逐件展开，舵机和轴承保持原位；再点“收起复原”返回装配状态。':'已收起复原，可继续查看端子与接线。';
});
$('wiring-note').textContent=WIRING_NOTE;
$('connection-list').replaceChildren(...CONNECTIONS.map(item=>{
  const card=document.createElement('article');card.className='connection-card';
  const title=document.createElement('h3');title.textContent=item.label;
  card.append(title);
  if(item.signals){
    const table=document.createElement('table');table.className='signal-table';
    const caption=document.createElement('caption');caption.textContent='按信号名对应，不按线色猜';table.append(caption);
    const head=document.createElement('tr');
    [COMPONENTS[item.from]?.shortLabel||'电池',COMPONENTS[item.to]?.shortLabel||item.to].forEach(label=>{const cell=document.createElement('th');cell.scope='col';cell.textContent=label;head.append(cell);});
    const thead=document.createElement('thead');thead.append(head);table.append(thead);
    const tbody=document.createElement('tbody');item.signals.forEach(pair=>{const row=document.createElement('tr');pair.forEach(signal=>{const cell=document.createElement('td');cell.textContent=signal;row.append(cell);});tbody.append(row);});table.append(tbody);card.append(table);
  }
  const detail=document.createElement('p');detail.textContent=item.detail;
  const link=document.createElement('a');link.href=item.sourceUrl;link.target='_blank';link.rel='noopener noreferrer';link.textContent='核对接口说明 ↗';
  card.append(detail,link);
  if(item.sourceNote){const note=document.createElement('p');note.className='source-note';note.textContent=item.sourceNote;card.append(note);}return card;
}));
drawComponent();
drawInspector();
const modelControls='[data-group],[data-view],[data-pose],#reset-view,#fade-others,#open-cover,#show-components,#show-wires,#show-battery,#focus-battery,#show-servo-ids,#toggle-explosion';
document.querySelectorAll(modelControls).forEach(button=>button.disabled=true);
try{
  const loaded=await new AssemblyView().init($('assembly-canvas'),selectJoint);view=loaded;
  electronics=await attachElectronics(view,selectComponent);electronics.setWiringVisible($('show-wires').checked);electronics.setServoIdsVisible($('show-servo-ids').checked);
  $('loading').hidden=true;
  document.querySelectorAll(modelControls).forEach(button=>button.disabled=false);
  view.update({});drawInspector();
  const requested=new URLSearchParams(location.search);
  if(COMPONENTS[requested.get('component')])selectComponent(requested.get('component'));
  else if(groups[requested.get('part')])setScope(requested.get('part'));
}catch(error){
  $('loading').hidden=true;$('model-error').hidden=false;
  $('error-detail').textContent='3D 需要支持 WebGL 的浏览器；下方仍可查看接线说明和板卡购买入口。'+(error?.message?'（'+error.message+'）':'');
}
