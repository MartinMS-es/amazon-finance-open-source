import sys,tempfile,sqlite3,json,zipfile,unittest,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from raw_export import archive
class ClosedConnection(sqlite3.Connection):
 def __exit__(self,*args):
  try:return super().__exit__(*args)
  finally:self.close()
class ExportTests(unittest.TestCase):
 def test_all_rows_and_original_file(self):
  with tempfile.TemporaryDirectory() as folder:
   data=Path(folder);(data/'reports').mkdir();original=b'col1;col2\noriginal;completo\n';(data/'reports'/'original.csv').write_bytes(original)
   def connection():return sqlite3.connect(data/'db.sqlite',factory=ClosedConnection)
   raw=dict(transactionId='=FORMULA',transactionType='Shipment',extraOriginal=dict(preserved=True))
   row=dict(raw=raw,date='2026-09-01',market='ES',currency='EUR',status='DEFERRED_RELEASED',amount=1234)
   with connection() as c:
    c.execute('create table records(payload text)');c.executemany('insert into records values(?)',[(json.dumps(row),)]*20001)
   jobs=[dict(id='report-1',kind='sales',market='ES',status='READY',filename='original.csv',reportId='amazon-report',fromDate='2026-09-01',toDate='2026-09-30'),dict(id='pending',kind='sales',market='ES',status='QUEUED')]
   stream,m=archive(connection,data,jobs,files=True)
   with stream,zipfile.ZipFile(stream) as z:
    self.assertEqual(len(z.read('transactions.ndjson').splitlines()),20001)
    self.assertEqual(json.loads(z.read('transactions.ndjson').splitlines()[0]),raw)
    self.assertEqual(z.read('reports/report-1.csv'),original)
    self.assertEqual(m['reports'][0]['sha256'],hashlib.sha256(original).hexdigest())
    self.assertEqual(len(m['tasks']),2);self.assertIn("'=FORMULA",z.read('transactions-index.csv').decode('utf-8-sig'))
    self.assertFalse(any('credential' in n or 'sqlite' in n for n in z.namelist()))
   stream,m=archive(connection,data,jobs,{'market':'FR'},True)
   with stream:self.assertEqual(m['transactions'],0);self.assertEqual(m['reports'],[])
 def test_path_traversal_excluded(self):
  with tempfile.TemporaryDirectory() as folder:
   data=Path(folder);(data/'reports').mkdir();(data/'secret.txt').write_text('private')
   def connection():return sqlite3.connect(data/'db.sqlite',factory=ClosedConnection)
   with connection() as c:c.execute('create table records(payload text)')
   stream,m=archive(connection,data,[dict(id='bad',kind='sales',market='ES',status='READY',filename='../secret.txt')],files=True)
   with stream:self.assertEqual(m['reports'],[])
if __name__=='__main__':unittest.main()
