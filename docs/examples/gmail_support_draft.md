# Gmail Support Draft Integration Playbook

This playbook shows how to embed the RLaaS support drafting loop directly inside Gmail using a Chrome extension. It complements the generic and Zendesk guides by covering browser extension permissioning, local storage buffering, and backend webhook plumbing.

## 1. Architecture snapshot
- **Chrome Extension (MV3)**: Content script + side panel surfaces draft suggestions; background service worker handles network calls and telemetry logging via the TypeScript SDK (Node adapter not required; uses Fetch + `BrowserStorageAdapter`).
- **Backend webhook**: Optional lightweight service (Python) that proxies RLaaS inference requests and enriches telemetry with CRM context.
- **RLaaS Collector**: Receives telemetry events with idempotency guarantees.

```
Gmail UI -> Chrome Extension (content script) -> Background worker -> RLaaS collector
                                            -> Backend webhook (optional)
```

## 2. Extension manifest (MV3)
Set up permissions and background service worker:
```json
{
  "manifest_version": 3,
  "name": "Gmail Draft Assist",
  "version": "0.1.0",
  "permissions": ["scripting", "storage", "identity"],
  "host_permissions": ["https://mail.google.com/*", "https://collector.rlaas.company/*"],
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [
    {
      "matches": ["https://mail.google.com/*"],
      "js": ["content.js"],
      "run_at": "document_idle"
    }
  ]
}
```

Include the RLaaS API key in extension storage (e.g., via OAuth + Identity API or enterprise policy) rather than bundling it.

## 3. Background service worker (TypeScript)
```ts
// src/background.ts
import { createNodeTelemetryClient, BrowserStorageAdapter } from "@rlaas/sdk";

const client = createNodeTelemetryClient({
  baseUrl: "https://collector.rlaas.company",
  apiKey: await loadApiKey(),
  fetchFn: fetch, // MV3 has global fetch
  storage: new BrowserStorageAdapter({ key: "gmail-telemetry" }),
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "draft_request") {
    handleDraftRequest(message.payload).then(sendResponse);
    return true; // keep channel open
  }
  if (message.type === "draft_feedback") {
    handleFeedback(message.payload).then(sendResponse);
    return true;
  }
  return false;
});

async function handleDraftRequest(payload: DraftRequest) {
  const interactionId = crypto.randomUUID();
  await client.logInteraction({
    tenant_id: payload.tenantId,
    user_id: payload.agentEmail,
    skill: "support_draft_email",
    input: { text: payload.emailBody, metadata: { thread_id: payload.threadId } },
    context: { customer_tier: payload.customerTier },
    version: { policy_id: "support-draft-v0", base_model: "llama3.1-8b" },
    timings: { ms_total: payload.latencyBudgetMs },
    costs: { tokens_in: 0, tokens_out: 0 },
    idempotency_key: interactionId,
  });

  const draft = await fetchDraftFromBackend(payload);

  await client.logOutput({
    tenant_id: payload.tenantId,
    interaction_id: interactionId,
    output: { text: draft.text, citations: draft.citations },
    timings: { ms_total: draft.latencyMs },
    costs: draft.costs,
    version: draft.version,
  });

  return { interactionId, draft };
}

async function handleFeedback(payload: DraftFeedback) {
  await client.submitFeedback({
    tenant_id: payload.tenantId,
    interaction_id: payload.interactionId,
    explicit: { thumb: payload.sent ? 1 : -1, comment: payload.comment },
    implicit: { edited_text: payload.finalText, sent: payload.sent },
    labels: { thread_id: payload.threadId },
  });

  await client.logTaskResult({
    tenant_id: payload.tenantId,
    interaction_id: payload.interactionId,
    label: { resolved: payload.sent },
  });

  await client.flush_offline?.();
}
```

## 4. Content script injection
Highlight email body field and send messages to background worker:
```ts
// src/content.ts
function injectDraftButton() {
  const composeBox = document.querySelector("div[role='textbox']");
  if (!composeBox || document.getElementById("rlaas-draft")) {
    return;
  }
  const button = document.createElement("button");
  button.id = "rlaas-draft";
  button.textContent = "Suggest Reply";
  button.onclick = async () => {
    const emailBody = composeBox.innerText;
    const response = await chrome.runtime.sendMessage({
      type: "draft_request",
      payload: {
        tenantId: "acme-support",
        agentEmail: getAgentEmail(),
        emailBody,
        threadId: getThreadId(),
        latencyBudgetMs: 2000,
      },
    });
    if (response?.draft) {
      composeBox.innerText = response.draft.text;
      // store interactionId for later feedback
      composeBox.dataset.rlaasInteractionId = response.interactionId;
    }
  };
  composeBox.parentElement?.appendChild(button);
}

const observer = new MutationObserver(injectDraftButton);
observer.observe(document.body, { childList: true, subtree: true });
```

When the agent sends the email, capture feedback:
```ts
chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "gmail_send" && message.interactionId) {
    chrome.runtime.sendMessage({
      type: "draft_feedback",
      payload: {
        tenantId: "acme-support",
        interactionId: message.interactionId,
        sent: true,
        finalText: message.finalBody,
        threadId: message.threadId,
      },
    });
  }
});
```

## 5. Backend webhook (optional)
If the extension should avoid direct RLaaS access, proxy through a minimal FastAPI service:
```python
@app.post("/draft")
async def draft_endpoint(payload: DraftRequest):
    response = await inference_gateway.fetch_reply(payload.email_body, thread_id=payload.thread_id)
    return response
```

Wrap telemetry as shown in Section 3 so both gateway calls and operator feedback are tracked.

## 6. Testing checklist
- **Idempotency**: Send multiple draft requests for the same interaction (reload compose window) and ensure only one row is inserted per interaction (`SELECT count(*) FROM events WHERE payload->>'thread_id' = ...`).
- **Offline mode**: Disable network, trigger draft; inspect `chrome.storage.local` to confirm queued events. Re-enable network and call `flushOffline()` to drain.
- **MinIO mirror**: Verify JSONL staging under `events/staging/interaction.create/` and run `make compact` to produce Parquet.
- **Zendesk vs. Gmail comparison**: Confirm both playbooks log consistent fields (`tenant_id`, `interaction_id`, `version.policy_id`) enabling unified analytics.

## 7. Production tips
- Use Chrome enterprise policies or managed storage to distribute API keys safely.
- Add privacy notices in the extension UI when telemetry is collected; allow per-agent opt-out toggles stored in RLaaS tenant metadata.
- Monitor draft latency and failure rates via RLaaS metrics; fall back to canned macros if the gateway is degraded.

## 8. Future enhancements
- Auto-flush telemetry when the browser regains connectivity (use `navigator.onLine` + `chrome.runtime.onConnect` events).
- Incorporate Gmail contextual data (labels, customer SLA) via the Gmail API with user consent.
- Integrate RLaaS win-rate reports into the extension popup for agent feedback loops.
