"""Analisis local sin mezclar monedas ni duplicar padres e hijos."""
from decimal import Decimal,ROUND_HALF_UP
FIELDS=('sales','refunds','fees','net','salesTax','refundTax','feeTax','salesExTax','refundsExTax','feesExTax','payouts','fundsToAmazon','unresolvedTax','otherMovements','identifiedResult','identifiedTaxes','netSalesExTax','netPayouts','reconciliationDifference')
def amount(node,currency):
 value=node.get('breakdownAmount') or {}
 if value.get('currencyCode')!=currency:return 0
 return int((Decimal(str(value.get('currencyAmount',0)))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def taxes(nodes,currency):
 total=0
 for node in nodes or []:
  # A tax parent already contains its children.
  if node.get('breakdownType')=='Tax':total+=amount(node,currency)
  else:total+=taxes(node.get('breakdowns'),currency)
 return total
def is_release_copy(row):
 raw=row.get('raw') or {}
 return row.get('status')=='RELEASED' and any(x.get('relatedIdentifierName')=='DEFERRED_TRANSACTION_ID' for x in (raw.get('relatedIdentifiers') or []))

def metrics(row):
 out=dict.fromkeys(FIELDS,0)
 if is_release_copy(row):return out
 raw=row.get('raw') or {};kind=raw.get('transactionType');currency=row['currency'];category=row.get('category');value=row['amount']
 nodes=raw.get('breakdowns') or []
 def group(name):return [n for n in nodes if n.get('breakdownType')==name]
 def group_amount(name):return sum(amount(n,currency) for n in group(name))
 if kind=='Transfer' and raw.get('description')=='Disbursement':
  out['payouts']=max(value,0);out['fundsToAmazon']=max(-value,0);out['netPayouts']=out['payouts']-out['fundsToAmazon'];return out
 if kind in ('Transfer','AdhocDisbursement') or category=='Liquidación':return out
 out['net']=value
 if category=='Sin clasificar' and raw:
  if kind=='Shipment':
   out['sales']=group_amount('Sales');out['salesTax']=taxes(group('Sales'),currency)
  elif kind=='Refund':
   out['refunds']=group_amount('Refunded Sales');out['refundTax']=taxes(group('Refunded Sales'),currency)
  if kind in ('Shipment','ServiceFee','ProductAdsPayment','Refund'):
   name='Refunded Expenses' if kind=='Refund' else 'Expenses'
   out['fees']=group_amount(name);out['feeTax']=taxes(group(name),currency)
  # Missing tax breakdown means unknown, not a verified zero tax amount.
  if kind in ('Shipment','Refund'):
   name='Sales' if kind=='Shipment' else 'Refunded Sales'
   if not any(n.get('breakdownType')=='Tax' for parent in group(name) for n in (parent.get('breakdowns') or [])):out['unresolvedTax']=1
 else:
  if category=='Venta':out['sales']=value;out['unresolvedTax']=1
  elif category=='Devolución':out['refunds']=value;out['unresolvedTax']=1
  elif category in ('Comisión','Logística FBA','Almacenamiento','Publicidad'):out['fees']=value
 out['salesExTax']=out['sales']-out['salesTax'];out['refundsExTax']=out['refunds']-out['refundTax'];out['feesExTax']=out['fees']-out['feeTax']
 out['netSalesExTax']=out['salesExTax']+out['refundsExTax']
 out['identifiedResult']=out['netSalesExTax']+out['feesExTax']
 out['identifiedTaxes']=out['salesTax']+out['refundTax']+out['feeTax']
 out['otherMovements']=out['net']-out['sales']-out['refunds']-out['fees']
 out['reconciliationDifference']=out['net']-(out['identifiedResult']+out['identifiedTaxes']+out['otherMovements'])
 return out

COST_LABELS={
 'Commission':('commission','Comisiones por vender'),
 'FBAPerUnitFulfillmentFee':('fulfillment','Preparación y entrega de pedidos'),
 'ShippingChargeback':('shipping','Cargos de transporte al cliente'),
 'StorageBillingFee':('storage','Almacenamiento mensual'),
 'LongTermStorageFee':('aged_storage','Almacenamiento prolongado'),
 'AdvertisingFee':('ads','Publicidad cobrada por Amazon'),
 'SubscriptionFee':('subscription','Cuota de la cuenta de vendedor'),
 'InboundTransportationFee':('inbound','Transporte hacia almacenes Amazon'),
 'DigitalServicesFee':('digital','Recargo por servicios digitales'),
 'DigitalServicesFeeFBA':('digital','Recargo por servicios digitales'),
 'DealParticipationFeeRollup':('deals','Tarifas por ofertas y promociones'),
 'DealPerformanceFeeRollup':('deals','Tarifas por ofertas y promociones'),
 'DealFee':('deals','Tarifas por ofertas y promociones'),
 'PromoRebates':('discounts','Descuentos y promociones a clientes'),
 'LiquidationProcessingFee':('liquidation','Tarifas de liquidación de inventario'),
 'LiquidationReferralFee':('liquidation','Tarifas de liquidación de inventario'),
 'EPRChargebackEcoFee':('environment','Cargos medioambientales'),
 'EPRChargebackServiceFee':('environment','Cargos medioambientales')}

def cost_parts(row):
 if is_release_copy(row):return []
 raw=row.get('raw') or {};kind=raw.get('transactionType');currency=row['currency']
 if row.get('category')!='Sin clasificar':
  labels={'Comisión':('commission','Comisiones por vender'),'Logística FBA':('fulfillment','Preparación y entrega de pedidos'),'Almacenamiento':('storage','Almacenamiento mensual'),'Publicidad':('ads','Publicidad cobrada por Amazon')}
  if row.get('category') in labels:
   key,label=labels[row['category']];return [(key,label,row['amount'],0,row['amount'],'Categoría importada')]
  return []
 if kind not in ('Shipment','ServiceFee','ProductAdsPayment','Refund'):return []
 def split(node):
  name=node.get('breakdownType') or 'Sin tipo';gross=amount(node,currency);tax=taxes([node],currency)
  if name=='Tax':return []
  if name in COST_LABELS:
   key,label=COST_LABELS[name];return [(key,label,gross,tax,gross-tax,name)]
  result=[]
  for child in node.get('breakdowns') or []:result.extend(split(child))
  remainingGross=gross-sum(x[2] for x in result);remainingTax=tax-sum(x[3] for x in result)
  if remainingGross or remainingTax:result.append(('other','Otros cargos pendientes de identificar',remainingGross,remainingTax,remainingGross-remainingTax,name))
  return result
 result=[];group='Refunded Expenses' if kind=='Refund' else 'Expenses'
 for node in raw.get('breakdowns') or []:
  if node.get('breakdownType')==group:result.extend(split(node))
 return result

def analyze(rows,filters=None):
 f=filters or {};selected=[];coverage={};all_count=0;excluded_releases=0
 for r in rows:
  all_count+=1
  if is_release_copy(r):excluded_releases+=1;continue
  key=(r['market'],r['currency'])
  if key not in coverage:coverage[key]=dict(market=key[0],currency=key[1],count=0,first=r['date'],last=r['date'])
  cov=coverage[key];cov['count']+=1;cov['first']=min(cov['first'],r['date']);cov['last']=max(cov['last'],r['date'])
  if f.get('market','ALL') not in ('ALL',r['market']):continue
  if r['currency']!=f.get('currency','EUR'):continue
  if f.get('from') and r['date']<f['from']:continue
  if f.get('to') and r['date']>f['to']:continue
  if f.get('status','ALL') not in ('ALL',r.get('status')):continue
  selected.append(r)
 total=dict.fromkeys(FIELDS,0);markets={};months={};statuses={};costs={}
 for r in selected:
  values=metrics(r)
  for key,label,gross,tax,base,source in cost_parts(r):
   bucket=costs.setdefault(key,dict(key=key,label=label,gross=0,tax=0,base=0,sources=set()))
   bucket['gross']+=gross;bucket['tax']+=tax;bucket['base']+=base;bucket['sources'].add(source)
  for target in (total,markets.setdefault(r['market'],dict(count=0,**dict.fromkeys(FIELDS,0))),months.setdefault(r['date'][:7],dict.fromkeys(FIELDS,0))):
   for k,v in values.items():target[k]+=v
  markets[r['market']]['count']+=1
  status=r.get('status') or 'Sin estado';statuses[status]=statuses.get(status,0)+1
 for bucket in costs.values():bucket['sources']=sorted(bucket['sources'])
 cost_difference=total['feesExTax']-sum(x['base'] for x in costs.values())
 return dict(summary=total,markets=markets,monthly=[[m,v['sales']] for m,v in sorted(months.items())][-12:],statuses=statuses,count=len(selected),total=all_count,coverage=list(coverage.values()),currency=f.get('currency','EUR'),costBreakdown=sorted(costs.values(),key=lambda x:x['base']),costDifference=cost_difference,excludedReleases=excluded_releases,scope='all_local_records')
