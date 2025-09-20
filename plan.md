RLaaS: a “learning workforce” for enterprise LLMs (free + deep plan)

Here’s a concrete way to build a continuous-learning SaaS that lets any LLM “learn on the job,” safely, cheaply, and with drop-in enterprise integration.

⸻

Implementation alignment (roadmap crosswalk)

- Phase 0–2 bootstraps Pillar A by seeding the monorepo, infra docker-compose, Postgres schema, and the telemetry/feedback SDK with event APIs and client libraries.
- Phase 3 extends Pillar B foundations by wiring retrieval memory that future reward models (Pillars B and C) depend on for grounded metrics.
- Phase 4–6 operationalize Pillars B and C: reward engines feed preference builders, which drive the LoRA + DPO trainer loop with MLflow tracking.
- Phase 7–8 close the loop for Pillar D through eval harnesses, safe deployment gates, and nightlies that publish adapters behind shadow/A/B routing.
- Phase 9–13 add the operator UX, integrations, observability, security, and cost controls that harden the SaaS for enterprise readiness.

Status sync (2025-09-19, see `progress.md`):
- Phase 0 gate closed: docker-compose stack stood up locally, tenant seed verified against Neon Postgres, and `/healthz` checks confirmed.
- Phase 1 execution live: FastAPI collector persists to Postgres, enforces per-event idempotency, stages MinIO JSONL, and ships OpenAPI artifacts + Python/TypeScript SDKs.
- Phase 2 staging: inference gateway skeleton exists; router/bandit wiring will follow once telemetry ingestion and SDK transport are stable.

Immediate next actions (P0 focus)

1. (DONE) Stand up the monorepo + docker-compose stack (gateway, trainer, reward, dashboard, SDKs) with pre-commit hooks and seeded tenant/policy tables.
2. (READY FOR DEV QA) Telemetry API + SDKs now include MinIO staging, Parquet compaction tooling, OpenAPI export, PII scrubbing hooks, idempotency enforcement, and Python/TypeScript transports.
3. (NEXT) Implement inference gateway + policy router with bandit scaffolding and shadow logging once telemetry ingestion stabilizes under real traffic.

⸻

0) Core idea (in one breath)

Instrument every LLM interaction → turn user actions into reward signals → aggregate into a per-tenant preference dataset → periodically train small adapters + reward models → ship new policies behind shadow/A/B gates with strict guardrails. Repeat. The base model stays stable; the policy around it (prompts, tools, retrieval, and LoRA adapters) keeps improving.

⸻

1) System blueprint (4 pillars)

Pillar A — Telemetry & Feedback SDK (data flywheel)
	•	Log every inference with inputs, tools used, retrieved context, outputs, latency, cost.
	•	Capture explicit feedback (👍/👎/5-star/comment) and implicit feedback (user edits, message sends vs discards, resolution status, handle time, conversions, CSAT).
	•	Align to a simple event spec:
	•	interaction.create (request)
	•	interaction.output (LLM response + traces)
	•	feedback.submit (explicit signals)
	•	task.result (downstream KPI labels: solved? time? refund? booking?)
	•	Free stack: FastAPI collector, Postgres (OLTP), Parquet on S3/MinIO (data lake), Airbyte or light webhooks for connectors, OpenTelemetry for traces.

Pillar B — Reward Engines (turn signals into numbers)
	•	Heuristics: edit distance ↓, time-to-send ↓, escalation? = bad, follow-up count.
	•	LLM-as-Judge (RLAIF): pair outputs; judge for helpfulness, harmlessness, faithfulness to retrieved facts. (Cache judgements; use multiple prompts → consensus.)
	•	Task-native metrics: extraction F1, triage accuracy, sales email reply rate, first-contact-resolution.
	•	Aggregate to preferences: (chosen, rejected, context) tuples for DPO/IPO; numeric rewards for bandits/PPO-style scoring.

Pillar C — Policy Training Loop (safe, cheap)
	•	What changes over time?
	1.	Prompt graphs (routing & tool use),
	2.	Retrieval memory (index + re-ranking),
	3.	Small adapters (LoRA on 7B–8B tenant models),
	4.	Reward models (small classifiers/judges).
	•	Training recipe (free-friendly):
	•	Offline SFT on high-reward traces → DPO/IPO on pairwise prefs. (TRL / PEFT)
	•	Keep adapters per-tenant and per-skill (e.g., “Invoice QA v3”), 4-bit LoRA to fit on a single 24-GB GPU (or CPU for tiny runs).
	•	For online exploration: contextual bandits across prompts/tools/adapters (e.g., Thompson Sampling). Keep epsilon small; cap risk.
	•	Catastrophic forgetting guard: replay buffer of golden examples + EWC-style regularization or periodic SFT refresh.

