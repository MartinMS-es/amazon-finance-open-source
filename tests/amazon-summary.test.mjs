import assert from 'node:assert/strict';
import {summarize} from '../lib/finance.mjs';
const b=(name,value,currency='EUR')=>({breakdownType:name,breakdownAmount:{currencyCode:currency,currencyAmount:value},breakdowns:[{breakdownType:'Child',breakdownAmount:{currencyCode:currency,currencyAmount:value}}]});
const row=(kind,amount,breakdowns)=>({category:'Sin clasificar',currency:'EUR',amount,raw:{transactionType:kind,breakdowns}});
const shipment=row('Shipment',8500,[b('Sales',100),b('Expenses',-15)]);
assert.deepEqual(summarize([shipment]),{sales:10000,fees:-1500,refunds:0,net:8500});
const refund=row('Refund',-8500,[b('Refunded Sales',-100),b('Refunded Expenses',15)]);
assert.deepEqual(summarize([shipment,refund]),{sales:10000,fees:0,refunds:-10000,net:0});
assert.deepEqual(summarize([row('Transfer',-8500,[b('Sales',-85)])]),{sales:0,fees:0,refunds:0,net:0});
assert.deepEqual(summarize([row('Adjustment',200,[b('Sales',2)])]),{sales:0,fees:0,refunds:0,net:200});
assert.equal(summarize([row('ProductAdsPayment',-250,[b('Expenses',-2.5)])]).fees,-250);
assert.equal(summarize([row('Shipment',100,[b('Sales',999,'GBP')])]).sales,0);
assert.deepEqual(summarize([{category:'Venta',amount:500}]),{sales:500,fees:0,refunds:0,net:500});
console.log('7 casos: ventas brutas, devoluciones, transferencias, ajustes, publicidad, monedas y CSV; sin duplicar hijos.');

const releaseCopy={...shipment,status:'RELEASED',raw:{...shipment.raw,relatedIdentifiers:[{relatedIdentifierName:'DEFERRED_TRANSACTION_ID',relatedIdentifierValue:'original'}]}};
assert.deepEqual(summarize([shipment,releaseCopy]),{sales:10000,fees:-1500,refunds:0,net:8500});
console.log('Liberacion vinculada no duplica ventas ni gastos.');
