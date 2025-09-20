# Zendesk Support Draft Integration Playbook

This guide extends the generic support draft example to a concrete Zendesk deployment. It highlights where to instrument telemetry, how to respect Zendesk APIs, and the operational steps for agents and admins.

## 1. Architecture overview
- **Zendesk Agent Workspace**: Agents triage tickets and review model-generated drafts.
- **Draft Assist App**: Custom Zendesk app built with ZAF v2, rendered in the ticket sidebar. Uses the TypeScript SDK (`@rlaas/sdk`) via a lightweight wrapper.
- **Backend Service**: Handles OAuth with Zendesk, fetches ticket context, calls the RLaaS inference gateway, and logs telemetry via the Python SDK.
- **RLaaS Collector**: Receives interaction, output, feedback, and task result events; enforces idempotency and stages data for Parquet compaction.

```
Agent Workspace -> Draft App (TS SDK) -> Backend (Python SDK) -> RLaaS Collector
                                      -> Zendesk REST APIs -> Ticket updates
```

## 2. Prerequisites
- Zendesk Support account with admin rights to install custom apps.
- OAuth credentials (client_id/secret) for backend access to the Zendesk API.
- RLaaS stack running with tenant `acme-support` (or your tenant) and API key.
- Backend service with `rl-sdk` configured (see Section 3).
- Front-end app scaffolded with the Zendesk App Framework (ZAF CLI) and bundler support for modern TypeScript.

## 3. Backend service (Python + FastAPI)
Create a telemetry module using the Python SDK:
```python
# backend/telemetry.py
from rl_sdk.client import TelemetryClient, ClientConfig

collector = TelemetryClient(ClientConfig(
    base_url="https://collector.rlaas.company",  # or http://localhost:8100
    api_key="acme-support-key",
    offline_path=".telemetry-buffer.ndjson",
))
```

When the Zendesk app requests a draft:
```python
async def generate_draft(ticket_id: str, agent: AgentContext) -> DraftPayload:
    interaction_id = uuid.uuid4().hex

    collector.log_interaction({
        "tenant_id": agent.tenant_id,
        "user_id": agent.user_id,
        "skill": "support_draft_email",
        "input": {
            "text": agent.email_body,
            "metadata": {"ticket_id": ticket_id, "brand_id": agent.brand_id},
        },
        "context": {
            "customer_tier": agent.customer_tier,
            "sla_mins": agent.sla_remaining,
        },
        "version": {"policy_id": "support-draft-v0", "base_model": "llama3.1-8b"},
        "timings": {"ms_total": agent.allowed_latency_ms},
        "costs": {"tokens_in": 0, "tokens_out": 0},
        "idempotency_key": interaction_id,
    })

    draft = await inference_gateway.fetch_reply(agent.email_body, ticket_id=ticket_id)

    collector.log_output({
        "tenant_id": agent.tenant_id,
        "interaction_id": interaction_id,
        "output": {
            "text": draft.body,
            "citations": draft.citations,
            "tool_calls": draft.tool_calls,
        },
        "timings": {"ms_total": draft.latency_ms},
        "costs": draft.costs,
        "version": draft.version,
    })

    return DraftPayload(interaction_id=interaction_id, body=draft.body)
```

When the agent sends or edits the draft:
```python
async def handle_agent_action(interaction_id: str, payload: AgentFeedback) -> None:
    collector.submit_feedback({
        "tenant_id": payload.tenant_id,
        "interaction_id": interaction_id,
        "explicit": {"thumb": 1 if payload.sent else -1, "comment": payload.comment},
        "implicit": {
            "edited_text": payload.final_body,
            "sent": payload.sent,
            "time_to_send_ms": payload.handle_time_ms,
        },
    })

    collector.log_task_result({
        "tenant_id": payload.tenant_id,
        "interaction_id": interaction_id,
        "label": {
            "resolved": payload.sent,
            "kpi_delta": payload.kpi_delta,
        },
    })
```

## 4. Zendesk app integration (TypeScript)
Within the ZAF app:
```ts
import { TelemetryProvider, useTelemetryLogger } from "@rlaas/sdk";
import { render } from "@zendeskgarden/react-modal"; // example UI lib

const config = {
  baseUrl: "https://collector.rlaas.company",
  apiKey: process.env.ZENDESK_RLAAS_API_KEY!,
  storage: new BrowserStorageAdapter({ key: "zendesk-telemetry" }),
};

function App() {
  const telemetry = useTelemetryLogger();

  async function handleSend(ticket: Ticket, draft: Draft) {
    await telemetry.submitFeedback({
      tenant_id: ticket.tenantId,
      interaction_id: draft.interactionId,
      explicit: { thumb: 1 },
      implicit: { sent: true, edited_text: draft.body },
      labels: { ticket_id: ticket.id },
    });
  }

  return <DraftReview onSend={handleSend} />;
}

document.addEventListener("DOMContentLoaded", () => {
  render(
    <TelemetryProvider config={config}>
      <App />
    </TelemetryProvider>,
    document.getElementById("root"),
  );
});
```

Works offline: the `BrowserStorageAdapter` queues events via `chrome.storage.local`, and `flushOffline()` can be triggered when the app detects connectivity.

## 5. Zendesk-specific considerations
- **Ticket context**: Use the Zendesk `ticket.sidebar` APIs to fetch requester info, tags, and brand. Include these fields in telemetry `context`/`labels` for richer reward signals.
- **Rate limits**: Batch `log_interaction` and `log_output` calls to avoid hitting Zendesk API rate limits when retrieving ticket history.
- **Security**: Store the RLaaS API key as a secure setting within Zendesk (encrypted) and inject at runtime. For multi-tenant setups, map Zendesk brands/groups to RLaaS tenants.
- **Consent & auditing**: Update Zendesk macros or footers to note when AI assistance is used; log telemetry `version.policy_id` for rollbacks.

## 6. Smoke test checklist
1. Install the app in Zendesk sandbox.
2. Open a ticket and request a draft; confirm the backend logs `interaction.create` and `interaction.output` rows.
3. Send the draft; confirm `feedback.submit` and `task.result` events appear once (check `idempotency_key`).
4. Validate MinIO staging and Parquet compaction as in the generic support guide.
5. Review the RLaaS dashboard (Phase 1 scope) for visible events.

## 7. Operational runbook
- **Agent training**: Provide quick reference cards explaining feedback buttons and how edits influence learning.
- **Support leads**: Monitor RLaaS metrics (win-rate, edit distance) before promoting new policies.
- **Incidents**: If RLaaS is unavailable, the SDK buffers events; ensure `flush_offline()` runs when services recover.

## 8. Next steps
- Integrate ticket outcome metrics (CSAT, reopen rate) via Zendesk incremental exports feeding `task.result`.
- Route drafts via RLaaS bandit policies once Phase 2 router is live.
- Build analytics dashboards combining Zendesk Explore data with RLaaS Parquet outputs.
