from datetime import date
from types import SimpleNamespace
from typing import cast

import pandas as pd
import pytest

from app.verifier.ports import Market, VerifierCore
from app.verifier.red_flags import collect_flags
from app.verifier.schemas import DataOrigin, RedFlagCode


@pytest.mark.parametrize("code", list(RedFlagCode))
def test_each_flag_has_a_specific_observation(code):
    day = date(2026, 1, 30)
    market = cast(Market, SimpleNamespace(
        surveillance=lambda *_: "ASM-1" if code == RedFlagCode.SURVEILLANCE_LIST else None,
        prices=lambda *_: pd.DataFrame({"Volume": [5_000] * 20 + [
            21_000 if code == RedFlagCode.PRE_POST_VOLUME_SPIKE else 5_000, 1_000_000,
        ]}, index=pd.bdate_range(end=day, periods=22)),
    ))
    core = VerifierCore(
        complete=lambda *_: None, check_output=lambda _: None, market=market,
        market_cap_bucket=lambda *_: "small_cap" if code == RedFlagCode.ILLIQUID_SMALL_CAP else None,
    )
    text = {
        RedFlagCode.GUARANTEED_RETURNS: "Pakka munafa.",
        RedFlagCode.URGENCY: "Last chance, jaldi!",
    }.get(code, "A message about XYZ.")
    flags = collect_flags(text=text, symbol="XYZ", applicable_date=day,
                          vague=code == RedFlagCode.VAGUE_CLAIM,
                          registered=False if code == RedFlagCode.NOT_SEBI_REGISTERED else None,
                          deleted=code == RedFlagCode.DELETED_POST, origin=DataOrigin.SYNTHETIC, core=core)
    assert [flag.code for flag in flags] == [code]
    assert flags[0].evidence
    if code == RedFlagCode.PRE_POST_VOLUME_SPIKE:
        assert flags[0].evidence == {"ratio": 4.2, "session": "2026-01-29"}
