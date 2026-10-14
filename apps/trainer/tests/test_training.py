import http.client
import json
import math
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from apps.trainer.app import model

ROOT = Path(__file__).resolve().parents[3]
DATA = json.loads((ROOT / 'apps/trainer/examples/preferences.json').read_text())


class TrainingTests(unittest.TestCase):
    def test_optimizer_and_unseen_preference(self):
        trained = model.train(DATA)
        self.assertAlmostEqual(trained['training']['initial_loss'], math.log(2))
        self.assertLess(trained['training']['final_loss'], 0.1)
        self.assertTrue(any(trained['weights']))
        good = model.score(trained, 'warranty replacement', 'warranty replacement Please review the requested details.')
        bad = model.score(trained, 'warranty replacement', 'unrelated unrelated unrelated!')
        self.assertGreater(good['reward'], bad['reward'])
        # One true optimizer step independently derived from the zero-margin derivative.
        delta = [a-b for a,b in zip(model.features(DATA[0]['prompt'], DATA[0]['chosen']),
                                   model.features(DATA[0]['prompt'], DATA[0]['rejected']))]
        one = model.train([DATA[0], DATA[0]], epochs=1, learning_rate=0.25)
        for expected, actual in zip(delta, one['weights']):
            self.assertAlmostEqual(actual, 0.125 * expected)

    def test_checkpoint_reload_and_failed_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'model.json'
            trained = model.train(DATA)
            model.save(path, trained)
            self.assertEqual(model.load(path), trained)
            before = path.read_bytes()
            with patch('apps.trainer.app.model.os.replace', side_effect=OSError('disk unavailable')):
                with self.assertRaises(OSError):
                    model.save(path, model.train(DATA, epochs=1))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(directory).iterdir()), [path])
            path.write_text('{broken')
            with self.assertRaises(ValueError):
                model.load(path)

    def test_validation(self):
        for data in [[], [DATA[0]], [dict(DATA[0], extra=True)]*2,
                     [{'prompt':'p','chosen':'same','rejected':'same'}]*2,
                     [dict(DATA[0], prompt='x'*2001)]*2]:
            with self.assertRaises(ValueError): model.train(data)
        for epochs in [True, 0, 2001, 1.5]:
            with self.assertRaises(ValueError): model.train(DATA, epochs=epochs)
        for rate in [True, float('nan'), float('inf'), 0, 3]:
            with self.assertRaises(ValueError): model.train(DATA, learning_rate=rate)
        valid = model.train(DATA)
        for weights in [[0], [float('nan')]*5, [True]*5]:
            with self.assertRaises(ValueError): model.validate_model(dict(valid, weights=weights))

    def test_cli_reload_and_corruption_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory)/'model.json'
            base = [sys.executable, '-m', 'apps.trainer.app.main', '--checkpoint', str(checkpoint)]
            run = subprocess.run(base+['train','--dataset',str(ROOT/'apps/trainer/examples/preferences.json')], cwd=ROOT, capture_output=True, text=True, check=True)
            trained = json.loads(run.stdout)
            run = subprocess.run(base+['score','--prompt','billing','--response','billing receipt'], cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(run.stdout), model.score(trained, 'billing', 'billing receipt'))
            checkpoint.write_text('{}')
            run = subprocess.run(base+['serve','--port','0'], cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('invalid checkpoint', run.stderr)


class HttpTests(unittest.TestCase):
    def start(self, checkpoint):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
        process = subprocess.Popen([sys.executable,'-m','apps.trainer.app.main','--checkpoint',str(checkpoint),'serve','--port',str(port)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.addCleanup(lambda: self.stop(process))
        for _ in range(100):
            if process.poll() is not None:
                self.fail(process.stderr.read().decode())
            try:
                self.request(port, 'GET','/healthz'); return process, port
            except OSError: time.sleep(0.02)
        self.fail('server did not become ready')

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.terminate(); process.wait(timeout=5)
        if process.stderr: process.stderr.close()

    @staticmethod
    def request(port, method, path, payload=None, raw=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1',port,timeout=5)
        body = json.dumps(payload).encode() if raw is None and payload is not None else raw
        connection.request(method,path,body=body,headers=headers or {'Content-Type':'application/json'})
        response=connection.getresponse(); content=response.read(); status=response.status
        connection.close()
        return status, content

    def test_http_train_score_restart_errors_and_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            checkpoint=Path(directory)/'reward.json'
            process, port=self.start(checkpoint)
            score={'prompt':'warranty replacement','response':'warranty replacement Please review the requested details.'}
            self.assertEqual(self.request(port,'POST','/v1/score',score)[0],503)
            status, body=self.request(port,'POST','/v1/train',{'pairs':DATA})
            self.assertEqual(status,200); trained=json.loads(body)
            self.assertLess(trained['training']['final_loss'],trained['training']['initial_loss'])
            status, before=self.request(port,'POST','/v1/score',score); self.assertEqual(status,200)
            self.assertEqual(json.loads(before),model.score(model.load(checkpoint),**score))
            self.assertEqual(self.request(port,'POST','/v1/train',{'pairs':DATA,'epochs':False})[0],422)
            self.assertEqual(self.request(port,'POST','/v1/score',dict(score,extra=1))[0],422)
            self.assertEqual(self.request(port,'POST','/v1/train',raw=b'{')[0],400)
            self.assertEqual(self.request(port,'POST','/v1/train',raw=b'\xff')[0],400)
            self.assertEqual(self.request(port,'POST','/v1/train',raw=b'{}',headers={'Content-Type':'text/plain'})[0],415)
            self.assertEqual(self.request(port,'POST','/v1/train',raw=b'',headers={'Content-Type':'application/json','Content-Length':'2000001'})[0],413)
            self.assertEqual(self.request(port,'GET','/no-such-route')[0],404)
            self.assertIn(b'trainer_training_runs_total 1',self.request(port,'GET','/metrics')[1])
            self.stop(process)
            process, port=self.start(checkpoint)
            self.assertEqual(self.request(port,'POST','/v1/score',score),(200,before))
            # Failed durable writes cannot replace the serving model or return success.
            checkpoint.unlink(); checkpoint.mkdir()
            self.assertEqual(self.request(port,'POST','/v1/train',{'pairs':DATA,'epochs':1})[0],503)
            self.assertEqual(self.request(port,'POST','/v1/score',score),(200,before))


if __name__ == '__main__': unittest.main()
