from __future__ import annotations

from apps.collector.app.pii import PayloadScrubber, ScrubConfig, build_scrubber


def test_scrubber_redacts_basic_patterns() -> None:
    scrubber = build_scrubber(enabled=True, allowlist=(), redaction_token="***")
    payload = {
        "tenant_id": "acme",
        "email": "user@example.com",
        "nested": {
            "phone": "+1 (555) 123-4567",
            "card": "4242 4242 4242 4242",
            "note": "Call me at 555-123-9876",
        },
    }
    scrubbed = scrubber.scrub(payload, tenant_id="widgets")
    assert scrubbed["email"] == "***"
    assert scrubbed["nested"]["phone"] == "***"
    assert scrubbed["nested"]["card"] == "***"
    assert "***" in scrubbed["nested"]["note"]


def test_allowlist_skips_scrubbing() -> None:
    config = ScrubConfig(enabled=True, tenant_allowlist=("vip",), redaction_token="[x]")
    scrubber = PayloadScrubber(config)
    payload = {"tenant_id": "vip", "email": "vip@example.com"}
    assert scrubber.scrub(payload, tenant_id="vip")["email"] == "vip@example.com"


def test_disabled_scrubber_returns_payload() -> None:
    scrubber = build_scrubber(enabled=False, allowlist=(), redaction_token="[x]")
    payload = {"email": "user@example.com"}
    assert scrubber.scrub(payload)["email"] == "user@example.com"
