RLaaS roadmap (technical, with checklists)

Below is a pragmatic, build-in-public plan to ship a continuous-learning RLaaS that slots into existing enterprise LLM workflows. Each phase has a checklist + clear gates.

⸻

Phase 0 — Project foundations

Goal: reproducible dev, secure multi-tenant skeleton.

Status: Complete — gate passed with monorepo stack running locally and tenant seed verified (Plan P0 Step 1).

Progress: Monorepo directories, service Dockerfiles, docker-compose stack, env template, and pre-commit tooling landed (`README.md`, `apps/*/README.md`, `.pre-commit-config.yaml`, `docker-compose.yml`). `/healthz` checks now succeed against running containers, and Neon Postgres holds the seeded tenant/policy data (`config/db/init.sql`, `config/db/seed.sql`).
Latest:
- Local `make up` run plus `/healthz` probes confirmed across gateway, reward, trainer, and collector services (see `progress.md`, 2025-09-19 12:18 PDT).
- Remote Neon Postgres configured, seeded, and re-verified (`config/db/init.sql`, `config/db/seed.sql`, psql query output at 2025-09-19 12:15 PDT).
- Hand-off notes captured in `docs/SMOKE_TEST.md` so new developers can reproduce the setup without rework.

Checklist
	•	Monorepo (apps: gateway, trainer, reward, dashboard, sdk-python, sdk-js)
	•	Dockerfiles + docker-compose (Postgres, MinIO/S3, Qdrant, Prometheus, Grafana)
	•	Env/secret management (Doppler/SOPS + KMS; local .env only for dev)
	•	Pre-commit (ruff/black/isort, mypy, eslint, hadolint)
	•	Basic RBAC & tenant model (Postgres schema: tenants, keys, policies, events)

Gate to pass (met 2025-09-19)
	•	make up brings full stack up locally; sample tenant and API key created.

⸻

Phase 1 — Telemetry & Feedback SDK

Goal: capture everything needed to learn from usage.

Status: Complete — telemetry ingestion, SDK parity (Python/TypeScript/React/Node/extension), and docs are live.

Progress: JSON schemas landed; FastAPI collector writes validated events into Postgres with connection pooling; placeholder gateway/reward/trainer services keep `/healthz` and `/metrics` coverage for end-to-end smoke tests (`config/schemas/events`, `apps/collector`, `apps/gateway/app/main.py`, `apps/reward/app/main.py`, `apps/trainer/app/main.py`). SDK suite now includes React hooks, Node keep-alive helpers, browser extension storage, and schema-derived types.
Latest:
- Event JSON Schemas committed for interaction, output, feedback, and task result payloads (`config/schemas/events`).
- Telemetry collector FastAPI service added with validation endpoints and Prometheus scrape target (`apps/collector`, `docker-compose.yml:4`).
- Collector now persists events to Postgres via connection pooling, stages JSONL payloads in MinIO, and ships a compaction CLI that writes Parquet batches (`apps/collector/app/storage.py`, `apps/collector/app/compaction.py`).
- OpenAPI artifacts are generated from shared JSON Schemas via `scripts/generate_openapi.py`, producing `docs/openapi/collector.json` for SDK consumers.
- Python SDK client delivers retries, offline buffering, idempotency headers, and pytest coverage; TypeScript SDK now ships a matching transport plus React helpers (`apps/sdk-python/src/rl_sdk`, `apps/sdk-js/src`).
- Focus (Sprint 09-19):
  - [x] Enable MinIO staging path + daily compaction (blocks Parquet exports for Roadmap Phase 1 gate).
  - [x] Generate OpenAPI schema + docs bundle for SDK authors.
  - [x] Implement Python SDK core client (httpx transport, retries, offline buffer) with contract tests.
  - [x] Extend PII scrub hooks prior to storage and document toggles per tenant.
  - [x] Deliver TypeScript SDK transport/offline buffer.
  - [x] Define collector idempotency helpers + default headers across SDKs.
  - [x] Ship React/Node/browser extension helpers and schema-derived event typings.

Checklist
	•	Event API (/v1/interaction.create, /v1/interaction.output, /v1/feedback.submit, /v1/task_result)
	•	JSON schemas (Pydantic) with versioning + idempotency keys
	•	PII scrubbing hooks (regex + classifier) before persistence
	•	Hot store: Postgres (OLTP). Cold store: Parquet on MinIO (daily compaction)
	•	Python & TypeScript SDKs (retry, backoff, offline buffer, 1-line install)
	•	Data contracts & docs with examples

