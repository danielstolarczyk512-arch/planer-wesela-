"""V8.5 tests include real ffmpeg audio mixing and portable WAV restore."""
import io
import json
import math
import shutil
import subprocess
import tempfile
import unittest
import uuid
import wave
from pathlib import Path
from unittest.mock import patch

from montaz import render
from qc.continuity_v85 import contact_sheet
from studio import portable_v83, quality_v85, style_guide, timeline_v85, visual_lock_v82
from studio.store import Store

SRC=Path(__file__).resolve().parent.parent

def fixture(root,number=1):
    pid=str(uuid.uuid4())
    p={'id':pid,'title':'Test V8.5','format':'9:16','duration':number*1.0,'shots':[
       {'id':f'S{i:02}','duration':1.0,'mode':'t2v','start':float(i-1),'shot_role':'zbliżenie twarzy',
        'dialogue':'Polska kwestia testowa' if i==1 else '', 'speaker':'ONA','edit_version':'v1'}
       for i in range(1,number+1)]}
    return p

def wave_bytes(seconds=.6):
    out=io.BytesIO()
    with wave.open(out,'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
        frames=b''.join(int(math.sin(2*math.pi*440*i/16000)*6000).to_bytes(2,'little',signed=True) for i in range(int(seconds*16000)))
        f.writeframes(frames)
    return out.getvalue()

class V85Core(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.p=fixture(self.root,2)
    def test_reference_is_new_approved_master(self):
        from PIL import Image
        master=SRC/'assets/style/visual_reference.png'
        with Image.open(master) as im:self.assertEqual(im.size,(1122,1402))
        self.assertEqual((SRC/'assets/style/MASTER_GOLDEN_STORYBOOK_V85.png').read_bytes(),master.read_bytes())
    def test_old_remote_master_is_never_reused(self):
        f=self.root/'data/style_guide.json';f.parent.mkdir(parents=True)
        f.write_text(json.dumps({'remote_reference_url':'https://example.org/stale','master_sha256':'old'}))
        (self.root/'assets/style').mkdir(parents=True)
        shutil.copy2(SRC/'assets/style/visual_reference.png',self.root/'assets/style/visual_reference.png')
        state=style_guide.state(self.root)
        self.assertFalse(state['remote_reference_url']);self.assertTrue(state['remote_outdated'])
        style_guide.write_remote(self.root,'https://example.org/current')
        self.assertEqual(style_guide.state(self.root)['remote_reference_url'],'https://example.org/current')
    def test_wav_upload_approval_and_cue(self):
        shot=self.p['shots'][0];raw=wave_bytes()
        info=timeline_v85.add_audio(self.root,self.p,shot,raw)
        self.assertFalse(info['approved'])
        with self.assertRaises(ValueError):timeline_v85.approve_audio(self.root,self.p,shot,info['sha256'],False)
        timeline_v85.approve_audio(self.root,self.p,shot,info['sha256'],True)
        rows=timeline_v85.cues(self.root,self.p,require_approved=True)
        self.assertEqual(len(rows),1);self.assertAlmostEqual(rows[0]['duration'],.6,places=2)
        self.assertIn('Polska kwestia',timeline_v85.srt_from_cues(rows,2.0))
    def test_audio_replaced_requires_new_review(self):
        shot=self.p['shots'][0]
        info=timeline_v85.add_audio(self.root,self.p,shot,wave_bytes())
        timeline_v85.approve_audio(self.root,self.p,shot,info['sha256'],True)
        timeline_v85.add_audio(self.root,self.p,shot,wave_bytes(.8))
        with self.assertRaises(ValueError):timeline_v85.cues(self.root,self.p,True)
    def test_audio_stale_after_dialogue_change(self):
        shot=self.p['shots'][0];info=timeline_v85.add_audio(self.root,self.p,shot,wave_bytes())
        timeline_v85.approve_audio(self.root,self.p,shot,info['sha256'],True)
        shot['dialogue']='INNA KWESTIA'
        with self.assertRaises(ValueError):timeline_v85.cues(self.root,self.p,True)
    def test_new_audio_revokes_lipsync_and_old_video(self):
        shot=self.p['shots'][0]
        shot['v7_lips_approved']=True;shot['qc_approved']=True
        shot['v82_clip_approval']={'sha256':'old'};old_edit=shot['edit_version']
        timeline_v85.add_audio(self.root,self.p,shot,wave_bytes())
        self.assertFalse(shot['v7_lips_approved'])
        self.assertFalse(shot['qc_approved'])
        self.assertNotEqual(old_edit,shot['edit_version'])
        self.assertNotIn('v82_clip_approval',shot)
    def test_audio_tamper_detected(self):
        shot=self.p['shots'][0];info=timeline_v85.add_audio(self.root,self.p,shot,wave_bytes())
        timeline_v85.approve_audio(self.root,self.p,shot,info['sha256'],True)
        timeline_v85.safe_audio(self.root,self.p['id'],'S01').write_bytes(wave_bytes(.4))
        with self.assertRaises(ValueError):timeline_v85.cues(self.root,self.p,True)
    def test_srt_no_overlap(self):
        cues=[{'start':0,'duration':2,'text':'Pierwsza długa kwestia'},
              {'start':1,'duration':1,'text':'Druga kwestia'}]
        srt=timeline_v85.srt_from_cues(cues,3)
        self.assertIn('00:00:01,000 --> 00:00:02,000',srt)
        self.assertIn('00:00:00,000 --> 00:00:01,000',srt)
    def test_reject_non_audio_and_invalid_offset(self):
        with self.assertRaises(ValueError):timeline_v85.add_audio(self.root,self.p,self.p['shots'][0],b'x'*3000)
        with self.assertRaises(ValueError):timeline_v85.add_audio(self.root,self.p,self.p['shots'][0],wave_bytes(),9)
    def test_quality_warns_on_long_portraits(self):
        p=fixture(self.root,1);p['shots'][0]['duration']=6;p['duration']=6
        p['shots'][0]['shot_role']='zbliżenie twarzy'
        a=quality_v85.review(self.root,p)
        self.assertTrue(any('Portret' in x['message'] for x in a['issues']))
        self.assertFalse(a['audio']['visual_and_phoneme_sync_verified'])
    def test_portable_wav_restored_unapproved(self):
        shot=self.p['shots'][0];info=timeline_v85.add_audio(self.root,self.p,shot,wave_bytes())
        timeline_v85.approve_audio(self.root,self.p,shot,info['sha256'],True)
        db=Store(self.root/'data/studio.sqlite');db.save_project(self.p)
        blob=portable_v83.package(self.root,self.p,[],True)
        portable_v83.validate_archive(blob)
        res=portable_v83.restore_archive(self.root,db,blob)
        new=db.get_project(res['project_id']);restored=new['shots'][0]['v85_audio']
        self.assertFalse(restored['approved'])
        self.assertTrue(timeline_v85.safe_audio(self.root,new['id'],'S01').is_file())
        self.assertEqual(restored['edit_version'],new['shots'][0]['edit_version'])

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg not installed')
class V85Video(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.p=fixture(self.root,2)
        self.clips=self.root/'data/clips'/self.p['id'];self.clips.mkdir(parents=True)
        for i,c in enumerate(('red','blue'),1):
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i',
                  f'color=c={c}:s=240x426:r=24:d=1.0','-c:v','libx264','-preset','ultrafast',
                  str(self.clips/f'S{i:02}.mp4')],check=True)
    def test_real_multitrack_ffmpeg_subtitles(self):
        shot=self.p['shots'][0]
        info=timeline_v85.add_audio(self.root,self.p,shot,wave_bytes(.8),offset=.2)
        timeline_v85.approve_audio(self.root,self.p,shot,info['sha256'],True)
        self.p['v85_audio_mix']={'enabled':True,'replace_clip_audio':True,'subtitles':True}
        output=self.root/'render.mp4'
        result=render(self.p,self.clips,output,quality='draft')
        self.assertTrue(output.exists())
        self.assertEqual(result['v85_audio_cues'],1)
        self.assertIn('00:00:00,200',output.with_suffix('.srt').read_text())
        probe=subprocess.run(['ffprobe','-v','error','-select_streams','a:0',
              '-show_entries','stream=codec_name','-of','csv=p=0',str(output)],capture_output=True,text=True)
        self.assertIn('aac',probe.stdout)
    def test_real_contact_sheet(self):
        from PIL import Image
        png=contact_sheet(SRC/'assets/style/visual_reference.png',self.clips/'S01.mp4')
        im=Image.open(io.BytesIO(png))
        self.assertEqual(im.size,(1360,500))
    def test_reject_muting_without_approved_audio(self):
        self.p['v85_audio_mix']={'enabled':True,'replace_clip_audio':True}
        with self.assertRaisesRegex(ValueError,'nie wyciszaj'):
            render(self.p,self.clips,self.root/'bad.mp4',quality='draft')

if __name__=='__main__':unittest.main()

class V85Web(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        from http.server import ThreadingHTTPServer

        import server
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        for rel in visual_lock_v82.SOURCE.values():
            dst=cls.root/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(SRC/rel,dst)
        cls.patch=patch.object(server,'ROOT',cls.root);cls.patch.start()
        cls.httpd=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.httpd.db=Store(cls.root/'data/studio.sqlite')
        cls.httpd.access_token='test-v85-token'
        cls.thread=threading.Thread(target=cls.httpd.serve_forever,daemon=True);cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.httpd.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown();cls.thread.join(timeout=5);cls.httpd.server_close();cls.patch.stop();cls.tmp.cleanup()
    def http(self,path,method='GET',body=None,headers=None):
        import urllib.error
        import urllib.request
        h={'X-Studio-Token':'test-v85-token',**(headers or {})}
        if isinstance(body,dict):body=json.dumps(body).encode();h['Content-Type']='application/json'
        req=urllib.request.Request(self.base+path,data=body,method=method,headers=h)
        try:
            with urllib.request.urlopen(req,timeout=20) as r:return r.status,r.read()
        except urllib.error.HTTPError as e:return e.code,e.read()
    def test_local_api_audio_and_style_review(self):
        p=fixture(self.root,2);self.httpd.db.save_project(p)
        status,raw=self.http('/api/v85')
        self.assertEqual(status,200);master=json.loads(raw)['master_style']
        self.assertEqual(master['width'],1122)
        root='/api/v85/projects/'+p['id']
        self.assertEqual(self.http(root+'/review')[0],200)
        self.assertEqual(self.http(root+'/config','POST',{'enabled':True,'replace_clip_audio':True})[0],403)
        self.assertEqual(self.http(root+'/config','POST',{'approve':True,'enabled':True,'replace_clip_audio':True})[0],200)
        self.assertEqual(self.http(root+'/shots/S01/audio','PUT',b'fake audio',{'Content-Type':'audio/wav'})[0],413)
        status,raw=self.http(root+'/shots/S01/audio','PUT',wave_bytes(),{'Content-Type':'audio/wav'})
        self.assertEqual(status,201,raw[:200])
        info=json.loads(raw)['audio']
        self.assertFalse(info['approved'])
        self.assertEqual(self.http(root+'/shots/S01/audio')[0],200)
        self.assertEqual(self.http(root+'/shots/S01/audio-approve','POST',{'sha256':info['sha256'],'heard':False})[0],409)
        self.assertEqual(self.http(root+'/shots/S01/audio-approve','POST',{'sha256':info['sha256'],'heard':True})[0],200)
        code,raw=self.http(root+'/subtitles');self.assertEqual(code,200)
        self.assertIn(b'Polska kwestia',raw)
        self.assertEqual(self.http(root+'/shots/S02/contact-sheet')[0],404)
        # The exact same approved WAV can drive existing V7 image+audio video.
        code,raw=self.http('/api/v7/projects/'+p['id']+'/shots/S01/voice-plan','POST',
                {'speaker':'ONA','transcript':'Polska kwestia testowa','camera':'speaker_closeup'})
        self.assertEqual(code,200,raw[:300])
        latest=self.httpd.db.get_project(p['id'])['shots'][0]
        self.assertTrue(latest['v85_audio']['approved'])
        self.assertEqual(latest['edit_version'],latest['v85_audio']['edit_version'])
