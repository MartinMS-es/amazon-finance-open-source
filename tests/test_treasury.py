import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from treasury_local import cash_summary

def balance(kind,value,children=None):return dict(balanceType=kind,amount=dict(currencyCode='EUR',currencyAmount=value),balances=children)
class TreasuryTests(unittest.TestCase):
 def test_no_double_counting_reserve(self):
  root=balance('TOTAL',100,[balance('AVAILABLE',60),balance('RESERVED',40,[balance('DEFERRED',30),balance('ACCOUNT_LEVEL_RESERVE',10)])]);root['partnerMetadata']={'marketplaceId':'A1RKKUPIHCS9HS'}
  row=dict(date='2022-01-01',market='ES',currency='EUR',amount=10000,raw=dict(transactionType='Transfer',description='Disbursement'))
  row['raw']['relatedIdentifiers']=[{'relatedIdentifierName':'FINANCIAL_EVENT_GROUP_ID','relatedIdentifierValue':'group'}]
  payments={'groups':[{'FinancialEventGroupId':'group','ProcessingStatus':'Closed','FundTransferStatus':'Succeeded','OriginalTotal':{'CurrencyCode':'EUR','CurrencyAmount':100},'FundTransferDate':'2026-09-01'}]}
  result=cash_summary([row],dict(balances=[root]),payment_snapshot=payments);self.assertEqual(result['paid'],10000);self.assertEqual(result['held'],4000);self.assertEqual(result['available'],6000)
  self.assertIsNone(cash_summary([row],dict(balances=[root]),'FR')['held'])
 def test_failed_and_open_are_not_paid(self):
  def group(ident,status,processing='Closed'):return dict(FinancialEventGroupId=ident,ProcessingStatus=processing,FundTransferStatus=status,OriginalTotal=dict(CurrencyCode='EUR',CurrencyAmount=100),FundTransferDate='2026-09-01')
  snapshot=dict(groups=[group('one','Succeeded'),group('two','Failed'),group('three','Unknown'),group('four','Succeeded','Open')])
  result=cash_summary([],None,payment_snapshot=snapshot)
  self.assertEqual(result['paid'],10000);self.assertEqual(result['failed'],1);self.assertEqual(result['unconfirmed'],3)
  self.assertEqual(cash_summary([],None,start='2026-10-01',payment_snapshot=snapshot)['periodPaid'],0)
 def test_absent_snapshot_is_not_zero(self):self.assertIsNone(cash_summary([],None)['held'])
if __name__=='__main__':unittest.main()
