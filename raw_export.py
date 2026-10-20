"""Exportaciones de datos Amazon, sin secretos ni limites de la vista."""
import csv,datetime,hashlib,io,json,tempfile,zipfile
from pathlib import Path
from contextlib import closing

def selected(row,f):
 return (f.get('market','ALL') in ('ALL',row.get('market')) and f.get('currency','ALL') in ('ALL',row.get('currency')) and (not f.get('from') or row.get('date','')>=f['from']) and (not f.get('to') or row.get('date','')<=f['to']) and f.get('status','ALL') in ('ALL',row.get('status')))

def archive(connection,data,jobs,filters=None,files=False):
 f=filters or {};data=Path(data).resolve()
 with closing(connection()) as c:
  rows=[json.loads(p) for p, in c.execute('SELECT payload FROM records')]
 rows=[r for r in rows if selected(r,f) and r.get('raw')]
 output=tempfile.TemporaryFile()
 manifest=dict(exportedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),filters=f,transactions=len(rows),reports=[],tasks=[],format='AFOS Amazon raw export v1',notes=['transactions.ndjson contiene un objeto Amazon original por linea, tal como esta guardado; no son las respuestas HTTP completas ni un historial de versiones.','Incluye operaciones originales y liberaciones vinculadas; no sumar ambas como ventas.','Solo datos descargados. No certifica que el historico este completo.','Los informes no se filtran por moneda ni estado financiero; se seleccionan por mercado y solapamiento de fechas. Los archivos se conservan enteros.'])
 try:
  with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
   with z.open('transactions.ndjson','w',force_zip64=True) as stream:
    for r in rows:stream.write((json.dumps(r['raw'],ensure_ascii=False)+'\n').encode('utf-8'))
   with z.open('transactions-index.csv','w',force_zip64=True) as stream:
    text=io.TextIOWrapper(stream,encoding='utf-8-sig',newline='');writer=csv.writer(text,delimiter=';')
    writer.writerow(['transaction_id','date','market','currency','amount_original','status','type','deferred_transaction_id','release_transaction_id'])
    def safe(value):
     s=str(value or '');return "'"+s if s.startswith(('=','+','-','@','\t','\r')) else s
    for r in rows:
     raw=r['raw'];refs={x.get('relatedIdentifierName'):x.get('relatedIdentifierValue') for x in (raw.get('relatedIdentifiers') or [])}
     writer.writerow([safe(raw.get('transactionId')),r['date'],r['market'],r['currency'],format(__import__('decimal').Decimal(r['amount'])/100,'.2f'),r.get('status'),safe(raw.get('transactionType')),safe(refs.get('DEFERRED_TRANSACTION_ID')),safe(refs.get('RELEASE_TRANSACTION_ID'))])
    text.flush();text.detach()
   if files:
    for job in jobs:
     if f.get('market','ALL') not in ('ALL',job.get('market')) and f.get('market') not in (job.get('markets') or []):continue
     if f.get('from') and job.get('toDate') and job['toDate']<f['from']:continue
     if f.get('to') and job.get('fromDate') and job['fromDate']>f['to']:continue
     manifest['tasks'].append({k:job.get(k) for k in ('id','reportId','kind','market','fromDate','toDate','status','error')})
     if job.get('status')!='READY' or not job.get('filename'):continue
     path=(data/'reports'/job['filename']).resolve()
     if not path.is_relative_to(data/'reports') or not path.is_file():continue
     digest=hashlib.sha256()
     with path.open('rb') as stream:
      for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
     name='reports/'+str(job['id'])+path.suffix
     z.write(path,name);manifest['reports'].append(dict(path=name,sha256=digest.hexdigest(),reportId=job.get('reportId'),kind=job['kind'],market=job['market'],fromDate=job.get('fromDate'),toDate=job.get('toDate')))
   z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
   z.writestr('LEEME.txt','Exportacion local de los datos descargados de Amazon.\ntransactions.ndjson: datos originales de cada movimiento (una linea JSON por movimiento).\ntransactions-index.csv: indice completo para contrastar fechas, mercados, importes y estados.\nreports/: informes originales completos que ya estaban disponibles al exportar.\nmanifest.json: filtros, procedencia, estados y SHA-256 de los informes.\nNo contiene credenciales, tokens de acceso ni configuracion de seguridad.\nNo sumar operaciones y sus liberaciones vinculadas. No sumar de nuevo informes a movimientos.\nLos registros financieros y los informes comerciales usan criterios de fecha distintos.\n')
  output.seek(0);return output,manifest
 except BaseException:
  output.close();raise
