export const markets={"CA": "Canadá", "US": "Estados Unidos", "MX": "México", "BR": "Brasil", "IE": "Irlanda", "ES": "España", "UK": "Reino Unido", "FR": "Francia", "BE": "Bélgica", "NL": "Países Bajos", "DE": "Alemania", "IT": "Italia", "SE": "Suecia", "ZA": "Sudáfrica", "PL": "Polonia", "EG": "Egipto", "TR": "Turquía", "SA": "Arabia Saudí", "AE": "Emiratos Árabes Unidos", "IN": "India", "SG": "Singapur", "AU": "Australia", "JP": "Japón", "OTHER": "Sin asignar"};
export const currencies=["AED", "AUD", "BRL", "CAD", "EGP", "EUR", "GBP", "INR", "JPY", "MXN", "PLN", "SAR", "SEK", "SGD", "TRY", "USD", "ZAR"];
export const categories=['Venta','Devolución','Comisión','Logística FBA','Almacenamiento','Publicidad','Ajuste','Liquidación','Sin clasificar'];
export function money(value){let s=String(value??'').trim().replace(/[€£$\s]/g,'');if(!s)throw Error('Importe vacío');if(s.includes(',')&&s.includes('.'))s=s.lastIndexOf(',')>s.lastIndexOf('.')?s.replace(/\./g,'').replace(',','.'):s.replace(/,/g,'');else if(s.includes(','))s=s.replace(',','.');if(!/^-?\d+(\.\d{1,2})?$/.test(s))throw Error('Importe no válido: '+value);const n=Number(s);if(!Number.isFinite(n)||Math.abs(n)>1e10)throw Error('Importe fuera de rango');return Math.round(n*100);}
export function csvParse(text){text=text.replace(/^\uFEFF/,'');const first=text.split(/\r?\n/)[0];const delimiter=first.includes('\t')?'\t':first.split(';').length>first.split(',').length?';':',';let rows=[],row=[],cell='',quoted=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}else if(c===delimiter&&!quoted){row.push(cell);cell='';}else if(c==='\n'&&!quoted){row.push(cell.replace(/\r$/,''));if(row.some(Boolean))rows.push(row);row=[];cell='';}else cell+=c;}if(quoted)throw Error('CSV con comillas sin cerrar');row.push(cell.replace(/\r$/,''));if(row.some(Boolean))rows.push(row);if(rows.length<2)throw Error('Se requiere cabecera y al menos una fila');const headers=rows.shift().map(s=>s.trim().toLowerCase());if(new Set(headers).size!==headers.length)throw Error('Cabeceras duplicadas');return rows.map((r,i)=>{if(r.length!==headers.length)throw Error('Columnas incorrectas en fila '+(i+2));return Object.fromEntries(headers.map((h,j)=>[h,r[j].trim()]));});}
export function normalizeRow(r){for(const k of ['id','fecha','mercado','moneda','tipo','importe'])if(!r[k])throw Error('Falta columna o valor: '+k);if(!/^\d{4}-\d{2}-\d{2}$/.test(r.fecha)||!Number.isFinite(Date.parse(r.fecha))||new Date(r.fecha).toISOString().slice(0,10)!==r.fecha)throw Error('Fecha no válida (AAAA-MM-DD)');const market=r.mercado.toUpperCase(),currency=r.moneda.toUpperCase();if(!markets[market])throw Error('Mercado desconocido: '+market);if(!currencies.includes(currency))throw Error('Moneda no admitida');if(!categories.includes(r.tipo))throw Error('Tipo no admitido: '+r.tipo);return {id:'csv:'+r.id,date:r.fecha,market,currency,category:r.tipo,amount:money(r.importe),order:r.pedido||'',sku:r.sku||'',reference:r.referencia||'',description:r.concepto||'',source:'CSV',status:'Importado'};}
export function csvEscape(v){const s=String(v??'');return '"'+((/^[=+@\-\t\r]/.test(s)&&!/^-[0-9]+(?:\.[0-9]+)?$/.test(s))?"'":'')+s.replace(/"/g,'""')+'"';}
export function exportCsv(rows){const h=['id','fecha','mercado','moneda','tipo','importe','pedido','sku','referencia','concepto'];return '\uFEFF'+[h,...rows.map(r=>[r.id.replace(/^csv:/,''),r.date,r.market,r.currency,r.category,(r.amount/100).toFixed(2),r.order,r.sku,r.reference,r.description])].map(r=>r.map(csvEscape).join(';')).join('\r\n');}
export function summarize(rows){
 const total={sales:0,refunds:0,fees:0,net:0};
 for(const r of rows){
  const raw=r.raw,kind=raw?.transactionType;
  if(r.status==='RELEASED'&&(raw?.relatedIdentifiers||[]).some(x=>x.relatedIdentifierName==='DEFERRED_TRANSACTION_ID'))continue;
  const transfer=['Transfer','AdhocDisbursement'].includes(kind);
  if(r.category!=='Liquidación'&&!transfer)total.net+=r.amount;
  if(r.category==='Sin clasificar'&&raw){
   // Use only top-level amounts: adding their children would duplicate money.
   const amount=type=>(raw.breakdowns||[]).filter(b=>b.breakdownType===type&&b.breakdownAmount?.currencyCode===r.currency).reduce((n,b)=>{const value=Number(b.breakdownAmount.currencyAmount);return n+(Number.isFinite(value)?Math.round((value+Number.EPSILON)*100):0);},0);
   if(kind==='Shipment'){total.sales+=amount('Sales');total.fees+=amount('Expenses');}
   else if(kind==='Refund'){total.refunds+=amount('Refunded Sales');total.fees+=amount('Refunded Expenses');}
   else if(['ServiceFee','ProductAdsPayment'].includes(kind))total.fees+=amount('Expenses');
  }else{
   if(r.category==='Venta')total.sales+=r.amount;
   if(r.category==='Devolución')total.refunds+=r.amount;
   if(['Comisión','Logística FBA','Almacenamiento','Publicidad'].includes(r.category))total.fees+=r.amount;
  }
 }
 return total;
}
export function matchCandidates(doc,rows){return doc.reference?rows.filter(r=>r.currency===doc.currency&&r.reference===doc.reference):[];}

