import {english} from './en.mjs';
let language='es';
try{language=globalThis.localStorage?.getItem('afos-language')==='en'?'en':'es';}catch{}
export function getLanguage(){return language;}
export function getLocale(){return language==='en'?'en-GB':'es-ES';}
export function setLanguage(value){language=value==='en'?'en':'es';try{globalThis.localStorage?.setItem('afos-language',language);}catch{}if(typeof document!=='undefined'){document.documentElement.lang=language;const banner=document.querySelector('.local-banner');if(banner)banner.textContent=language==='en'?'Local version · Data stored on this PC · Private Amazon connection':'Versión local · Datos guardados en este ordenador · Conexión privada a Amazon';}if(typeof window!=='undefined')window.dispatchEvent(new Event('afos-language-change'));}
export function translate(value){
 if(language!=='en'||typeof value!=='string')return value;
 const normalized=value.replace(/\s+/g,' ').trim();
 if(english[normalized])return value.replace(value.trim(),english[normalized]);
 // Dynamic notices often append counts to a fixed, translated prefix or suffix.
 for(const key of Object.keys(english).sort((a,b)=>b.length-a.length)){
  if(key.length<10)continue;
  if(normalized.startsWith(key+' '))return english[key]+translate(normalized.slice(key.length));
  if(normalized.endsWith(' '+key))return translate(normalized.slice(0,-key.length))+english[key];
 }
 return value;
}
