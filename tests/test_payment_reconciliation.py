import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from payment_reconciliation import aggregate_transactions,annual_summary
class PaymentTests(unittest.TestCase):
 def test_release_only_counts_inside_payment(self):
  raw=dict(transactionType='Shipment',transactionStatus='RELEASED',totalAmount=dict(currencyCode='EUR',currencyAmount=85),relatedIdentifiers=[dict(relatedIdentifierName='DEFERRED_TRANSACTION_ID',relatedIdentifierValue='original')],breakdowns=[dict(breakdownType='Sales',breakdownAmount=dict(currencyCode='EUR',currencyAmount=100)),dict(breakdownType='Expenses',breakdownAmount=dict(currencyCode='EUR',currencyAmount=-15))])
  a=aggregate_transactions([raw,dict(raw,transactionStatus='DEFERRED_RELEASED')],'EUR');self.assertEqual(a['metrics']['net'],8500);self.assertEqual(a['transactions'],1)
 def test_year_scope_and_unexplained_difference(self):
  payments=[dict(reference='one',confirmed=True,date='2026-01-10',amount=10000),dict(reference='old',confirmed=True,date='2025-01-10',amount=20000),dict(reference='failed',confirmed=False,date='2026-01-10',amount=5000)]
  detail=aggregate_transactions([],'EUR');detail['complete']=True
  a=annual_summary(payments,{'one':detail},2026);self.assertEqual(a['paid'],10000);self.assertEqual(a['difference'],10000);self.assertIsNone(a['taxPayable']);self.assertEqual(a['count'],1)
if __name__=='__main__':unittest.main()
