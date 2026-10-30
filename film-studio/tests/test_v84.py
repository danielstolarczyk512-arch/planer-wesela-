"""V8.4 offline integration: variants, story, concurrency guard, portable restore."""
import io
import json
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch

from studio import ai, engine, jobs_v84, longform_v83, portable_v83
from studio import story_director_v84 as sd
from studio.store import Store


class V84Tests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.db=Store(self.root/'data'/'db.sqlite')
    def project(self):
        p=engine.new_project({'duration':180,'claims_approved':True})
        engine.develop_demo(p)
        return p
    def test_longform_has_polish_dialogues_and_early_real_ui(self):
        p=self.project()
        self.assertEqual(len(p['shots']),46)
        self.assertEqual(round(sum(s['duration'] for s in p['shots']),3),180)
        self.assertGreaterEqual(sum(bool(s['dialogue']) for s in p['shots']),10)
        self.assertLess(min(s['start'] for s in p['shots'] if s['mode']=='ui'),45)
        self.assertTrue(all(s.get('scene_bible') for s in p['shots']))
        self.assertTrue(all(s.get('voice_status')=='needs_recording' for s in p['shots'] if s.get('dialogue')))
    def test_concepts_result_in_distinct_story(self):
        p=self.project();a=dict(p)
        b=dict(p)
        longform_v83.build(a,{'id':'X','title':'Szpiegowskie stoły','genre':'Komedia szpiegowska','feature':'plan stołów'})
        longform_v83.build(b,{'id':'Y','title':'Kasa','genre':'Komedia finansowa','feature':'budżet'})
        self.assertNotEqual(a['script'],b['script'])
        self.assertNotEqual([s['beat'] for s in a['shots']],[s['beat'] for s in b['shots']])
        self.assertEqual(sum(s['duration'] for s in b['shots']),180)
    def test_doctor_180_never_uses_sogni(self):
        p=self.project()
        with patch.object(ai.sogni,'chat',side_effect=AssertionError('NO SOGNI')) as call:
            result=ai.script_doctor(p,self.db.save_project)
        call.assert_not_called()
        self.assertEqual(result['script_review']['offline'],True)
    def test_render_plan_prevents_double_use(self):
        p=self.project()
        jobs=[{'id':str(uuid.uuid4()),'shot_id':'S01','status':'submission_uncertain','kind':'video'}]
        budget=sd.render_plan(p,jobs)
        self.assertGreater(budget['previously_submitted_source_seconds'],0)
        self.assertTrue(budget['cost_unknown'])
        with self.assertRaises(ValueError):jobs_v84.require_safe_submission(jobs,'S01','video',str(uuid.uuid4()))
        self.assertTrue(jobs_v84.require_safe_submission(jobs,'S02','video','other'))
    def test_renders_in_portable_and_restore_rekeys_project(self):
        p=self.project();self.db.save_project(p)
        pid=p['id']
        audio=self.root/'data'/'v7_audio'/pid/'S02.wav';audio.parent.mkdir(parents=True);audio.write_bytes(b'RIFF'+b'1'*400)
        render=self.root/'data'/'v7_renders'/pid/'S02.mp4';render.parent.mkdir(parents=True);render.write_bytes(b'fake_mp4_bytes_for_backup')
        frame=self.root/'data'/'keyframes'/pid/'S02.png';frame.parent.mkdir(parents=True);frame.write_bytes(b'fake_png_bytes')
        p['shots'][1]['firstframe_local']='S02.png';p['shots'][1]['v7_audio_file']=str(audio)
        blob=portable_v83.package(self.root,p,[],True)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            self.assertIn('assets/data/v7_renders/'+pid+'/S02.mp4',z.namelist())
        res=portable_v83.restore_archive(self.root,self.db,blob)
        new=res['project_id'];self.assertNotEqual(pid,new)
        self.assertEqual((self.root/'data'/'v7_renders'/new/'S02.mp4').read_bytes(),render.read_bytes())
        again=self.db.get_project(new)
        self.assertFalse(again['v82_visual_lock'])
        self.assertFalse(again['shots'][1]['qc_approved'])
        self.assertTrue(str(again['shots'][1]['v7_audio_file']).endswith('/'+new+'/S02.wav'))
        self.assertEqual(self.db.get_project(pid)['id'],pid)
    def test_restore_detects_tampering_and_preserves_existing(self):
        p=self.project();self.db.save_project(p)
        blob=portable_v83.package(self.root,p,[],False)
        edited=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(blob)) as zin,zipfile.ZipFile(edited,'w') as zout:
            for n in zin.namelist():zout.writestr(n,b'xxx' if n=='projekt.json' else zin.read(n))
        with self.assertRaises(Exception):portable_v83.restore_archive(self.root,self.db,edited.getvalue())
        self.assertEqual(len(self.db.list_projects()),1)
    def test_script_qa_never_claims_visual_recognition(self):
        p=self.project();r=sd.continuity_report(p)
        self.assertTrue(r['requires_human_review'])
        self.assertFalse(r['items'][0]['style_identity_verified_automatically'])

