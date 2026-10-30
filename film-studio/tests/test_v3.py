"""Version 3 acceptance tests: no-Spark guarantee, storyboard versions and real sound."""
import json
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import server
from server import Handler
from studio import engine, sogni
from studio.store import Store


class SubscriptionOnlyTests(unittest.TestCase):
    def setUp(self):
        self.shot={'id':'S01','mode':'t2v','prompt':'Cinematic fictional bride and groom carefully arranging wedding guest seats at a table. Film light, 50 mm lens.',
                   'video_model':'minimax-h3-fasth3-t2v-turbo','generation_seconds':5.2}

    def test_video_subscription_only(self):
        b=sogni.workflow_body(self.shot,True,10)
        self.assertEqual(b['billing_mode'],'subscription')
        self.assertEqual(b['token_type'],'auto')
        self.assertEqual(b['input']['steps'][0]['arguments']['videoModel'],self.shot['video_model'])
        self.assertNotIn('spark',str(b).lower())

    def test_image_subscription_only(self):
        b=sogni.image_body(self.shot,True,12)
        self.assertEqual(b['billing_mode'],'subscription')
        self.assertEqual(b['input']['steps'][0]['arguments']['model'],'krea-2-turbo')

    def test_external_vendor_models_blocked_before_network(self):
        for model in ['seedance-2.5','wan-3','happyhorse-1.1','gpt-image-2','unsupported']:
            with self.subTest(model=model),self.assertRaises(sogni.ProviderError):
                sogni.workflow_body(dict(self.shot,video_model=model))
        with self.assertRaises(sogni.ProviderError):sogni.chat('safe','prompt',model='premium')

    def test_billing_modes_fail_closed(self):
        for mode in ['auto','tokens',None]:
            with self.subTest(mode=mode),self.assertRaises(sogni.ProviderError):
                sogni.subscription_guard({'billing_mode':mode},self.shot['video_model'])
        with self.assertRaises(sogni.ProviderError):
            sogni.subscription_guard({'billing_mode':'subscription','token_type':'sogni'},self.shot['video_model'])

    def test_inactive_subscription_rejected_before_generation(self):
        with patch.object(sogni,'request',return_value=(200,{'data':{'subscription':{'active':False,'status':'expired'}}})) as req:
            with self.assertRaisesRegex(sogni.ProviderError,'Brak aktywnego'):
                sogni.start_render(self.shot,12,'c7f947e8-79b0-40a8-905d-8f32969a0572')
        self.assertEqual(req.call_count,1)
        self.assertEqual(req.call_args.args[:2],('GET','/v1/subscriptions/status'))

    def test_active_subscription_chat_requires_only_plan(self):
        def api_mock(method,path,data=None,**kwargs):
            if path=='/v1/subscriptions/status':return (200,{'data':{'subscription':{'active':True,'status':'active'}}})
            self.assertEqual(path,'/v1/chat/completions')
            self.assertEqual(data['billing_mode'],'subscription')
            self.assertEqual(data['sogni_tools'],False)
            return (200,{'choices':[{'message':{'content':'{"ok":true}'}}]})
        with patch.object(sogni,'request',side_effect=api_mock):
            self.assertEqual(sogni.chat('s','p')[0],'{"ok":true}')

    def test_negative_approval_gate(self):
        p=engine.new_project({'title':'Test'})
        engine.develop_demo(p)
        with self.assertRaises(sogni.ProviderError):
            sogni.workflow_body(dict(p['shots'][0],video_model='seedance-2.5'),True)


