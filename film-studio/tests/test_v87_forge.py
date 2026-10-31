"""Testy kreatora referencji V8.7 — bez wywołań Sogni (sieć zablokowana atrapami)."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from studio import reference_forge_v87 as F
from studio import sogni

OK = {'sparkSpent': 0, 'paidSparkSpent': 0, 'spark_net': 25.0, 'sogni_net': 0.0, 'fair_limited': False, 'fair_daily_pct': 1}


class Forge(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = patch.object(F, 'ROOT', self.tmp / 'forge')
        self.root.start()
        self.img = self.tmp / 'a.png'
        Image.new('RGB', (64, 64), 'red').save(self.img)

    def tearDown(self):
        self.root.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_and_validation(self):
        m = F.create('character', 'Ona Żółć', 'Kobieta około trzydziestki, brązowe włosy w kok, piegi', 'realistic', [self.img])
        self.assertTrue(m['id'].startswith('ona_zolc'))
        self.assertEqual(len(m['sources']), 1)
        with self.assertRaises(ValueError):
            F.create('animal', 'x', 'opis opisowy opisany', 'realistic')
        with self.assertRaises(ValueError):
            F.create('character', 'x', 'za krótki', 'realistic')
        with self.assertRaises(ValueError):
            F.create('character', 'x', 'opis opisowy opisany', 'comic')
        with self.assertRaises(ValueError):
            F.create('character', 'x', 'opis opisowy opisany', 'realistic', [self.img] * 4)

    def test_prompts_style_and_anchor(self):
        m = F.create('character', 'Jan', 'Mężczyzna, krótkie brązowe włosy, ciemny T-shirt', 'realistic', [self.img])
        self.assertIn('Photorealistic', F.view_prompt(m, 'front'))
        self.assertIn('NOT animated', F.view_prompt(m, 'front'))
        m['anchor'] = 'front_a.png'
        self.assertIn('APPROVED anchor', F.view_prompt(m, 'profile'))
        a = F.create('location', 'Sala', 'Sala weselna z żyrandolami i okrągłymi stołami', 'animated')
        self.assertIn('NOT photorealistic', F.view_prompt(a, 'wide_evening'))
        self.assertIn('No people', F.view_prompt(a, 'detail'))
        self.assertEqual(len(F.CHARACTER_VIEWS), 8)
        self.assertEqual(len(F.LOCATION_VIEWS), 6)

    def test_body_is_subscription_only(self):
        b = F.build_body('k', 'prompt ' * 10, ['https://x/1.png'], (768, 1024))
        self.assertEqual(b['billing_mode'], 'subscription')
        self.assertEqual(b['token_type'], 'auto')
        self.assertFalse(b['confirm_cost'])
        self.assertEqual(b['input']['steps'][0]['toolName'], 'edit_image')
        self.assertEqual(F.build_body('k', 'prompt ' * 10, [], (768, 1024))['input']['steps'][0]['toolName'], 'generate_image')
        with self.assertRaises(sogni.ProviderError):
            F.build_body('k', 'p' * 40, ['http://x/1.png'], (1, 1))

    def test_set_requires_anchor_and_approval_needs_confirmation(self):
        m = F.create('character', 'Ola', 'Kobieta, okrągła twarz, duże oczy, kok z okularami', 'realistic', [self.img])
        with patch.object(F, 'usage_snapshot', return_value=OK), self.assertRaises(F.HaltError):
            F.generate(m['id'], ['profile'])
        d = F.ROOT / m['id']
        (d / 'front_a.png').write_bytes(self.img.read_bytes())
        meta = json.loads((d / 'meta.json').read_text(encoding='utf8'))
        meta['images']['front_a'] = {'file': 'front_a.png', 'view': 'front', 'sha256': hashlib.sha256(self.img.read_bytes()).hexdigest(), 'created': 'x'}
        (d / 'meta.json').write_text(json.dumps(meta), encoding='utf8')
        with self.assertRaises(PermissionError):
            F.approve(m['id'], 'front_a')
        out = F.approve(m['id'], 'front_a', viewed_confirmed=True)
        self.assertEqual(out['anchor'], 'front_a.png')
        (d / 'front_a.png').write_bytes(b'zmienione')
        with self.assertRaises(ValueError):
            F.approve(m['id'], 'front_a', viewed_confirmed=True)
        man = F.manifest(m['id'])
        self.assertFalse(man['complete'])
        self.assertEqual(len(man['missing_views']), 7)

    def test_halt_on_cost_increase_and_fair_use(self):
        b = {'sparkSpent': 0, 'paidSparkSpent': 0, 'spark_net': 25.0, 'sogni_net': 0.0}
        with self.assertRaises(F.HaltError):
            F.assert_free(b, b | {'paidSparkSpent': 1}, 'x')
        with self.assertRaises(F.HaltError):
            F.assert_free(b, b | {'spark_net': 24.0}, 'x')
        with patch.object(F, 'usage_snapshot', return_value={'fair_limited': False, 'fair_daily_pct': 95}), self.assertRaises(F.HaltError):
            F.gate()


class ForgeApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        from http.server import ThreadingHTTPServer

        import server
        from studio.store import Store
        cls.tmp = Path(tempfile.mkdtemp())
        cls.p1 = patch.object(F, 'ROOT', cls.tmp / 'forge')
        cls.p1.start()
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.httpd.db = Store(cls.tmp / 'studio.sqlite')
        cls.httpd.access_token = 'tok'
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.httpd.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.thread.join(timeout=5)
        cls.httpd.server_close()
        cls.p1.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def http(self, path, method='GET', body=None):
        import urllib.error
        import urllib.request
        h = {'X-Studio-Token': 'tok'}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h['Content-Type'] = 'application/json'
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base + path, data=data, method=method, headers=h), timeout=20) as r:
                return r.status, json.loads(r.read() or b'{}')
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b'{}')

    def test_flow_without_sogni(self):
        self.assertEqual(self.http('/api/v87/forge')[1]['billing_mode'], 'subscription_only')
        st, body = self.http('/api/v87/forge', 'POST', {'kind': 'location', 'name': 'Sala testowa', 'description': 'Sala weselna z żyrandolami i stołami', 'style': 'realistic'})
        self.assertEqual(st, 201)
        eid = body['id']
        self.assertEqual(self.http('/api/v87/forge', 'POST', {'kind': 'x', 'name': 'a', 'description': 'długi opis opisowy'})[0], 400)
        self.assertEqual(self.http(f'/api/v87/forge/{eid}/generate', 'POST', {'views': ['wide_evening']})[0], 428)
        self.assertEqual(self.http(f'/api/v87/forge/{eid}/approve', 'POST', {'image': 'wide_evening_a'})[0], 403)
        self.assertEqual(self.http(f'/api/v87/forge/{eid}/approve', 'POST', {'image': 'wide_evening_a', 'viewed': True})[0], 404)
        self.assertEqual(self.http('/api/v87/forge/nie_ma')[0], 404)
        self.assertEqual(self.http(f'/api/v87/forge/{eid}')[1]['views'][0]['id'], 'wide_evening')


if __name__ == '__main__':
    unittest.main()
