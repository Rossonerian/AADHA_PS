"""Build an auditable deterministic review ledger from public PDF content.

No LLM and no price outcomes are consulted during document selection. Candidates
still require review; filenames never establish a company or claim by themselves.
"""

import csv
import json
import re
from collections import Counter
from datetime import datetime
from functools import lru_cache
from pathlib import Path

ROOT = Path("data/market_cache/verifier_collection")
BBG = {
    "INFO": "INFY",
    "HDFCB": "HDFCBANK",
    "ICICIBC": "ICICIBANK",
    "MM": "M&M",
    "MSIL": "MARUTI",
    "KMB": "KOTAKBANK",
    "AXSB": "AXISBANK",
    "BHARTI": "BHARTIARTL",
    "TTAN": "TITAN",
    "HUVR": "HINDUNILVR",
    "COAL": "COALINDIA",
    "NTPC": "NTPC",
    "TATA": "TATASTEEL",
    "COCHIN": "COCHINSHIP",
    "SUNP": "SUNPHARMA",
    "LPC": "LUPIN",
    "DRRD": "DRREDDY",
    "APNT": "ASIANPAINT",
    "BJFIN": "BAJFINANCE",
    "HCLT": "HCLTECH",
    "WPRO": "WIPRO",
    "BJAUT": "BAJAJ-AUTO",
}
BRANDS = {
    "idbi_capital": ["idbicapital"],
    "sharekhan": ["sharekhan"],
    "motilal_oswal": ["motilaloswal"],
    "prabhudas_lilladher": ["prabhudaslilladher"],
    "axis_securities": ["axissecurities", "axisdirect"],
    "keynote_capitals": ["keynotecapital"],
    "emkay": ["emkay"],
    "geojit": ["geojit"],
    "hdfc_securities": ["hdfcsec", "hsieresearch"],
    "bp_wealth": ["bpwealth", "bpequities"],
    "icici_securities": ["icicisecurities", "icicidirect"],
    "nuvama": ["nuvama", "edelweiss"],
    "choice_broking": ["choiceequity", "choicebroking"],
    "yes_securities": ["yessecurities"],
    "lkp_securities": ["lkp"],
    "way2wealth": ["way2wealth"],
    "deven_choksey": ["krchoksey", "devenchoksey"],
    "nirmal_bang_institutional_equities": ["nirmalbang"],
    "jm_financial": ["jmfinancial"],
    "cd_equisearch": ["cdequisearch", "cdequi"],
    "asit_c_mehta": ["asitcmehta"],
    "anand_rathi_securities": ["anandrathi"],
    "kotak_securities": ["kotaksecurities"],
    "hem_securities": ["hemsecurities"],
    "axis_capital": ["axiscapital"],
    "ventura": ["ventura"],
    "ashika_research": ["ashika"],
    "systematix_shares_&_stocks": ["systematix"],
    "east_india_securities": ["eastindia"],
    "sushil_finance": ["sushilfinance"],
    "religare": ["religare"],
    "bob_capital_markets": ["bobcapital", "bobcaps"],
    "bonanza_india_research": ["bonanza"],
    "chola_wealth_direct": ["cholawealth", "cholamandalam"],
    "iifl": ["iifl"],
    "ajcon_global_services_ltd": ["ajcon"],
    "monarch_networth_capital": ["monarchnetworth"],
    "idfc_securities": ["idfcsecurities"],
    "nomura_research": ["nomura"],
    "dolat_capital_market": ["dolat"],
    "khambatta_securities_ltd": ["khambatta"],
    "khambatta_securities": ["khambatta"],
    "smc_online": ["smcglobal", "smctradeonline"],
    "sbi_securities": ["sbisecurities"],
    "elara_securities": ["elarasecurities", "elaracapital"],
    "centrum_broking": ["centrumbroking", "centrum"],
}


