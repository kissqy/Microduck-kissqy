// Keep the warning inside the page: a native confirm can enqueue window blur
// after returning, which would cancel the motion just submitted by ServicePanel.
export function requestCenterConfirmation(){
  const dialog=document.createElement('dialog');
  dialog.className='service-center-dialog';
  dialog.innerHTML=`<h3 id="center-warning-title">全部顺序回到 2048？</h3>
    <p>全部 15 颗舵机将顺序回到编码器 2048。这不是已保存的标定零位，已装配部件可能发生干涉。请确认空间充足并支撑机身。</p>
    <div class="service-action-row"><button type="button" class="button" data-center-cancel autofocus>取消</button><button type="button" class="button accent" data-center-confirm>确认执行</button></div>`;
  dialog.setAttribute('aria-labelledby','center-warning-title');
  let resolve,settled=false;
  const result=new Promise(done=>{resolve=done;});
  const finish=confirmed=>{
    if(settled)return;settled=true;
    if(dialog.open)dialog.close();
    dialog.remove();resolve(confirmed);
  };
  dialog.querySelector('[data-center-cancel]').addEventListener('click',()=>finish(false));
  dialog.querySelector('[data-center-confirm]').addEventListener('click',()=>finish(true));
  dialog.addEventListener('cancel',event=>{event.preventDefault();finish(false);});
  dialog.addEventListener('close',()=>finish(false));
  document.body.append(dialog);
  try{dialog.showModal();}catch(error){finish(false);throw error;}
  return {result,cancel:()=>finish(false)};
}
