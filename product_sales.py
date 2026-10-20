"""Unidades por ASIN desde informes comerciales completos sin solapar periodos."""
import datetime,json
from decimal import Decimal
from amazon_local import MARKET_IDS

def product_sales(data,jobs,start,end,market='ALL'):
 first=datetime.date.fromisoformat(start);last=datetime.date.fromisoformat(end)
 if last<first or (last-first).days>730:raise ValueError('Selecciona un periodo de hasta dos años')
 ids={v:k for k,v in MARKET_IDS.items()};candidates=[]
 for job in jobs:
  if job.get('kind')!='sales' or job.get('status')!='READY':continue
  path=(Path(data)/'reports'/job.get('filename','')).resolve()
  if not path.is_relative_to((Path(data)/'reports').resolve()) or not path.is_file():continue
  report=json.loads(path.read_bytes());spec=report.get('reportSpecification') or {}
  mids=spec.get('marketplaceIds') or []
  if len(mids)!=1 or mids[0] not in ids:continue
  code=ids[mids[0]]
  if market not in ('ALL',code):continue
  if (spec.get('reportOptions') or {}).get('asinGranularity','PARENT')!='CHILD':continue
  a=datetime.date.fromisoformat(spec['dataStartTime'][:10]);b=datetime.date.fromisoformat(spec['dataEndTime'][:10])
  if a<first or b>last:continue
  candidates.append((code,a,b,job,report))
 used={};totals={};sources=[]
 for code,a,b,job,report in sorted(candidates,key=lambda x:((x[2]-x[1]).days,x[3].get('created','')),reverse=True):
  days={a+datetime.timedelta(days=i) for i in range((b-a).days+1)}
  if used.setdefault(code,set())&days:continue
  used[code]|=days;sources.append(dict(market=code,fromDate=a.isoformat(),toDate=b.isoformat(),id=job['id']))
  for item in report.get('salesAndTrafficByAsin') or []:
   asin=item.get('childAsin')
   if not asin:continue
   values=item.get('salesByAsin') or {};money=values.get('orderedProductSales') or {};currency=money.get('currencyCode','')
   key=(code,asin,currency);r=totals.setdefault(key,dict(market=code,asin=asin,parentAsin=item.get('parentAsin',''),unitsOrdered=0,unitsShipped=0,unitsRefunded=0,sales=0,currency=currency))
   for k in ('unitsOrdered','unitsShipped','unitsRefunded'):r[k]+=int(values.get(k) or 0)
   r['sales']+=int((Decimal(str(money.get('amount',0)))*100).quantize(Decimal('1')))
 return dict(rows=sorted(totals.values(),key=lambda x:x['unitsOrdered'],reverse=True),sources=sources,coverage={m:len(d) for m,d in used.items()},expectedDays=(last-first).days+1,fromDate=start,toDate=end)
from pathlib import Path