def norm(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


@lru_cache(maxsize=16384)
def company_key(text):
    text = re.sub(r"\([A-Z0-9&.\-]{2,12}\)", "", text)
    text = re.sub(
        r"\s*(?:\||\s|[-\u2013\u2014])\s*(?:BUY|SELL|HOLD|ADD|REDUCE|ACCUMULATE)\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+Systematix\s+Shares.*$", "", text, flags=re.IGNORECASE)
    return norm(
        re.sub(
            r"\b(?:limited|ltd|holdings|co\.?|company)\b",
            "",
            text.replace("&", "and"),
            flags=re.IGNORECASE,
        )
    )


def quoted_number(text, label):
    pattern = (
        rf"(?i:\b{label}\b)\s*(?:\([^\n)]{{0,24}}\))?\s*[:\-\u2013\u2014]?\s*"
        r"(?:(?i:of)\s+)?(?:(?i:INR|Rs\.?|Rupees)\s*)?[`\u20b9]?\s*"
        r"(?P<number>\d+(?:,\d{2,3})*(?:\.\d+)?)(?![\w,]|\.\d)"
    )
    matches = list(re.finditer(pattern, text))

    # Explicit field labels take precedence over narrative historical forecasts.
    def field_priority(match):
        prefix = (
            text[text.rfind("\n", 0, match.start()) + 1 : match.start()].strip().lower()
        )
        return 0 if prefix in ("", "current", "revised", "new") else 1

    for match in sorted(matches, key=field_priority):
        if re.search(
            r"\b(?:previous|earlier|prior|old)\s*$",
            text[max(0, match.start() - 25) : match.start()],
            re.IGNORECASE,
        ):
            continue
        rest = text[match.end() : match.end() + 12]
        if re.match(r"\s*(?:%|percent\b)", rest, re.IGNORECASE):
            continue
        if re.match(r"\s*[-\u2013\u2014/]\s*\d", rest):
            continue  # Ambiguous range or two-currency field.
        number = float(match["number"].replace(",", ""))
        if number > 0:
            return number, match[0].strip()
    return None, None


def horizon_for(text):
    """Keep stated ranges unsupported; never silently shorten a long forecast."""
    text = text.translate(
        str.maketrans({c: "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2212"})
    )
    duration = r"(?P<n>\d+|twelve|one)(?:\s*(?:-|to)\s*(?P<high>\d+))?\s*[- ]?\s*(?P<unit>months?|mths?|years?|yrs?|weeks?|days?|M\b)"
    label = r"(?:duration|target\s*period|(?:investment|time)\s*horizon|(?:investment|time)\s*period|holding(?:\s*period)?|time\s*frame)"
    patterns = [
        rf"{label}\s*(?:[:\-\u2013]\s*)?(?:of\s*)?{duration}",
        rf"{duration}\s*(?:investment\s*period|horizon)",
        rf"expected\s+(?:absolute\s+)?returns?\s*\(?\s*(?:over\s*)?{duration}",
        rf"target\s*price\s*[-\u2013]\s*{duration}",
        rf"(?:price\s*target|target\s*price)\s*\(\s*{duration}\s*\)",
        rf"performance\s+horizon\s+is\s+{duration}",
        rf"expected\s+over\s+a\s+{duration}\s+period",
        rf"ratings\s+denote\s+the\s+following\s+{duration}\s+forecast",
        rf"security\s+is\s+expected[^\n]{{0,90}}over\s+the\s+next\s+{duration}",
        rf"total\s+return\s+expectation\s*\(\s*{duration}",
        rf"ratings?\s+guide\s*\(\s*{duration}",
        rf"over\s+a\s+period\s+of\s+{duration}",
        rf"recommendations\s+and\s+absolute\s+returns\s*\(%\)\s*over\s*{duration}",
        rf"stock.s\s+total\s+return\s+is\s+expected[^\n]{{0,80}}over\s+the\s+next\s+{duration}",
        rf"{duration}\s+TP\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        if match["high"]:
            return None, "ambiguous_source_horizon", match[0]
        number = {"one": 1, "twelve": 12}.get(match["n"].lower())
        if number is None:
            number = int(match["n"])
        unit = match["unit"].lower()
        multiplier = (
            252
            if unit.startswith(("y",))
            else 5 if unit.startswith("w") else 1 if unit.startswith("d") else 20
        )
        window = number * multiplier
        if not 1 <= window <= 252:
            return None, "unsupported_source_horizon", match[0]
        return window, "stated_horizon", match["n"] + " " + match["unit"]
    return 20, "verifier_default_20_sessions", None


def review(record, symbols, isins):
    publisher = record["publisher"]
    all_text = "\n".join(record["pages"])
    if not any(b in norm(all_text) for b in BRANDS.get(publisher, [])):
        return None, "publisher_not_confirmed"
    source_day = datetime.strptime(record["filename_date"], "%Y%m%d").date()
    date_field = re.search(
        r"\b(?i:DATE)\s*[:\-]?\s*(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b",
        all_text[:25000],
    )
    if date_field:
        source_day = datetime(
            int(date_field[3]), int(date_field[2]), int(date_field[1])
        ).date()
    day = rf"0?{source_day.day}(?:st|nd|rd|th)?"
    month = rf"(?:{source_day.strftime('%B')}|{source_day.strftime('%b')})"
    year = source_day.year
    date_pattern = (
        rf"\b(?:{day}\s*{month}\s*,?\s*{year}|"
        rf"{month}\s*{day}\s*,?\s*{year}|"
        rf"0?{source_day.day}\s*[./-]\s*0?{source_day.month}\s*[./-]\s*{year})\b"
    )
    if not re.search(date_pattern, all_text[:25000], re.IGNORECASE):
        return None, "publication_date_not_confirmed"
    pages = record["pages"] if publisher == "kotak_securities" else record["pages"][:3]
    for page_index, page in enumerate(pages):
        # A cover page is harmless; broad multi-company tables remain ambiguous.
        found = {
            isins[m] for m in re.findall(r"\bIN[A-Z0-9]{10}\b", page) if m in isins
        }
        if not found:
            found = {
                m
                for m in re.findall(
                    r"\b(?i:NSE(?:\s+code|\s+symbol)?\s*[:\-]?)\s*([A-Z0-9&.\-]+)", page
                )
                if m in symbols
            }
        if not found:
            codes = re.findall(
                r"(?i:Bloomberg(?:\s+code)?|Bloom\s+Code|BB\s*Code|Ticker/Price)\s*[:\-]?\s*([A-Z0-9&.\-]+)(?:\s*[:.]\s*|\s+)IN\b",
                page,
            )
            found = {BBG.get(c, c) for c in codes if BBG.get(c, c) in symbols}
        if not found:
            # A standalone report heading can establish the company, using NSE's
            # official company name. Never fuzzy-resolve an arbitrary paragraph.
            titles = set()
            lines = [x.strip() for x in page[:10000].splitlines() if x.strip()]
            for i, line in enumerate(lines):
                titles.add(
                    company_key(
                        re.sub(r"^(?:BUY|SELL|ADD|REDUCE|HOLD|ACCUMULATE)\s+", "", line)
                    )
                )
                if i + 1 < len(lines):
                    titles.add(company_key(line + " " + lines[i + 1]))
            found = {
                s
                for s, name in symbols.items()
                if company_key(name) in titles
                and not any(b in norm(name) for b in BRANDS.get(publisher, []))
            }
        if len(found) != 1:
            continue
        symbol = next(iter(found))
        if publisher == "kotak_securities":
            dated = re.search(
                r"Dated:\s*(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(20\d{2})",
                page,
                re.IGNORECASE,
            )
            if not dated:
                continue
            source_day = datetime.strptime(" ".join(dated.groups()), "%d %B %Y").date()
        cmp, cmp_quote = quoted_number(
            page, r"CMP|Current\s+(?:Market\s+)?Price|Share\s+Price"
        )
        if cmp is None and publisher == "centrum_broking":
            price_field = re.search(r"(?m)^\s*Price:\s*Rs[\d,.]+", page)
            if price_field:
                cmp, cmp_quote = quoted_number(price_field[0], "Price")
        target, target_quote = quoted_number(
            page, r"Target\s+Price|Price\s+Target|Target\s*/\s*Upside|Target|TP|PT"
        )
        if publisher == "kotak_securities":
            price_pair = re.search(
                r"Current\s+Market\s+Price\s*\(CMP\)\s*Target\s+Price\s*Rs\.\s*([\d,.]+)\s*Rs\.\s*([\d,.]+)",
                page,
                re.IGNORECASE,
            )
            if price_pair:
                cmp, target = (float(price_pair[i].replace(",", "")) for i in (1, 2))
                cmp_quote, target_quote = "Rs. " + price_pair[1], "Rs. " + price_pair[2]
        quoted_range = None
        range_match = re.search(
            r"(?i:Reco\s*Price)\s*(?:\([^\n)]{0,12}\))?\s*[:\-]?\s*([\d,]+(?:\.\d+)?)\s*[-\u2013]\s*([\d,]+(?:\.\d+)?)",
            page,
        )
        if cmp is None and range_match and target is not None:
            low, high = (float(range_match[i].replace(",", "")) for i in (1, 2))
            if 0 < low < high:
                quoted_range = [low, high]
        table = re.search(
            r"CMP\s+Target\s+Price\s*\n(?P<row>[^\n]+)", page, re.IGNORECASE
        )
        if table:
            # Sushil's four-column row is explicitly labelled: cap, high/low, CMP, target.
            values = re.fullmatch(
                r"Rs\.\s*[\d,.]+\s*Cr\.\s*Rs\.\s*[\d,.]+/[\d,.]+\s*Rs\.\s*(?P<cmp>[\d,.]+)\s*Rs\.\s*(?P<target>[\d,.]+)",
                table["row"].strip(),
            )
            if values:
                cmp = float(values["cmp"].replace(",", ""))
                target = float(values["target"].replace(",", ""))
                cmp_quote = "Rs. " + values["cmp"]
                target_quote = "Rs. " + values["target"]
        explicit_direction = None
        direct_rating = re.search(
            r"(?m)^\s*(BUY|SELL|Buy|Sell)\s*(?:$|[A-Z][A-Za-z &.]+$)", page[:2500]
        )
        if direct_rating:
            explicit_direction = "up" if direct_rating[1].upper() == "BUY" else "down"
        if quoted_range and target is not None:
            explicit_direction = (
                "up"
                if target > quoted_range[1]
                else "down" if target < quoted_range[0] else None
            )
        if (
            target is None
            or (cmp is None and explicit_direction is None)
            or cmp == target
        ):
            continue
        # Only numeric level forecasts; do not treat an earnings estimate as a stock target.
        if cmp is not None and not 0.2 < target / cmp < 5:
            continue
        if re.search(r"\bstop[ -]?loss\b", page, re.IGNORECASE):
            continue  # Barrier calls need a separately established nominal/adjusted basis.
        window, horizon_basis, horizon = horizon_for(
            page if publisher == "kotak_securities" else all_text
        )
        if window is None:
            return None, horizon_basis
        record = {k: v for k, v in record.items() if k != "pages"}
        return {
            **record,
            "symbol": symbol,
            "company_name": symbols[symbol],
            "report_date": str(source_day),
            "claim_page": page_index + 1,
            "direction": (
                ("up" if target > cmp else "down")
                if cmp is not None
                else explicit_direction
            ),
            "direction_basis": (
                "published_target_vs_cmp"
                if cmp is not None
                else (
                    "published_target_vs_reference_range"
                    if quoted_range
                    else "explicit_source_rating"
                )
            ),
            "quoted_reference_range": quoted_range,
            "range_evidence": range_match[0] if quoted_range and range_match else None,
            "rating_evidence": (
                direct_rating[0].strip() if cmp is None and direct_rating else None
            ),
            "quoted_cmp": cmp,
            "target": target,
            "entry": None,
            "stop": None,
            "cmp_evidence": cmp_quote,
            "target_evidence": target_quote,
            "window_days": window,
            "horizon_basis": horizon_basis,
            "horizon_evidence": horizon,
            "data_origin": "real",
        }, "candidate"
    return None, "no_unambiguous_single_security_price_forecast"


def main():
    rows = list(csv.DictReader((ROOT / "nse_equity.csv").open(encoding="utf-8")))
    symbols = {r["SYMBOL"]: r["NAME OF COMPANY"] for r in rows}
    isins = {r[" ISIN NUMBER"]: r["SYMBOL"] for r in rows}
    accepted, rejected, seen = [], [], set()
    for path in sorted((ROOT / "text").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("superseded"):
            rejected.append(
                {"key": record["key"], "reason": "superseded_discovery_date"}
            )
            continue
        # Apply conservative alias collapsing even to older cached discoveries.
        from collect_verifier_sources import identity

        record["publisher"] = identity(record["publisher"])
        if record["sha256"] in seen:
            rejected.append({"key": record["key"], "reason": "duplicate_pdf"})
            continue
        seen.add(record["sha256"])
        result, reason = review(record, symbols, isins)
        if result:
            accepted.append(result)
        else:
            rejected.append(
                {
                    "key": record["key"],
                    "publisher": record["publisher"],
                    "reason": reason,
                }
            )
    (ROOT / "candidates.json").write_text(
        json.dumps(accepted, indent=2), encoding="utf-8"
    )
    (ROOT / "rejected.json").write_text(
        json.dumps(rejected, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "candidates": len(accepted),
                "counts": Counter(r["publisher"] for r in accepted),
                "horizon_bases": Counter(r["horizon_basis"] for r in accepted),
                "rejections": Counter(r["reason"] for r in rejected),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
