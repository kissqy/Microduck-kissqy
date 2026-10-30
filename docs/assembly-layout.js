// The viewing layout stays usable while the 3D model loads or WebGL is unavailable.
const workspace=document.querySelector('.workspace');
const dialog=document.getElementById('viewer-dialog');
const options=document.querySelector('.viewer-options');
const triggers=[...document.querySelectorAll('[data-expand-viewer]')];
const placeholder=document.createComment('assembly workspace');
workspace.before(placeholder);
options.open=!matchMedia('(max-width:1050px)').matches;
let opener=null,scrollY=0,optionsBefore=false,nextAnchor=null;
function expand(event){
 if(dialog.open){dialog.close();return;}
 opener=event.currentTarget;scrollY=window.scrollY;optionsBefore=options.open;
 if(matchMedia('(max-width:1050px), (max-height:550px)').matches)options.open=false;
 dialog.append(workspace);
 try{dialog.showModal();}catch{placeholder.after(workspace);options.open=optionsBefore;return;}
 document.body.classList.add('viewer-expanded');
 triggers.forEach(button=>{button.textContent='退出全屏';button.setAttribute('aria-expanded','true');});
 workspace.querySelector('[data-expand-viewer]').focus({preventScroll:true});
}
triggers.forEach(button=>{button.setAttribute('aria-expanded','false');button.addEventListener('click',expand);});
dialog.addEventListener('close',()=>{
 placeholder.after(workspace);options.open=optionsBefore;
 document.body.classList.remove('viewer-expanded');
 triggers.forEach((button,index)=>{button.textContent=index===0?'全屏查看 3D':'全屏查看';button.setAttribute('aria-expanded','false');});
 opener?.focus({preventScroll:true});
 if(nextAnchor){document.getElementById(nextAnchor)?.scrollIntoView();nextAnchor=null;}
 else window.scrollTo({top:scrollY,behavior:'instant'});
});
// Interface links leave the enlarged view before scrolling to their destination.
dialog.addEventListener('click',event=>{const link=event.target.closest('a[href^="#"]');if(link){event.preventDefault();nextAnchor=decodeURIComponent(link.hash.slice(1));dialog.close();}});
