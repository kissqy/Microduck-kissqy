import {configureShopping} from './build-shopping-route.js?v=20261027-print199';
const storageKey='microduck-build-v1';
const boardModes=['assembled','diy-owned','diy-new'];
const printingModes=['own','service','buy-printer'];
const boardNames={assembled:'买成品板','diy-owned':'手工焊 · 已有工具','diy-new':'手工焊 · 需要买工具'};
const printingNames={own:'有打印机 · 自己打印',service:'无打印机 · 找人代打','buy-printer':'无打印机 · 买机器自己打'};
const money=cents=>'¥'+(cents/100).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2});
const range=(minimum,maximum)=>minimum===maximum?money(minimum):money(minimum)+'–'+money(maximum);
function readState(){
 const result={costs:{},prepared:[],route:{boards:'assembled',printing:'own'}};
 try{
  const saved=JSON.parse(localStorage.getItem(storageKey)||'null');
  if(saved&&typeof saved==='object'){
   result.costs=saved.costs&&typeof saved.costs==='object'?saved.costs:{};
   result.prepared=Array.isArray(saved.prepared)?saved.prepared.filter(x=>typeof x==='string'):[];
   if(boardModes.includes(saved.route?.boards))result.route.boards=saved.route.boards;
   if(printingModes.includes(saved.route?.printing))result.route.printing=saved.route.printing;
  }
 }catch{}
 return result;
}
let state=readState();
const save=field=>{try{const latest=readState();latest[field]=state[field];localStorage.setItem(storageKey,JSON.stringify(latest));}catch{}};
const priceInput=key=>{const raw=state.costs[key];if(raw===undefined||raw==='')return null;const number=Number(raw);return Number.isFinite(number)&&number>=0&&number<=1000000?Math.round(number*100):null;};
let data;
try{const response=await fetch(new URL('./data.json?v=20261030-urt2',import.meta.url));if(response.ok)data=await response.json();}catch{}
if(data){
 const body=data.items.reduce((sum,item)=>sum+item.subtotalCents,0),boards=data.boards.reduce((sum,item)=>sum+item.subtotalCents,0),assembled=body+boards;
 const shopping=configureShopping(data);
 const budgetPage=!!document.getElementById('calculator');
 if(budgetPage){
  const query=new URLSearchParams(location.search);
  if(query.has('boards'))state.route.boards=query.get('boards')==='diy'?(query.get('tools')==='new'?'diy-new':'diy-owned'):'assembled';
  if(printingModes.includes(query.get('printing')))state.route.printing=query.get('printing');
  if(query.has('boards')||printingModes.includes(query.get('printing')))save('route');
 }
 const plans=[{id:'own',fields:['ownPrint','extras','shipping']},{id:'service',fields:['printService','extras','shipping'],quote:'printService',quoteText:'待填代打报价'},{id:'buy-printer',fields:['printer','ownPrint','extras','shipping'],quote:'printer',quoteText:'待填打印机价格'}];
 const names={ownPrint:'打印耗材',printService:'代打费用',printer:'打印机设备费',extras:'待补配件',shipping:'运费与零星费用'};
 const defaultValues={printer:String(data.printerReferenceCents/100),printService:String(data.printServiceReferenceCents/100)};
 const references={printer:data.printerReferenceCents,printService:data.printServiceReferenceCents};
 const cost=key=>state.costs[key]===undefined&&Object.hasOwn(references,key)?references[key]:priceInput(key);
 const shoppingHref=printing=>{
  const query=new URLSearchParams({printing,boards:state.route.boards==='assembled'?'assembled':'diy'});
  if(state.route.boards!=='assembled')query.set('tools',state.route.boards==='diy-new'?'new':'owned');
  return 'shopping.html?'+query.toString();
 };
 function updateBudget(){
  const diy=state.route.boards!=='assembled',buyTools=state.route.boards==='diy-new';
  const minimum=diy?body+data.diyMaterialsMinCents+(buyTools?data.diyToolsMinCents:0):assembled;
  const maximum=diy?body+data.diyMaterialsMaxCents+(buyTools?data.diyToolsMaxCents:0):assembled;
  const basis=diy?'本体＋首批板卡材料'+(buyTools?'＋工具与耗材预算':''):'本体＋成品 HAT／IMU';
  plans.forEach(plan=>{
   const card=document.querySelector('[data-plan="'+plan.id+'"]');if(!card)return;
   const values=plan.fields.map(cost),addition=values.reduce((sum,value)=>sum+(value??0),0),needsQuote=plan.quote&&cost(plan.quote)===null,price=card.querySelector('[data-price]');
   price.textContent=needsQuote?plan.quoteText:range(minimum+addition,maximum+addition);
   price.classList.toggle('quote-needed',!!needsQuote);price.classList.toggle('range',diy);
   card.classList.toggle('featured',state.route.printing===plan.id);
   const missing=plan.fields.filter((_,index)=>values[index]===null);
   card.querySelector('[data-pending]').textContent=needsQuote?(plan.id==='service'?'填入整套代打报价后计算；无需购买打印机。':'填入设备价格后计算这一档预算。'):missing.length?'＋待补：'+missing.map(key=>names[key]).join('、'):'已含你填写的补充预算';
   card.querySelector('[data-plan-description]').textContent=basis+'；'+(plan.id==='own'?'已有打印机，不重复算设备费。':plan.id==='service'?'缝合怪版代打参考 '+money(data.printServiceReferenceCents)+'，可改实际报价，无需买打印机。':'另加打印机与耗材，设备参考 '+money(data.printerReferenceCents)+'，可按实价调整。');
   card.querySelector('a').setAttribute('href',shoppingHref(plan.id));
  });
  const boardCostLabel=document.getElementById('board-cost-label'),boardCostValue=document.getElementById('board-cost-value');
  if(boardCostLabel)boardCostLabel.textContent=diy?'HAT／IMU 自焊材料'+(buyTools?'＋工具与耗材':''):'HAT 与 IMU 成品板';
  if(boardCostValue)boardCostValue.textContent=range(minimum-body,maximum-body);
  document.querySelectorAll('[data-basis-total]').forEach(el=>el.textContent=range(minimum,maximum));
  document.querySelectorAll('[data-board-choice]').forEach(input=>input.checked=input.value===state.route.boards);
  document.querySelectorAll('[data-plan-choice]').forEach(input=>input.checked=input.value===state.route.printing);
  document.querySelectorAll('[data-current-shopping]').forEach(link=>link.setAttribute('href',shoppingHref(state.route.printing)));
  const selected=plans.find(plan=>plan.id===state.route.printing);
  document.querySelectorAll('[data-cost]').forEach(input=>input.closest('label').hidden=!selected.fields.includes(input.dataset.cost));
  const note=document.getElementById('route-price-note');
  if(note)note.textContent='当前按“'+boardNames[state.route.boards]+'”计算。'+(diy?'已用自焊材料替换成品板 '+money(boards)+'；'+(buyTools?'已加工具与耗材预算。':'已有焊接工具按复用计算，缺少耗材另补。'):'含成品 HAT '+money(data.boards.find(item=>item.id==='hat').subtotalCents)+' 与 IMU '+money(data.boards.find(item=>item.id==='imu').subtotalCents)+'。')+'均含作者参考本体配置、手柄、32GB TF 卡及读卡器；'+(state.route.printing==='service'?'代打按填写报价计入；':'自己打印耗材按填写预算计入；')+'HUB、运费等待补费用另计。HUB 自带缓冲电容，不单独购买。';
  document.querySelectorAll('[data-base-total]').forEach(el=>el.textContent=shopping?.baseLabel??money(assembled));
  const hint=document.getElementById('budget-state');
  if(hint)hint.textContent='当前选择：'+boardNames[state.route.boards]+' ／ '+printingNames[state.route.printing]+'。只显示这套方案需要填写的费用，其他方案的输入会保留。'+(buyTools?'自焊工具已计入，同一工具不要重复填入待补配件。':'已有可复用项目填 0，尚未报价的留空。');
 }
 const selectRoute=(key,value)=>{state.route[key]=value;save('route');updateBudget();};
 document.querySelectorAll('[data-board-choice]').forEach(input=>input.addEventListener('change',()=>{if(input.checked)selectRoute('boards',input.value);}));
 document.querySelectorAll('[data-plan-choice]').forEach(input=>input.addEventListener('change',()=>{if(input.checked)selectRoute('printing',input.value);}));
 document.querySelectorAll('[data-plan]').forEach(card=>card.addEventListener('click',event=>{if(!event.target.closest('label,input'))selectRoute('printing',card.dataset.plan);}));
 document.querySelectorAll('[data-cost]').forEach(input=>{const key=input.dataset.cost;input.value=state.costs[key]??defaultValues[key]??'';input.addEventListener('input',()=>{state.costs[key]=input.value;save('costs');updateBudget();});});
 document.getElementById('reset-budget')?.addEventListener('click',()=>{state.costs={};state.route={boards:'assembled',printing:'own'};save('costs');save('route');document.querySelectorAll('[data-cost]').forEach(input=>input.value=defaultValues[input.dataset.cost]??'');updateBudget();});
 const required=shopping?.required??[...data.boards,...data.items,data.printingEdition,...data.unpriced],priced=shopping?.priced??[...data.boards,...data.items],byId=new Map(required.map(item=>[item.id,item]));
 function updatePrepared(){
  const done=new Set(state.prepared.filter(id=>byId.has(id)));
  document.querySelectorAll('[data-prepared]').forEach(input=>{input.checked=done.has(input.dataset.prepared);input.closest('tr')?.classList.toggle('prepared-row',input.checked);});
  const count=document.getElementById('prepared-count');if(count)count.textContent=done.size+' / '+required.length+' 项已备齐';
  const bar=document.getElementById('prepared-bar');if(bar)bar.style.width=(done.size/required.length*100)+'%';
  const left=priced.filter(item=>!done.has(item.id)).reduce((sum,item)=>sum+item.subtotalCents,0),total=document.getElementById('remaining-total');if(total)total.textContent=money(left);
 }
 document.querySelectorAll('[data-prepared]').forEach(input=>input.addEventListener('change',()=>{const done=new Set(state.prepared);input.checked?done.add(input.dataset.prepared):done.delete(input.dataset.prepared);state.prepared=[...done];save('prepared');updatePrepared();}));
 document.getElementById('reset-prepared')?.addEventListener('click',()=>{state.prepared=[];save('prepared');updatePrepared();});
 function refreshSavedState(){state=readState();document.querySelectorAll('[data-cost]').forEach(input=>input.value=state.costs[input.dataset.cost]??defaultValues[input.dataset.cost]??'');updateBudget();updatePrepared();}
 window.addEventListener('pageshow',event=>{if(event.persisted)refreshSavedState();});
 window.addEventListener('storage',event=>{if(event.key===storageKey)refreshSavedState();});
 updateBudget();updatePrepared();
}
document.getElementById('print-list')?.addEventListener('click',()=>window.print());
