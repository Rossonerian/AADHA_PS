"""Probe the factual Finnhub allowlist without printing credentials or opinions."""

import json
from datetime import UTC, datetime
from typing import Any

from app.core.finnhub import FinnhubClient, FinnhubUnavailableError
from app.nasdaq_verifier.service import build_questions


class Probe(FinnhubClient):
    def __init__(self) -> None:
        super().__init__()
        self.endpoints: dict[str, int | None] = {}

    def _get(self, path: str, **params: Any) -> Any:
        try:
            data = super()._get(path, **params)
        except FinnhubUnavailableError as exc:
            response = getattr(exc.__cause__, "response", None)
            self.endpoints[path] = getattr(response, "status_code", None)
            raise
        self.endpoints[path] = 200
        return data


def main() -> int:
    client = Probe()
    try:
        snapshot = client.snapshot("AAPL")
    except FinnhubUnavailableError:
        print(json.dumps({"status": "blocked", "endpoints": client.endpoints}))
        return 2
    fields = (
        "symbol",
        "price",
        "day_low",
        "day_high",
        "week52_low",
        "week52_high",
        "market_cap_musd",
        "pe_ttm",
        "data_origin",
    )
    print(
        json.dumps(
            {
                "checked_at": datetime.now(UTC).isoformat(),
                "status": "ok",
                "snapshot": {k: snapshot[k] for k in fields},
                "chart_points": len(snapshot["chart"]),
                "question_count": len(build_questions(snapshot)),
                "endpoints": client.endpoints,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
