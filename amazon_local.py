"""Conector local SP-API. Datos y tokens no se exponen al navegador."""
import os,json,time,threading,datetime,uuid,hashlib,gzip,io,csv,ctypes
from ctypes import wintypes
from urllib.request import Request,urlopen,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,quote,urlparse
from amazon_markets import MARKET_IDS,MARKET_REGIONS,REGION_ENDPOINTS,region_for_market
REPORTS=[
 {'key':'sales','name':'Ventas y tráfico por día y ASIN','type':'GET_SALES_AND_TRAFFIC_REPORT','role':'Brand Analytics','format':'json','mode':'request','note':'Ventas de pedidos: no equivale a cobros ni beneficio.'},
 {'key':'shipments','name':'Ventas enviadas por FBA','type':'GET_FBA_FULFILLMENT_CUSTOMER_SHIPMENT_SALES_DATA','role':'Amazon Fulfillment','format':'tsv','mode':'request'},
 {'key':'returns','name':'Devoluciones de clientes FBA','type':'GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA','role':'Amazon Fulfillment','format':'tsv','mode':'request'},
 {'key':'reimbursements','name':'Reembolsos de inventario FBA','type':'GET_FBA_REIMBURSEMENTS_DATA','role':'Amazon Fulfillment','format':'tsv','mode':'request'},
 {'key':'storage','name':'Estimación de almacenamiento FBA','type':'GET_FBA_STORAGE_FEE_CHARGES_DATA','role':'Amazon Fulfillment','format':'tsv','mode':'request','note':'Estimación mensual, no sustituye la factura de cargos.'},
 {'key':'settlement','name':'Liquidaciones V2','type':'GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2','role':'Finance and Accounting','format':'tsv','mode':'existing','note':'Amazon genera estos informes. Se buscan por fecha de creación.'},
 {'key':'vcs','name':'Cálculos de IVA y facturación VCS','type':'SC_VAT_TAX_REPORT','role':'Tax Invoicing (Restricted)','format':'csv','mode':'request','restricted':True,'note':'Requiere aprobación fiscal de Amazon y VCS. No es una descarga de los PDF.'},
 {'key':'vat','name':'Transacciones de IVA paneuropeas','type':'GET_VAT_TRANSACTION_DATA','role':'Tax Invoicing (Restricted)','format':'tsv','mode':'request','restricted':True,'note':'Disponible desde el día 3 del mes. Incluye los mercados disponibles; Amazon ignora el filtro de mercado.'}
]
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
class AmazonError(ValueError):
 def __init__(self,message,status=400):super().__init__(message);self.status=status
class Blob(ctypes.Structure):
 _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
def protect(data,decode=False):
 if os.name!='nt':raise ValueError('El almacén de credenciales local requiere Windows DPAPI')
 buf=ctypes.create_string_buffer(data);src=Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)));out=Blob()
 crypt=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
 if decode:
  fn=crypt.CryptUnprotectData;fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
 else:
  fn=crypt.CryptProtectData;fn.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
 fn.restype=wintypes.BOOL
 if not fn(ctypes.byref(src),None,None,None,None,1,ctypes.byref(out)):raise ValueError('No se pudo acceder al almacén cifrado de Windows')
 try:return ctypes.string_at(out.pbData,out.cbData)
 finally:kernel.LocalFree(ctypes.cast(out.pbData,ctypes.c_void_p))
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
def safe_download(url,compression=None):
 u=urlparse(url);host=(u.hostname or '').lower()
 if u.scheme!='https' or u.username or u.password or u.port not in (None,443) or not any(host.endswith(x) for x in ['.amazonaws.com','.amazon.com','.cloudfront.net']):raise ValueError('Dominio de descarga no admitido')
 limit=50*1024*1024
 try:
  with build_opener(NoRedirect()).open(Request(url),timeout=45) as r:data=r.read(limit+1)
 except Exception:raise AmazonError('No se pudo descargar el archivo de Amazon. Reintenta para renovar su enlace.',503)
 if len(data)>limit:raise ValueError('Informe superior al límite de 50 MB')
 if compression=='GZIP':
  with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:data=f.read(limit+1)
 elif compression:raise ValueError('Compresión de informe no admitida')
 if len(data)>limit:raise ValueError('Informe descomprimido superior a 50 MB')
 return data
