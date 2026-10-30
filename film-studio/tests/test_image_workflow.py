import unittest
from unittest.mock import patch

from studio import sogni


class ImageWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.plan_patcher=patch.object(sogni,'assert_active_subscription',return_value={'active':True})
        self.plan_patcher.start();self.addCleanup(self.plan_patcher.stop)
        self.shot={'id':'S01','mode':'t2v','prompt':'Cinematic portrait of a fictional young couple planning their wedding at an elegant wedding table, soft daylight, 85mm lens', 'generation_seconds':5.2,'video_model':'minimax-h3-fasth3-t2v-turbo'}
    def test_image_quote_is_strictly_offline(self):
        with patch.object(sogni,'request',side_effect=AssertionError('no remote estimate allowed')) as transport:
            result=sogni.estimate_image(self.shot)
        self.assertIsNone(result['estimated_capacity'])
        self.assertEqual(result['source'],'local_preflight')
        transport.assert_not_called()
        body=sogni.image_body(self.shot,False)
        self.assertFalse(body['confirm_cost'])
        self.assertEqual(body['input']['steps'][0]['toolName'],'generate_image')
    def test_i2v_source_image_is_required(self):
        shot=dict(self.shot,video_model='minimax-h3-fasth3-i2v-turbo')
        with self.assertRaises(sogni.ProviderError):sogni.workflow_body(shot)
        shot['image_url']='https://assets.example.org/keyframe.png'
        body=sogni.workflow_body(shot,False)
        step=body['input']['steps'][0]
        self.assertEqual(step['toolName'],'animate_photo')
        self.assertEqual(step['arguments']['sourceImageIndex'],-1)
        self.assertEqual(body['media_references'][0]['kind'],'image')
