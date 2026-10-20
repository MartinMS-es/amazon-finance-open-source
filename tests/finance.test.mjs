import assert from 'node:assert/strict';
import {money,csvParse,normalizeRow,exportCsv,summarize,matchCandidates} from '../lib/finance.mjs';
let passed=0;function test(name,fn){fn();console.log('OK '+name);passed++;}
test('Importes europeos y negativos',()=>{assert.equal(money('1.234,56'),123456);assert.equal(money('-12.50'),-1250);assert.throws(()=>money('texto'));assert.throws(()=>money(''));});
const input='id;fecha;mercado;moneda;tipo;importe;concepto\n1;2026-10-01;ES;EUR;Venta;100,00;"Venta; sílica"\n2;2026-10-01;ES;EUR;Comisión;-15,00;Comisión\n3;2026-10-01;ES;EUR;Liquidación;85,00;Pago';
test('CSV citado y signos',()=>{const rows=csvParse(input).map(normalizeRow);assert.equal(rows[0].description,'Venta; sílica');assert.equal(rows[1].amount,-1500);assert.equal(summarize(rows).net,8500);});
test('Fecha inválida y tipo desconocido rechazados',()=>{const row=csvParse(input)[0];assert.throws(()=>normalizeRow({...row,fecha:'2026-02-30'}));assert.throws(()=>normalizeRow({...row,tipo:'otro'}));});
test('Referencia y moneda deben coincidir para sugerencia',()=>{const rows=[{reference:'F1',currency:'GBP'},{reference:'F1',currency:'EUR'}];assert.equal(matchCandidates({reference:'F1',currency:'EUR'},rows).length,1);assert.equal(matchCandidates({reference:'',currency:'EUR'},rows).length,0);});
test('Exportación protege celdas de fórmula',()=>{const row=normalizeRow(csvParse(input)[0]);assert.ok(exportCsv([{...row,description:'=HYPERLINK("x")'}]).includes("'=HYPERLINK"));});
test('CSV con comillas abiertas y columnas incorrectas se rechaza',()=>{assert.throws(()=>csvParse('a;b\n"x;y'));assert.throws(()=>csvParse('a;b\n1;2;3'));});


test('Exportar e importar mantiene importes negativos',()=>{const rows=csvParse(input).map(normalizeRow);const back=csvParse(exportCsv(rows)).map(normalizeRow);assert.equal(back[1].amount,-1500);});

console.log(passed+' comprobaciones superadas');
