import os,sys,tempfile,threading,json,urllib.request,urllib.error,importlib.util,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from contextlib import nullcontext
with nullcontext(str(ROOT/'tests'/'runtime-data')) as tmp:
 os.environ['AFOS_DATA_DIR']=tmp
 spec=importlib.util.spec_from_file_location('finance_server',ROOT/'local_server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 server=m.ThreadingHTTPServer(('127.0.0.1',0),m.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 origin='http://127.0.0.1:'+str(server.server_port)
 def request(path,body=None,method='GET',ctype='application/json',origin_header=True):
  data=json.dumps(body).encode() if body is not None and ctype=='application/json' else body
  headers={'Content-Type':ctype}
  if origin_header:headers['Origin']=origin
  req=urllib.request.Request(origin+path,data=data,method=method,headers=headers)
  try:
   with urllib.request.urlopen(req) as r:return r.status,json.loads(r.read())
  except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
 row=dict(id='t1',fecha='2026-10-01',mercado='ES',moneda='EUR',tipo='Comisión',importe='-12,10',referencia='F1')
 assert request('/api/data',{'rows':[row]},'POST',origin_header=False)[0]==400
 assert request('/api/data',{'rows':[row]},'POST')[0]==200
 assert request('/api/data',{'rows':[row]},'POST')[0]==200
 assert len(request('/api/data')[1]['rows'])==1
 assert request('/api/data',{'rows':[dict(row,fecha='2026-02-30')]},'POST')[0]==400
 from pypdf import PdfWriter
 out=io.BytesIO();w=PdfWriter();w.add_blank_page(width=200,height=200);w.write(out)
 boundary='AFOS_TEST_BOUNDARY'
 body=('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="test.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode()+out.getvalue()+('\r\n--'+boundary+'\r\nContent-Disposition: form-data; name="text"\r\n\r\nInvoice number: F1\r\n--'+boundary+'--\r\n').encode()
 st,doc=request('/api/documents',body,'POST','multipart/form-data; boundary='+boundary);assert st==200,doc
 assert request('/api/documents',body,'POST','multipart/form-data; boundary='+boundary)[1]['duplicate']
 fields=dict(type='Recibida',market='ES',currency='EUR',number='F1',date='2026-10-01',issuer='Amazon',base='10.00',tax='2.10',total='12.10',reference='F1',validate=True,match=True,matched=['csv:t1'])
 assert request('/api/documents/'+doc['id'],dict(fields,total='14.00'),'PATCH')[0]==400
 assert request('/api/documents/'+doc['id'],fields,'PATCH')[0]==200
 d=request('/api/data')[1];assert d['documents'][0]['status']=='Conciliado'
 assert len(d['rows'])==1 and d['rows'][0]['amount']==-1210
 assert request('/api/documents/'+doc['id'],dict(fields,currency='GBP'),'PATCH')[0]==400
 assert request('/api/amazon')[1]['ready']==False
 with m.conn() as audit:
  events=list(audit.execute('SELECT method,route,status FROM security_events'))
  assert any(r['method']=='POST' and r['route']=='/api/data' and r['status']==400 for r in events)
  assert any(r['method']=='PATCH' and r['route']=='/api/documents/:id' and r['status']==200 for r in events)
  assert all(r['route'] in {'/api/data','/api/amazon','/api/reports','/api/documents/:id','/api/reports/:id'} for r in events)
 server.shutdown();server.server_close()
print('11 comprobaciones integradas superadas: importación, actualización, fechas, PDF duplicados, importes, conciliación, moneda y origen.')


