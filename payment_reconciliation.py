"""Desglose de pagos por grupo, segun la relacion oficial de Amazon."""
import datetime
from analysis_local import metrics,FIELDS

def aggregate_transactions(transactions,currency):
 total=dict.fromkeys(FIELDS,0);count=0
 for raw in transactions:
  if raw.get('transactionStatus')!='RELEASED':continue
  money=raw.get('totalAmount') or {}
  if money.get('currencyCode')!=currency:continue
  kind=raw.get('transactionType')
  if kind in ('Transfer','AdhocDisbursement'):continue
  from decimal import Decimal
  row=dict(currency=currency,category='Sin clasificar',amount=int((Decimal(str(money['currencyAmount']))*100).quantize(Decimal('1'))),raw=raw,status='PAYMENT_ALLOCATION')
  # A release copy counts inside its payment allocation, never as a new sale globally.
  values=metrics(row)
  for key,value in values.items():total[key]+=value
  count+=1
 return dict(metrics=total,transactions=count)

def annual_summary(payments,details,year):
 selected=[p for p in payments if p['confirmed'] and p['amount']>0 and p['date'].startswith(str(year)+'-')]
 total={k:0 for k in ('identifiedResult','salesTax','refundTax','feeTax','otherMovements','net','salesExTax','refundsExTax','feesExTax','unresolvedTax')};known=0;unknown=0;rows=[]
 for payment in selected:
  detail=details.get(payment['reference']);item=dict(payment)
  if detail and detail.get('complete'):
   known+=1;values=detail['metrics']
   for k in total:total[k]+=values.get(k,0)
   item['allocation']=values;item['difference']=payment['amount']-values['net']
  else:unknown+=1;item['allocation']=None;item['difference']=None
  rows.append(item)
 return dict(year=year,paid=sum(x['amount'] for x in selected),count=len(selected),detailed=known,pending=unknown,breakdown=total,details=rows,allocatedPaid=sum(p['amount'] for p in rows if p['allocation'] is not None),difference=sum(p['difference'] for p in rows if p['difference'] is not None),taxPayable=None)


def reconcile_year(engine):
 import time
 from amazon_local import now,AmazonError
 from urllib.parse import urlencode
 year=datetime.date.today().year
 snapshot=engine.get('confirmed_payment_groups') or {};groups=[g for g in snapshot.get('groups',[]) if g.get('ProcessingStatus')=='Closed' and g.get('FundTransferStatus')=='Succeeded' and (g.get('FundTransferDate') or '').startswith(str(year)+'-') and float((g.get('OriginalTotal') or {}).get('CurrencyAmount',0))>0]
 for group in sorted(groups,key=lambda g:g.get('FundTransferDate',''),reverse=True):
  ident=group['FinancialEventGroupId'];key='payment_detail:'+ident
  previous=engine.get(key)
  if previous and previous.get('complete'):continue
  token=None;seen=set();transactions=[]
  try:
   while True:
    q=dict(relatedIdentifierName='FINANCIAL_EVENT_GROUP_ID',relatedIdentifierValue=ident,transactionStatus='RELEASED')
    if token:q['nextToken']=token
    for attempt in range(5):
     try:result=engine.api('/finances/2024-06-19/transactions?'+urlencode(q),region=group.get('region','EU'));break
     except AmazonError as e:
      if e.status not in (429,500,502,503,504) or attempt==4:raise
      time.sleep(min(60,5*2**attempt))
    payload=result.get('payload') or {};transactions.extend(payload.get('transactions') or []);token=payload.get('nextToken')
    if not token:break
    if token in seen:raise ValueError('Pagina repetida')
    seen.add(token);time.sleep(2.1)
   # Save originals separately from global activity, with all pages and provenance.
   with engine.conn() as c:
    c.execute('CREATE TABLE IF NOT EXISTS payment_source_documents(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
    c.execute('INSERT INTO payment_source_documents VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(ident,__import__('json').dumps(dict(checked=now(),transactions=transactions))))
   detail=aggregate_transactions(transactions,group['OriginalTotal']['CurrencyCode']);detail.update(complete=True,checked=now(),currency=group['OriginalTotal']['CurrencyCode']);engine.put(key,detail)
  except Exception as e:engine.put(key,dict(complete=False,checked=now(),error=str(e) if isinstance(e,ValueError) else 'Error local al consultar el detalle'))
  time.sleep(2.1)
