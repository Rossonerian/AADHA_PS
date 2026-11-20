"""Import only unambiguous NSE rows from the pinned official AMFI PDF.

Run with PYTHONPATH=services/api after installing the API dev dependencies.
The observation date is today: this snapshot cannot justify historical flags.
"""

import hashlib
import json
import re
from datetime import date, datetime
from io import BytesIO

import requests
from app.verifier.evidence import DEFAULT_DIR, MarketCapFact
from app.verifier.ports import MARKET_TZ
from pypdf import PdfReader

URL = "https://portal.amfiindia.com/spages/AverageMarketCapitalization30Jun2026.pdf"
EXPECTED_SHA256 = "77d2a536e01c7f431579faa912dd56bd546fbd58825f8fa50246c4ff9328a3ac"
# After the ISIN: BSE symbol/value, NSE symbol/value, optional MSEI symbol/value,
# the average across exchanges and AMFI's category. Wrapped/ambiguous rows skip.
ROW = re.compile(
    r"\bIN[A-Z0-9]{10}\s+\S+\s+[\d,.-]+\s+"
    r"(?P<symbol>[A-Z0-9][A-Z0-9&.-]*)\s+[\d,.]+\s+"
    r"(?:\S+\s+)?[\d,.-]+\s+(?P<cap>[\d,.]+)\s+"
    r"(?P<bucket>Large|Mid|Small) Cap\s*$"
)


def main() -> None:
    response = requests.get(URL, timeout=30)
    response.raise_for_status()
    digest = hashlib.sha256(response.content).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("AMFI document changed; review before importing new evidence")
    reader = PdfReader(BytesIO(response.content))
    facts: dict[str, MarketCapFact] = {}
    for page, contents in enumerate(reader.pages, 1):
        for line in (contents.extract_text() or "").splitlines():
            match = ROW.search(line)
            if not match:
                continue
            symbol = match["symbol"]
            fact = MarketCapFact.model_validate(
                {
                    "symbol": symbol,
                    "bucket": match["bucket"].lower() + "_cap",
                    "average_market_cap_inr_crore": float(
                        match["cap"].replace(",", "")
                    ),
                    "period_end": "2026-06-30",
                    "observed_on": datetime.now(MARKET_TZ).date(),
                    "valid_until": date(2026, 12, 31),
                    "source_url": URL,
                    "source_sha256": digest,
                    "page": page,
                    "data_origin": "real",
                }
            )
            if symbol in facts:
                raise ValueError("Duplicate AMFI NSE symbol; review PDF before import")
            facts[symbol] = fact
    if len(facts) < 1000 or facts.get("TCS") is None:
        raise ValueError("Unexpected AMFI format; refusing incomplete import")
    DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
    (DEFAULT_DIR / "market_cap.json").write_text(
        json.dumps([facts[s].model_dump(mode="json") for s in sorted(facts)], indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "records": len(facts),
                "source_url": URL,
                "sha256": digest,
                "observed_on": str(datetime.now(MARKET_TZ).date()),
            }
        )
    )


if __name__ == "__main__":
    main()
