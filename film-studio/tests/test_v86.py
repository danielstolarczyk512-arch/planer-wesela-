"""V8.6: real Boguś assets, safe role isolation, actual media audit (offline)."""
import hashlib
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
from studio import engine, personas, reference_v6, rendered_inspector_v86
from studio.store import Store

ROOT=Path(__file__).resolve().parent.parent

class CharacterV86(unittest.TestCase):
    def test_original_bundle_images_exact(self):
        rows=[r for r in reference_v6.entries() if r['category']=='WUJEK']
        self.assertEqual(len(rows),18)
        self.assertEqual(len(reference_v6.entries()),78)
        self.assertEqual(len([r for r in reference_v6.entries() if r['category']!='WUJEK']),60)
        for r in rows:
            file=reference_v6.file_for(r['id'])
            self.assertEqual(file.stat().st_size,r['bytes'])
            self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),r['sha256'])
            self.assertNotEqual(r['review'],'approved')
    def test_canonical_persona_is_the_original_bogus(self):
        p=personas.BOGUS_PERSONA
        self.assertEqual(p['role'],'WUJEK')
        self.assertIn('plum',p['look'].lower())
        self.assertIn('moustache',p['look'].lower())
        self.assertIn('Bogdan',p['name'])
        self.assertIn('Never transfer',p['look'])
    def test_boot_seed_idempotent_and_role(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);folder=root/'assets/starter_personas';folder.mkdir(parents=True)
            shutil.copy2(ROOT/'assets/starter_personas/wujek_portrait.png',folder/'wujek_portrait.png')
            db=Store(root/'a.sqlite3')
            personas.seed_wujek(db,root);personas.seed_wujek(db,root)
            self.assertEqual(db.get_persona(personas.BOGUS_ID)['role'],'WUJEK')
            self.assertEqual(db.get_persona(personas.BOGUS_ID)['assets']['portrait'],'portrait.png')
            self.assertEqual(sum(p['id']==personas.BOGUS_ID for p in db.list_personas()),1)
    def test_bogus_not_silently_approved(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(reference_v6,'REVIEWS',Path(td)/'review.json'):
                self.assertFalse(reference_v6.suggest_for_shot({'characters':['WUJEK']}))
                with self.assertRaisesRegex(ValueError,'nie jest zatwierdzona'):
                    reference_v6.resolve_for_shot({'characters':['WUJEK'],'v6_reference_ids':['WUJEK__PORTRAIT']})
    def test_three_cast_safe_order_and_isolation(self):
        overrides={r['id']:{'review':'approved'} for r in reference_v6.entries()}
        with patch.object(reference_v6,'_decisions',return_value=overrides):
            shot={'characters':['ONA','ON','WUJEK'],'prompt':'A comical uncle joins the wedding couple','mode':'t2v'}
            chosen=reference_v6.resolve_for_shot(shot)
            self.assertEqual({r['category'] for r in chosen},{'KOBIETA','MEZCZYZNA','WUJEK'})
            self.assertTrue(reference_v6.review_safety(shot)['ready'])
            self.assertIn('LONG narrow face',reference_v6.prepare_prompt({},shot))
            with self.assertRaisesRegex(ValueError,'nie pasuje do obsady'):
                reference_v6.resolve_for_shot({'characters':['ON'],'v6_reference_ids':['WUJEK__PORTRAIT']})
    def test_tamper_sha_before_review(self):
        row=next(r for r in reference_v6.entries() if r['category']=='WUJEK')
        with tempfile.TemporaryDirectory() as td:
            fake=Path(td)/'forgery.png';fake.write_bytes(b'not your uncle')
            with patch.object(reference_v6,'_catalog',return_value={'items':[dict(row,path='forgery.png',bytes=len(fake.read_bytes()))]}),\
                 patch.object(reference_v6,'ASSETS',Path(td)),\
                 patch.object(reference_v6,'REVIEWS',Path(td)/'d.json'):
                with self.assertRaisesRegex(ValueError,'SHA-256'):reference_v6.review(row['id'],'approved')
    def test_dry_run_camera_and_audio_speakers(self):
        from studio import dialogue_v7, timeline_v85, voice_v8
        self.assertIn('WUJEK',timeline_v85.SPEAKERS)
        self.assertIn('WUJEK',dialogue_v7.SPEAKERS)
        v=voice_v8.build_variants_request('Ja tylko jedną rzecz podpowiem...','comic','WUJEK')
        self.assertEqual(v['speaker'],'WUJEK')
    def test_three_people_with_style_fits_4_references_not_more(self):
        cast=[{'id':r,'reference_url':'https://example.test/'+r+'.png'} for r in ('ONA','ON','WUJEK')]
        shot={'characters':['ONA','ON','WUJEK'],'reference_image_urls':[]}
        p={'cast':cast}
        self.assertEqual(len(personas.shot_provider_refs(p,shot,'https://example.test/style.png')),4)
        shot['reference_image_urls']=['https://example.test/extra.png']
        with self.assertRaisesRegex(ValueError,'Zbyt wiele referencji'):
            personas.shot_provider_refs(p,shot,'https://example.test/style.png')
    def test_role_mismatch_cannot_cast_uncle_as_male_lead(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=Store(root/'db.sqlite3')
            uncle=personas.new_persona(personas.BOGUS_PERSONA);uncle['id']=personas.BOGUS_ID
            db.save_persona(uncle)
            with self.assertRaisesRegex(ValueError,'przypisanie roli'):
                personas.selected_cast(db,{'ON':personas.BOGUS_ID})

    def test_legacy_cast_not_replaced_automatically(self):
        self.assertEqual({x['id'] for x in engine.CAST},{'ONA','ON'})

@unittest.skipUnless(shutil.which('ffprobe') and shutil.which('ffmpeg'),'ffmpeg missing')
class FilmV86(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.mp4=self.root/'film.mp4'
        subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-f','lavfi','-i','color=c=black:s=320x568:r=24:d=3',
                        '-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=48000',
                        '-shortest','-t','3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(self.mp4)],
                        check=True,timeout=30)
    def test_full_film_inspector_actual_mp4(self):
        r=rendered_inspector_v86.inspect(self.mp4,planned_duration=20)
        self.assertAlmostEqual(r['media']['duration'],3,delta=.1)
        self.assertEqual(r['media']['width'],320)
        self.assertGreaterEqual(r['motion']['static_percent'],90)
        self.assertIn('duration',{x['type'] for x in r['warnings']})
        self.assertEqual(r['external_requests'],0)
        self.assertIn('naturalność polskiej mowy',r['not_verified'])
    def test_corrupt_non_mp4_rejected(self):
        junk=self.root/'malware.mp4';junk.write_bytes(b'bad'*1000)
        with self.assertRaises(ValueError):rendered_inspector_v86.inspect(junk)
    def test_offline_server_upload_and_retrieve_with_explicit_consent(self):
        db=Store(self.root/'db.sqlite3');proj=engine.new_project({'title':'V86','duration':20});db.save_project(proj)
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        http.db=db;http.access_token='local-test-v86'
        original_root=server.ROOT
        server.ROOT=self.root
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        self.addCleanup(lambda:(http.shutdown(),http.server_close(),thread.join(),setattr(server,'ROOT',original_root)))
        origin='http://127.0.0.1:'+str(http.server_port)
        def request(path,method='GET',data=None,headers=None):
            h={'X-Studio-Token':'local-test-v86'};h.update(headers or {})
            req=urllib.request.Request(origin+path,method=method,data=data,headers=h)
            try:
                with urllib.request.urlopen(req,timeout=35) as r:return r.status,json.loads(r.read())
            except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
        status,data=request('/api/v86');self.assertEqual(status,200)
        self.assertEqual(data['uncle']['reference_count'],18)
        path='/api/v86/projects/'+proj['id']+'/film'
        s,data=request(path,'PUT',self.mp4.read_bytes(),{'Content-Type':'video/mp4'})
        self.assertEqual(s,403)
        s,data=request(path,'PUT',self.mp4.read_bytes(),{'Content-Type':'video/mp4','X-Film-Review-Consent':'true'})
        self.assertEqual(s,201)
        self.assertEqual(data['report']['external_requests'],0)
        s,data=request(path);self.assertEqual(s,200);self.assertTrue(data['uploaded'])
        self.assertTrue(rendered_inspector_v86.movie_file(self.root,proj['id']).exists())

if __name__=='__main__':unittest.main()