if __name__=='__main__':unittest.main()

class V84Web(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        from http.server import ThreadingHTTPServer
        from unittest.mock import patch

        import server
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.patch=patch.object(server,'ROOT',cls.root);cls.patch.start()
        cls.srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.srv.db=Store(cls.root/'data'/'studio.sqlite');cls.srv.access_token='test-v84-token'
        cls.thread=threading.Thread(target=cls.srv.serve_forever,daemon=True);cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.srv.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown();cls.thread.join(timeout=3);cls.srv.server_close();cls.patch.stop();cls.tmp.cleanup()
    def http(self,path,method='GET',body=None,contenttype=None,headers=None):
        import urllib.error
        import urllib.request
        headers={'X-Studio-Token':'test-v84-token',**(headers or {})}
        if isinstance(body,dict):body=json.dumps(body).encode();headers['Content-Type']='application/json'
        elif body is not None:headers['Content-Type']=contenttype or 'application/zip'
        request=urllib.request.Request(self.base+path,data=body,method=method,headers=headers)
        try:
            with urllib.request.urlopen(request,timeout=30) as response:return response.status,response.read()
        except urllib.error.HTTPError as error:return error.code,error.read()
    def test_api_routes_and_restore_permission(self):
        status,raw=self.http('/api/projects','POST',{'title':'V84 test','duration':180});self.assertEqual(status,201)
        pid=json.loads(raw)['project']['id']
        status,raw=self.http('/api/projects/'+pid+'/develop','POST',{'mode':'demo'});self.assertEqual(status,200)
        status,raw=self.http('/api/v84/projects/'+pid+'/story-review');self.assertEqual(status,200)
        self.assertGreater(json.loads(raw)['dialogue_count'],0)
        status,raw=self.http('/api/v84/projects/'+pid+'/render-plan');self.assertEqual(status,200)
        self.assertEqual(json.loads(raw)['new_video_jobs'],40)
        status,raw=self.http('/api/v84/projects/'+pid+'/continuity');self.assertEqual(status,200)
        self.assertTrue(json.loads(raw)['requires_human_review'])
        p=self.srv.db.get_project(pid)
        archive=portable_v83.package(self.root,p,[],False)
        self.assertEqual(self.http('/api/v84/restore','POST',archive)[0],403)
        status,raw=self.http('/api/v84/restore','POST',archive,headers={'X-Restore-Approved':'true'})
        self.assertEqual(status,201,raw[:500]);self.assertNotEqual(json.loads(raw)['project_id'],pid)
        self.assertEqual(len(self.srv.db.list_projects()),2)

def _check_voice_dialogue_change(self):
    status,raw=self.http('/api/projects','POST',{'title':'Dialog editing','duration':180});self.assertEqual(status,201)
    pid=json.loads(raw)['project']['id']
    self.http('/api/projects/'+pid+'/develop','POST',{'mode':'demo'})
    current=self.srv.db.get_project(pid)
    shot=current['shots'][1]
    self.assertTrue(shot['dialogue'])
    shot['v7_lips_approved']=True
    shot['v7_voice']={'approved':True}
    self.srv.db.save_project(current)
    status,raw=self.http('/api/projects/'+pid+'/shots/S02','PUT',{'dialogue':'Nie wierzę!','speaker':'ON','acting_direction':'spontaniczne zaskoczenie'})
    self.assertEqual(status,200,raw[:500])
    result=json.loads(raw)['project']['shots'][1]
    self.assertFalse(result['v7_lips_approved'])
    self.assertNotIn('v7_voice',result)
    self.assertEqual(result['dialogue'],'Nie wierzę!')
    status,raw=self.http('/api/projects/'+pid+'/shots/S02','PUT',{'speaker':'ONA'})
    self.assertEqual(status,409)
V84Web.test_dialogue_changes_revoke_voice_approval=_check_voice_dialogue_change
