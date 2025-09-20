# Support Draft Integration (Example)

Practical walkthrough for instrumenting the "support email drafting" skill with the RLaaS telemetry stack. The flow assumes a React front-end where agents review drafts and a Python backend that calls the collector.

## 1. Prerequisites
- Phase 1 stack running (see `docs/SMOKE_TEST.md`).
- Collector base URL and API key for the tenant (default: `http://localhost:8100`, `acme-support-key`).
- Python environment with `rl-sdk` available (see `apps/sdk-python`).
- Front-end bundler capable of using the TypeScript SDK (`apps/sdk-js`).

## 2. Backend setup (FastAPI example)
```python
# app/telemetry.py
from rl_sdk.client import TelemetryClient, ClientConfig

collector = TelemetryClient(ClientConfig(
    base_url="http://localhost:8100",
    api_key="acme-support-key",
    offline_path=".telemetry-buffer.ndjson",
))
```

Log the initial interaction before you call your model, and the resulting output afterwards:
```python
import uuid

async def generate_reply(draft_request: DraftRequest) -> DraftResponse:
    interaction_id = uuid.uuid4().hex

    collector.log_interaction({
        "tenant_id": draft_request.tenant_id,
        "user_id": draft_request.agent_id,
        "skill": "support_draft_email",
        "input": {"text": draft_request.prompt},
        "version": {"policy_id": "support-draft-v0", "base_model": "llama3.1-8b"},
        "timings": {"ms_total": draft_request.latency_budget_ms},
        "costs": {"tokens_in": 0, "tokens_out": 0},
        "idempotency_key": interaction_id,  # optional override
    })

    llm_output = await call_model(...)

    collector.log_output({
        "tenant_id": draft_request.tenant_id,
        "interaction_id": interaction_id,
        "output": {"text": llm_output.text, "citations": llm_output.citations},
        "timings": {"ms_total": llm_output.latency_ms},
        "costs": llm_output.cost,  # tokens + dollars
        "version": {"policy_id": llm_output.policy_id, "base_model": llm_output.base_model},
    })

    return DraftResponse(interaction_id=interaction_id, text=llm_output.text)
```

When the agent accepts/edits the draft, capture feedback and task result:
```python
async def record_feedback(interaction_id: str, decision: FeedbackPayload) -> None:
    collector.submit_feedback({
        "tenant_id": decision.tenant_id,
        "interaction_id": interaction_id,
        "explicit": {"thumb": 1 if decision.sent else -1, "comment": decision.notes},
        "implicit": {"edited_text": decision.final_body, "sent": decision.sent},
    })

    collector.log_task_result({
        "tenant_id": decision.tenant_id,
        "interaction_id": interaction_id,
        "label": {"resolved": decision.sent, "handle_time_ms": decision.handle_time_ms},
    })
```

> The Python SDK automatically assigns `Idempotency-Key` headers and persists queued events to disk if the collector is offline.

## 3. Front-end setup (React)
Install the TypeScript SDK and wrap your app:
```tsx
// src/main.tsx
import { TelemetryProvider } from "@rlaas/sdk";

const config = {
  baseUrl: "http://localhost:8100",
  apiKey: "acme-support-key",
};

root.render(
  <TelemetryProvider config={config}>
    <App />
  </TelemetryProvider>
);
```

In a component where the model output is reviewed, use the hook helpers:
```tsx
import { useTelemetryLogger } from "@rlaas/sdk";

export function DraftReview({ draft }: { draft: Draft }) {
  const telemetry = useTelemetryLogger();

  const handleAccept = async () => {
    await telemetry.submitFeedback({
      tenant_id: draft.tenantId,
      interaction_id: draft.interactionId,
      explicit: { thumb: 1 },
      implicit: { sent: true, edited_text: draft.currentText },
    });
  };

  return (
    <div>
      <textarea defaultValue={draft.currentText} />
      <button onClick={handleAccept}>Send</button>
    </div>
  );
}
```

The React provider ensures every request includes an `Idempotency-Key`, and retries are handled transparently.

## 4. Smoke test the loop
1. Start the stack: `make up`.
2. Send a synthetic interaction via your backend or `curl` (see Step 2).
3. Verify dedupe: `SELECT idempotency_key, count(*) FROM events GROUP BY 1;` → keys should appear once.
4. Ensure MinIO staging contains the JSONL mirror: `mc ls local/rlaas-events/events/staging/interaction.create/`.
5. Run the compaction CLI to create a Parquet batch: `make compact DATE=$(date +%F)`.

## 5. Operational tips
- Call `flush_offline()` on service shutdown to empty SDK buffers.
- Treat `interaction_id` as the join key for outputs, feedback, and task results.
- Use the generated OpenAPI spec (`docs/openapi/collector.json`) to scaffold additional clients or contract tests.
- For browser environments without `localStorage`, supply a custom `StorageAdapter` to the SDK.

## 6. Next steps
- Add UI affordances to capture rich feedback (e.g., star ratings). The schemas accept arbitrary labels.
- Feed interaction/task events into the reward builder (Phase 4) to start compiling preference datasets.
- Document the workflow for your support platform (Zendesk, Salesforce) and include the necessary OAuth/API integration details.
