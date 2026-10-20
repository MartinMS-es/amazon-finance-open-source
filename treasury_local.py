"""Tesoreria: transferencias historicas y saldos actuales, nunca restados entre si."""
from decimal import Decimal
from amazon_local import MARKET_IDS

def cash_summary(rows,snapshot,market='ALL',currency='EUR',start='',end='',payment_snapshot=None,payment_details=None):
 mapping={}
 for row in rows:
  raw=row.get('raw') or {}
  if raw.get('transactionType')!='Transfer':continue
  for ref in raw.get('relatedIdentifiers') or []:
   if ref.get('relatedIdentifierName')=='FINANCIAL_EVENT_GROUP_ID':mapping.setdefault(ref.get('relatedIdentifierValue'),set()).add(row['market'])
 paid=0;returned=0;first=None;last=None;payments=[];periodPaid=0;unconfirmed=0;failed=0;unassigned=0
 for group in (payment_snapshot or {}).get('groups') or []:
  money=group.get('OriginalTotal') or {}
  if money.get('CurrencyCode')!=currency:continue
  codes=mapping.get(group['FinancialEventGroupId'],set());code=next(iter(codes)) if len(codes)==1 else 'SIN_ASIGNAR'
  if code=='SIN_ASIGNAR':unassigned+=1
  if market not in ('ALL',code):continue
  value=int((Decimal(str(money.get('CurrencyAmount',0)))*100).quantize(Decimal('1')))
  date=(group.get('FundTransferDate') or '')[:10];state=group.get('FundTransferStatus') or 'Sin confirmar'
  confirmed=group.get('ProcessingStatus')=='Closed' and state=='Succeeded'
  payments.append(dict(date=date,market=code,amount=value,reference=group['FinancialEventGroupId'],status=state,confirmed=confirmed))
  if state=='Failed':failed+=1
  if not confirmed:unconfirmed+=1;continue
  paid+=max(value,0);returned+=max(-value,0)
  if date:
   first=min(first,date) if first else date;last=max(last,date) if last else date
   if (not start or date>=start) and (not end or date<=end):periodPaid+=max(value,0)
 if payment_snapshot is None:paid=None;returned=None;periodPaid=None
 ids={v:k for k,v in MARKET_IDS.items()};values={};counts={};updated=[]
 def walk(nodes):
  for node in nodes or []:
   money=node.get('amount') or {};kind=node.get('balanceType')
   if money.get('currencyCode')==currency:
    values[kind]=values.get(kind,0)+int((Decimal(str(money['currencyAmount']))*100).quantize(Decimal('1')));counts[kind]=counts.get(kind,0)+1
   walk(node.get('balances'))
 for root in (snapshot or {}).get('balances') or []:
  code=ids.get((root.get('partnerMetadata') or {}).get('marketplaceId'),'OTHER')
  if market not in ('ALL',code):continue
  walk([root])
  if root.get('lastUpdatedTime'):updated.append(root['lastUpdatedTime'])
 from payment_reconciliation import annual_summary
 import datetime
 annual=annual_summary(payments,payment_details or {},datetime.date.today().year)
 if payment_snapshot is None:annual['paid']=None
 return dict(annual=annual,payments=sorted(payments,key=lambda x:x['date'],reverse=True),periodPaid=periodPaid,paid=paid,returned=returned,netPaid=paid-returned if paid is not None else None,paymentsChecked=(payment_snapshot or {}).get('checked'),paymentsCoverage=(payment_snapshot or {}).get('coverage',[]),paymentsErrors=(payment_snapshot or {}).get('errors',[]),paymentsComplete=(payment_snapshot or {}).get('complete',False),unconfirmed=unconfirmed,failed=failed,unassigned=unassigned,paymentFirst=first,paymentLast=last,held=values.get('RESERVED'),deferred=values.get('DEFERRED'),accountReserve=values.get('ACCOUNT_LEVEL_RESERVE'),available=values.get('AVAILABLE'),total=values.get('TOTAL'),checked=(snapshot or {}).get('checked'),oldestBalanceUpdate=min(updated) if updated else None,currency=currency,market=market)
