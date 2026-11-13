// One visual language for feedback at the card that owns the operation.
import {formatError} from './messages.js';
export function showFeedback(element,message,status='info'){
  if(!element)return;
  const text=status==='error'?formatError(message):String(message||'');
  if(element.textContent!==text)element.textContent=text;
  element.classList.add('panel-note','service-job');
  for(const tone of ['info','running','completed','warning','error'])element.classList.toggle(tone,tone===status&&!!text);
}
