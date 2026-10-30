import unittest

from studio import ai, engine


class EngineTests(unittest.TestCase):
    def setUp(self):self.p=engine.new_project({'title':'Test','idea':'Zaplanuj z humorem wesele','duration':30,'feature':'plan stołów'})
    def test_ten_concepts_two_reviewers(self):
        engine.develop_demo(self.p)
        self.assertEqual(len(self.p['concepts']),10)
        self.assertEqual(len(self.p['reviews']),10)
        self.assertTrue(all(len(x['reviews'])==2 for x in self.p['reviews']))
        self.assertEqual(self.p['mode'],'demo')
        self.assertEqual(self.p['selected_concept_id'],'C01')
    def test_timeline_and_product_truth(self):
        engine.develop_demo(self.p)
        self.assertAlmostEqual(sum(s['duration'] for s in self.p['shots']),30,places=2)
        self.assertTrue(any(s['mode']=='ui' for s in self.p['shots']))
        self.assertTrue(any(s['mode']=='overlay' for s in self.p['shots']))
        self.assertIn('Funkcje produktu',engine.validate_story(self.p)[0])
        self.p['claims_approved']=True
        self.assertEqual(engine.validate_story(self.p),[])
    def test_variant_duration(self):
        for d in (15,30,45,60):
            p=engine.new_project({'duration':d})
            engine.develop_demo(p)
            self.assertAlmostEqual(sum(s['duration'] for s in p['shots']),d,places=2)
    def test_switch_concepts(self):
        engine.develop_demo(self.p)
        engine.select_demo(self.p,'C02')
        self.assertEqual(self.p['selected_concept_id'],'C02')
        self.assertIn('Kontrola budżetu',self.p['script'])
        with self.assertRaises(ValueError):engine.select_demo(self.p,'CXX')
    def test_parse_json(self):
        self.assertEqual(ai.parse_json('```json\n{"abc": 1}\n```')['abc'],1)
        with self.assertRaises(ValueError):ai.parse_json('fake')
    def test_ranges_and_review_scores(self):
        engine.develop_demo(self.p)
        for c in self.p['reviews']:
            for r in c['reviews']:
                self.assertEqual(sum(r['scores'].values()),r['total'])
                for key,v in r['scores'].items():self.assertLessEqual(v,engine.WEIGHTS[key])
