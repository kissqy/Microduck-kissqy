const triggers=[...document.querySelectorAll('[data-power-reference-open]')];
if(triggers.length){
 const dialog=document.createElement('dialog');
 dialog.className='power-reference-dialog';
 dialog.id='battery-power-reference';
 dialog.setAttribute('aria-labelledby','power-reference-title');
 dialog.setAttribute('aria-describedby','power-reference-copy');
 dialog.innerHTML=`
  <header class="power-reference-header">
   <h2 id="power-reference-title">电池取电实拍</h2>
   <button type="button" class="power-reference-close" aria-label="关闭取电图片" autofocus>×</button>
  </header>
  <div class="power-reference-body">
   <a class="power-reference-photo" href="../assets/battery-screw-power.jpg" target="_blank" rel="noopener" aria-label="查看取电实拍原图">
    <img src="../assets/battery-screw-power.jpg" alt="配套电池仓内，两颗螺丝作为电池取电触点的实拍" width="864" height="1536" loading="lazy">
   </a>
   <div class="power-reference-copy" id="power-reference-copy">
    <p>HUB 电源口 <strong>CN1 使用 XH2.54-2P</strong>，可按电池选择取电方式。</p>
    <p><strong>螺丝取电：</strong>XH2.54 电源线连接电池仓的 <strong>M2.6 螺丝触点</strong>，方便快捷。螺纹卡得紧，运动时不易松脱断电，简单实用。</p>
    <p><strong>电池直插：</strong>电压和极性匹配的 <strong>XH2.54 接口电池</strong>，可直接插入 HUB。</p>
    <p><strong>香蕉板取电：</strong>也可以自购香蕉板，将 <strong>XH2.54 电源线焊接到香蕉板</strong>，再插入 HUB。</p>
    <p class="power-reference-wiring">取出的正极接 HUB <strong>VIN（+）</strong>，负极接 <strong>GND（−）</strong>，按实板丝印核对极性。</p>
    <p class="power-reference-hint">点击图片可查看原图。</p>
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