class V3ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.tmp.name)
        cls.root_patch=patch.object(server,'ROOT',cls.root)
        cls.root_patch.start()
        cls.httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.httpd.db=Store(cls.root/'db.sqlite3')
        cls.httpd.access_token='safe-local-test-token'
        cls.thread=threading.Thread(target=cls.httpd.serve_forever,daemon=True)
        cls.thread.start();cls.base=f'http://127.0.0.1:{cls.httpd.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown();cls.httpd.server_close();cls.thread.join(timeout=3)
        cls.root_patch.stop();cls.tmp.cleanup()

    def call(self,path,method='GET',data=None,raw=None,content_type='application/json'):
        headers={'X-Studio-Token':'safe-local-test-token'}
        body=json.dumps(data).encode() if data is not None else raw
        if body is not None:headers['Content-Type']=content_type
        req=urllib.request.Request(self.base+path,data=body,headers=headers,method=method)
        try:
            with urllib.request.urlopen(req,timeout=15) as r:
                return r.status,r.read()
        except urllib.error.HTTPError as e:return e.code,e.read()

    def create(self):
        _,raw=self.call('/api/projects','POST',{'title':'Test v3','duration':15})
        id=json.loads(raw)['project']['id']
        self.call(f'/api/projects/{id}/develop','POST',{'mode':'demo'})
        return id

    def test_manual_script_invalidates_storyboard_and_blocks_render(self):
        id=self.create()
        status,_=self.call(f'/api/projects/{id}/script','PUT',{'script':'Nowy scenariusz — odmienna historia'})
        self.assertEqual(status,200)
        status,res=self.call(f'/api/projects/{id}/shots/S01/quote','POST',{})
        self.assertEqual(status,409)
        self.assertIn('nieaktualny',json.loads(res)['error'])
        status,res=self.call(f'/api/projects/{id}/readiness')
        self.assertEqual(status,200)
        self.assertTrue(any('nie odpowiada' in x for x in json.loads(res)['issues']))

    def test_cast_change_invalidates_quotes_and_videos(self):
        id=self.create();p=self.httpd.db.get_project(id)
        p['shots'][0]['quote']={'id':'old-quote'}
        p['shots'][0]['media_url']='https://example.org/old.mp4'
        self.httpd.db.save_project(p)
        status,res=self.call(f'/api/projects/{id}/cast','PUT',{'cast':p['cast']})
        self.assertEqual(status,200)
        shot=json.loads(res)['project']['shots'][0]
        self.assertNotIn('quote',shot)
        self.assertNotIn('media_url',shot)
        self.assertTrue(shot.get('edit_version'))

    def test_local_clip_upload_rejects_invalid_content(self):
        id=self.create()
        status,_=self.call(f'/api/projects/{id}/clips/S01','POST',raw=b'not a movie at all',content_type='video/mp4')
        self.assertEqual(status,400)

    def test_assemble_real_mp4_with_original_audio(self):
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            self.skipTest('FFmpeg/FFprobe required')
        id=self.create()
        p=self.httpd.db.get_project(id)
        p['script']='Autentyczny ekran aplikacji i puenta.'
        p['claims_approved']=True
        p['shots']=[{'id':'S01','duration':0.55,'start':0,'mode':'ui','beat':'prawdziwe UI'}]
        p['duration']=0.55
        self.httpd.db.save_project(p)
        sample=self.root/'a.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi',
            '-i','color=c=purple:s=240x426:r=24:d=0.85','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=0.85',
            '-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',str(sample)],check=True)
        status,res=self.call(f'/api/projects/{id}/clips/S01','POST',raw=sample.read_bytes(),content_type='video/mp4')
        self.assertEqual(status,200,res)
        with patch('montaz.probe_format',return_value=(240,426)):
            status,res=self.call(f'/api/projects/{id}/assemble','POST',{})
        self.assertEqual(status,200,res[:300])
        status,video=self.call(f'/api/projects/{id}/movie')
        self.assertEqual(status,200)
        self.assertGreater(len(video),1000)
        movie=self.root/'received.mp4';movie.write_bytes(video)
        probe=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type',
            '-of','csv=p=0',str(movie)],capture_output=True,text=True,check=True)
        self.assertIn('video',probe.stdout)
        self.assertIn('audio',probe.stdout)
        # Re-editing the shot must invalidate the uploaded video, not silently reuse it.
        status,_=self.call(f'/api/projects/{id}/shots/S01','PUT',{'beat':'Zmieniona scena'})
        self.assertEqual(status,200)
        status,raw=self.call(f'/api/projects/{id}/readiness')
        self.assertEqual(status,200)
        self.assertFalse(json.loads(raw)['clips'][0]['available'])
        status,raw=self.call(f'/api/projects/{id}/assemble','POST',{})
        self.assertEqual(status,409)


if __name__=='__main__':unittest.main()
