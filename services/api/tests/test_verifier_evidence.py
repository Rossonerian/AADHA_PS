"""Evidence never guesses when provenance is absent, stale, conflicting or synthetic."""

import json
from datetime import date

from app.verifier.evidence import EvidenceProviders
from app.verifier.ports import platform_core


def test_bound_real_amfi_snapshot_does_not_leak_into_historical_flags():
    core = platform_core()
    assert core.market_cap_bucket("TCS", date(2026, 11, 21)) == "large_cap"
    assert core.market_cap_bucket("TCS", date(2025, 1, 1)) is None
    assert core.market_cap_bucket("20MICRONS", date(2026, 11, 21)) == "small_cap"
    assert core.market_cap_bucket("20MICRONS", date(2027, 1, 1)) is None
    assert core.post_deleted("https://t.me/s/unknown/1") is None


def test_invalid_evidence_is_unknown(tmp_path):
    provider = EvidenceProviders(tmp_path)
    assert provider.market_cap_bucket("TCS", date(2026, 11, 21)) is None
    (tmp_path / "market_cap.json").write_text("invalid json")
    assert provider.market_cap_bucket("TCS", date(2026, 11, 21)) is None
    (tmp_path / "confirmed_deletions.json").write_text(
        json.dumps(
            [
                {
                    "post_url": "https://t.me/s/example/1",
                    "status": 404,
                    "data_origin": "real",
                },
                {"post_url": "https://t.me/s/example/1", "confirmation": "timeout"},
            ]
        )
    )
    assert provider.post_deleted("https://t.me/s/example/1") is None


def test_confirmed_deletion_requires_a_prior_capture_and_explicit_notice(tmp_path):
    record = {
        "post_url": "https://t.me/s/example/1",
        "evidence_url": "https://t.me/s/example/2",
        "previous_content_sha256": "a" * 64,
        "previously_observed_at": "2025-01-01T00:00:00Z",
        "confirmed_at": "2025-01-02T00:00:00Z",
        "confirmation": "publisher_confirmation",
        "evidence_sha256": "b" * 64,
        "data_origin": "real",
    }
    path = tmp_path / "confirmed_deletions.json"
    provider = EvidenceProviders(tmp_path)
    path.write_text(json.dumps([record]))
    assert provider.post_deleted(record["post_url"]) is True
    record["confirmed_at"] = "2099-01-02T00:00:00Z"
    path.write_text(json.dumps([record]))
    assert provider.post_deleted(record["post_url"]) is None
    record["confirmed_at"] = "2024-01-02T00:00:00Z"
    path.write_text(json.dumps([record]))
    assert provider.post_deleted(record["post_url"]) is None
    record["data_origin"] = "synthetic"
    path.write_text(json.dumps([record]))
    assert provider.post_deleted(record["post_url"]) is None
