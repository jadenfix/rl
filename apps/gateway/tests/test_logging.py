from apps.gateway.app.logging import build_shadow_log
from apps.gateway.app.models import InferenceRequest, Policy, PolicyDecision
from apps.gateway.app.models import InteractionOutputEvent  # generated types maybe? not needed

def test_build_shadow_log_structure():
    request = InferenceRequest(tenant_id="acme", skill="support", input={"text": "hello"})
    decision = PolicyDecision(
        selected=Policy(policy_id="support@v1", status="active", base_model="llama"),
        shadow_candidates=[Policy(policy_id="support@shadow", status="shadow", base_model="llama")],
        reason="shadow_sampled",
    )

    payload = build_shadow_log(
        request,
        decision,
        [
            type("Result", (), {"text": "shadow text", "metadata": {"source": "stub"}})(),
        ],
    )

    assert payload["tenant_id"] == "acme"
    assert payload["shadow_entries"][0]["policy_id"] == "support@shadow"
