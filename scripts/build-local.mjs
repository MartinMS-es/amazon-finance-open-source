import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import ts from 'typescript';
const translations=Object.fromEntries(fs.readFileSync('lib/translations-en.tsv','utf8').split(/\r?\n/).filter(line=>line.includes('\t')).map(line=>{const i=line.indexOf('\t');return [line.slice(0,i).trim(),line.slice(i+1).trim()];}));fs.writeFileSync('lib/en.mjs','export const english='+JSON.stringify(translations)+';');
const root=process.cwd(),req=createRequire(import.meta.url),mods=[],seen=new Map();
const aliases={'react':path.join(root,'node_modules/react/cjs/react.production.js'),'react/jsx-runtime':path.join(root,'lib/local-jsx-runtime.mjs'),'react/jsx-runtime-original':path.join(root,'node_modules/react/cjs/react-jsx-runtime.production.js'),'react-dom/client':path.join(root,'node_modules/react-dom/cjs/react-dom-client.production.js'),'react-dom':path.join(root,'node_modules/react-dom/cjs/react-dom.production.js'),'scheduler':path.join(root,'node_modules/scheduler/cjs/scheduler.production.js')};
function resolve(spec,file){if(aliases[spec])return aliases[spec];if(spec.startsWith('.')){const base=path.resolve(path.dirname(file),spec);for(const p of [base,base+'.tsx',base+'.ts',base+'.mjs',base+'.js'])if(fs.existsSync(p)&&fs.statSync(p).isFile())return p;}return createRequire(file).resolve(spec);}
function bundle(file){file=path.resolve(file);if(seen.has(file))return seen.get(file);const id=mods.length;seen.set(file,id);mods.push('');let s=fs.readFileSync(file,'utf8');if(file.endsWith('pdf.ts'))s=s.replace(/const path='\/pdfjs\/pdf.mjs';const pdf:any=await import\(\/\* @vite-ignore \*\/ path\);/,"const pdf:any=await (globalThis as any).__loadPdf();");
if(/\.(tsx?|mjs)$/.test(file))s=ts.transpileModule(s,{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
s=s.replace(/process\.env\.NODE_ENV/g,'"production"').replace(/require\(["']([^"']+)["']\)/g,(_,spec)=>'__r('+bundle(resolve(spec,file))+')');mods[id]='function(module,exports,__r){\n'+s+'\n}';return id;}
const id=bundle(path.join(root,'app/dashboard.tsx')),client=bundle(aliases['react-dom/client']),react=bundle(aliases.react);
fs.mkdirSync('local-web',{recursive:true});fs.writeFileSync('local-web/app.js','globalThis.__loadPdf=()=>import("/pdfjs/pdf.mjs");const __mods=['+mods.join(',')+'];const __cache={};function __r(i){if(__cache[i])return __cache[i].exports;const m=__cache[i]={exports:{}};__mods[i](m,m.exports,__r);return m.exports;}__r('+client+').createRoot(document.getElementById("root")).render(__r('+react+').createElement(__r('+id+').default));');
fs.writeFileSync('local-web/style.css',fs.readFileSync('app/globals.css','utf8').replace('@import "tailwindcss";','')+'\n.local-banner{padding:9px 20px;background:#f8edcb;color:#715b23;text-align:center;font:12px Arial}.local-banner b{font-weight:700}');
fs.writeFileSync('local-web/index.html','<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AMAZON FINANCE OPEN SOURCE · Local</title><link rel="stylesheet" href="/style.css"></head><body><div class="local-banner"><b>Versión local</b> · Datos guardados en este ordenador · Conexión y sincronización disponibles en la aplicación</div><div id="root"></div><script src="/app.js" defer></script></body></html>');
console.log('Aplicación local compilada sin procesos secundarios. '+mods.length+' módulos.');


fs.writeFileSync('local-web/i18n-auth.js',fs.readFileSync('scripts/auth-language-template.js','utf8').replace('__CATALOGUE__',JSON.stringify(translations)));
