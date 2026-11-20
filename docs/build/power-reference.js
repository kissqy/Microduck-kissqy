const triggers=[...document.querySelectorAll('[data-power-reference-open]')];
if(triggers.length){
 const dialog=document.createElement('dialog');
 dialog.className='power-reference-dialog';
 dialog.id='battery-power-reference';
 dialog.setAttribute('aria-labelledby','power-reference-title');
 dialog.setAttribute('aria-describedby','power-reference-copy');
 dialog.innerHTML=`
  <header class="power-reference-header">
   <h2 id="power-reference-title">新版香蕉取电板 · ¥39</h2>
   <button type="button" class="power-reference-close" aria-label="关闭取电图片" autofocus>×</button>
  </header>
  <div class="power-reference-body">
   <a class="power-reference-photo" href="../assets/boards/banana-battery-front-white.jpg" target="_blank" rel="noopener" aria-label="查看香蕉板接好电池的实拍原图">
    <img src="../assets/boards/banana-battery-front-white.jpg" alt="新版香蕉取电板插入电池触点的实拍" width="864" height="1536" loading="lazy">
   </a>
   <div class="power-reference-copy" id="power-reference-copy">
    <p><strong>HUB V3 全部接口均为 AMP2.0。</strong>香蕉取电板也采用 AMP2.0，搭配匹配的成品线即可直插免焊。</p>
    <p><strong>新版香蕉取电板 ¥39／块，配套成品线直插免焊。</strong></p>
    <p>双香蕉插针插入 NP-F550 电池触点，配套 AMP2.0 电源线接 HUB V3 CN1：2=VIN，3=GND，1=NC 留空。</p>
    <p class="power-reference-wiring">按所用版本的实板丝印核对接口和极性，再连接匹配的成品线。</p>
    <p class="power-reference-hint">图片为新版香蕉板已接好电池的实拍；点击可查看原图。</p>
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
