# Reward Service

The first implemented reward is deterministic normalized Levenshtein similarity
between a generated candidate and the user's edited text. It is a text-change
signal only: it does not establish model quality, user satisfaction, or business
impact.

## Run locally

```bash
python apps/reward/app/main.py
curl -sS http://localhost:8080/v1/rewards/edit-similarity \
  -H 'Content-Type: application/json' \
  -d '{"candidate":"Hello customer","edited":"Hello there"}'
```

The `score` is `1 - levenshtein_distance / max(input lengths)`, or `1.0` when
both strings are empty. Inputs are Unicode strings limited to 2,000 code points;
the JSON body is limited to 65,536 bytes and unknown fields are rejected.

Prometheus-format request counters are available at `/metrics`; liveness is at
`/healthz`.

## Verify

```bash
python -m pytest --rootdir=. apps/reward/tests -q
```

Future roadmap items such as task-specific rewards, judge models, persisted
preferences, and evidence of business correlation are not implemented here.

An actual-process GIF/MP4 walkthrough and reproducible capture receipt live in
[`../../demo`](../../demo/README.md).
- APIs to expose reward distributions and health metrics