Gate
	•	Golden “email-draft” sample app emits traces; events visible in SQL & Parquet.

⸻

Phase 2 — Serving gateway & policy router

Goal: vendor-agnostic inference with shadow/A-B gates.

Status: In progress — FastAPI gateway skeleton with policy store/bandit stubs live; inference backends still stubbed.

Progress: Gateway now serves FastAPI `/v1/infer`, `/v1/policies`, and Prometheus metrics with policy routing hooked to Postgres; policy store filters active/shadow candidates and samples shadow traffic (`apps/gateway/app/main.py`, `apps/gateway/app/policy.py`, `apps/gateway/app/router.py`).

Latest:
- FastAPI/Prometheus gateway replaces placeholder HTTPServer; idempotent request models and counters added (`apps/gateway/app/main.py`).
- Policy store fetches tenant policies from Postgres with skill-aware fallback and shadow sampling (configurable via env).
- Inference endpoint returns structured decisions, logs dual-run shadow outputs, ships telemetry to the collector, and can call real backends via configurable HTTP client (`apps/gateway/app/main.py`, `apps/gateway/app/telemetry.py`, `apps/gateway/app/backends.py`).
- Added pytest coverage for router decisions, shadow logging, and output event metadata (`apps/gateway/tests`).

Checklist
	•	Inference API (/v1/infer) with request tracing (OpenTelemetry)
	•	Policy registry: policy_id, base model, prompt graph, adapter refs
	•	Routing layer: sticky control, shadow mode, A/B, canary %, per-tenant caps
	•	Bandit module (Thompson Sampling) over candidate policies with guardrails
	•	Token metering + cost attribution per tenant/skill
	•	Pluggable backends: vLLM/TGI + proxy to OpenAI/Anthropic (closed-model mode)

Gate
	•	Can run baseline + candidate in shadow and log both safely.

⸻

Phase 3 — Retrieval & memory (optional but high ROI)

Goal: stable grounding to cut hallucinations and create learnable context.

Checklist
	•	Qdrant index per tenant; schema: doc_id, chunk, meta, source
	•	Chunker + embedder workers (OSS: BGE/MiniLM)
	•	Reranker (cross-encoder) plug; fall back to BM25
	•	Snapshotting + TTL; data lineage for citations

Gate
	•	Groundedness score improves on eval set vs no-RAG baseline.

⸻

Phase 4 — Reward engines

Goal: turn edits/actions into numbers and prefs.

Checklist
	•	Implicit metrics: edit similarity (Levenshtein), time-to-send, escalation
	•	Task metrics: extraction F1, triage accuracy, reply rate, FCR
	•	LLM-as-Judge harness (self-consistency + multi-prompt consensus + caching)
	•	Reward scaler (0–1), outlier clipping, data leakage checks
	•	Reward dashboard with per-skill distributions

Gate
	•	Correlation shown between reward and business proxy (e.g., edit↓ ⇒ CSAT↑).

⸻

Phase 5 — Preference & dataset builder

Goal: DPO/IPO-ready datasets with QA.

Checklist
	•	Pairwise constructor (chosen vs rejected/edited) with provenance
	•	Dedup, decontam, tenant isolation; min examples per skill thresholds
	•	Train/val/test splits by conversation thread to avoid leakage
	•	Data QA notebook (Great Expectations)

Gate
	•	≥5k high-quality pairs for MVP skill; pass QA suite.

⸻

Phase 6 — Training pipeline (LoRA + DPO)

Goal: cheap adapters that actually learn.

Checklist
	•	TRL/PEFT trainer (4-bit, LoRA r=8–16) with Hydra configs
	•	Baselines: SFT-only vs SFT→DPO; early stop on val loss/metric
	•	Safety fine-tuning: constitutional prompts, refusal shaping set
	•	Catastrophic forgetting guard (replay buffer + periodic SFT refresh)
	•	MLflow tracking; artifacts stored (adapter weights, tokenizer, configs)

Gate
	•	Offline eval: ≥X% win-rate vs baseline + no regressions on safety suite.

⸻

Phase 7 — Eval & safety harness

Goal: trustable promotion criteria.

Checklist
	•	Static eval sets: task metrics + red-team jailbreaks + groundedness checks
	•	Online replay eval (counterfactual) with IPS/DR estimators
	•	Hallucination/PII detector in the loop; block-list/allow-list policies
	•	Promotion rubric (metrics deltas, power analysis, stat-sig)

Gate
	•	Candidate policy@vN+1 meets rubric; promotion report auto-generated.