Pillar D — Safe Deployment & Governance
	•	Shadow mode → A/B → full rollout with automatic rollback on KPI regressions.
	•	Guardrails: input filters (PII, safety), output verifiers (groundedness/hallucination checks), policy-based refusals.
	•	Tenancy: hard data isolation, per-tenant adapters, optional federated preference learning (DP noise) to share skill shapes without sharing raw data.
	•	Audit: immutable trace store, diff every policy change, consent flags, retention windows.

⸻

2) Free/OSS reference stack (minimal but production-ish)
	•	Serving: vLLM or TGI for open models (Llama 3.1/8B, Mistral 7B); FastAPI gateway.
	•	Orchestration: LangGraph (tool flows) or a thin in-house router.
	•	Vector DB: Qdrant (OSS), FAISS for offline.
	•	Storage: Postgres + MinIO (S3) + Parquet; DuckDB for quick analytics.
	•	Pipelines: Airflow/Prefect for nightly retrains; Ray optional for scale.
	•	Training: HuggingFace TRL + PEFT + bitsandbytes; MLflow for experiments; DVC for data.
	•	Observability: OpenTelemetry, Prometheus/Grafana, Great Expectations for data QA.
	•	UI: Next.js (free), or embed in existing tools via browser extension.

All free, self-hostable, runs on a single machine with a consumer GPU or rented spot GPU; dev can run CPU-only with 4-bit quant + small batches.

⸻

3) Data contracts (what you ask enterprises to send)

interaction:
  tenant_id: str
  user_id: str
  skill: "support_draft_email|invoice_qa|triage|..."
  input: { text: str, attachments?: [uri], metadata?: {...} }
  context: { retrieval_chunks?: [...], customer_tier?: str, sla_mins?: int }
  output: { text: str, tool_calls?: [...], citations?: [...] }
  timings: { ms_total: int, ms_decode: int }
  costs: { tokens_in: int, tokens_out: int }
  version: { policy_id: "skill@v12", base_model: "llama3.1-8b-instruct" }
feedback:
  explicit?: { thumb: +1|-1, rating?: 1-5, comment?: str }
  implicit?: { edited_text?: str, sent?: bool, time_to_send_ms?: int, escalated?: bool }
task_result:
  label?: { correct?: bool, f1?: float, resolved?: bool }


⸻

4) Training loop (cheap DPO + bandits)

Nightly (offline):
	1.	Build pairwise prefs from logs (chosen vs rejected/edited).
	2.	Train LoRA adapters with DPO:
	•	Base: Llama-3.1-8B-instruct (or your enterprise base).
	•	4-bit quant, rank=8–16; micro-batches 4–8.
	3.	Evaluate on held-out tenant golden set + safety suite.
	4.	If ↑ on KPIs and safety pass → publish skill@v{n+1} in shadow.

Live (online):
	•	For the same skill, keep N policies: baseline + 1–2 candidates.
	•	Router samples a candidate via Thompson Sampling on recent reward.
	•	Hard caps on exploration per hour/tenant; auto-stop on drift.

⸻

5) Example: tiny code you can ship today

Client SDK (drop-in anywhere):

# pip install httpx tiktoken rapidfuzz
import httpx, time, difflib
API="https://your-rlsaas/api"

def log_event(kind, payload): httpx.post(f"{API}/{kind}", json=payload, timeout=5)

def call_llm(skill, text, ctx):
    t0=time.time()
    r=httpx.post(f"{API}/infer", json={"skill":skill,"input":text,"context":ctx}).json()
    log_event("interaction", {
        "tenant_id": ctx["tenant_id"], "user_id": ctx["user_id"], "skill": skill,
        "input":{"text":text}, "output":{"text":r["text"],"citations":r.get("cites",[])},
        "timings":{"ms_total": int(1000*(time.time()-t0))}, "version": r["version"]
    })
    return r

def submit_feedback(interaction_id, user_text, model_text, sent):
    edit_sim = difflib.SequenceMatcher(None, model_text, user_text).ratio()
    log_event("feedback", {
        "interaction_id": interaction_id,
        "explicit": {"thumb": +1 if sent else -1},
        "implicit": {"edited_text": user_text, "sent": sent, "edit_similarity": edit_sim}
    })

