const triggers=[...document.querySelectorAll('[data-power-reference-open]')];
if(triggers.length){
 const dialog=document.createElement('dialog');
 dialog.className='power-reference-dialog';
 dialog.id='battery-power-reference';
 dialog.setAttribute('aria-labelledby','power-reference-title');
 dialog.setAttribute('aria-describedby','power-reference-copy');
 dialog.innerHTML=`
  <header class="power-reference-header">
   <h2 id="power-reference-title">HUB V3 与旧版取电参考</h2>
   <button type="button" class="power-reference-close" aria-label="关闭取电图片" autofocus>×</button>
  </header>
  <div class="power-reference-body">
   <a class="power-reference-photo" href="../assets/battery-screw-power.jpg" target="_blank" rel="noopener" aria-label="查看旧版螺丝取电实拍原图">
    <img src="../assets/battery-screw-power.jpg" alt="旧版取电参考：电池仓内两颗螺丝作为电池取电触点的实拍" width="864" height="1536" loading="lazy">
   </a>
   <div class="power-reference-copy" id="power-reference-copy">
    <p><strong>HUB V3 全部接口均为 AMP2.0。</strong>香蕉取电板也采用 AMP2.0，搭配匹配的成品线即可直插免焊。</p>
    <p><strong>香蕉取电板暂未上架，预计 2026 年 11 月 16 日前后上架。</strong></p>
    <p><strong>旧版 HUB 历史参考：</strong>图中是旧版电池仓的 M2.6 螺丝取电。旧版 HUB 的 CN1 使用 XH2.54-2P；螺丝接线、XH2.54 电池直插及香蕉板焊线方式不作为 HUB V3 的直插接法。</p>
    <p class="power-reference-wiring">按所用版本的实板丝印核对接口和极性，再连接匹配的成品线。</p>
    <p class="power-reference-hint">图片仅展示旧版螺丝取电；点击可查看原图。</p>
   </div>
  </div>`;
 document.body.append(dialog);
 const open=()=>{
  if(dialog.open)return;
  dialog.showModal();
  document.body.classList.add('power-reference-open');
 };
 triggers.forEach(trigger=>trigger.addEventListener('click',event=>{event.preventDefault();open();}));
 dialog.querySelector('.power-reference-close').addEventListener('click',()=>dialog.close());
 dialog.addEventListener('click',event=>{
  if(event.target!==dialog)return;
  const rect=dialog.getBoundingClientRect();
  if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)dialog.close();
 });
 dialog.addEventListener('close',()=>{
  document.body.classList.remove('power-reference-open');
  if(location.hash==='#'+dialog.id)history.replaceState(null,'',location.pathname+location.search);
 });
 const openFromHash=()=>{if(location.hash==='#'+dialog.id)open();};
 window.addEventListener('hashchange',openFromHash);
 openFromHash();
}
