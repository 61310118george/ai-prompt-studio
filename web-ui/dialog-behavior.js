export function installDialogDismissal() {
  let pressed=null;
  const outside=(dialog,event)=>{
    const rect=dialog.getBoundingClientRect();
    return event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom;
  };
  document.addEventListener('pointerdown',event=>{
    const dialog=event.target;
    pressed=event.button===0&&dialog instanceof HTMLDialogElement&&dialog.open&&outside(dialog,event)?dialog:null;
  },true);
  document.addEventListener('pointercancel',()=>{pressed=null;},true);
  document.addEventListener('click',event=>{
    const dialog=pressed;pressed=null;
    if(!dialog||event.target!==dialog||!dialog.open||!outside(dialog,event))return;
    // Reuse Escape semantics, including draft confirmation and async-result invalidation.
    if(dialog.dispatchEvent(new Event('cancel',{cancelable:true}))&&dialog.open)dialog.close();
  },true);
}
