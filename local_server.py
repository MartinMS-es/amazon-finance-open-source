"""Servidor local de AMAZON FINANCE OPEN SOURCE. Solo escucha 127.0.0.1. Sin dependencias."""
import os,json,sqlite3,hashlib,uuid,re,datetime,decimal,threading
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from email.parser import BytesParser
from email.policy import default
from urllib.parse import urlparse,parse_qs
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('AFOS_DATA_DIR',str(ROOT/'local-data'))).resolve()
DATA.mkdir(parents=True,exist_ok=True)
(DATA/'documents').mkdir(exist_ok=True)
LOCK=threading.Lock()
def conn():
 c=sqlite3.connect(DATA/'finance.sqlite',timeout=30)
 c.row_factory=sqlite3.Row
 return c
with conn() as c:
 c.execute('CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,hash TEXT UNIQUE,name TEXT,payload TEXT,created TEXT)')
 c.execute('CREATE TABLE IF NOT EXISTS security_events(id TEXT PRIMARY KEY,created TEXT NOT NULL,method TEXT NOT NULL,route TEXT NOT NULL,status INTEGER NOT NULL)')
from amazon_markets import MARKET_IDS, CURRENCIES
MARKETS=set(MARKET_IDS)|{'OTHER'}
CATEGORIES={'Venta','Devolución','Comisión','Logística FBA','Almacenamiento','Publicidad','Ajuste','Liquidación','Sin clasificar'}

def cents(v):
 s=re.sub(r'[€£$\s]','',str(v))
 if ',' in s and '.' in s:
  s=s.replace('.','').replace(',','.') if s.rfind(',')>s.rfind('.') else s.replace(',','')
 elif ',' in s:s=s.replace(',','.')
 if not re.fullmatch(r'-?\d+(\.\d{1,2})?',s):raise ValueError('Importe no válido')
 n=int(decimal.Decimal(s)*100)
 if abs(n)>10**12:raise ValueError('Importe fuera de rango')
 return n
def normalize(r):
 for key in ['id','fecha','mercado','moneda','tipo','importe']:
  if not r.get(key):raise ValueError('Falta '+key)
 if datetime.date.fromisoformat(r['fecha']).isoformat()!=r['fecha']:raise ValueError('Fecha no válida')
 m=r['mercado'].upper();cur=r['moneda'].upper()
 if m not in MARKETS or cur not in CURRENCIES or r['tipo'] not in CATEGORIES:raise ValueError('Mercado, moneda o tipo no válidos')
 return dict(id='csv:'+r['id'],date=r['fecha'],market=m,currency=cur,category=r['tipo'],amount=cents(r['importe']),order=r.get('pedido',''),sku=r.get('sku',''),reference=r.get('referencia',''),description=r.get('concepto',''),source='CSV',status='Importado')
