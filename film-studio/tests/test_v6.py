"""V6 deterministic camera plan, input validation, safety, and import checkpoint."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio import camera360, camera360_cli, reference_v6, sogni

_ISO=None
def setUpModule():
    """Izolacja: testy nie mogą czytać ani zapisywać prawdziwych decyzji recenzji z data/references_v6."""
    global _ISO
    from studio import reference_v6 as _r
    _ISO=tempfile.TemporaryDirectory()
    _ISO.patches=[patch.object(_r,'DATA',Path(_ISO.name)),patch.object(_r,'REVIEWS',Path(_ISO.name)/'review_decisions.json')]
    for _p in _ISO.patches:_p.start()

def tearDownModule():
    for _p in _ISO.patches:_p.stop()
    _ISO.cleanup()

class TestV6References(unittest.TestCase):
    def test_all_images_are_included_and_not_autopromoted(self):
        values=reference_v6.entries()
        self.assertEqual(len(values),78)
        self.assertEqual(sum(v['category']=='PARA' for v in values),10)
        self.assertEqual(sum(v['review']=='approved' for v in values),0)
        self.assertEqual(sum(v['review']=='pending_correction' for v in values),4)
    def test_real_png_and_manifest_size(self):
        r=reference_v6.entries()[0]
        f=reference_v6.file_for(r['id'])
        self.assertTrue(f.read_bytes()[:8]==b'\x89PNG\r\n\x1a\n')
        self.assertEqual(f.stat().st_size,r['bytes'])
    def test_pending_images_do_not_autoselect(self):
        self.assertEqual(reference_v6.suggest_for_shot({'characters':['ONA','ON']}),[])
    def test_missing_and_bad_ids_fail(self):
        for ident in ['../../data/secrets','other','/etc/passwd']:
            with self.assertRaises(ValueError):reference_v6.file_for(ident)
    def test_cannot_attach_unapproved_photo(self):
        chosen=reference_v6.entries()[0]
        with self.assertRaises(ValueError):reference_v6.resolve_for_shot({'characters':['ONA'],'v6_reference_ids':[chosen['id']]})
    def test_review_persists_in_isolated_store(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(reference_v6,'DATA',Path(td)),patch.object(reference_v6,'REVIEWS',Path(td)/'decisions.json'):
                r=reference_v6.entries()[0]
                approved=reference_v6.review(r['id'],'approved','face manually checked')
                self.assertEqual(approved['review'],'approved')
                found=reference_v6.suggest_for_shot({'characters':['ONA']})
                if r['category']=='KOBIETA': self.assertTrue(found)
                other=reference_v6.entries()[-1]
                with self.assertRaises(ValueError):reference_v6.set_remote(other['id'],'https://example.org/img.png')
    def test_url_fails_open_only_if_old(self):
        self.assertEqual(reference_v6.live_url({'review':'approved','remote_url':'https://x.test/a.png','remote_synced_at':'2020-01-01T00:00:00+00:00'}),'')
    def test_restricted_roles(self):
        with self.assertRaises(ValueError):reference_v6.resolve_for_shot({'characters':['ON'],'v6_reference_ids':['KOBIETA__MASTER__01_front']})

class TestV6360(unittest.TestCase):
    def test_grid_is_96_angles(self):
        r=camera360.public_presets()
        self.assertEqual(len(r['angles']['azimuths'])*len(r['angles']['elevations'])*len(r['angles']['distances']),96)
        self.assertEqual(len(r['presets']),6)
    def test_dialogue_reveal_two_points(self):
        p=camera360.build('dialogue_reveal',{'id':'S03','characters':['ONA','ON'],'prompt':'Couple at kitchen table'})
        self.assertEqual(p['points'][1]['azimuth'],'front-right')
        self.assertEqual(p['render_policy'],'manual_review_before_sogni_subscription_only')
        self.assertTrue(p['analysis']['warnings'])
    def test_ui_rejected(self):
        with self.assertRaises(ValueError):camera360.build('dialogue_reveal',{'mode':'ui'})
    def test_more_than_64_rejected(self):
        with self.assertRaises(ValueError):camera360.build('dialogue_reveal',points=[('front','eye-level','medium')]*65)
    def test_large_jump_warning(self):
        p=camera360.build('hero_orbit',points=[('front','eye-level','medium'),('back','eye-level','medium')]);self.assertTrue(any('180°' in x for x in p['analysis']['warnings']))
    def test_unknown_angles_rejected(self):
        for k in ['rightish','360','../bad']:
            with self.assertRaises(ValueError):camera360.point(k)
    def test_recipe_stays_dry_run_and_subscription(self):
        p=camera360.build('dialogue_reveal')
        r=camera360.make_cli_recipe(p,'assets/one.png')
        self.assertTrue(r['dry_run'])
        self.assertEqual(len(r['commands']),2)
        for x in r['commands']:
            args=x['arguments'];self.assertEqual(args[args.index('--billing-mode')+1],'subscription')
            self.assertNotIn('--angles-360-video',args)
    def test_shell_injection_rejected(self):
        with self.assertRaises(ValueError):camera360.make_cli_recipe(camera360.build('dialogue_reveal'),'foo.png;touch boom')
    def test_live_requires_explicit_approval_no_network(self):
        with self.assertRaises(ValueError):camera360_cli.generate_one('id','front','eye-level','medium',False)
    def test_single_angle_command_is_hard_covered(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)
            fake=target/'sogni-agent';fake.write_text('binary')
            ref=reference_v6.entries()[0]
            original=camera360_cli.RENDERS
            class P: returncode=0;stdout='{"paymentModel":"subscription"}';stderr=''
            def fake_run(args,**kwargs):
                self.assertIn('--billing-mode',args)
                self.assertEqual(args[args.index('--billing-mode')+1],'subscription')
                self.assertIn('--multi-angle',args)
                self.assertNotIn('--angles-360',args)
                Path(args[args.index('-o')+1]).write_bytes(b'\x89PNG\r\n\x1a\n'+b'Z'*1024)
                return P()
            try:
                camera360_cli.RENDERS=target/'renders'
                with patch.object(reference_v6,'find',return_value={**ref,'review':'approved'}),\
                    patch.object(camera360_cli.shutil,'which',return_value=str(fake)),\
                    patch.object(sogni,'key',return_value='REDACTED_TEST_SECRET'),\
                    patch.object(sogni,'assert_active_subscription',return_value={'active':True}),\
                    patch.object(camera360_cli.subprocess,'run',side_effect=fake_run):
                    result=camera360_cli.generate_one(ref['id'],'front-right','eye-level','medium',True)
                self.assertEqual(result['payment_model_reported'],'subscription')
                self.assertFalse(result['qc_approved'])
            finally:camera360_cli.RENDERS=original

if __name__=='__main__':unittest.main()
