"""V4 acceptance tests: editorial output, approval gates, timeline and FFmpeg."""
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
from director.story import apply_director_v4
from montaz import make_edl, render
from qc.story import audit
from qc.video import inspect_shot
from server import Handler
from studio import engine, sogni
from studio.store import Store


class DirectorV4Tests(unittest.TestCase):
    def project(self):
        p=engine.new_project({'title':'Operacja: Plan Stołów', 'feature':'plan stołów','duration':30})
        engine.develop_demo(p)
        return p
    def test_builds_ten_natural_shots_no_fake_ui(self):
        p=self.project();old=p['shot_generation']
        apply_director_v4(p)
        self.assertEqual(len(p['shots']),10)
        self.assertNotEqual(old,p['shot_generation'])
        self.assertAlmostEqual(sum(s['duration'] for s in p['shots']),30,places=3)
        self.assertTrue(any(s['shot_role']=='payoff' for s in p['shots']))
        self.assertEqual([x['mode'] for x in p['shots']].count('ui'),1)
        self.assertEqual([x['mode'] for x in p['shots']].count('overlay'),1)
        self.assertTrue(all(x['continuity_id']=='SALA_A_2026' for x in p['shots']))
        self.assertTrue(all(x['qc_approved'] is False for x in p['shots']))
        self.assertTrue(all(x['duration']<=4.5 for x in p['shots']))
        self.assertFalse(audit(p)['blocking'])
        self.assertTrue(all(s.get('in_point')==0 for s in p['shots']))
        self.assertEqual(len(make_edl(p)),10)
    def test_rejects_stale_script(self):
        p=self.project();p['storyboard_stale']=True
        with self.assertRaises(ValueError):apply_director_v4(p)
    def test_other_features_require_custom_director(self):
        p=self.project();p['feature']='budżet'
        with self.assertRaises(ValueError):apply_director_v4(p)
    def test_approval_gate_in_final_render(self):
        p=self.project();apply_director_v4(p)
        with self.assertRaisesRegex(ValueError,'zatwierdzenie'):render(p,'/does/not/exist','/tmp/no.mp4',quality='draft')
    def test_subscription_hard_block_remains(self):
        p=self.project();apply_director_v4(p)
        shot=next(s for s in p['shots'] if s['mode']=='t2v')
        payload=sogni.workflow_body(shot,True,12)
        self.assertEqual(payload['billing_mode'],'subscription')
        with self.assertRaises(sogni.ProviderError):sogni.subscription_guard({'billing_mode':'auto'},shot['video_model'])
        with self.assertRaises(sogni.ProviderError):sogni.workflow_body(dict(shot,video_model='seedance-2.5'),True)

