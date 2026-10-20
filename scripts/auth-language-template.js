(()=>{
 const dictionary=__CATALOGUE__;
 const originals=new WeakMap();let lang='es';try{lang=localStorage.getItem('afos-language')==='en'?'en':'es';}catch{}
 const select=document.createElement('select');select.setAttribute('aria-label','Idioma / Language');select.innerHTML='<option value="es">Español</option><option value="en">English</option>';select.value=lang;select.style.cssText='float:right;padding:6px;margin-bottom:12px';document.querySelector('main')?.prepend(select);
 function render(){document.documentElement.lang=lang;const walk=document.createTreeWalker(document.querySelector('main'),NodeFilter.SHOW_TEXT);let n;while(n=walk.nextNode()){if(n.parentElement.closest('script,style,#key,select'))continue;const text=n.textContent,key=text.trim();if(lang==='en'&&dictionary[key]){originals.set(n,key);const translated=text.replace(key,dictionary[key]);if(n.textContent!==translated)n.textContent=translated;}else if(lang==='es'&&originals.has(n)&&key===dictionary[originals.get(n)])n.textContent=text.replace(key,originals.get(n));}const code=document.getElementById('code');if(code)code.placeholder=lang==='en'?'6 digits':'6 dígitos';}
 select.onchange=()=>{lang=select.value;try{localStorage.setItem('afos-language',lang);}catch{}render();};new MutationObserver(render).observe(document.querySelector('main'),{childList:true,characterData:true,subtree:true});render();
})();
