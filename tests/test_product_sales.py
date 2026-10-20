import sys,json,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from product_sales import product_sales
class ProductTests(unittest.TestCase):
 def test_no_overlap_and_quantity(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder);(p/'reports').mkdir();jobs=[]
   for i in range(2):
    report=dict(reportSpecification=dict(marketplaceIds=['A1RKKUPIHCS9HS'],dataStartTime='2026-09-01',dataEndTime='2026-09-30',reportOptions=dict(asinGranularity='CHILD')),salesAndTrafficByAsin=[dict(childAsin='TEST',parentAsin='PARENT',salesByAsin=dict(unitsOrdered=12,unitsShipped=10,unitsRefunded=1,orderedProductSales=dict(amount=120,currencyCode='EUR')))])
    (p/'reports'/str(i)).write_text(json.dumps(report));jobs.append(dict(id=str(i),kind='sales',status='READY',filename=str(i)))
   result=product_sales(p,jobs,'2026-09-01','2026-09-30')
   self.assertEqual(result['rows'][0]['unitsOrdered'],12);self.assertEqual(result['coverage']['ES'],30);self.assertEqual(len(result['sources']),1)
   self.assertEqual(product_sales(p,jobs,'2026-09-01','2026-09-15')['rows'],[])
   self.assertEqual(product_sales(p,jobs,'2026-09-01','2026-09-30','FR')['rows'],[])
if __name__=='__main__':unittest.main()
