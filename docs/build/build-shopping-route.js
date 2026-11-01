const money=cents=>'¥'+(cents/100).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2});
const range=(minimum,maximum)=>minimum===maximum?money(minimum):money(minimum)+'–'+money(maximum);

/** Configure the purchase list for the route explicitly selected on the budget page. */
export function configureShopping(data){
 if(!document.getElementById('prepared-count'))return null;
 const query=new URLSearchParams(location.search);
 const hasPrinting=['own','service','buy-printer'].includes(query.get('printing'));
 const printing=hasPrinting?query.get('printing'):'own';
 const diy=query.get('boards')==='diy',buyTools=diy&&query.get('tools')==='new';
 const body=data.items.reduce((sum,item)=>sum+item.subtotalCents,0);
 const assembled=body+data.boards.reduce((sum,item)=>sum+(item.subtotalCents??0),0);
 const minimum=body+data.diyMaterialsMinCents+(buyTools?data.diyToolsMinCents:0);
 const maximum=body+data.diyMaterialsMaxCents+(buyTools?data.diyToolsMaxCents:0);
 const serviceFee=printing==='service'?data.printServiceReferenceCents:0;
 const baseLabel=diy||serviceFee?range((diy?minimum:assembled)+serviceFee,(diy?maximum:assembled)+serviceFee):null;
 const routeBoards=diy?data.boards.filter(item=>item.diyRequired):data.boards;
 const priced=[...routeBoards,...data.items].filter(item=>Number.isFinite(item.subtotalCents));
 const unpriced=data.unpriced.filter(item=>item.id!=='printing'&&(!buyTools||item.id!=='hand-tools'));
 const required=[...routeBoards,...data.items,...unpriced,...(data.printingEdition?[data.printingEdition]:[])];
 const route=new URLSearchParams();
 route.set('boards',diy?'diy':'assembled');
 if(diy)route.set('tools',buyTools?'new':'owned');
 route.set('printing',printing);
 const budget='budget.html'+(route.size?'?'+route.toString():'');
 const routeName=diy?'手工焊 HAT／IMU · '+(buyTools?'从零购买工具':'已有焊接工具'):'购买成品 HAT／IMU／HUB';
 const printingNames={own:'有打印机 · 自己打印',service:'无打印机 · 找人代打','buy-printer':'无打印机 · 买机器自己打'};
 const byId=id=>document.getElementById(id);
 const text=(tag,value)=>{const element=document.createElement(tag);element.textContent=value;return element;};
 const setText=(id,value)=>{const element=byId(id);if(element)element.textContent=value;};

 if(diy){
  const boards=byId('boards');if(boards){
   const retained=new Set(routeBoards.map(item=>item.id));
   boards.querySelectorAll('[data-board-id]').forEach(row=>{row.hidden=!retained.has(row.dataset.boardId);});
   const heading=boards.querySelector('h2');if(heading)heading.textContent='HUB 成品板（价格以商品页为准）';
  }
  if(buyTools)document.querySelectorAll('[data-prepared="hand-tools"]').forEach(input=>{const item=input.closest('.unpriced-item');if(item)item.hidden=true;});
  document.querySelectorAll('.toc a[href="#boards"]').forEach(link=>{link.href='#boards';link.textContent='HUB 成品板';});
  const lead=document.querySelector('.page-head .lead');if(lead)lead.textContent='当前选择手工焊板卡：先备齐下方本体零件和 HUB 成品板，再按详细 BOM 准备 HAT／IMU 的 PCB、元件与焊接工具。';
  const badge=document.querySelector('.page-head .badge');if(badge)badge.textContent=buyTools?'自焊板卡 · 从零购买工具':'自焊板卡 · 已有焊接工具';
  const panel=byId('diy');
  if(panel){
   const first=panel.querySelector('p');if(first)first.textContent='当前路线不购买成品 HAT／IMU。首批 PCB 与元件材料参考 '+range(data.diyMaterialsMinCents,data.diyMaterialsMaxCents)+'；'+(buyTools?'另计工具与耗材预算 '+range(data.diyToolsMinCents,data.diyToolsMaxCents)+'。':'已有焊接设备可复用，缺少的耗材按实际补齐。');
   let checks=byId('diy-route-checks');
   if(!checks){checks=document.createElement('div');checks.id='diy-route-checks';checks.className='unpriced-list';panel.append(checks);}
   const addCheck=(id,name,description)=>{
    required.push({id,name});
    if(checks.querySelector('[data-prepared="'+id+'"]'))return;
    const article=document.createElement('article');article.className='unpriced-item';
    const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.dataset.prepared=id;
    label.append(input,text('span',name));article.append(label,text('p',description));checks.append(article);
   };
   addCheck('diy-materials','自焊 HAT／IMU 的 PCB 与元件','按详细 BOM 准备，首批整包材料参考 '+range(data.diyMaterialsMinCents,data.diyMaterialsMaxCents)+'。');
   if(buyTools)addCheck('diy-tools','焊接工具与耗材','参考预算 '+range(data.diyToolsMinCents,data.diyToolsMaxCents)+'，同一工具不要重复计入待补配件。');
   panel.querySelectorAll('a[href="budget.html#self-solder"]').forEach(link=>{link.href=budget;link.textContent='返回当前自焊预算 →';});
  }
 }
 const summary=document.querySelector('.summary-bar > div');
 if(summary&&(diy||printing==='service')){
  const labels=summary.querySelectorAll('small');
  if(labels[0])labels[0].textContent=(diy?'本体采购＋首批自焊板卡材料'+(buyTools?'＋工具预算':''):'基础采购')+(printing==='service'?'＋缝合怪版代打':'');
  if(labels[1])labels[1].textContent=(diy?'已扣除成品 HAT／IMU；':'')+(printing==='service'?'已计入代打参考 '+money(data.printServiceReferenceCents)+'，可在预算页按实际报价调整；':'打印耗材'+(printing==='buy-printer'?'与打印机设备费':'')+'另计；')+'HUB 按商品页价格另计，其他待补项目和运费另计。';
 }
 setText('printing-route-note',printing==='service'?'当前选择缝合怪版整套代打，参考 '+money(data.printServiceReferenceCents)+' 已计入本页参考合计；可在预算页改为实际报价。':'当前选择自己打印，不计入 '+money(data.printServiceReferenceCents)+' 的代打费；按缝合怪版说明准备硬质件与 TPU 耗材。'+(printing==='buy-printer'?'打印机设备费用在预算页另计。':''));
 const remaining=byId('remaining-total');
 if(remaining?.parentElement)remaining.parentElement.replaceChildren(document.createTextNode('未勾选的已列价基础零件参考合计：'),remaining,document.createTextNode('；'+(printing==='service'?'缝合怪版代打 '+money(data.printServiceReferenceCents)+' 另见打印专区；':'')+(diy?'自焊板卡材料、工具与':'')+'待报价项目另看对应清单。'));
 document.querySelectorAll('.summary-bar > a').forEach(link=>link.href=budget);
 if(diy||hasPrinting){
  setText('printing-choice-title',routeName+(printing?' ／ '+printingNames[printing]:''));
  const descriptions={
   own:'打印机已有，准备结构件与 TPU 的打印耗材，设备费不重复计入。',
   service:'缝合怪版整套代打参考 '+money(data.printServiceReferenceCents)+'，已计入本页参考合计；无需购买打印机，可在预算页改为实际报价。',
   'buy-printer':'另购打印机与硬质件、TPU 耗材；设备费按实际机型报价填写。',
  };
  setText('printing-choice-description',(diy?'先备齐本体零件、自焊板卡材料'+(buyTools?'和焊接工具':'')+'。':'先备齐下方成品板路线的基础零件。')+(printing?descriptions[printing]:''));
  const items=[];
  if(printing==='service')items.push('缝合怪版代打参考 '+money(data.printServiceReferenceCents)+'；下单时核对整套硬质结构件、TPU 部件与电池仓版本，实际报价可在预算页调整。');
  if(printing==='buy-printer')items.push('打印机设备参考预算 '+money(data.printerReferenceCents)+'；按实际报价调整，并准备硬质件与 TPU 耗材。');
  if(printing==='own')items.push('核对打印包与材料配置，电池仓选择其中一份，按硬质件和 TPU 分别准备耗材。');
  if(diy)items.push('HUB 成品板仍需准备；HAT／IMU 按 PCB 详细 BOM 自焊，完成自焊 IMU 固件烧录。');
  items.push((diy?'本体＋自焊材料'+(buyTools?'＋工具预算':''):'基础采购')+(printing==='service'?'＋缝合怪版代打':'')+'参考 '+(baseLabel||money(assembled))+'；'+(printing==='service'?'':printing==='buy-printer'?'打印机设备、打印耗材、':'打印耗材、')+'HUB 按商品页价格、其他待补项目与运费另计，不是最终完工总价。');
  const list=byId('printing-choice-items');if(list)list.replaceChildren(...items.map(value=>text('li',value)));
  const quote=byId('printing-choice-quote');if(quote){quote.href=budget+'#calculator';quote.textContent=printing==='service'?'调整代打与补充预算 →':printing==='buy-printer'?'调整设备与耗材预算 →':'返回当前预算 →';}
  const firstAction=document.querySelector('#printing-choice .actions a');if(firstAction)firstAction.href='#boards';
  const panel=byId('printing-choice');if(panel)panel.hidden=false;
 }
 return {required,priced,baseLabel};
}
