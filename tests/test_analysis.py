import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis_local import analyze,metrics

def node(name,value,children=None):return dict(breakdownType=name,breakdownAmount=dict(currencyCode='EUR',currencyAmount=value),breakdowns=children)
def row(kind,value,nodes,**extra):return dict(id='test',date='2025-01-01',market='ES',currency='EUR',amount=value,category='Sin clasificar',status='RELEASED',raw=dict(transactionType=kind,description='Disbursement' if kind=='Transfer' else '',breakdowns=nodes),**extra)
class AnalysisTests(unittest.TestCase):
 def test_release_is_not_a_second_sale(self):
  original=row('Shipment',8500,[node('Sales',100),node('Expenses',-15)])
  original['status']='DEFERRED_RELEASED';original['raw']['transactionId']='original'
  release=row('Shipment',8500,[node('Sales',100),node('Expenses',-15)])
  release['date']='2025-02-01';release['raw']['relatedIdentifiers']=[dict(relatedIdentifierName='DEFERRED_TRANSACTION_ID',relatedIdentifierValue='original')]
  result=analyze([original,release]);self.assertEqual(result['summary']['sales'],10000);self.assertEqual(result['summary']['fees'],-1500);self.assertEqual(result['count'],1);self.assertEqual(result['excludedReleases'],1)
  self.assertEqual(analyze([original,release],{'from':'2025-02-01','to':'2025-02-28'})['summary']['sales'],0)
 def test_cost_breakdown_reconciles(self):
  commission=node('Commission',-12,[node('Base',-10),node('Tax',-2)])
  ads=node('AdvertisingFee',-5)
  r=row('Shipment',8300,[node('Sales',100),node('Expenses',-17,[node('AmazonFees',-12,[commission]),ads])])
  a=analyze([r]);self.assertEqual(a['costDifference'],0)
  costs={x['key']:x for x in a['costBreakdown']}
  self.assertEqual(costs['commission']['base'],-1000);self.assertEqual(costs['commission']['tax'],-200)
  self.assertEqual(costs['ads']['base'],-500)
 def test_unknown_cost_not_guessed(self):
  r=row('ServiceFee',-400,[node('Expenses',-4,[node('UnrecognizedFee',-4)])])
  a=analyze([r]);self.assertEqual(a['costBreakdown'][0]['key'],'other');self.assertEqual(a['costDifference'],0)
 def test_financial_bridge(self):
  sale=row('Shipment',10000,[node('Sales',121,[node('Tax',21)]),node('Expenses',-21,[node('Tax',-1)])])
  adjustment=row('Adjustment',500,[]);payout=row('Transfer',8000,[])
  result=analyze([sale,adjustment,payout])['summary']
  self.assertEqual(result['identifiedResult'],8000);self.assertEqual(result['identifiedTaxes'],2000);self.assertEqual(result['otherMovements'],500)
  self.assertEqual(result['net'],10500);self.assertEqual(result['reconciliationDifference'],0);self.assertEqual(result['netPayouts'],8000)
 def test_taxes_and_parents(self):
  r=row('Shipment',10000,[node('Sales',121,[node('ProductCharges',100),node('Tax',21,[node('Tax',21)])]),node('Expenses',-21,[node('Commission',-21,[node('Base',-20),node('Tax',-1)])])])
  m=metrics(r);self.assertEqual((m['sales'],m['salesTax'],m['salesExTax'],m['feeTax'],m['feesExTax']),(12100,2100,10000,-100,-2000))
 def test_payout_is_not_loss_or_sale(self):
  m=metrics(row('Transfer',8000,[node('Sales',80)]));self.assertEqual(m['payouts'],8000);self.assertEqual(m['net'],0);self.assertEqual(m['sales'],0)
  self.assertEqual(metrics(row('Transfer',-100,[]))['fundsToAmazon'],100)
 def test_no_20000_limit(self):
  r=row('Shipment',100,[node('Sales',1)])
  a=analyze((r for _ in range(20001)));self.assertEqual(a['summary']['sales'],2000100);self.assertEqual(a['markets']['ES']['count'],20001)
 def test_currency_status_and_market(self):
  a=row('Shipment',100,[]);b=dict(a,currency='GBP',market='UK');c=dict(a,status='DEFERRED')
  result=analyze([a,b,c],{'currency':'EUR','status':'RELEASED','market':'ES'});self.assertEqual(result['count'],1);self.assertEqual(len(result['coverage']),2)
 def test_null_breakdowns_and_refund(self):
  self.assertEqual(metrics(row('Shipment',100,None))['unresolvedTax'],1)
  m=metrics(row('Refund',-12100,[node('Refunded Sales',-121,[node('Tax',-21)])]));self.assertEqual(m['refundsExTax'],-10000)
if __name__=='__main__':unittest.main()
