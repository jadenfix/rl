"""Actual Docker training and persisted-checkpoint restart; no cloud services."""
import http.client
import json
from pathlib import Path
import subprocess
import time
import uuid


def docker(*arguments, check=True):
    return subprocess.run(['docker', *arguments], check=check, capture_output=True, text=True, timeout=120)


def request(port, method, route, payload=None):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        connection.request(method, route, body=json.dumps(payload) if payload is not None else None,
                           headers={'Content-Type':'application/json'})
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def main():
    identity = 'rlaas-trainer-' + uuid.uuid4().hex[:12]
    volume = identity + '-state'
    docker('volume', 'create', volume)
    try:
        docker('run', '-d', '--name', identity, '--read-only', '--cap-drop=ALL',
               '--security-opt=no-new-privileges', '--tmpfs', '/tmp', '-v', volume+':/data',
               '-p', '127.0.0.1::8090', 'rlaas-trainer:test')
        port = int(docker('port', identity, '8090').stdout.strip().rsplit(':',1)[1])
        def ready():
            for _ in range(100):
                try:
                    status, body = request(port, 'GET', '/healthz')
                    if status == 200: return body
                except OSError: pass
                time.sleep(0.1)
            raise RuntimeError('container did not become healthy: '+docker('logs',identity,check=False).stdout)
        assert ready()['model_ready'] is False
        preferences = json.loads(Path('apps/trainer/examples/preferences.json').read_text())
        status, trained = request(port, 'POST', '/v1/train', {'pairs':preferences})
        assert status == 200 and trained['training']['final_loss'] < trained['training']['initial_loss']
        payload = {'prompt':'warranty replacement','response':'warranty replacement Please review the requested details.'}
        status, before = request(port, 'POST', '/v1/score', payload)
        assert status == 200
        docker('restart', identity)
        assert ready()['model_ready'] is True
        assert request(port, 'POST', '/v1/score', payload) == (200, before)
        # The on-disk artifact agrees with the measured train response.
        checkpoint = json.loads(docker('exec',identity,'cat','/data/reward-model.json').stdout)
        assert checkpoint == trained
        print(json.dumps({'docker_restart_score':before,'training':trained['training'],'checkpoint_matches':True}, sort_keys=True))
    finally:
        docker('rm','-f',identity,check=False)
        docker('volume','rm',volume,check=False)


if __name__ == '__main__': main()
