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
from studio import cinematic_v7, dialogue_v7, voice_cli_v7
from studio.store import Store


def wav_file(path,secs=5.3):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
        f.writeframes(b'\x00\x00'*int(16000*secs))
    return path

class TestV7Units(unittest.TestCase):
    def test_speaker_requires_correct_character(self):
        with tempfile.TemporaryDirectory() as td:
            f=wav_file(Path(td)/'pl.wav')
            self.assertEqual(dialogue_v7.audio_probe(f)['channels'],1)
            shot={'id':'S01','mode':'t2v','characters':['ONA']}
            info=dialogue_v7.prepare_talking_shot(shot,'ONA','Kochanie, zobacz tutaj!',f)
            self.assertEqual(info['language'],'pl-PL')
            self.assertTrue('lips' in dialogue_v7.prompt_for_speaker('ONA',info['transcript']))
            with self.assertRaises(ValueError):dialogue_v7.prepare_talking_shot(shot,'ON','Słuchaj',f)
    def test_camera_style_coverage_and_orbit_safety(self):
        shot={'id':'S01','mode':'t2v','characters':['ONA','ON'],'dialogue':'Tak, jutro!','duration':5}
        cover=cinematic_v7.coverage(shot,'ONA')
        self.assertEqual(len(cover['shots']),3)
        self.assertEqual(round(sum(x['seconds'] for x in cover['shots']),1),5.)
        self.assertEqual(cinematic_v7.plan(shot,'speaker_closeup','ONA')['distance'],'close-up')
        with self.assertRaises(ValueError):cinematic_v7.plan(shot,'gentle_orbit','ONA')
        with self.assertRaises(ValueError):cinematic_v7.plan(shot,'turnaround_reference_only','ONA')
    def test_recipe_is_offline_and_subscription_only(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);f=wav_file(base/'polski.wav');pic=base/'portrait.png';pic.write_bytes(b'\x89PNG\r\n\x1a\nTEST')
            shot={'id':'S01','mode':'t2v','characters':['ONA']}
            info=dialogue_v7.prepare_talking_shot(shot,'ONA','Dzień dobry!',f)
            with patch.object(voice_cli_v7,'OUTPUTS',base/'renders'):
                rec=voice_cli_v7.recipe(shot,info,pic)
                self.assertTrue(rec['dry_run']);args=rec['arguments']
                self.assertEqual(args[args.index('--billing-mode')+1],'subscription')
                self.assertEqual(args[args.index('-m')+1],'minimax-h3-fasth3-ia2v-turbo')
                self.assertIn('--ref-audio',args)
                with self.assertRaises(ValueError):voice_cli_v7.generate_once(shot,info,pic,approve=False)
    def test_reject_invalid_audio_and_script(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'f.mp3';f.write_bytes(b'wrong audio'*100)
            with self.assertRaises(ValueError):dialogue_v7.audio_probe(f)
            self.assertFalse(dialogue_v7.dialogue_clean('<html>hello'))

class TestV7Http(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t=tempfile.TemporaryDirectory();cls.srv=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.srv.db=Store(Path(cls.t.name)/'v7.sqlite3');cls.srv.access_token='testing-v7-only'
        cls.td=threading.Thread(target=cls.srv.serve_forever,daemon=True);cls.td.start()
        cls.base=f'http://127.0.0.1:{cls.srv.server_port}'
    @classmethod
    def tearDownClass(cls):cls.srv.shutdown();cls.srv.server_close();cls.td.join();cls.t.cleanup()
    def req(self,path,method='GET',body=None,content_type=None):
        data=None;hdr={'X-Studio-Token':'testing-v7-only'}
        if body is not None:
            if isinstance(body,bytes):data=body;hdr['Content-Type']=content_type or 'audio/wav'
            else:data=json.dumps(body).encode('utf-8');hdr['Content-Type']='application/json'
        r=urllib.request.Request(self.base+path,data=data,method=method,headers=hdr)
        try:
            with urllib.request.urlopen(r,timeout=15) as resp:return resp.status,json.loads(resp.read())
        except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
    def test_routes_voice_clip_and_camera(self):
        self.assertEqual(self.req('/api/v7')[0],200)
        status,p=self.req('/api/projects','POST',{'title':'Test lip-sync'});self.assertEqual(status,201)
        project_id=p['project']['id']
        self.req('/api/projects/'+project_id+'/develop','POST',{'mode':'demo'})
        # V7 camera must create explicit shot plan, not send cloud requests
        path=f'/api/v7/projects/{project_id}/shots/S01/'
        result=self.req(path+'camera','POST',{'preset':'speaker_closeup','speaker':'ONA'})
        self.assertEqual(result[0],200,msg=str(result))
        with tempfile.TemporaryDirectory() as td:
            f=wav_file(Path(td)/'s.wav')
            status,response=self.req(path+'voice-file','PUT',f.read_bytes(),'audio/wav')
            self.assertEqual(status,200)
            self.assertEqual(response['audio']['channels'],1)
            status,plan=self.req(path+'voice-plan','POST',{'speaker':'ONA','transcript':'Tak, razem damy radę!','camera':'speaker_closeup'})
            self.assertEqual(status,200)
            status,ref=self.req(path+'voice-generate','POST',{'approve':False,'reference_id':'unknown'})
            self.assertIn(status,(403,409))
            status,_=self.req(path+'lips-approve','POST',{'watched':True})
            self.assertIn(status,(403,409))
            status,ready=self.req('/api/projects/'+project_id+'/readiness')
            self.assertEqual(status,200)
            self.assertTrue(any('V7:' in x for x in ready['issues']))

if __name__=='__main__':unittest.main()
