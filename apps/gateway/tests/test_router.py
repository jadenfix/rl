from apps.gateway.app.config import GatewaySettings
from apps.gateway.app.models import Policy
from apps.gateway.app.router import PolicyRouter


def make_settings(**overrides):
    defaults = dict(
        postgres_dsn="postgresql://test",
        shadow_sampling_rate=1.0,
        default_statuses=("active", "shadow"),
        collector_url="http://collector",
        collector_api_key="",
        inference_base_url="",
        inference_api_key="",
        use_stub_backend=True,
    )
    defaults.update(overrides)
    return GatewaySettings(**defaults)


def test_router_selects_active_and_samples_shadow():
    settings = make_settings(shadow_sampling_rate=1.0)
    router = PolicyRouter(settings=settings)
    policies = [
        Policy(policy_id="support@v1", status="active", base_model="llama-3.1"),
        Policy(policy_id="support@shadow", status="shadow", base_model="llama-3.1"),
    ]

    decision = router.choose(policies)

    assert decision.selected.policy_id == "support@v1"
    assert decision.shadow_candidates[0].policy_id == "support@shadow"
    assert decision.reason == "shadow_sampled"


def test_router_falls_back_when_no_active():
    settings = make_settings(shadow_sampling_rate=0.0)
    router = PolicyRouter(settings=settings)
    policies = [Policy(policy_id="support@shadow", status="shadow", base_model="llama-3.1")]

    decision = router.choose(policies)

    assert decision.selected.policy_id == "support@shadow"
    assert not decision.shadow_candidates
    assert decision.reason == "active"