Offline DPO adapter (TRL) sketch:

from datasets import load_dataset
from trl import DPOTrainer, DPOConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model

tok = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3.1-8B-Instruct", use_fast=True)
base = AutoModelForCausalLM.from_pretrained(..., load_in_4bit=True, device_map="auto")

peft_cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules=["q_proj","v_proj"])
model = get_peft_model(base, peft_cfg)

prefs = load_dataset("parquet", data_files={"train": "prefs_train.parquet", "eval": "prefs_eval.parquet"})
cfg = DPOConfig(per_device_train_batch_size=2, gradient_accumulation_steps=8, learning_rate=5e-5, max_steps=2000)

trainer = DPOTrainer(model=model, processing_class=tok, beta=0.1, args=cfg,
                     train_dataset=prefs["train"], eval_dataset=prefs["eval"],
                     formatting_func=lambda ex: {"prompt": ex["prompt"], "chosen": ex["chosen"], "rejected": ex["rejected"]})
trainer.train()
model.save_pretrained("./tenantA_invoice_qa_lora_v3")

Router with bandits (toy):

import random
from collections import defaultdict
# policy -> Beta(a,b)
posteriors = defaultdict(lambda: [1,1])

def choose_policy(skill):
    policies = registry[skill]  # ["base","lora_v2","lora_v3"]
    samples = {p: random.betavariate(*posteriors[p]) for p in policies}
    return max(samples, key=samples.get)

def record_reward(policy, r):  # r in {0,1} or scaled
    a,b = posteriors[policy]
    posteriors[policy] = [a + r, b + (1-r)]


⸻

6) Integration patterns (drop-in for enterprise)
	•	Email/CRM (Gmail/Outlook, Salesforce, HubSpot): draft-assist. Reward = send-rate ↑, edits ↓, replies ↑.
	•	Support (Zendesk, ServiceNow): reply drafts & triage. Reward = FCR↑, handle-time↓, escalation↓.
	•	Doc QA / Extraction: precision/recall from validator or spot QA; negative reward on hallucinations (judge + grounding score).
	•	Agent tool-use: teach tool call sequences; reward on success paths and latency/cost trade-offs.

Deliver via:
	•	SDK (5 functions): infer, log, feedback, train, deploy.
	•	Webhook mode: they send traces; you return better policies.
	•	Browser extension: instrument edits inside Gmail/Zendesk/SFDC natively.

⸻

7) Safety & compliance (must-haves)
	•	Policy sandwich: pre-filters (PII, unsafe); mid-training with constitutional rules; post-hoc verifiers (groundedness, PII scrubs).
	•	Shadow runs only until safety suite passes (red-team prompts, jailbreaks, data leakage tests).
	•	Auditable diffs: every deployment shows “what changed,” metrics, and sample outputs.
	•	Per-tenant keys & storage, opt-out from cross-tenant meta-learning; optional DP noise for shared reward model pretraining.

⸻

8) MVP scope (fastest path to “wow”)
	•	One skill: Support email drafting.
	•	One model: Llama-3.1-8B-Instruct + LoRA.
	•	One metric bundle: edit similarity, send-rate, CSAT proxy (thumbs).
	•	Nightly DPO; live bandit across {baseline, LoRA}.
	•	Simple dashboard: CTR, edit distance, win-rate vs baseline, cost/latency.

This gives visible learning within days of live traffic, at near-zero infra cost.

⸻

9) Why this is “groundbreaking SaaS”
	•	Always-learning without risky base-model changes.
	•	Per-tenant specialization via tiny adapters and prompts.
	•	Objective, auditable improvement tied to business KPIs, not vibes.
	•	Vendor-agnostic: works with open models or wraps closed ones (you still optimize prompts/tools/retrieval/reward and learn routing; for closed models you skip LoRA but keep bandits + prompt/graph learning).

⸻

10) What to build first (feature checklist)
	•	Telemetry/feedback SDK + API.
	•	Preference builder (pairs + judges).
	•	DPO trainer (LoRA) with MLflow tracking.
	•	Bandit router + safety gates (shadow/A-B).
	•	Minimal admin UI (policies, metrics, rollbacks).
	•	Connectors: Gmail/Zendesk/Salesforce (start with 1).

If you want, I can turn this into a repo scaffold (FastAPI + vLLM + TRL + Qdrant + MLflow) and a minimal Next.js admin panel, plus a sample “support drafting” skill with the full loop wired end-to-end.