def read_report(data,fmt):
 text=None
 for encoding in (['utf-16'] if data.startswith((b'\xff\xfe',b'\xfe\xff')) else ['utf-8-sig','cp1252']):
  try:text=data.decode(encoding);break
  except UnicodeError:continue
 if text is None:raise ValueError('Codificación no reconocida')
 if fmt=='json':
  d=json.loads(text);daily=d.get('salesAndTrafficByDate',[]);asins=d.get('salesAndTrafficByAsin',[])
  return dict(daily=daily,asins=asins)
 return list(csv.DictReader(io.StringIO(text),delimiter='\t' if fmt=='tsv' else ','))
class Engine:
 def __init__(self,connection,data):
  self.conn=connection;self.data=data;self.mutex=threading.RLock();self.token=None;self.expiry=0;self.region_tokens={};self.last_create=0;self.last_document=0;self.closed=threading.Event()
  (data/'reports').mkdir(exist_ok=True)
  with self.conn() as c:
   c.execute('CREATE TABLE IF NOT EXISTS integration_state(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
   c.execute('CREATE TABLE IF NOT EXISTS amazon_reports(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
 def get(self,key):
  with self.conn() as c:r=c.execute('SELECT payload FROM integration_state WHERE id=?',(key,)).fetchone()
  return json.loads(r[0]) if r else None
 def put(self,key,value):
  with self.conn() as c:c.execute('INSERT INTO integration_state VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(key,json.dumps(value)))
 def credentials(self,region='EU'):
  if region not in REGION_ENDPOINTS:raise ValueError('Región de Amazon no admitida')
  prefix='AMAZON_' if region=='EU' else 'AMAZON_'+region+'_'
  e={k:os.environ.get(prefix+k.upper(),'') for k in ['client_id','client_secret','refresh_token']}
  if all(e.values()):return e
  p=self.data/('amazon-credentials.dpapi' if region=='EU' else 'amazon-credentials-'+region+'.dpapi')
  return json.loads(protect(p.read_bytes(),True)) if p.exists() else None
 def configured_regions(self):
  result=[]
  for region in REGION_ENDPOINTS:
   try:
    if self.credentials(region):result.append(region)
   except ValueError:pass
  return result
 def status(self):
  configured=self.configured_regions();connection=self.get('connection')
  regional=dict((connection or {}).get('regions') or {})
  if connection and not regional:regional['EU']=dict(checked=connection.get('checked'),markets=connection.get('markets',[]))
  return dict(ready=bool(configured),regions={r:dict(ready=r in configured,connected=r in regional) for r in REGION_ENDPOINTS},local=True,secure=os.environ.get('AFOS_SECURE')=='1' or (self.data/'secure-enabled').exists(),storage='Windows DPAPI',connection=dict(connection,regions=regional) if connection else None,sync=self.get('sync'),history={k:v for k,v in (self.get('historical_recovery') or {}).items() if k in ['status','phase','period','pages','updated','error','queued','since','partial','unavailable']},catalog=REPORTS)
 def configure(self,b):
  region=b.get('region','EU')
  if region not in REGION_ENDPOINTS:raise ValueError('Región de Amazon no admitida')
  values={k:str(b.get(k,'')).strip() for k in ['client_id','client_secret','refresh_token']}
  if any(not x or len(x)>10000 for x in values.values()):raise ValueError('Completa los tres valores de la aplicación de Amazon')
  if not values['client_id'].startswith('amzn1.application-oa2-client.'):raise ValueError('El Client ID debe ser el identificador LWA de la aplicación')
  encrypted=protect(json.dumps(values).encode())
  with self.mutex:
   if self.status()['regions'][region]['connected']:raise ValueError('Ya hay una cuenta comprobada en esta región. Para cambiar de cuenta hay que preparar un espacio de datos independiente.')
   path=self.data/('amazon-credentials.dpapi' if region=='EU' else 'amazon-credentials-'+region+'.dpapi');temp=path.with_suffix('.tmp');temp.write_bytes(encrypted);temp.replace(path)
   self.region_tokens.pop(region,None)
   if region=='EU':self.token=None;self.expiry=0
  return dict(ok=True,ready=True,region=region)
 def http_json(self,url,method='GET',body=None,headers=None):
  data=json.dumps(body).encode() if body is not None else None
  try:
   with urlopen(Request(url,data=data,method=method,headers=headers or {}),timeout=40) as r:return json.load(r)
  except HTTPError as e:
   if e.code==429:raise AmazonError('Amazon ha limitado temporalmente las peticiones. Se reintentará sin perder la cola.',429)
   if e.code in (401,403):raise AmazonError('Amazon ha denegado el acceso. Comprueba la autorización y el rol del informe.',e.code)
   raise AmazonError('Amazon ha respondido HTTP '+str(e.code)+'. Revisa el periodo y los permisos.',e.code)
  except (URLError,TimeoutError):raise AmazonError('No se ha podido contactar con Amazon. Comprueba la conexión.',503)
 def access_token(self,region='EU'):
  with self.mutex:
   if region not in REGION_ENDPOINTS:raise ValueError('Región de Amazon no admitida')
   if region=='EU' and self.token and self.expiry>time.time():return self.token
   if region!='EU' and self.region_tokens.get(region,{}).get('expiry',0)>time.time():return self.region_tokens[region]['token']
   creds=self.credentials(region)
   if not creds:raise ValueError('Primero registra y autoriza la aplicación de Amazon')
   body=urlencode(dict(grant_type='refresh_token',**creds)).encode()
   try:
    with urlopen(Request('https://api.amazon.com/auth/o2/token',data=body,headers={'Content-Type':'application/x-www-form-urlencoded'}),timeout=30) as r:result=json.load(r)
   except Exception:raise AmazonError('No se pudo autorizar la aplicación con Amazon. Revisa los tres valores y la autoautorización.',401)
   if not result.get('access_token'):raise AmazonError('Amazon no devolvió un token de acceso',401)
   expiry=time.time()+max(0,int(result.get('expires_in',3600))-120)
   if region=='EU':self.token=result['access_token'];self.expiry=expiry
   else:self.region_tokens[region]=dict(token=result['access_token'],expiry=expiry)
   return result['access_token']
 def api(self,path,method='GET',body=None,token=None,region='EU'):
  if not path.startswith('/') or path.startswith('//'):raise ValueError('Ruta no válida')
  if region not in REGION_ENDPOINTS:raise ValueError('Región de Amazon no admitida')
  return self.http_json(REGION_ENDPOINTS[region]+path,method,body,{'x-amz-access-token':token or self.access_token(region),'Content-Type':'application/json','User-Agent':'AmazonFinanceOpenSource/0.2'})
 def test(self,region='EU'):
  with self.mutex:
   r=self.api('/sellers/v1/marketplaceParticipations',region=region)
   ids={v:k for k,v in MARKET_IDS.items()}
   markets=[dict(id=x['marketplace']['id'],name=x['marketplace']['name'],code=ids[x['marketplace']['id']],region=region) for x in r.get('payload',[]) if x.get('participation',{}).get('isParticipating') and x['marketplace']['id'] in ids and MARKET_REGIONS[ids[x['marketplace']['id']]]==region]
   if not markets:raise ValueError('No se han encontrado mercados activos en esta región con esta autorización')
   previous=self.get('connection') or {};regions=previous.get('regions') or ({'EU':previous} if previous else {})
   regions[region]=dict(checked=now(),markets=markets)
   combined=dict(checked=now(),regions=regions,markets=[m for r in regions.values() for m in r.get('markets',[])])
   self.put('connection',combined);return dict(checked=combined['checked'],markets=markets,region=region)
 def refresh_payment_groups(self,since='2022-01-01',region='EU'):
  from_date=datetime.date.fromisoformat(since);today=datetime.datetime.now(datetime.timezone.utc).date()
  groups={};coverage=[];errors=[]
  previous=self.get('confirmed_payment_groups') or {}
  for group in previous.get('groups',[]):groups[group['FinancialEventGroupId']]=group
  coverage=[x for x in previous.get('coverage',[]) if x.get('region','EU')!=region];errors=[x for x in previous.get('errors',[]) if x.get('region','EU')!=region]
  stop=today
  while stop>=from_date:
   start=max(from_date,stop-datetime.timedelta(days=177));token=None;seen=set()
   try:
    while True:
     q={'NextToken':token} if token else dict(FinancialEventGroupStartedAfter=start.isoformat()+'T00:00:00Z',FinancialEventGroupStartedBefore=min(datetime.datetime.combine(stop+datetime.timedelta(days=1),datetime.time(),datetime.timezone.utc),datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=3)).isoformat(),MaxResultsPerPage=100)
     result=self.api('/finances/v0/financialEventGroups?'+urlencode(q),region=region);payload=result.get('payload') or {}
     for raw in payload.get('FinancialEventGroupList') or []:
      group={k:raw[k] for k in ('FinancialEventGroupId','ProcessingStatus','FundTransferStatus','FundTransferDate','OriginalTotal','FinancialEventGroupStart','FinancialEventGroupEnd') if k in raw}
      group['region']=region
      if group['FinancialEventGroupId'] in groups and groups[group['FinancialEventGroupId']].get('region','EU')!=region:raise ValueError('Identificador de liquidación repetido entre regiones; requiere revisión')
      groups[group['FinancialEventGroupId']]=group
     token=payload.get('NextToken')
     if not token:break
     if token in seen:raise ValueError('Pagina de liquidaciones repetida')
     seen.add(token);time.sleep(2.1)
    coverage.append(dict(start=start.isoformat(),end=stop.isoformat(),region=region))
   except AmazonError as exc:
    errors.append(dict(start=start.isoformat(),end=stop.isoformat(),status=exc.status,error=str(exc),region=region))
   self.put('confirmed_payment_groups',dict(checked=now(),groups=list(groups.values()),coverage=coverage,errors=errors,complete=False,since=since))
   stop=start-datetime.timedelta(days=1);time.sleep(2.1)
  self.put('confirmed_payment_groups',dict(checked=now(),groups=list(groups.values()),coverage=coverage,errors=errors,complete=not errors,since=since))
  self.start_payment_details()
  return dict(ok=True,groups=len(groups),unavailable=len(errors))
 def start_payment_details(self):
  if getattr(self,'payment_detail_thread',None) and self.payment_detail_thread.is_alive():return
  def work():
   try:
    from payment_reconciliation import reconcile_year
    reconcile_year(self)
   except Exception:pass
  self.payment_detail_thread=threading.Thread(target=work,daemon=True,name='amazon-payment-details');self.payment_detail_thread.start()
 def refresh_balances(self,region='EU'):
  with self.mutex:
   balances=[];token=None;seen=set()
   while True:
    path='/finances/2024-06-19/balances'+(('?'+urlencode({'nextToken':token})) if token else '')
    result=self.api(path,region=region);payload=result.get('payload') or {};balances.extend(payload.get('balances') or [])
    token=payload.get('nextToken')
    if not token:break
    if token in seen:raise ValueError('Amazon ha repetido una pagina de saldos; no se guarda un saldo parcial')
    seen.add(token);time.sleep(2.1)
   old=self.get('current_balances') or {}
   balances=[dict(b,region=region) for b in balances]+[b for b in old.get('balances',[]) if b.get('region','EU')!=region]
   snapshot=dict(checked=now(),balances=balances);self.put('current_balances',snapshot);return dict(ok=True,checked=snapshot['checked'])
 def save_job(self,j):
  with self.conn() as c:c.execute('INSERT INTO amazon_reports VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(j['id'],json.dumps(j)))
 def jobs(self):
  with self.conn() as c:return [json.loads(r[0]) for r in c.execute('SELECT payload FROM amazon_reports ORDER BY rowid DESC')]
 def enqueue(self,b):
  kind=next((r for r in REPORTS if r['key']==b.get('kind')),None)
  if not kind:raise ValueError('Tipo de informe no admitido')
  from_date=datetime.date.fromisoformat(b.get('from',''));to_date=datetime.date.fromisoformat(b.get('to',''))
  if to_date<from_date or (to_date-from_date).days>730 or to_date>datetime.datetime.now(datetime.timezone.utc).date():raise ValueError('Selecciona un periodo pasado de hasta dos años')
  if not self.get('connection'):raise ValueError('Primero comprueba los mercados de tu cuenta')
  authorized={m['code'] for m in self.get('connection')['markets']}
  requested=b.get('markets',[])
  if not isinstance(requested,list) or not requested or not set(requested)<=authorized:raise ValueError('Selecciona mercados autorizados')
  if kind['key']=='vat':
   if from_date.day!=1 or to_date!=((from_date.replace(day=28)+datetime.timedelta(days=4)).replace(day=1)-datetime.timedelta(days=1)):raise ValueError('El informe paneuropeo de IVA debe solicitarse por mes natural completo')
   if to_date>=datetime.datetime.now(datetime.timezone.utc).date().replace(day=1):raise ValueError('Selecciona un mes cerrado para IVA')
   eligible=authorized&{'ES','DE','FR','IT','UK','NL','BE','SE','PL','IE'}
   if not eligible:raise ValueError('El informe paneuropeo de IVA requiere mercados europeos autorizados')
   requested=[sorted(eligible)[0]]
  existing={j.get('requestKey') for j in self.jobs()}
  count=0
  for market in sorted(set(requested)):
   start=from_date
   while start<=to_date:
    end=to_date if kind['key']=='vat' or kind['mode']=='existing' else min(start+datetime.timedelta(days=30),to_date)
    key=hashlib.sha256(json.dumps([kind['key'],market,start.isoformat(),end.isoformat()]).encode()).hexdigest()
    if key not in existing:
     job=dict(region=region_for_market(market),id=str(uuid.uuid4()),requestKey=key,kind=kind['key'],name=kind['name'],reportType=kind['type'],market=market,fromDate=start.isoformat(),toDate=end.isoformat(),status='QUEUED',created=now(),attempts=0,nextAt=0,downloaded=False)
     self.save_job(job);existing.add(key);count+=1
    start=end+datetime.timedelta(days=1)
  return dict(queued=count)
 def step(self,ident):
  with self.mutex:
   j=next((r for r in self.jobs() if r['id']==ident),None)
   if not j:raise ValueError('Informe no encontrado')
   if j['status'] in ['READY','CANCELLED','FATAL']:return j
   if j.get('nextAt',0)>time.time():return j
   kind=next(r for r in REPORTS if r['key']==j['kind'])
   region=j.get('region',region_for_market(j.get('market')))
   try:
    if j['status']=='ERROR':j['status']=j.get('resumeStatus','QUEUED')
    if j['status']=='QUEUED':
     if kind['mode']=='existing':
      q={'nextToken':j['listToken']} if j.get('listToken') else dict(reportTypes=kind['type'],marketplaceIds=MARKET_IDS[j['market']],createdSince=j['fromDate']+'T00:00:00Z',createdUntil=j['toDate']+'T23:59:59Z',pageSize=100)
      result=self.api('/reports/2021-06-30/reports?'+urlencode(q),region=region)
      for meta in result.get('reports',[]):
       key='existing:'+meta['reportId']
       if any(x.get('requestKey')==key for x in self.jobs()):continue
       child=dict(j,id=str(uuid.uuid4()),requestKey=key,reportId=meta['reportId'],status=meta.get('processingStatus','IN_QUEUE'),documentId=meta.get('reportDocumentId'),name=kind['name'],nextAt=0)
       self.save_job(child)
      if result.get('nextToken'):j['listToken']=result['nextToken'];j['nextAt']=time.time()+50
      else:j['status']='LISTED'
     else:
      if time.time()-self.last_create<110:j['nextAt']=self.last_create+110;self.save_job(j);return j
      body=dict(reportType=kind['type'],marketplaceIds=[MARKET_IDS[j['market']]],dataStartTime=j['fromDate']+'T00:00:00Z',dataEndTime=j['toDate']+'T23:59:59Z')
      if kind['key']=='sales':body['reportOptions']={'dateGranularity':'DAY','asinGranularity':'CHILD'}
      result=self.api('/reports/2021-06-30/reports','POST',body,region=region);j['reportId']=result['reportId'];j['status']='IN_QUEUE';self.last_create=time.time();j['nextAt']=time.time()+20
    elif j['status'] in ['IN_QUEUE','IN_PROGRESS','DONE']:
     result=self.api('/reports/2021-06-30/reports/'+quote(j['reportId'],safe=''),region=region);j['status']=result['processingStatus'];j['documentId']=result.get('reportDocumentId');j['nextAt']=time.time()+20
     if j['status']=='DONE' and j.get('documentId'):
      if time.time()-self.last_document<65:
       j['nextAt']=self.last_document+65;self.save_job(j);return j
      self.last_document=time.time()
      path='/reports/2021-06-30/documents/'+quote(j['documentId'],safe='');token=None
      if kind.get('restricted'):
       rdt=self.api('/tokens/2021-03-01/restrictedDataToken','POST',{'restrictedResources':[{'method':'GET','path':path}]},region=region)
       token=rdt['restrictedDataToken']
      meta=self.api(path,token=token,region=region);data=safe_download(meta['url'],meta.get('compressionAlgorithm'))
      parsed=read_report(data,kind['format'])
      filename=j['id']+'.'+kind['format'];p=self.data/'reports'/filename;temp=p.with_suffix(p.suffix+'.tmp');temp.write_bytes(data);temp.replace(p)
      j.update(status='READY',downloaded=True,filename=filename,size=len(data),columns=list(parsed[0]) if isinstance(parsed,list) and parsed else [],rows=len(parsed) if isinstance(parsed,list) else len(parsed.get('daily',[])),preview=parsed[:5] if isinstance(parsed,list) else dict(daily=parsed.get('daily',[])[:5],asins=parsed.get('asins',[])[:5]))
    j['error']='';j['updated']=now();self.save_job(j);return j
   except Exception as e:
    status=e.status if isinstance(e,AmazonError) else 400;j['attempts']=j.get('attempts',0)+1
    j['error']=str(e) if isinstance(e,(AmazonError,ValueError)) else 'No se pudo procesar el informe. Revisa el archivo y vuelve a intentarlo.'
    j['resumeStatus']=j.get('status','QUEUED');j['status']='ERROR';j['nextAt']=time.time()+min(3600,60*2**min(j['attempts'],5))
    if status not in (429,500,502,503,504) or j['attempts']>=5:j['blocked']=True
    self.save_job(j);return j
 def retry(self,ident):
  j=next((r for r in self.jobs() if r['id']==ident),None)
  if not j or j['status']!='ERROR':raise ValueError('Solo se reintentan informes con error')
  j.update(status=j.get('resumeStatus','QUEUED'),attempts=0,blocked=False,nextAt=0,error='');self.save_job(j);return dict(ok=True)
 def report_file(self,ident):
  j=next((r for r in self.jobs() if r['id']==ident),None)
  if not j or j['status']!='READY':raise ValueError('Informe no descargado todavía')
  kind=next(r for r in REPORTS if r['key']==j['kind'])
  path=(self.data/'reports'/j['filename']).resolve()
  if not path.is_relative_to((self.data/'reports').resolve()):raise ValueError('Ruta no válida')
  return j,path,kind['format']
 def sync_finances(self,b):
  with self.mutex:
   if b.get('action')=='continue':
    cursor=self.get('sync')
    if not cursor or not cursor.get('nextToken'):raise ValueError('No hay páginas pendientes')
   else:
    start=datetime.datetime.combine(datetime.date.fromisoformat(b.get('from','')),datetime.time(),datetime.timezone.utc)
    end=datetime.datetime.combine(datetime.date.fromisoformat(b.get('to',''))+datetime.timedelta(days=1),datetime.time(),datetime.timezone.utc)
    end=min(end,datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=3))
    if end<=start or end-start>datetime.timedelta(days=179):raise ValueError('Selecciona hasta 179 días pasados')
    cursor=dict(fromDate=start.isoformat(),toDate=end.isoformat(),count=0,region=b.get('region','EU'))
   q=dict(postedAfter=cursor['fromDate'],postedBefore=cursor['toDate'])
   if cursor.get('nextToken'):q['nextToken']=cursor['nextToken']
   result=self.api('/finances/2024-06-19/transactions?'+urlencode(q),region=cursor.get('region','EU'));payload=result.get('payload',{})
   rows=[];ids={v:k for k,v in MARKET_IDS.items()}
   for t in (payload.get('transactions') or []):
    if not t.get('transactionId') or not t.get('totalAmount',{}).get('currencyCode'):raise ValueError('Movimiento financiero incompleto')
    refs={r['relatedIdentifierName']:r['relatedIdentifierValue'] for r in (t.get('relatedIdentifiers') or [])}
    amount=int((__import__('decimal').Decimal(str(t['totalAmount']['currencyAmount']))*100).quantize(__import__('decimal').Decimal('1')))
    rows.append(dict(region=cursor.get('region','EU'),id='amazon:'+('' if cursor.get('region','EU')=='EU' else cursor['region']+':')+t['transactionId'],date=t['postedDate'][:10],market=ids.get(t.get('marketplaceDetails',{}).get('marketplaceId'),'OTHER'),currency=t['totalAmount']['currencyCode'],amount=amount,category='Sin clasificar',description=t.get('description') or t.get('transactionType') or 'Movimiento Amazon',order=refs.get('ORDER_ID',''),reference=refs.get('SETTLEMENT_ID',''),sku='',source='Amazon SP-API',status=t.get('transactionStatus',''),raw=t))
   with self.conn() as c:
    linked=set()
    for d in c.execute('SELECT payload FROM documents'):linked.update(json.loads(d[0]).get('matched',[]))
    for r in rows:
     if r['id'] in linked:
      prev=c.execute('SELECT payload FROM records WHERE id=?',(r['id'],)).fetchone()
      if prev and any(json.loads(prev[0]).get(k)!=r.get(k) for k in ['amount','currency','date','reference']):raise ValueError('Amazon ha modificado un movimiento conciliado. Revisa y desvincula su factura antes de actualizarlo.')
    c.executemany('INSERT INTO records VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',[(r['id'],json.dumps(r)) for r in rows])
   cursor.update(count=cursor['count']+len(rows),nextToken=payload.get('nextToken'),complete=not payload.get('nextToken'),updated=now());self.put('sync',cursor);return cursor
 def start(self):
  def worker():
   while not self.closed.wait(5):
    try:
     if not self.configured_regions():continue
     pending=[j for j in self.jobs() if j['status'] not in ['READY','LISTED','FATAL','CANCELLED'] and not j.get('blocked') and j.get('nextAt',0)<=time.time()]
     if pending:self.step(sorted(pending,key=lambda j:(j.get('priority',10),j.get('nextAt',0),j['created']))[0]['id'])
    except Exception:continue
  thread=threading.Thread(target=worker,daemon=True,name='amazon-reports');thread.start()

