import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from server import Handler
from studio import sogni
from studio.store import Store


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.server.db=Store(Path(cls.temp.name)/'db.sqlite3')
        cls.server.access_token='super-test-token'
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=2);cls.temp.cleanup()
    def http(self,path,body=None,method='GET',token='super-test-token'):
        headers={'X-Studio-Token':token}
        if body is not None:headers['Content-Type']='application/json'
        req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=5) as r:return r.status,r.read(),r.headers
        except urllib.error.HTTPError as e:return e.code,e.read(),e.headers
    def test_local_api_flow(self):
        status,body,_=self.http('/api/projects',token='wrong')
        self.assertEqual(status,401)
        status,body,_=self.http('/api/projects',{'title':'Integracyjny','idea':'Mój pomysł','duration':30},'POST')
        self.assertEqual(status,201)
        pid=json.loads(body)['project']['id']
        status,body,_=self.http(f'/api/projects/{pid}/develop',{'mode':'demo'},'POST')
        self.assertEqual(status,200)
        p=json.loads(body)['project'];self.assertEqual(len(p['concepts']),10)
        status,body,_=self.http(f'/api/projects/{pid}/select',{'concept_id':'C02'},'POST')
        self.assertEqual(status,200)
        p=json.loads(body)['project'];self.assertEqual(p['selected_concept_id'],'C02')
        status,body,_=self.http(f'/api/projects/{pid}/script',{'script':'Zmieniony scenariusz'},'PUT')
        self.assertEqual(status,200)
        status,body,headers=self.http(f'/api/projects/{pid}/export')
        self.assertEqual(status,200)
        self.assertEqual(body[:2],b'PK')
    def test_paid_gates(self):
        status,raw,_=self.http('/api/projects',{'title':'Gates'},'POST')
        pid=json.loads(raw)['project']['id']
        status,body,_=self.http(f'/api/projects/{pid}/develop',{'mode':'ai','allow_paid':False},'POST')
        self.assertEqual(status,403)
        self.http(f'/api/projects/{pid}/develop',{'mode':'demo'},'POST')
        status,body,_=self.http(f'/api/projects/{pid}/shots/S01/render',{'approve':True,'quote_id':'fake','max_capacity_units':25},'POST')
        self.assertEqual(status,409)
    def test_quote_render_mock(self):
        _,raw,_=self.http('/api/projects',{'title':'Mock'},'POST')
        pid=json.loads(raw)['project']['id']
        self.http(f'/api/projects/{pid}/develop',{'mode':'demo'},'POST')
        with patch.object(sogni,'estimate',return_value={'estimated_capacity':{'total':3.7},'requires_confirmation':True}):
            status,data,_=self.http(f'/api/projects/{pid}/shots/S01/quote',{},'POST')
        self.assertEqual(status,200)
        q=json.loads(data)['quote']
        with patch.object(sogni,'start_render',return_value={'workflowId':'wf_fake123','status':'queued'}) as fun:
            status,data,_=self.http(f'/api/projects/{pid}/shots/S01/render',{'approve':True,'quote_id':q['id'],'max_capacity_units':5},'POST')
        self.assertEqual(status,200);self.assertEqual(fun.call_count,1)
        job=json.loads(data)['job'];self.assertEqual(job['status'],'queued')
        with patch.object(sogni,'get_workflow',return_value={'status':'completed','steps':[{'artifacts':[{'url':'https://example.org/clip.mp4'}]}]}):
            status,data,_=self.http(f'/api/projects/{pid}/jobs/{job["id"]}')
            self.assertEqual(status,200);self.assertEqual(json.loads(data)['job']['media_url'],'https://example.org/clip.mp4')
