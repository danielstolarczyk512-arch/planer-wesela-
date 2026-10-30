"""Regression tests for V8.2: zero network, local assets, explicit quality consent."""
import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import server
from studio import visual_lock_v82 as v
from studio.store import Store

SRC=Path(__file__).resolve().parent.parent

def fixtures(root):
    for key,rel in v.SOURCE.items():
        dst=root/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(SRC/rel,dst)

def project():
    return {'id':'abcd1234-1234-4123-8123-123456789012','shots':[{'id':'S01','mode':'t2v',
        'characters':['ONA','ON'],'video_model':'minimax-h3-fasth3-t2v-turbo','edit_version':'v1'}]}

class VisualLockUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);fixtures(self.root)
    def approve_all(self):
        for name,row in v.summary(self.root)['slots'].items():
            v.approve(self.root,name,row['sha256'],True,'Reviewed in test')
    def test_candidates_not_implicitly_approved(self):
        state=v.summary(self.root)
        self.assertEqual(state['version'],'8.2.0')
        self.assertTrue(state['slots']['style']['approved'])
        self.assertFalse(state['slots']['woman']['approved'])
        self.assertFalse(state['ready'])
    def test_master_requires_viewed_and_exact_digest(self):
        row=v.summary(self.root)['slots']['woman']
        for observed,viewed in [('invalid',True),(row['sha256'],False)]:
            with self.assertRaises(ValueError):v.approve(self.root,'woman',observed,viewed,'x')
        self.assertTrue(v.approve(self.root,'woman',row['sha256'],True,'yes')['ready'])
    def test_lock_needs_review_and_records_digest(self):
        p=project()
        with self.assertRaises(ValueError):v.pin_project(p,self.root)
        self.approve_all()
        v.pin_project(p,self.root)
        self.assertTrue(p['v82_visual_lock'])
        self.assertEqual(p['v82_visual_snapshot']['woman']['sha256'],v.summary(self.root)['slots']['woman']['sha256'])
        self.assertNotEqual(p['shots'][0]['edit_version'],'v1')
    def test_master_changed_blocks_old_projects(self):
        self.approve_all();p=project();v.pin_project(p,self.root)
        file=self.root/v.SOURCE['style']
        with file.open('ab') as f:f.write(b'changed')
        self.assertTrue(v.check_masters(p,self.root))
    def test_keyframe_requires_manual_review_and_sha_and_edit_binding(self):
        self.approve_all();p=project();v.pin_project(p,self.root)
        shot=p['shots'][0]
        dest=self.root/'data'/'keyframes'/p['id'];dest.mkdir(parents=True)
        shutil.copy2(self.root/v.SOURCE['couple'],dest/'S01.png');shot['firstframe_local']='S01.png'
        with self.assertRaises(ValueError):v.approve_frame(p,shot,self.root,True,False,True)
        v.approve_frame(p,shot,self.root,True,True,True)
        self.assertEqual(v.check_frame(p,shot,self.root),[])
        self.assertTrue(v.check_video(p,shot,self.root))
        shot['edit_version']='edited'
        self.assertTrue(v.check_frame(p,shot,self.root))
    def test_upload_candidate_demotes_approval(self):
        self.approve_all();img=(self.root/v.SOURCE['man']).read_bytes()
        row=v.replace(self.root,'woman',img,'image/png')
        self.assertFalse(row['approved']);self.assertFalse(row['ready'])
        with self.assertRaises(ValueError):v.replace(self.root,'woman',b'NOT_A_PNG','image/png')
    def test_safe_paths(self):
        for path in ('../../etc/passwd','/tmp/secret','assets/../outside'):
            with self.assertRaises(ValueError):v.safe_file(self.root,path)
    def test_verify_actual_dimensions(self):
        actual=v.verify_image(self.root/v.SOURCE['style'])
        self.assertEqual((actual['width'],actual['height']),(1122,1402))
        self.assertEqual(actual['format'],'png')
    def test_existing_project_preserved_until_opt_in(self):
        p=project()
        self.assertEqual(v.check_video(p,p['shots'][0],self.root),[])
        self.assertFalse(v.project_report(p,self.root)['enabled'])

class VisualLockHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        fixtures(cls.root)
        cls.root_patch=patch.object(server,'ROOT',cls.root);cls.root_patch.start()
        cls.srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.srv.db=Store(cls.root/'data'/'test.sqlite3');cls.srv.access_token='v82-token'
        cls.thread=threading.Thread(target=cls.srv.serve_forever,daemon=True);cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.srv.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown();cls.srv.server_close();cls.thread.join()
        cls.root_patch.stop();cls.tmp.cleanup()
    def request(self,path,method='GET',body=None,binary=False,authorized=True):
        headers={'X-Studio-Token':'v82-token'} if authorized else {}
        data=None
        if binary:
            data=body;headers['Content-Type']='image/png'
        elif body is not None:
            data=json.dumps(body).encode('utf-8');headers['Content-Type']='application/json'
        req=urllib.request.Request(self.base+path,data=data,method=method,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=12) as r:return r.status,json.loads(r.read()) if 'json' in r.headers.get('Content-Type','') else r.read()
        except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
    def test_web_endpoints_and_render_gate(self):
        self.assertEqual(self.request('/api/v82/masters',authorized=False)[0],401)
        status,created=self.request('/api/projects','POST',{'title':'V82 test'})
        self.assertEqual(status,201)
        pid=created['project']['id']
        self.assertEqual(self.request('/api/projects/'+pid+'/develop','POST',{'mode':'demo'})[0],200)
        lock='/api/v82/projects/'+pid+'/lock'
        self.assertEqual(self.request(lock,'POST',{'approve':True,'enabled':True})[0],409)
        status,data=self.request('/api/v82/masters')
        self.assertEqual(status,200)
        for slot,row in data['slots'].items():
            self.assertEqual(self.request('/api/v82/masters/'+slot+'/approve','POST',{
                'sha256':row['sha256'],'viewed':True})[0],200)
        self.assertEqual(self.request(lock,'POST',{'approve':True,'enabled':True})[0],200)
        report=self.request('/api/v82/projects/'+pid+'/report')[1]
        self.assertTrue(report['enabled'])
        # strict preflight must block before asking Sogni for a quote
        with patch.object(server.sogni,'estimate',side_effect=AssertionError('should not contact Sogni')):
            self.assertEqual(self.request('/api/projects/'+pid+'/shots/S01/quote','POST',{})[0],409)
        image=(SRC/v.SOURCE['couple']).read_bytes()
        url='/api/projects/'+pid+'/shots/S01/keyframe'
        self.assertEqual(self.request(url,'PUT',image,binary=True)[0],200)
        self.assertEqual(self.request(url+'/sync','POST',{'approve':True})[0],409)
        approval='/api/v82/projects/'+pid+'/shots/S01/approve-keyframe'
        self.assertEqual(self.request(approval,'POST',{'viewed':True,'style_ok':False,'identity_ok':True})[0],409)
        observed=self.request('/api/v82/projects/'+pid+'/shots/S01/frame-info')[1]['sha256']
        self.assertEqual(self.request(approval,'POST',{'viewed':True,'style_ok':True,'identity_ok':True,'observed_sha':'0'*64})[0],409)
        self.assertEqual(self.request(approval,'POST',{'viewed':True,'style_ok':True,'identity_ok':True,'observed_sha':observed})[0],200)
        with patch.object(server.sogni,'upload_reference_image',return_value={'url':'https://example.test/approved.png'}):
            self.assertEqual(self.request(url+'/sync','POST',{'approve':True})[0],200)
        with patch.object(server.sogni,'estimate',return_value={'model':'test','capacity':2}):
            status,quote=self.request('/api/projects/'+pid+'/shots/S01/quote','POST',{})
            self.assertEqual(status,200,quote)
        self.assertEqual(self.request('/api/v82/projects/'+pid+'/shots/S01/keyframe-preview')[0],200)
        self.assertEqual(self.request('/api/projects/'+pid+'/shots/S01/render','POST',{'approve':False})[0],403)
        # new frame invalidates approval and synchronized references
        self.assertEqual(self.request(url,'PUT',image,binary=True)[0],200)
        self.assertEqual(self.request('/api/projects/'+pid+'/shots/S01/quote','POST',{})[0],409)
        # legacy projects remain opt-in
        self.assertEqual(self.request('/api/projects/'+pid)[1]['project']['v82_visual_lock'],True)

if __name__=='__main__':unittest.main()
