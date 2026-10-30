"""HTTP behavior: V6 360 plan and checkpoint review never spend tokens."""
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
from studio.store import Store

_ISO=None
def setUpModule():
    """Izolacja: testy nie mogą czytać ani zapisywać prawdziwych decyzji recenzji z data/references_v6."""
    global _ISO
    from studio import reference_v6 as _r
    _ISO=tempfile.TemporaryDirectory()
    _ISO.patches=[patch.object(_r,'DATA',Path(_ISO.name)),patch.object(_r,'REVIEWS',Path(_ISO.name)/'review_decisions.json')]
    for _p in _ISO.patches:_p.start()

def tearDownModule():
    for _p in _ISO.patches:_p.stop()
    _ISO.cleanup()

class V6HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.server.db=Store(Path(cls.tmp.name)/'app.sqlite3');cls.server.access_token='v6-test-secret'
        cls.worker=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.worker.start()
        cls.root='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.worker.join();cls.tmp.cleanup()
    def ask(self,path,method='GET',data=None):
        headers={'X-Studio-Token':'v6-test-secret'}
        if data is not None:headers['Content-Type']='application/json'
        req=urllib.request.Request(self.root+path,method=method,headers=headers,
            data=json.dumps(data).encode() if data is not None else None)
        try:
            with urllib.request.urlopen(req,timeout=10) as r:return r.status,r.read(),r.headers
        except urllib.error.HTTPError as e:return e.code,e.read(),e.headers
    def test_v6_endpoints_presets_project_plan_safe(self):
        status,raw,_=self.ask('/api/v6/camera360');self.assertEqual(status,200)
        self.assertEqual(len(json.loads(raw)['presets']),6)
        status,raw,_=self.ask('/api/v6/references');self.assertEqual(status,200)
        self.assertEqual(json.loads(raw)['count'],78)
        status,raw,_=self.ask('/api/projects',method='POST',data={'title':'Test 360'})
        pid=json.loads(raw)['project']['id']
        self.ask('/api/projects/'+pid+'/develop',method='POST',data={'mode':'demo'})
        status,raw,_=self.ask('/api/projects/'+pid+'/shots/S01/360',method='POST',data={'preset_id':'dialogue_reveal'})
        self.assertEqual(status,200)
        info=json.loads(raw)['plan'];self.assertEqual(len(info['points']),2)
        status,raw,_=self.ask('/api/projects/'+pid+'/shots/S01/360/recipe',method='POST',data={'source_image':'assets/demo.png'})
        self.assertEqual(status,200)
        self.assertTrue(json.loads(raw)['recipe']['dry_run'])
        status,raw,_=self.ask('/api/projects/'+pid+'/shots/S01/360',method='POST',data={'preset_id':'not_exist'})
        self.assertEqual(status,400)
        status,raw,_=self.ask('/api/v6/camera360/generate',method='POST',data={'approve':False,'reference_id':'x','azimuth':'front'})
        self.assertEqual(status,409)
    def test_reference_png_and_unapproved_block(self):
        status,raw,_=self.ask('/api/v6/references')
        ref=json.loads(raw)['images'][0]
        status,img,headers=self.ask('/api/v6/references/'+ref['id']+'/image')
        self.assertEqual(status,200);self.assertEqual(headers.get('Content-Type'),'image/png')
        self.assertTrue(img.startswith(b'\x89PNG'))
        status,raw,_=self.ask('/api/v6/references/'+ref['id']+'/sync','POST',{'approve':False})
        self.assertEqual(status,403)

if __name__=='__main__':unittest.main()