class ApiV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.tmp.name)
        cls.patchroot=patch.object(server,'ROOT',cls.root);cls.patchroot.start()
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.http.db=Store(cls.root/'db.sqlite3');cls.http.access_token='test-safety-v4'
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.http.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join(timeout=4)
        cls.patchroot.stop();cls.tmp.cleanup()
    def call(self,path,method='GET',data=None,raw=None):
        body=json.dumps(data).encode() if data is not None else raw
        hdr={'X-Studio-Token':'test-safety-v4'}
        if body is not None:hdr['Content-Type']='video/mp4' if raw is not None else 'application/json'
        req=urllib.request.Request(self.url+path,headers=hdr,data=body,method=method)
        try:
            with urllib.request.urlopen(req,timeout=30) as r:return r.status,r.read()
        except urllib.error.HTTPError as e:return e.code,e.read()
    def create(self):
        st,b=self.call('/api/projects','POST',{'title':'V4','feature':'plan stołów','duration':30})
        self.assertEqual(st,201)
        pid=json.loads(b)['project']['id']
        st,_=self.call(f'/api/projects/{pid}/develop','POST',{'mode':'demo'})
        self.assertEqual(st,200)
        return pid
    def test_quality_endpoint_and_existing_project_compatibility(self):
        pid=self.create()
        st,b=self.call(f'/api/projects/{pid}/director-v4','POST',{})
        self.assertEqual(st,200,b)
        p=json.loads(b)['project'];self.assertEqual(len(p['shots']),10)
        st,b=self.call(f'/api/projects/{pid}/v4/story-audit')
        self.assertEqual(st,200);self.assertTrue(json.loads(b)['audit']['ready'])
        st,b=self.call(f'/api/projects/{pid}/readiness')
        self.assertEqual(st,200)
        self.assertTrue(any('akceptacji' in x for x in json.loads(b)['issues']))
    def test_ui_provenance_and_actual_video_quality(self):
        if not shutil.which('ffmpeg'):self.skipTest('ffmpeg missing')
        pid=self.create();self.call(f'/api/projects/{pid}/director-v4','POST',{})
        sample=self.root/'ui.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i',
                        'color=c=white:s=240x426:r=24:d=6','-c:v','libx264','-preset','ultrafast',str(sample)],check=True)
        data=sample.read_bytes();st,b=self.call(f'/api/projects/{pid}/clips/S06','POST',raw=data)
        self.assertEqual(st,200,b)
        st,b=self.call(f'/api/projects/{pid}/clips/S06/preview');self.assertEqual(st,200)
        self.assertEqual(b[:40],data[:40])
        st,b=self.call(f'/api/projects/{pid}/clips/S06/inspect')
        self.assertEqual(st,200);self.assertTrue(json.loads(b)['report']['technical_pass'])
        st,b=self.call(f'/api/projects/{pid}/clips/S06/approve','POST',{'viewed':True,'authentic':False,'source_url':'https://example.com'})
        self.assertEqual(st,400)
        st,b=self.call(f'/api/projects/{pid}/clips/S06/approve','POST',{'viewed':True,'authentic':True,'source_url':'https://nasz-dzien.example/plan-stolow'})
        self.assertEqual(st,200,b)
        self.assertTrue(json.loads(b)['project']['shots'][5]['qc_approved'])
        # Replacing footage invalidates QC approval/provenance.
        st,_=self.call(f'/api/projects/{pid}/clips/S06','POST',raw=data)
        self.assertEqual(st,200)
        st,b=self.call(f'/api/projects/{pid}')
        s=json.loads(b)['project']['shots'][5]
        self.assertFalse(s['qc_approved']);self.assertNotIn('ui_provenance',s)

class FfmpegV4Tests(unittest.TestCase):
    def test_real_ffmpeg_timeline_and_audio(self):
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):self.skipTest('ffmpeg missing')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);clips=root/'clips';clips.mkdir()
            p=engine.new_project({'feature':'plan stołów','duration':30})
            engine.develop_demo(p);apply_director_v4(p)
            # Tiny fixtures for the e2e codec verification; never presented as actual Sogni renders.
            for i,s in enumerate(p['shots']):
                s['duration']=0.25
                s['in_point']=0.08
                s['start']=i*0.25
                s['qc_approved']=True
                if s['mode']=='ui':s['ui_provenance']={'user_confirmed_real_ui':True}
                src=clips/(s['id']+'.mp4')
                color=['red','purple','yellow','orange','white','pink','blue','green','black','navy'][i]
                subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',
                                '-f','lavfi','-i',f'color=c={color}:s=160x284:r=24:d=0.7',
                                '-f','lavfi','-i','sine=frequency=320:sample_rate=48000:duration=0.7',
                                '-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',str(src)],check=True)
            p['duration']=2.5
            # Keep the test affordable by rendering at draft dimensions.
            with patch('montaz.probe_format',return_value=(160,284)):
                out=root/'result.mp4';result=render(p,clips,out,quality='draft')
            self.assertEqual(len(result['edl']),10)
            self.assertTrue(out.exists());self.assertGreater(out.stat().st_size,2000)
            report=inspect_shot(out,{'duration':2.5})
            self.assertTrue(report['technical_pass'],report)
            self.assertTrue(report['metadata']['audio_present'])
            self.assertAlmostEqual(report['metadata']['seconds'],2.5,delta=0.3)

if __name__=='__main__':unittest.main()
