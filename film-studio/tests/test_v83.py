"""V8.3 acceptance: long-form, stable cast, actual media references, safe quotes,
portable backups, and live HTTP routes with NO network side effects."""
import io
import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import server
from studio import character_bible_v83, engine, portable_v83, reference_v83, sogni
from studio import visual_lock_v82 as visual
from studio.store import Store

SRC=Path(__file__).resolve().parent.parent

def fixtures(root):
    for name,rel in visual.SOURCE.items():
        dst=root/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(SRC/rel,dst)

def approve_all(root):
    for name,r in visual.summary(root)['slots'].items():
        visual.approve(root,name,r['sha256'],True,'Reviewed in integration test')

class Unit(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);fixtures(self.root)
    def locked(self):
        approve_all(self.root)
        p=engine.new_project({'duration':180,'claims_approved':True})
        engine.develop_demo(p)
        visual.pin_project(p,self.root)
        p['v83_reference_mode']=True
        p['v83_character_snapshot']=character_bible_v83.binding(p)['roles']
        return p
    def test_longform_180_actual_total_and_early_product(self):
        p=engine.new_project({'duration':180,'claims_approved':True})
        engine.develop_demo(p)
        self.assertEqual(p['duration'],180)
        self.assertEqual(sum(s['duration'] for s in p['shots']),180)
        self.assertGreaterEqual(len(p['shots']),35)
        self.assertEqual(len(p['acts']),4)
        self.assertLess(min(s['start'] for s in p['shots'] if s['mode']=='ui'),45)
        self.assertEqual(engine.validate_story(p),[])
    def test_short_format_unaffected(self):
        p=engine.new_project({'duration':30});engine.develop_demo(p)
        self.assertEqual(len(p['shots']),6)
    def test_canonical_characters_not_legacy_look(self):
        p=engine.new_project({'duration':180});engine.develop_demo(p)
        self.assertIn('sunglasses',p['cast'][0]['look'])
        self.assertIn('rounded jaw',p['cast'][1]['look'])
        self.assertEqual(character_bible_v83.binding(p)['roles']['ONA']['name'],p['cast'][0]['name'])
    def test_no_refs_until_master_lock(self):
        p=engine.new_project({'duration':180});engine.develop_demo(p)
        with self.assertRaises(ValueError):reference_v83.plan(p,p['shots'][0],self.root)
    def test_pinned_source_images_in_request(self):
        p=self.locked();shot=p['shots'][0]
        refs=reference_v83.plan(p,shot,self.root)
        self.assertEqual(refs['slots'],['couple','woman','man','style'])
        with self.assertRaises(ValueError):reference_v83.prepare_image_request(p,shot,self.root)
        reference_v83.mark_uploaded(p,shot,self.root,[{'slot':row['slot'],'url':'https://example.org/'+row['slot']+'.png'} for row in refs['files']])
        prepared=reference_v83.prepare_image_request(p,shot,self.root)
        body=sogni.image_body(prepared,True,100)
        step=body['input']['steps'][0]
        self.assertEqual(step['toolName'],'edit_image')
        self.assertEqual(step['arguments']['model'],'krea-identity-edit')
        self.assertEqual(step['arguments']['sourceImageIndex'],-1)
        self.assertEqual(step['arguments']['referenceImageIndices'],[-2,-3,-4])
        self.assertEqual(len(body['media_references']),4)
        self.assertEqual(body['billing_mode'],'subscription')
        self.assertEqual(body['max_estimated_capacity_units'],100)
    def test_change_invalidates_uploaded_reference(self):
        p=self.locked();shot=p['shots'][0]
        refs=reference_v83.plan(p,shot,self.root)
        reference_v83.mark_uploaded(p,shot,self.root,[{'slot':r['slot'],'url':'https://example.org/ref.png'} for r in refs['files']])
        shot['edit_version']='changed'
        with self.assertRaises(ValueError):reference_v83.remote_refs(p,shot,self.root)
    def test_quote_never_network_even_for_free_unit_plan(self):
        with patch.object(sogni,'request',side_effect=AssertionError('would start workflow')) as remote:
            shot={'id':'S01','mode':'t2v','prompt':'A detailed animated scene with the same approved characters in cozy kitchen.',
                  'video_model':'minimax-h3-fasth3-t2v-turbo','generation_seconds':5.2}
            self.assertIsNone(sogni.estimate(shot)['estimated_capacity'])
            self.assertIsNone(sogni.estimate_image(shot)['estimated_capacity'])
        remote.assert_not_called()
    def test_portable_bundle_contains_approved_local_assets(self):
        p=self.locked();shot=p['shots'][0]
        base=self.root/'data'/'keyframes'/p['id'];base.mkdir(parents=True)
        shutil.copy2(self.root/visual.SOURCE['couple'],base/'S01.png')
        shot['firstframe_local']='S01.png'
        out=portable_v83.package(self.root,p,[],include_clips=False)
        with zipfile.ZipFile(io.BytesIO(out)) as z:
            self.assertIn('assets/data/keyframes/'+p['id']+'/S01.png',z.namelist())
            self.assertNotIn('SOGNI_API_KEY',z.read('projekt.json').decode())
        self.assertGreaterEqual(portable_v83.validate_archive(out)['files'],5)
    def test_export_rewrites_absolute_audio_file(self):
        p=self.locked();shot=p['shots'][0]
        audio=self.root/'data'/'v7_audio'/p['id']
        audio.mkdir(parents=True,exist_ok=True)
        (audio/'S01.wav').write_bytes(b'RIFF'+b'0'*128)
        shot['v7_audio_file']=str(audio/'S01.wav')
        blob=portable_v83.package(self.root,p,[],False)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            saved=json.loads(z.read('projekt.json'))['project']['shots'][0]
            self.assertEqual(saved['v7_audio_file'],'data/v7_audio/'+p['id']+'/S01.wav')
            self.assertIn('assets/'+saved['v7_audio_file'],z.namelist())

    def test_portable_tampering_detected(self):
        p=self.locked();out=portable_v83.package(self.root,p,[],False)
        b=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(out)) as z1, zipfile.ZipFile(b,'w') as z2:
            for name in z1.namelist():z2.writestr(name,b'altered' if name.endswith('.png') else z1.read(name))
        with self.assertRaises(ValueError):portable_v83.validate_archive(b.getvalue())

