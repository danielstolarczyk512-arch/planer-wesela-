import json
import unittest
from unittest.mock import patch

from studio import ai, engine


class AiDoctorTests(unittest.TestCase):
    def test_script_doctor_saves_draft_and_new_shots(self):
        p=engine.new_project({'duration':30})
        engine.develop_demo(p)
        original=p['script'];old_generation=p['shot_generation']
        existing=[dict(x) for x in p['shots']]
        extra=[dict(existing[0],id='S07',duration=1.5),dict(existing[1],id='S08',duration=1.5)]
        for item in existing:item['duration']=round(item['duration']*0.9,4)
        # Reallocate to exactly 30s for the revised eight-shot output
        extra[1]['duration']=round(30-sum(i['duration'] for i in existing)-extra[0]['duration'],4)
        existing+=extra
        concept=next(c for c in p['concepts'] if c['id']==p['selected_concept_id'])
        result={'script':'Poprawiony '+original,'cast':engine.CAST,'shots':[
            {k:shot[k] for k in ('id','start','duration','beat','function','dialogue','camera','prompt','mode','generation_seconds','video_model')} for shot in existing
        ]}
        review={'verdict':'Zbyt mało mocnego humoru','critical_issues':['tempo','dialogi','puenta'],'revision_directions':['Skróć dialog','Wzmocnij puentę'],'score_before':70}
        with patch.object(ai.sogni,'chat',side_effect=[(json.dumps(review),{}),(json.dumps(result),{})]) as llm:
            saved=[]
            updated=ai.script_doctor(p,lambda x:saved.append(dict(x)))
        self.assertEqual(llm.call_count,2)
        self.assertEqual(updated['script_versions'][0]['script'],original)
        self.assertEqual(updated['revisions'],1)
        self.assertNotEqual(updated['shot_generation'],old_generation)
        self.assertEqual(len(saved),2)
        self.assertEqual(updated['mode'],'sogni_ai')
    def test_doctor_limit(self):
        p=engine.new_project({});engine.develop_demo(p);p['revisions']=3
        with self.assertRaises(ValueError):ai.script_doctor(p,lambda _:None)
