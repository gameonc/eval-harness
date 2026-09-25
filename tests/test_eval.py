import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import eval_harness as h

ROOT = Path(__file__).resolve().parents[1]

class EvaluationTests(unittest.TestCase):
    def test_known_confusion_matrix(self):
        m = h.evaluate([('fraud', .9), ('fraud', .1), ('legit', .7), ('legit', .2)])
        self.assertEqual([m[k] for k in ('tp','fn','fp','tn')], [1,1,1,1])
        self.assertEqual(m['recall'],50)
    def test_reject_invalid_scores(self):
        for x in ('nan','inf','-inf',-1,1.1,True,None,'bad'):
            with self.subTest(x=x), self.assertRaises(ValueError): h.probability(x)
    def test_boundary_score(self):
        self.assertEqual(h.evaluate([('fraud',.5)],.5)['tp'],1)
    def test_undefined_is_null(self):
        m=h.evaluate([('legit',0)])
        self.assertIsNone(m['recall']); self.assertIsNone(m['precision'])
        json.dumps(m,allow_nan=False)
    def test_coverage(self):
        m=h.run([{'actual_outcome':'fraud','risk_score':'.9'},{'actual_outcome':'legit','risk_score':''}],.5)
        self.assertEqual(m['coverage'],50);self.assertEqual(m['unscorable'],1)
    def test_invalid_label_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.csv'; p.write_text('actual_outcome,risk_score\nunknown,.4\n')
            with self.assertRaises(ValueError): h.read_rows(p)
    def test_duplicate_headers_and_extra_fields(self):
        for text in ('actual_outcome,risk_score,risk_score\nfraud,.2,.3\n','actual_outcome,risk_score\nfraud,.2,extra\n'):
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'bad.csv';p.write_text(text)
                with self.assertRaises(ValueError):h.read_rows(p)
    def test_webhook_url_boundaries(self):
        for url in ('http://example.com','https://user:pass@example.com','https://example.com?token=x','file:///tmp/a'):
            with self.assertRaises(ValueError):h.validate_webhook(url)
    def test_redirect_denied(self):
        self.assertIsNone(h.NoRedirect().redirect_request(None,None,302,'',{},'https://evil.example'))
    def test_malformed_upstream(self):
        for raw in (b'[]',b'{"risk_score":"nan"}',b'{"confidence":0.9}',b'bad',b'x'*65537):
            with patch('urllib.request.OpenerDirector.open',return_value=io.BytesIO(raw)):
                self.assertIsNone(h.score_carrier({},'https://example.test/score'))
    def test_upstream_timeout(self):
        with patch('urllib.request.OpenerDirector.open',side_effect=TimeoutError):
            self.assertIsNone(h.score_carrier({},'https://example.test/score'))
    def test_webhook_success_minimum_payload(self):
        with patch('urllib.request.OpenerDirector.open',return_value=io.BytesIO(b'{"risk_score":0.7}')) as call:
            self.assertEqual(h.score_carrier({'notes':'private','carrier_name':'Fictional'},'https://example.test/score'),.7)
            self.assertNotIn('notes',json.loads(call.call_args.args[0].data))
    def test_offline_cli(self):
        r=subprocess.run([sys.executable,str(ROOT/'eval_harness.py'),str(ROOT/'examples/synthetic.csv'),'--json','--sweep'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        m=json.loads(r.stdout);self.assertEqual(m['total'],20);self.assertEqual(len(m['threshold_sweep']),19)
    def test_no_scored_rows_exit_one(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'empty.csv';p.write_text('actual_outcome,risk_score\n')
            r=subprocess.run([sys.executable,str(ROOT/'eval_harness.py'),str(p),'--json'],capture_output=True,text=True)
            self.assertEqual(r.returncode,1);self.assertEqual(json.loads(r.stdout)['coverage'],0)

if __name__=='__main__':unittest.main()