⸻

Phase 8 — Deployment & rollback

Goal: safe shipping, fast rollback.

Checklist
	•	Policy bundle spec (prompt graph + adapter refs + guardrail config)
	•	Shadow→A/B→gradual rollout automation (per tenant & skill)
	•	Health checks & auto-rollback on KPI regression or error budget burn
	•	Policy diff viewer (prompts, tools, adapters, metrics)

Gate
	•	Rollback < 1 minute, no data loss; audit trail captured.

⸻

Phase 9 — Admin dashboard (Next.js)

Goal: operators can see/act.

Checklist
	•	Tenants, skills, policies list
	•	Metrics: win-rate, reward, edit-distance, cost, latency (timeseries)
	•	Toggle: enable/disable shadow/A-B; adjust traffic weights
	•	Event explorer (search traces, sample conversations with PII masked)
	•	Export: Parquet slices for audits

Gate
	•	Ops can promote/rollback without CLI; auditors can reconstruct decisions.

⸻

Phase 10 — Enterprise integrations (MVP)

Goal: drop-in value where users live.

Checklist
	•	Gmail/Outlook draft-assist (sidebar/extension), feedback hooks wired
	•	Zendesk macro assistant; FCR/handle-time labels ingested
	•	Salesforce email composer; reply-rate tracking
	•	Webhooks + Zapier-friendly actions

Gate
	•	End-to-end: user edits → reward → next-day adapter beats baseline in A/B.

⸻

Phase 11 — Observability & SLOs

Goal: production reliability.

Checklist
	•	Metrics: QPS, p50/p95 latency, tokens, costs, win-rate, error classes
	•	Logs + traces (OTel) stitched across gateway→router→backend
	•	SLOs: 99% ≤ 2s p95; error budget & paging (Grafana/Alertmanager)
	•	Synthetic probes (health prompts) + nightly regression suite

Gate
	•	1-page runbook; oncall can mitigate model/infra incidents.

⸻

Phase 12 — Security & compliance

Goal: pass vendor reviews.

Checklist
	•	Data isolation per tenant (row-level security), encryption at rest & in transit
	•	Key rotation, scoped API keys, audit logs (who changed what, when)
	•	DSR endpoints (export/delete), retention policies, configurable regions
	•	SOC2 pre-audit checklist; threat model & DPIA docs

Gate
	•	External pen-test passes; DPA templates ready.

⸻

Phase 13 — Cost & latency controls

Goal: keep it cheap & fast.

Checklist
	•	Prompt/candidate caching (semantic + exact)
	•	Quantization (AWQ/GPTQ) for adapters; KV-cache reuse
	•	Dynamic max-tokens, tool-first routing, early-exit
	•	Cost dashboard per tenant/skill; budgets + rate limits

Gate
	•	Cost/token ↓ ≥30% at equal or better quality.

⸻

Phase 14 — Stretch (V2+)

Optional
	•	Federated preference learning across tenants (DP noise)
	•	Active-learning UI for human labeling sprints
	•	Auto-prompt evolution (CMA-ES/PE for prompt graphs under safety)
	•	Tool-use sequence optimization via offline RL / IPS

⸻

Acceptance criteria for the MVP
	•	One live “support email drafting” skill with adapters improving win-rate ≥10% vs baseline during A/B over 1 week.
	•	Edit-distance ↓ and send-rate ↑ with stat-sig.
	•	Safe rollout/rollback flows exercised; full audit trail.
	•	SDKs + docs allow a new tenant to integrate in ≤1 day.

⸻

Implementation slices (suggested order)
	1.	P0: Phase 0–2
	2.	P1: Phase 4–6 (rewards → prefs → training)
	3.	P2: Phase 7–8 (eval + deployment gates)
	4.	P3: Phase 9–10 (dashboard + 1 integration)
	5.	P4: Phase 11–13 (SLOs, security, cost)

⸻

Quick checklists you can paste into issues

SDK
	•	Auth (API key), retries, offline queue
	•	infer(), log_interaction(), submit_feedback(), task_result()
	•	Types, examples, CI tests

Trainer
	•	Data loader (Parquet → HF datasets)
	•	SFT → DPO pipeline configs
	•	Safety set merge; replay buffer
	•	MLflow tracking; artifact push

Router
	•	Registry CRUD
	•	Shadow dual-run
	•	Bandit scorer + risk caps
	•	Win-rate computation

Safety
	•	PII filter in/out
	•	Groundedness checker
	•	Red-team test battery
	•	Block on failure
