import sys,tempfile,sqlite3,time,unittest,json,os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from amazon_markets import MARKET_IDS,MARKET_REGIONS,REGION_ENDPOINTS,CURRENCIES
from amazon_local import Engine
class GlobalMarketsTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
  self.engine=Engine(lambda:sqlite3.connect(self.path/'db'),self.path)
 def tearDown(self):
  import gc;gc.collect();self.temp.cleanup()
 def test_official_catalogue(self):
  self.assertEqual(len(MARKET_IDS),23);self.assertEqual(len(set(MARKET_IDS.values())),23)
  self.assertEqual(MARKET_REGIONS['BR'],'NA');self.assertEqual(MARKET_REGIONS['IN'],'EU');self.assertEqual(MARKET_REGIONS['JP'],'FE')
  self.assertTrue({'JPY','AUD','MXN','AED','INR'}<=CURRENCIES)
 def test_endpoints_and_token_isolation(self):
  engine=self.engine;engine.token='synthetic-eu';engine.expiry=time.time()+60;engine.region_tokens={'NA':{'token':'synthetic-na','expiry':time.time()+60},'FE':{'token':'synthetic-fe','expiry':time.time()+60}}
  calls=[];engine.http_json=lambda url,method,body,headers:calls.append((url,headers['x-amz-access-token'])) or {}
  for region in ('EU','NA','FE'):engine.api('/test',region=region)
  self.assertEqual([x[0] for x in calls],[REGION_ENDPOINTS[r]+'/test' for r in ('EU','NA','FE')]);self.assertEqual(len(set(x[1] for x in calls)),3)
  with self.assertRaises(ValueError):engine.api('/test',region='evil')
 def test_legacy_credentials_and_connections_preserved(self):
  engine=self.engine
  with patch.dict(os.environ,{},clear=True):
   for region in ('EU','NA','FE'):
    engine.configure(dict(region=region,client_id='amzn1.application-oa2-client.synthetic',client_secret='synthetic-secret',refresh_token='synthetic-'+region))
   self.assertTrue((self.path/'amazon-credentials.dpapi').exists());self.assertEqual(engine.credentials('NA')['refresh_token'],'synthetic-NA');self.assertEqual(engine.credentials('EU')['refresh_token'],'synthetic-EU')
   def api(path,method='GET',body=None,token=None,region='EU'):
    code={'EU':'ES','NA':'US','FE':'JP'}[region]
    return {'payload':[{'marketplace':{'id':MARKET_IDS[code],'name':code},'participation':{'isParticipating':True}}]}
   engine.api=api
   for region in ('EU','NA','FE'):engine.test(region)
   self.assertEqual({m['code'] for m in engine.get('connection')['markets']},{'ES','US','JP'})
   self.assertTrue(all(r['connected'] for r in engine.status()['regions'].values()))
   with self.assertRaises(ValueError):engine.configure(dict(region='EU',client_id='amzn1.application-oa2-client.synthetic',client_secret='synthetic',refresh_token='synthetic'))
 def test_report_region_persists(self):
  engine=self.engine;engine.put('connection',{'markets':[{'code':'US'}]})
  engine.enqueue(dict(kind='sales',markets=['US'],**{'from':'2026-09-01','to':'2026-09-30'}))
  calls=[]
  def api(path,method='GET',body=None,token=None,region='EU'):calls.append(region);return {'reportId':'synthetic-report'}
  engine.api=api;job=engine.jobs()[0];engine.step(job['id']);self.assertEqual(calls,['NA']);self.assertEqual(job['region'],'NA')
if __name__=='__main__':unittest.main()
