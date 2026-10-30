"""V8 regression: safe audio A/B, pacing, UI provenance, API authorization."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import wave
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from server import Handler
from studio import pace_v8, product_demo_v8, voice_v8
from studio.store import Store


def make_wav(path, seconds=2):
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
        w.writeframes(b'\0\0'*int(16000*seconds))
    return path

class V8UnitTest(unittest.TestCase):
    def test_polish_emotion_presets(self):
        req=voice_v8.build_variants_request('Serio? Już wszystko gotowe?', 'comic','ON')
        self.assertEqual(req['language_id'],'pl')
        self.assertEqual(len(req['variants']),2)
        self.assertGreater(req['variants'][1]['exaggeration'],req['variants'][0]['exaggeration'])
    def test_requires_consent(self):
        with self.assertRaises(ValueError):voice_v8.validate_request('Dzień dobry','warm',consent=False)
    def test_reject_oversized_text(self):
        with self.assertRaises(ValueError):voice_v8.validate_request('x'*400,'warm',consent=True)
    def test_approval_rejects_changed_audio(self):
        with tempfile.TemporaryDirectory() as td:
            f=make_wav(Path(td)/'variant_1.wav')
            info=voice_v8.voice_probe(f)
            shot={'v8_voice_variants':[{'id':'variant_1','file':str(f),'audio':info}]}
            with self.assertRaises(ValueError):voice_v8.approve(shot,'variant_1',False)
            self.assertEqual(voice_v8.approve(shot,'variant_1',True)['id'],'variant_1')
            f.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):voice_v8.approve(shot,'variant_1',True)
    def test_pacing_flags_late_ui_and_repetition(self):
        p={'duration':30,'shots':[
            {'id':'S01','duration':9,'mode':'t2v','camera':'close'},
            {'id':'S02','duration':9,'mode':'t2v','camera':'close'},
            {'id':'S03','duration':8,'mode':'t2v','camera':'close'},
            {'id':'S04','duration':4,'mode':'ui','camera':'ui'}]}
        report=pace_v8.audit(p)
        self.assertAlmostEqual(report['first_product_second'],26)
        self.assertTrue(any('Trzeci' in x['message'] for x in report['issues']))
        self.assertTrue(any('Pierwsze UI' in x['message'] for x in report['issues']))
        self.assertFalse(p.get('shots')[0].get('duration')!=9)
    def test_pacing_never_trims_dialog(self):
        p={'shots':[{'id':'S01','duration':9,'dialogue':'Tak, świetnie!'},{'id':'S02','duration':9}]}
        proposal=pace_v8.suggest_cuts(p)
        self.assertEqual(proposal['proposals'][0]['trim_seconds'],0)
        self.assertFalse(proposal['applied'])
    def test_product_requires_verified_real_ui(self):
        with self.assertRaises(ValueError):product_demo_v8.plan({'mode':'ui'},confirmed=True)
        shot={'mode':'ui','ui_provenance':{'user_confirmed_real_ui':True}}
        result=product_demo_v8.plan(shot,1.3,0.3,0.6,True)
        self.assertIn('crop=1080:1920',result['ffmpeg_filter'])
        self.assertNotIn('pad=',result['ffmpeg_filter'])
        with self.assertRaises(ValueError):product_demo_v8.plan(shot,5,0.5,0.5,True)

class V8HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.server.db=Store(Path(cls.temp.name)/'studio.sqlite3')
        cls.server.access_token='v8-test-token'
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()
    def request(self,path,method='GET',body=None,authorized=True):
        headers={'Content-Type':'application/json'}
        if authorized:headers['X-Studio-Token']='v8-test-token'
        data=json.dumps(body).encode() if body is not None else None
        req=urllib.request.Request(self.base+path,data=data,headers=headers,method=method)
        try:
            with urllib.request.urlopen(req,timeout=12) as r:
                return r.status,json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code,json.loads(e.read())
    def test_v8_endpoints_work_without_paid_requests(self):
        self.assertEqual(self.request('/api/v8',authorized=False)[0],401)
        self.assertEqual(self.request('/api/v8')[1]['version'],'8.0.0')
        status,res=self.request('/api/projects','POST',{'title':'V8 creative test'})
        self.assertEqual(status,201)
        pid=res['project']['id']
        self.request('/api/projects/'+pid+'/develop','POST',{'mode':'demo'})
        self.assertEqual(self.request(f'/api/v8/projects/{pid}/pace')[0],200)
        path=f'/api/v8/projects/{pid}/shots/S01/'
        self.assertEqual(self.request(path+'voice-generate','POST',{'approve':True})[0],409)
        self.assertEqual(self.request(path+'voice-prepare','POST',{'speaker':'ONA','text':'Tak, mamy plan!',
            'emotion':'comic','voice_consent':False})[0],403)
        status,res=self.request(path+'voice-prepare','POST',{'speaker':'ONA','text':'Tak, mamy plan!',
            'emotion':'comic','voice_consent':True})
        self.assertEqual(status,200,res)
        self.assertEqual(self.request(path+'voice-list')[0],200)
        self.assertEqual(self.request(path+'voice-approve','POST',{'variant_id':'variant_1','listened':True,
           'polish_ok':True,'voice_consent':True})[0],409)
        with tempfile.TemporaryDirectory() as td:
            f=make_wav(Path(td)/'variant_1.wav')
            entry={'id':'variant_1','file':str(f),'audio':voice_v8.voice_probe(f),'approved':False}
            with patch.object(voice_v8,'isolated_dir',return_value=Path(td)),patch.object(voice_v8,'run_chatterbox',return_value=[entry]):
                status,res=self.request(path+'voice-generate','POST',{'approve':True})
                self.assertEqual(status,200,res)
                status,res=self.request(path+'voice-approve','POST',{'variant_id':'variant_1',
                       'listened':True,'polish_ok':True,'voice_consent':True})
                self.assertEqual(status,200,res)
                self.assertEqual(res['approved'],'variant_1')
            status,ready=self.request('/api/projects/'+pid+'/readiness')
            self.assertEqual(status,200)
            self.assertTrue(any('V7:' in x for x in ready['issues']))
if __name__=='__main__':unittest.main()

class V8MontageTest(unittest.TestCase):
    def test_real_vertical_ui_framing_ffmpeg(self):
        import shutil
        import subprocess

        from montaz import render
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            self.skipTest('FFmpeg unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);clips=base/'clips';clips.mkdir()
            src=clips/'S01.mp4'
            subprocess.run(['ffmpeg','-loglevel','error','-y','-f','lavfi','-i',
                'testsrc=size=400x224:rate=24:duration=1', '-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',str(src)],check=True)
            shot={'id':'S01','mode':'ui','duration':0.5,'qc_approved':True,
                 'v8_product_frame':product_demo_v8.plan({'mode':'ui','ui_provenance':{'user_confirmed_real_ui':True}},1.0,0.45,0.5,True)}
            project={'format':'9:16','duration':.5,'v8_enabled':True,'shots':[shot]}
            result=render(project,clips,base/'render.mp4',quality='draft')
            self.assertTrue((base/'render.mp4').is_file())
            self.assertEqual(result['resolution'],[360,640])
            with patch.dict(project,{'shots':[dict(shot,qc_approved=False)]}):
                with self.assertRaisesRegex(ValueError,'wymaga ponownej akceptacji'):
                    render(project,clips,base/'bad.mp4',quality='draft')

class V8MotionTest(unittest.TestCase):
    def test_detect_static_vs_moving_without_claiming_art_quality(self):
        import shutil
        import subprocess

        from qc.motion_v8 import inspect_motion
        if not shutil.which('ffmpeg'):self.skipTest('No FFmpeg')
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/'static.mp4'
            subprocess.run(['ffmpeg','-loglevel','error','-y','-f','lavfi','-i',
                'color=c=gray:s=192x320:d=3:r=24','-c:v','libx264','-preset','ultrafast',str(src)],check=True)
            rep=inspect_motion(src)
            self.assertGreater(rep['almost_identical_frame_pairs_fraction'],.85)
            self.assertTrue(rep['human_review_required'])
            self.assertTrue(rep['issues'])