class Web(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);fixtures(cls.root)
        cls.patch=patch.object(server,'ROOT',cls.root);cls.patch.start()
        cls.srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.srv.access_token='test-v83-token';cls.srv.db=Store(cls.root/'data'/'v6.sqlite3')
        cls.thread=threading.Thread(target=cls.srv.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.srv.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown();cls.srv.server_close();cls.thread.join();cls.patch.stop();cls.tmp.cleanup()
    def request(self,path,method='GET',data=None,token=True):
        headers={'X-Studio-Token':'test-v83-token'} if token else {}
        if data is not None:headers['Content-Type']='application/json'
        req=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=20) as resp:
                return resp.status,json.loads(resp.read()) if 'json' in resp.headers.get('Content-Type','') else resp.read()
        except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
    def test_http_longform_and_no_auto_upload(self):
        r,created=self.request('/api/projects','POST',{'duration':180,'title':'V83 180s'})
        self.assertEqual(r,201)
        pid=created['project']['id'];self.assertEqual(created['project']['duration'],180)
        _,developed=self.request('/api/projects/'+pid+'/develop','POST',{'mode':'demo'})
        self.assertGreater(len(developed['project']['shots']),35)
        self.assertEqual(self.request('/api/v83/projects/'+pid+'/bible')[0],200)
        self.assertEqual(self.request('/api/v83/projects/'+pid+'/bible',token=False)[0],401)
        self.assertEqual(self.request('/api/v83/projects/'+pid+'/mode','POST',{'approve':True,'enabled':True})[0],409)
        approve_all(self.root)
        self.assertEqual(self.request('/api/v82/projects/'+pid+'/lock','POST',{'approve':True,'enabled':True})[0],200)
        self.assertEqual(self.request('/api/v83/projects/'+pid+'/mode','POST',{'approve':True,'enabled':True})[0],200)
        status,response=self.request('/api/v83/projects/'+pid+'/shots/S01/references')
        self.assertEqual(status,200)
        self.assertFalse(response['uploaded'])
        with patch.object(server.sogni,'upload_reference_image',side_effect=AssertionError('not approved')):
            self.assertEqual(self.request('/api/v83/projects/'+pid+'/shots/S01/upload-references','POST',{'approve':False})[0],403)
        with patch.object(server.sogni,'upload_reference_image',return_value={'url':'https://example.org/ok.png'}):
            self.assertEqual(self.request('/api/v83/projects/'+pid+'/shots/S01/upload-references','POST',{'approve':True})[0],200)
        self.assertTrue(self.request('/api/v83/projects/'+pid+'/shots/S01/references')[1]['uploaded'])
        with patch.object(server.sogni,'estimate_image',return_value={'estimated_capacity':None,'source':'local_preflight'}):
            self.assertEqual(self.request('/api/projects/'+pid+'/shots/S01/image-quote','POST',{})[0],200)
        self.assertEqual(self.request('/api/v83/projects/'+pid+'/jobs')[0],200)
        self.assertEqual(self.request('/api/v83/projects/'+pid+'/backup?clips=0')[0],200)

if __name__=='__main__':unittest.main()
