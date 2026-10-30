import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio import engine, personas, sogni
from studio.store import Store

ROOT=Path(__file__).resolve().parents[1]

class TestV5Characters(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        (self.root/'assets').mkdir()
        # avoid copying full assets in tests? symlink on linux if possible.
        import shutil
        shutil.copytree(ROOT/'assets'/'starter_personas',self.root/'assets'/'starter_personas')
        self.db=Store(self.root/'db.sqlite')
        personas.seed_defaults(self.db,self.root)
    def tearDown(self):self.tmp.cleanup()
    def test_seeded_two_independent_characters_and_photos(self):
        assert len(self.db.list_personas())==2
        names=[p['name'] for p in self.db.list_personas()]
        self.assertTrue(any('Natalia' in n for n in names))
        self.assertTrue(any('Daniel' in n for n in names))
        for p in self.db.list_personas():
            self.assertIn('portrait',p['assets'])
            self.assertIn('sheet',p['assets'])
            for mode in ('front','threequarter','profile','back'):
                self.assertIn(mode,p['assets'])
                self.assertTrue((self.root/'data'/'personas'/p['id']/p['assets'][mode]).is_file())
    def test_bind_cast_keeps_leads_in_demo_shots_and_style(self):
        p=engine.new_project({'title':'V5 smoke','feature':'plan stołów','duration':30})
        engine.develop_demo(p)
        personas.bind_cast(p,self.db,{'ONA':'11111111-1111-4111-8111-111111111111','ON':'22222222-2222-4222-8222-222222222222'})
        self.assertEqual([x['id'] for x in p['cast']],['ONA','ON'])
        self.assertEqual(p['visual_style_id'],personas.STYLE_ID)
        self.assertIn('ONA',p['shots'][0]['characters'])
        v=personas.prepare_for_sogni(p,p['shots'][0])
        self.assertIn('Golden',personas.STYLE_NAME)
        self.assertIn('NOT live action',v['prompt'])
        self.assertIn('Natalia',v['prompt'])
        self.assertIn('Daniel',v['prompt'])
    def test_old_live_action_removed_at_generation(self):
        p=engine.new_project({'title':'V5','feature':'plan stołów','duration':30})
        engine.develop_demo(p)
        personas.bind_cast(p,self.db,{'ONA':'11111111-1111-4111-8111-111111111111'})
        shot=p['shots'][0]
        shot['prompt']='Cinematic realistic live action. '+ 'A couple speaking softly at home.'
        effective=personas.render_prompt(p,shot)
        self.assertNotIn('Cinematic realistic live action',effective)
        self.assertIn('stylized cinematic CGI animation',effective)
        self.assertIn('polka',effective)
    def test_reference_to_r2v_without_charge(self):
        p=engine.new_project({'title':'Test V5'})
        engine.develop_demo(p)
        female=self.db.get_persona('11111111-1111-4111-8111-111111111111')
        female['remote_reference_url']='https://example.test/reference.png'
        self.db.save_persona(female)
        personas.bind_cast(p,self.db,{'ONA':female['id']})
        output=personas.prepare_for_sogni(p,p['shots'][0])
        self.assertTrue(output['video_model'].endswith('r2v-turbo'))
        self.assertEqual(output['reference_image_urls'],[female['remote_reference_url']])
        body=sogni.workflow_body(output,False,format='9:16')
        self.assertEqual(body['billing_mode'],'subscription')
        self.assertEqual(body['token_type'],'auto')
        self.assertEqual(body['media_references'][0]['url'],female['remote_reference_url'])
        self.assertEqual(body['input']['steps'][0]['arguments']['referenceImageIndices'],[-1])
    def test_cast_switch_invalidates_previous_render(self):
        p=engine.new_project({});engine.develop_demo(p)
        p['shots'][0].update(qc_approved=True,quote={'id':'old'},workflow_id='wf_old')
        personas.bind_cast(p,self.db,{'ON':'22222222-2222-4222-8222-222222222222'})
        self.assertFalse(p['shots'][0]['qc_approved'])
        self.assertNotIn('quote',p['shots'][0]);self.assertNotIn('workflow_id',p['shots'][0])
    def test_upload_guard_model_and_cost(self):
        with self.assertRaises(sogni.ProviderError):
            sogni.subscription_guard({'billing_mode':'auto','token_type':'auto'})
        with self.assertRaises(sogni.ProviderError):
            sogni.subscription_guard({'billing_mode':'subscription'},'seedance2-5')
        with patch.object(sogni,'assert_active_subscription',side_effect=sogni.ProviderError('inactive',403)):
            with self.assertRaises(sogni.ProviderError):
                sogni.upload_reference_image(self.root/'assets'/'starter_personas'/'ona_portrait.png')
    def test_seed_idempotence_and_existing_projects(self):
        personas.seed_defaults(self.db,self.root)
        self.assertEqual(len(self.db.list_personas()),2)
        p=engine.new_project({});engine.develop_demo(p)
        self.assertEqual(len(p['shots']),6)
    def test_inconsistent_id_rejected(self):
        with self.assertRaises(ValueError):
            personas.bind_cast(engine.new_project({}),self.db,{'ONA':'00000000-0000-4000-8000-000000000000'})
    def test_four_or_more_angles_keep_identity(self):
        for person in self.db.list_personas():
            all_assets=person['assets']
            self.assertGreaterEqual(len(all_assets),10)
            self.assertIn('expression_6',all_assets)

if __name__=='__main__':unittest.main()
