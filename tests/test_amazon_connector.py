"""Pruebas del conector con transporte simulado. Nunca llaman a Amazon."""
import sys,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['AFOS_DATA_DIR']=str(ROOT/'tests'/'connector-data')
import local_server as server
import amazon_local as a
engine=server.AMAZON;checks=0
assert server.DATA.resolve()==(ROOT/'tests'/'connector-data').resolve()
with server.conn() as db:
 for table in ['integration_state','amazon_reports','records','documents']:db.execute('DELETE FROM '+table)
def check(v,name):
 global checks
 assert v,name
 checks+=1;print('OK',name)
check(not engine.status()['connection'],'Espacio de pruebas independiente')
try:engine.configure({});raise AssertionError('Aceptó credenciales vacías')
except ValueError:checks+=1
if os.name=='nt':
 sample=b'valor-sintetico-sin-credenciales';encoded=a.protect(sample)
 check(encoded!=sample and a.protect(encoded,True)==sample,'Cifrado DPAPI con datos sintéticos')
for url in ['http://127.0.0.1/a','https://example.com/a','https://s3.amazonaws.com.evil.test/a','https://user:password@s3.amazonaws.com/a']:
 try:a.safe_download(url);raise AssertionError('Aceptó URL insegura')
 except ValueError:checks+=1
calls=[]
sales={'salesAndTrafficByDate':[{'date':'2026-09-01','salesByDate':{'orderedProductSales':{'amount':100,'currencyCode':'EUR'},'unitsOrdered':2}}],'salesAndTrafficByAsin':[{'childAsin':'BTEST','salesByAsin':{'unitsOrdered':2}}]}
def api(path,method='GET',body=None,token=None,region='EU'):
 calls.append((path,method,body,token))
 if path.startswith('/sellers/'):return {'payload':[{'marketplace':{'id':a.MARKET_IDS['ES'],'name':'España'},'participation':{'isParticipating':True}}]}
 if path=='/reports/2021-06-30/reports' and method=='POST':return {'reportId':'REPORT-1'}
 if '/reports/REPORT-1' in path:return {'processingStatus':'DONE','reportDocumentId':'DOC-1'}
 if path.startswith('/tokens/'):return {'restrictedDataToken':'synthetic-rdt'}
 if '/documents/DOC-1' in path:return {'url':'https://test.s3.amazonaws.com/report'}
 if path.startswith('/finances/'):return {'payload':{'transactions':[{'transactionId':'T1','postedDate':'2026-09-01T00:00:00Z','transactionStatus':'RELEASED','totalAmount':{'currencyCode':'EUR','currencyAmount':12.1},'marketplaceDetails':{'marketplaceId':a.MARKET_IDS['ES']},'relatedIdentifiers':[{'relatedIdentifierName':'ORDER_ID','relatedIdentifierValue':'ORDER1'}]}]}}
 raise AssertionError(path)
engine.api=api
a.safe_download=lambda *args:json.dumps(sales).encode()
connection=engine.test();check(connection['markets'][0]['code']=='ES','Mercados se detectan desde la autorización')
body={'kind':'sales','from':'2026-09-01','to':'2026-09-30','markets':['ES']}
queued=engine.enqueue(body);check(queued['queued']==1,'Cola de informes')
check(engine.enqueue(body)['queued']==0,'No duplica solicitudes de mismo tipo, mercado y periodo')
j=next(j for j in engine.jobs() if j['kind']=='sales')
check(engine.step(j['id'])['status']=='IN_QUEUE','Solicita el informe y conserva su ID')
j=next(j for j in engine.jobs() if j['id']==j['id']);j['nextAt']=0;engine.save_job(j)
result=engine.step(j['id']);check(result['status']=='READY' and result['rows']==1,'Descarga y análisis JSON')
_,path,fmt=engine.report_file(j['id']);check(json.loads(path.read_bytes())==sales and fmt=='json','Conserva el archivo original')
creation=next(c for c in calls if c[1]=='POST' and c[0]=='/reports/2021-06-30/reports')
check(creation[2]['reportOptions']['asinGranularity']=='CHILD','Solicita detalle ASIN hijo')
check(creation[2]['marketplaceIds']==[a.MARKET_IDS['ES']],'Restringe al mercado autorizado')
try:engine.enqueue(dict(body,markets=['DE']));raise AssertionError('Mercado sin permiso')
except ValueError:checks+=1
try:engine.enqueue(dict(body,kind='unknown'));raise AssertionError('Tipo arbitrario')
except ValueError:checks+=1
try:engine.enqueue(dict(body,kind='vat',**{'from':'2026-09-02'}));raise AssertionError('IVA parcial')
except ValueError:checks+=1
engine.last_create=0
engine.enqueue(dict(body,kind='vcs'))
vcs=next(x for x in engine.jobs() if x['kind']=='vcs');engine.step(vcs['id']);vcs=next(x for x in engine.jobs() if x['id']==vcs['id']);vcs['nextAt']=0;engine.save_job(vcs)
a.safe_download=lambda *args:b'invoice,total\nF1,12.10\n'
result=engine.step(vcs['id']);check(result['status']=='DONE' and result['nextAt']>a.time.time(),'Respeta la espera entre documentos de Amazon')
engine.last_document=0;result['nextAt']=0;engine.save_job(result)
result=engine.step(vcs['id']);check(result['status']=='READY','Informe fiscal con RDT')
check(any(c[0].startswith('/tokens/') and c[2]['restrictedResources'][0]['path'].endswith('/DOC-1') for c in calls),'RDT limitado al documento solicitado')
check(any('/documents/' in c[0] and c[3]=='synthetic-rdt' for c in calls),'Usa el RDT para el documento fiscal')
sync=engine.sync_finances({'from':'2026-09-01','to':'2026-09-30'})
check(sync['complete'] and sync['count']==1,'Recuperación financiera')
with server.conn() as db:
 rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM records')]
check(rows[0]['amount']==1210 and rows[0]['order']=='ORDER1','Importes exactos y referencia de pedido')
engine.sync_finances({'from':'2026-09-01','to':'2026-09-30'})
with server.conn() as db:check(db.execute('SELECT count(*) FROM records').fetchone()[0]==1,'Sin duplicación financiera al repetir periodo')
print(checks,'comprobaciones del conector superadas; sin conexión de producción.')