from amazon_local import Engine,REPORTS
from local_security import Sessions,secret,tls_context,LOGIN_HTML
from local_auth import LocalAuth,AUTH_HTML
SECURE=os.environ.get('AFOS_SECURE')=='1' or (DATA/'secure-enabled').exists()
SESSIONS=Sessions(secret(DATA)) if SECURE else None
AUTH=LocalAuth(DATA,SESSIONS) if SECURE else None
AMAZON=Engine(conn,DATA)
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send_response(self,code,message=None):
  # Solo metadatos de rutas conocidas: nunca cuerpos, URLs completas o credenciales.
  path=urlparse(self.path).path
  route=path if path in {'/api/data','/api/amazon','/api/reports','/api/session','/api/auth/status','/api/auth/begin','/api/auth/setup','/api/auth/login','/api/auth/change','/api/auth/logout'} else '/api/documents/:id' if path.startswith('/api/documents/') else '/api/reports/:id' if path.startswith('/api/reports/') else None
  if route:
   database=None
   try:
    database=conn()
    with database:
     database.execute('INSERT INTO security_events VALUES(?,?,?,?,?)',(str(uuid.uuid4()),datetime.datetime.now(datetime.timezone.utc).isoformat(),self.command,route,int(code)))
   except Exception:
    print('Aviso: no se pudo guardar un evento de actividad local.',flush=True)
   finally:
    if database:database.close()
  super().send_response(code,message)
 def send(self,data,status=200,ctype='application/json'):
  body=json.dumps(data,ensure_ascii=False).encode() if ctype=='application/json' else data
  self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def allowed(self,write=False):
  host=self.headers.get('Host','')
  if host not in {'127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)}:raise ValueError('Host no autorizado')
  scheme='https' if SECURE else 'http'
  origins={scheme+'://127.0.0.1:'+str(self.server.server_port),scheme+'://localhost:'+str(self.server.server_port)}
  if (write or self.headers.get('Origin')) and self.headers.get('Origin') not in origins:raise ValueError('Origen no autorizado')
  path=urlparse(self.path).path
  public={'/api/health','/api/auth/status','/api/auth/begin','/api/auth/setup','/api/auth/login','/api/auth/change'}
  if SECURE and path.startswith('/api/') and path not in public and not SESSIONS.valid(self.headers.get('Cookie')):raise PermissionError('Sesión requerida: inicia sesión con contraseña y autenticador')
 def do_GET(self):
  try:
   self.allowed();p=urlparse(self.path).path
   if p=='/api/health':return self.send(dict(ok=True,local=True,secure=SECURE,mfa=AUTH.status()['mfa'] if AUTH else False))
   if p=='/api/auth/status' and SECURE:return self.send(dict(AUTH.status(),authenticated=SESSIONS.valid(self.headers.get('Cookie'))))
   if p=='/access' and SECURE:return self.send(AUTH_HTML,ctype='text/html; charset=utf-8')
   if p=='/' and SECURE and not SESSIONS.valid(self.headers.get('Cookie')):return self.send(AUTH_HTML,ctype='text/html; charset=utf-8')
   if p=='/api/data':
    with conn() as c:
     rows=[json.loads(r[0]) for r in c.execute('SELECT payload FROM records')]
     docs=[dict(json.loads(r['payload']),id=r['id'],name=r['name'],created=r['created']) for r in c.execute('SELECT * FROM documents ORDER BY created DESC')]
    return self.send(dict(rows=sorted(rows,key=lambda r:r['date'],reverse=True)[:20000],documents=docs[:2000],truncated=len(rows)>20000 or len(docs)>2000,sync=AMAZON.get('sync'),connection=AMAZON.get('connection')))
   if p=='/api/analysis':
    from analysis_local import analyze
    filters={k:v[0] for k,v in parse_qs(urlparse(self.path).query).items() if k in ('market','currency','from','to','status')}
    with conn() as c:result=analyze((json.loads(r[0]) for r in c.execute('SELECT payload FROM records')),filters)
    return self.send(result)
   if p=='/api/exports/accountant.zip':
    from accountant_export import build
    q={k:v[0] for k,v in parse_qs(urlparse(self.path).query).items()}
    stream,manifest=build(conn,DATA,q.get('from',''),q.get('to',''),q.get('markets','').split(','),q.get('unassigned','1')=='1')
    try:
     stream.seek(0,2);size=stream.tell();stream.seek(0)
     self.send_response(200);self.send_header('Content-Type','application/zip');self.send_header('Content-Disposition','attachment; filename=afos-paquete-contable.zip');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-AFOS-Warnings',str(len(set(manifest['warnings']))));self.send_header('Content-Length',str(size));self.end_headers()
     while chunk:=stream.read(1024*1024):self.wfile.write(chunk)
    finally:stream.close()
    return
   if p=='/api/exports/amazon.zip':
    from raw_export import archive
    q={k:v[0] for k,v in parse_qs(urlparse(self.path).query).items()}
    filters={k:v for k,v in q.items() if k in ('market','currency','from','to','status')}
    stream,manifest=archive(conn,DATA,AMAZON.jobs(),filters,q.get('files')=='1')
    try:
     stream.seek(0,2);size=stream.tell();stream.seek(0)
     self.send_response(200);self.send_header('Content-Type','application/zip');self.send_header('Content-Disposition','attachment; filename=afos-amazon-originales.zip');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(size));self.end_headers()
     while chunk:=stream.read(1024*1024):self.wfile.write(chunk)
    finally:stream.close()
    return
   if p=='/api/product-sales':
    from product_sales import product_sales
    q={k:v[0] for k,v in parse_qs(urlparse(self.path).query).items()}
    return self.send(product_sales(DATA,AMAZON.jobs(),q.get('from',''),q.get('to',''),q.get('market','ALL')))
   if p=='/api/treasury':
    from treasury_local import cash_summary
    q={k:v[0] for k,v in parse_qs(urlparse(self.path).query).items()}
    with conn() as c:details={r[0].split(':',1)[1]:json.loads(r[1]) for r in c.execute("SELECT id,payload FROM integration_state WHERE id LIKE 'payment_detail:%'")}
    with conn() as c:result=cash_summary((json.loads(r[0]) for r in c.execute('SELECT payload FROM records')),AMAZON.get('current_balances'),q.get('market','ALL'),q.get('currency','EUR'),q.get('from',''),q.get('to',''),AMAZON.get('confirmed_payment_groups'),details)
    return self.send(result)
   if p=='/api/amazon':return self.send(AMAZON.status())
   if p=='/api/reports':return self.send(dict(catalog=REPORTS,jobs=AMAZON.jobs()))
   if p.startswith('/api/reports/') and p.endswith('/download'):
    ident=p.split('/')[3];job,path,fmt=AMAZON.report_file(ident)
    content=path.read_bytes()
    self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Disposition','attachment; filename="'+job['kind']+'-'+job['market']+'-'+job['fromDate']+'.'+fmt+'"');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
   if p.startswith('/api/documents/'):
    ident=p.rsplit('/',1)[-1]
    if not re.fullmatch(r'[a-f0-9-]{36}',ident):raise ValueError('ID no válido')
    file=DATA/'documents'/(ident+'.pdf')
    return self.send(file.read_bytes(),ctype='application/pdf')
   file=(ROOT/'public'/p.lstrip('/')) if p.startswith('/pdfjs/') else (ROOT/'local-web'/('index.html' if p=='/' else p.lstrip('/')))
   if not file.resolve().is_relative_to((ROOT/'public').resolve()) and not file.resolve().is_relative_to((ROOT/'local-web').resolve()):raise ValueError('Ruta no válida')
   if not file.is_file():return self.send(dict(error='No encontrado'),404)
   ctype={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript','.mjs':'text/javascript'}.get(file.suffix,'application/octet-stream')
   self.send(file.read_bytes(),ctype=ctype)
  except PermissionError as e:self.send(dict(error=str(e)),401)
  except Exception as e:self.send(dict(error=str(e)),400)
 def do_POST(self):
  try:
   self.allowed(True)
   length=int(self.headers.get('Content-Length',0))
   if length<1 or length>17*1024*1024:raise ValueError('Tamaño no válido')
   raw=self.rfile.read(length);p=urlparse(self.path).path
   if p.startswith('/api/auth/') and SECURE:
    if length>8192:raise ValueError('Petición de acceso demasiado grande')
    body=json.loads(raw)
    if not isinstance(body,dict):raise ValueError('Formato de acceso no válido')
    if p=='/api/auth/begin':return self.send(AUTH.begin(str(body.get('ticket',''))))
    if p=='/api/auth/logout':
     SESSIONS.revoke(self.headers.get('Cookie'))
     self.send_response(200);self.send_header('Set-Cookie','__Host-afos_session=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0');self.send_header('Cache-Control','no-store');self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'{}');return
    if p=='/api/auth/setup':session=AUTH.setup(body)
    elif p=='/api/auth/login':session=AUTH.login(body)
    elif p=='/api/auth/change':session=AUTH.change(body)
    else:raise ValueError('Acción de acceso no admitida')
    self.send_response(200);self.send_header('Set-Cookie','__Host-afos_session='+session+'; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=1800');self.send_header('Cache-Control','no-store');self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'{}');return
   if p=='/api/data':
    b=json.loads(raw);items=b.get('rows',[])
    if not isinstance(items,list) or not 1<=len(items)<=5000:raise ValueError('Entre 1 y 5000 filas por importación')
    rows=[normalize(r) for r in items]
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('IDs duplicados')
    with LOCK,conn() as c:
     linked=set()
     for docrow in c.execute('SELECT payload FROM documents'):
      linked.update(json.loads(docrow[0]).get('matched',[]))
     for item in rows:
      if item['id'] in linked:
       existing=c.execute('SELECT payload FROM records WHERE id=?',(item['id'],)).fetchone()
       before=json.loads(existing[0]) if existing else {}
       if any(before.get(k)!=item.get(k) for k in ['amount','currency','category','date','reference']):raise ValueError('Movimiento conciliado: guarda el documento como borrador para desvincularlo antes de modificarlo')
     c.executemany('INSERT INTO records VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',[(r['id'],json.dumps(r)) for r in rows])
    return self.send(dict(count=len(rows)))
   if p=='/api/documents':
    msg=BytesParser(policy=default).parsebytes(('Content-Type: '+self.headers.get('Content-Type','')+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw)
    pdf=None;text='';name=''
    for part in msg.iter_parts():
     if part.get_param('name',header='content-disposition')=='file':pdf=part.get_payload(decode=True);name=part.get_filename() or 'factura.pdf'
     elif part.get_param('name',header='content-disposition')=='text':text=part.get_content()
    if not pdf or not pdf.startswith(b'%PDF-') or len(pdf)>15*1024*1024:raise ValueError('PDF no válido o superior a 15 MB')
    digest=hashlib.sha256(pdf).hexdigest()
    with LOCK,conn() as c:
     old=c.execute('SELECT id FROM documents WHERE hash=?',(digest,)).fetchone()
     if old:return self.send(dict(duplicate=True,id=old[0]))
     ident=str(uuid.uuid4());path=DATA/'documents'/(ident+'.pdf');path.write_bytes(pdf)
     payload=dict(text=text[:150000],type='Recibida',number='',date='',market='OTHER',currency='EUR',issuer='',base=None,tax=None,total=None,reference='',status='Pendiente',matched=[],note='')
     try:c.execute('INSERT INTO documents VALUES(?,?,?,?,?)',(ident,digest,name[:200],json.dumps(payload),datetime.datetime.now(datetime.timezone.utc).isoformat()))
     except Exception:path.unlink(missing_ok=True);raise
    return self.send(dict(id=ident))
   if p=='/api/amazon':
    b=json.loads(raw);action=b.get('action')
    if action=='configure':
     if length>40000:raise ValueError('Configuración demasiado grande')
     return self.send(AMAZON.configure(b))
    if action=='test':return self.send(AMAZON.test(b.get('region','EU')))
    if action=='payment_groups':return self.send(dict(regions={r:AMAZON.refresh_payment_groups(region=r) for r in AMAZON.configured_regions()}))
    if action=='balances':return self.send(dict(regions={r:AMAZON.refresh_balances(region=r) for r in AMAZON.configured_regions()}))
    if action in ('sync','continue'):
     if (AMAZON.get('historical_recovery') or {}).get('status')=='RUNNING':raise ValueError('La recuperacion historica esta en curso. Espera antes de iniciar otra consulta financiera.')
     return self.send(AMAZON.sync_finances(b))
    raise ValueError('Acción no admitida')
   if p=='/api/reports':
    b=json.loads(raw)
    if b.get('action')=='enqueue':return self.send(AMAZON.enqueue(b))
    if b.get('action')=='retry':return self.send(AMAZON.retry(b.get('id')))
    if b.get('action')=='process':return self.send(AMAZON.step(b.get('id')))
    raise ValueError('Acción no admitida')
   self.send(dict(error='No encontrado'),404)
  except Exception as e:self.send(dict(error=str(e)),400)
 def do_PATCH(self):
  try:
   self.allowed(True);length=int(self.headers.get('Content-Length',0))
   if length<1 or length>500000:raise ValueError('Petición no válida')
   ident=urlparse(self.path).path.rsplit('/',1)[-1];b=json.loads(self.rfile.read(length))
   if not urlparse(self.path).path.startswith('/api/documents/'):raise ValueError('Ruta no válida')
   with LOCK,conn() as c:
    r=c.execute('SELECT payload FROM documents WHERE id=?',(ident,)).fetchone()
    if not r:raise ValueError('Documento no encontrado')
    d=json.loads(r[0])
    if b.get('type') not in {'Emitida','Recibida','Abono'} or b.get('market') not in MARKETS or b.get('currency') not in CURRENCIES:raise ValueError('Tipo, mercado o moneda no válidos')
    for key in ['type','market','currency','number','date','issuer','reference','note']:d[key]=str(b.get(key,''))[:2000]
    if d['date'] and datetime.date.fromisoformat(d['date']).isoformat()!=d['date']:raise ValueError('Fecha no válida')
    for key in ['base','tax','total']:d[key]=None if b.get(key,'')=='' else cents(b[key])
    d['matched']=[];d['status']='Pendiente'
    if b.get('validate'):
     if not all(d[k] for k in ['number','date','issuer']) or any(d[k] is None for k in ['base','tax','total']):raise ValueError('Completa emisor, número, fecha e importes')
     if abs(d['base']+d['tax']-d['total'])>1:raise ValueError('Base + IVA no coincide con total')
     d['status']='Validado'
    if b.get('match'):
     ids=b.get('matched',[])
     if not b.get('validate') or not isinstance(ids,list) or not 1<=len(ids)<=200:raise ValueError('Selecciona movimientos')
     if len(set(ids))!=len(ids):raise ValueError('Movimiento repetido')
     rows=[]
     for rid in ids:
      item=c.execute('SELECT payload FROM records WHERE id=?',(rid,)).fetchone()
      if not item:raise ValueError('Movimiento inexistente')
      rows.append(json.loads(item[0]))
     if any(x['currency']!=d['currency'] for x in rows):raise ValueError('Monedas distintas')
     for other in c.execute('SELECT payload FROM documents WHERE id<>?',(ident,)):
      if set(json.loads(other[0]).get('matched',[]))&set(ids):raise ValueError('Movimiento vinculado a otro documento')
     target=abs(d['total']) if d['type']=='Emitida' else -abs(d['total'])
     if abs(sum(x['amount'] for x in rows)-target)>1:raise ValueError('Los movimientos no coinciden con el total firmado de la factura')
     d['status']='Conciliado';d['matched']=ids
    c.execute('UPDATE documents SET payload=? WHERE id=?',(json.dumps(d),ident))
   self.send(dict(ok=True))
  except Exception as e:self.send(dict(error=str(e)),400)
if __name__=='__main__':
 AMAZON.start()
 server=ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('AFOS_PORT','18766' if SECURE else '18765'))),Handler)
 if SECURE:server.socket=tls_context(DATA).wrap_socket(server.socket,server_side=True)
 print('AMAZON FINANCE OPEN SOURCE local: '+('https' if SECURE else 'http')+'://127.0.0.1:'+str(server.server_port),flush=True)
 server.serve_forever()

