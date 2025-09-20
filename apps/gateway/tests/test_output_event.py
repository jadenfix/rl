from apps.gateway.app.main import _build_output_event
from apps.gateway.app.backends import BackendResult


def test_build_output_event_includes_latency_and_metadata():
    result = BackendResult(text="hello", metadata={"costs": {"tokens_in": 10, "tokens_out": 20}})
    event = _build_output_event(
        tenant_id="acme",
        interaction_id="123",
        result=result,
        policy_id="support@v1",
        base_model="llama",
        status="active",
        latency=0.123,
        metadata={"thread_id": "t1"},
    )

    assert event["timings"]["ms_total"] >= 1
    assert event["costs"]["tokens_out"] == 20
    assert event["metadata"]["thread_id"] == "t1"
    assert event["idempotency_key"].endswith(":active")
