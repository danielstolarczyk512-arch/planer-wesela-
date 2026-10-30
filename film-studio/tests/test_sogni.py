import os
import unittest
from unittest.mock import patch

from studio import sogni


class SogniTests(unittest.TestCase):
    def setUp(self):
        self.plan_patcher=patch.object(sogni,'assert_active_subscription',return_value={'active':True})
        self.plan_patcher.start();self.addCleanup(self.plan_patcher.stop)
        self.shot={'id':'S01','mode':'t2v','prompt':'A cinematic realistic couple planning a wedding at a table, gentle camera push, stable hands and faces.', 'video_model':'minimax-h3-fasth3-t2v-turbo','generation_seconds':5.2}
    def test_text_requests_disable_media_tools(self):
        with patch.object(sogni,'request',return_value=(200,{'choices':[{'message':{'content':'{"ok":true}'}}],'usage':{'total_tokens':42}})) as transport:
            res,usage=sogni.chat('prompt','question')
            body=transport.call_args.args[2]
            self.assertEqual(body['sogni_tools'],False)
            self.assertEqual(body['sogni_tool_execution'],False)
            self.assertEqual(usage['total_tokens'],42)
    def test_quote_is_strictly_local_no_execution_risk(self):
        with patch.object(sogni,'request',side_effect=AssertionError('no remote preflight')) as transport:
            q=sogni.estimate(self.shot)
        self.assertIsNone(q['estimated_capacity'])
        self.assertEqual(q['source'],'local_preflight')
        transport.assert_not_called()
    def test_paid_request_is_bounded_and_idempotent(self):
        with patch.object(sogni,'request',return_value=(201,{'data':{'workflow':{'workflowId':'wf_123','status':'queued'}}})) as transport:
            r=sogni.start_render(self.shot,12.5,'f30dfe03-9a1f-4aa3-924e-2fa199a','9:16')
            self.assertEqual(r['workflowId'],'wf_123')
            b=transport.call_args.args[2]
            self.assertTrue(b['confirm_cost'])
            self.assertEqual(b['max_estimated_capacity_units'],12.5)
            self.assertIn('Idempotency-Key',transport.call_args.kwargs['extra_headers'])
    def test_paid_request_rejects_bad_shot(self):
        x=self.shot.copy();x['mode']='ui'
        with self.assertRaises(sogni.ProviderError):sogni.workflow_body(x)
        x=self.shot.copy();x['video_model']='evil-model'
        with self.assertRaises(sogni.ProviderError):sogni.workflow_body(x)
        x=self.shot.copy();x['reference_image_urls']=['http://insecure.example/image.jpg']
        with self.assertRaises(sogni.ProviderError):sogni.workflow_body(x)
    def test_no_key_rejected(self):
        with patch.dict(os.environ,{'SOGNI_API_KEY':''}):
            with self.assertRaises(sogni.ProviderError):sogni.request('GET','/v2/account/me')
