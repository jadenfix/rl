# Preference reward trainer

This service now trains and serves a small **linear Bradley–Terry reward model**
from explicit `(prompt, chosen, rejected)` preferences. It performs real batch
gradient descent on pairwise logistic loss. Its five transparent features are
prompt-word overlap, bounded response length, vocabulary diversity, and the
presence of question/exclamation marks. It uses only the Python standard library.

This is a measurable CPU baseline, not LoRA, SFT, DPO, a language generator, or
an enterprise reward judge. The bundled eight preferences are **synthetic**;
training preference accuracy is an in-sample fit, not evidence of user satisfaction,
safety, business lift, or general language quality. Feature gaming and preference
bias remain serious limits. The separate edit-similarity reward endpoint and its
existing demo retain their original algorithm and outputs.

## Train, reload and score

From the repository root, with Python 3.12:

```bash
python -m apps.trainer.app.main --checkpoint /tmp/rlaas-model.json train --dataset apps/trainer/examples/preferences.json
python -m apps.trainer.app.main --checkpoint /tmp/rlaas-model.json score --prompt 'warranty replacement' --response 'warranty replacement Please review the requested details.'
python -m apps.trainer.app.main --checkpoint /tmp/rlaas-model.json serve --port 8090
```

Training prints the actual initial/final loss, weights, update count, training
preference accuracy and dataset SHA-256. A checkpoint is written by an atomic
same-directory replacement with file/directory fsync on POSIX. A new process loads
that model without retraining. Invalid existing checkpoints fail startup.

## Local HTTP workflow

```bash
curl -fsS http://127.0.0.1:8090/healthz
python -c 'import json; print(json.dumps({"pairs": json.load(open("apps/trainer/examples/preferences.json"))}))' > /tmp/preferences-request.json
curl -fsS -H 'Content-Type: application/json' --data-binary @/tmp/preferences-request.json http://127.0.0.1:8090/v1/train
curl -fsS -H 'Content-Type: application/json' -d '{"prompt":"invoice refund","response":"invoice refund Please review the requested details."}' http://127.0.0.1:8090/v1/score
curl -fsS http://127.0.0.1:8090/v1/model
curl -fsS http://127.0.0.1:8090/metrics
```

`/v1/train` accepts 2–256 validated preferences, 1–2000 epochs and a finite
learning rate in `(0,2]`. Requests have a 2 MB body cap, 2000-character text cap,
5-second socket read deadline and closed connections. Unknown fields, malformed
JSON, indistinguishable preferences and invalid hyperparameters are rejected.
Scoring before training returns 503, not an invented reward. Failed checkpoint
writes return 503 and keep the existing in-memory model. Metrics report actual
process-local requests and completed training calls; counters reset on restart.
Training is synchronous and serialized with scoring, suitable for this bounded
local baseline only.

The CLI server defaults to loopback. Docker Compose publishes only
`127.0.0.1:8090` and persists checkpoints in the `trainer-data` volume. The internal
Docker listener is unauthenticated: do not expose it to untrusted networks or use
it as a tenant service. Authenticated tenant isolation, remote training workers,
TRL/PEFT, GPU models, Parquet loaders, MLflow, deployment/shadow gates and a real
inference runner remain explicit roadmap work.

## Verify

```bash
python -m unittest discover -s apps/trainer/tests -v
python -m pytest --rootdir=. apps/gateway/tests apps/collector/tests apps/reward/tests apps/trainer/tests -q
```

Tests independently check one optimizer derivative, decreasing loss and a held-out
prompt preference; atomic-write failure preservation; fresh CLI checkpoint scoring;
actual subprocess HTTP training/scoring; restart byte-identical predictions;
invalid JSON/body/fields/hyperparameters; corrupt startup; storage outages; and
observed metrics. No provider key, database or downloaded model is required.
