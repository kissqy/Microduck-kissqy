const dialogs=[...document.querySelectorAll('[data-group-buy-dialog]')];
const byId=new Map(dialogs.map(dialog=>[dialog.id,dialog]));

function openGroupBuy(id){
 const dialog=byId.get(id);
 if(!dialog||dialog.open)return;
 dialog.showModal();
 document.body.classList.add('group-buy-open');
}

document.querySelectorAll('[data-group-buy-open]').forEach(button=>{
 button.addEventListener('click',()=>openGroupBuy(button.dataset.groupBuyOpen));
});

dialogs.forEach(dialog=>{
 dialog.querySelectorAll('[data-group-buy-close]').forEach(button=>{
  button.addEventListener('click',()=>dialog.close());
 });
 dialog.addEventListener('click',event=>{
  if(event.target!==dialog)return;
  const rect=dialog.getBoundingClientRect();
  if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)dialog.close();
 });
 dialog.addEventListener('close',()=>{
  if(!dialogs.some(item=>item.open))document.body.classList.remove('group-buy-open');
  if(location.hash==='#'+dialog.id)history.replaceState(null,'',location.pathname+location.search);
 });
});

const openLinkedDialog=()=>openGroupBuy(location.hash.slice(1));
window.addEventListener('hashchange',openLinkedDialog);
openLinkedDialog();
