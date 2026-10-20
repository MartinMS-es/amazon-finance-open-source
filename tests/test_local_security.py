import sys,os,ssl,threading,json,urllib.request,urllib.error,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from local_security import Sessions,ticket,prepare_tls,tls_context,secret
from local_auth import totp
data=ROOT/'tests'/'security-data';data.mkdir(exist_ok=True)
prepare_tls(data)
key=secret(data)
sessions=Sessions(key)
value=ticket(key);session=sessions.exchange(value)
assert sessions.valid('__Host-afos_session='+session)
assert not sessions.valid('__Host-afos_session=invalid')
try:sessions.exchange(value);raise AssertionError('Ticket reutilizado')
except ValueError:pass
try:sessions.exchange(value+'x');raise AssertionError('Firma manipulada')
except ValueError:pass
os.environ['AFOS_SECURE']='1';os.environ['AFOS_DATA_DIR']=str(data)
spec=importlib.util.spec_from_file_location('secure_test_server',ROOT/'local_server.py');servermod=importlib.util.module_from_spec(spec);spec.loader.exec_module(servermod)
server=servermod.ThreadingHTTPServer(('127.0.0.1',0),servermod.Handler)
server.socket=tls_context(data).wrap_socket(server.socket,server_side=True)
threading.Thread(target=server.serve_forever,daemon=True).start()
origin='https://127.0.0.1:'+str(server.server_port)
context=ssl.create_default_context(cafile=str(data/'tls'/'localhost.pem'))
def request(path,body=None,cookie=None,origin_header=None):
    headers={}
    if body is not None:headers.update({'Content-Type':'application/json','Origin':origin if origin_header is None else origin_header})
    if cookie:headers['Cookie']=cookie
    req=urllib.request.Request(origin+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    try:
        with urllib.request.urlopen(req,context=context) as r:return r.status,r.headers,r.read()
    except urllib.error.HTTPError as r:return r.code,r.headers,r.read()
try:
    assert request('/api/health')[0]==200
    assert request('/api/data')[0]==401
    import time
    signed=ticket(key)
    assert request('/api/auth/begin',{'ticket':signed},origin_header='https://evil.example')[0]==400
    assert request('/api/session',{'ticket':signed})[0]==400
    # A new test directory may have an account from a previous run. Never change production.
    if servermod.AUTH.path.exists():servermod.AUTH.path.unlink()
    _,_,enrollment_raw=request('/api/auth/begin',{'ticket':signed})
    enrollment=json.loads(enrollment_raw)
    assert enrollment['qr'].startswith('data:image/svg+xml;base64,')
    body={'enrollment':enrollment['enrollment'],'password':'Synthetic-Only!Test123','code':totp(enrollment['secret'],int(time.time()//30))}
    status,headers,_=request('/api/auth/setup',body)
    assert status==200
    cookie=headers['Set-Cookie']
    assert all(flag in cookie for flag in ['HttpOnly','Secure','SameSite=Strict'])
    assert request('/api/data',cookie=cookie.split(';')[0])[0]==200
    assert request('/api/exports/accountant.zip?from=2026-01-01&to=2026-09-30&markets=ES,FR')[0]==401
    status,download_headers,content=request('/api/exports/accountant.zip?from=2026-01-01&to=2026-09-30&markets=ES,FR',cookie=cookie.split(';')[0])
    assert status==200 and download_headers['Content-Type']=='application/zip'
    import io,zipfile
    with zipfile.ZipFile(io.BytesIO(content)) as exported:
        manifest=json.loads(exported.read('manifest.json'))
        assert manifest['fromDate']=='2026-01-01' and manifest['toDate']=='2026-09-30' and manifest['markets']==['ES','FR']
        assert '01_movimientos_financieros.csv' in exported.namelist()
    print('Descarga contable HTTPS autenticada y filtros de periodo/mercados: OK')
    assert request('/api/auth/begin',{'ticket':signed})[0]==400
    assert request('/api/session',{'ticket':signed},cookie=cookie.split(';')[0])[0]==404
    assert request('/api/data',cookie='__Host-afos_session=invalid')[0]==401
    assert not list((data/'tls').glob('key-*.tmp'))
    assert request('/api/auth/logout',{},cookie=cookie.split(';')[0])[0]==200
    assert request('/api/data',cookie=cookie.split(';')[0])[0]==401
    print('HTTPS validado, alta MFA desde ticket local, sesión obligatoria, sin bypass por ticket, logout y cookies protegidas: OK')
finally:
    server.shutdown();server.server_close()
