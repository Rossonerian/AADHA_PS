"""Run the existing exact-match evaluator against the real shared core.

Run from the repository root with PYTHONPATH=services/api. No fake client,
fallback model, corpus edits, or extraction tuning are used by this runner.
"""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import ConfigurationError, ExternalServiceError
from app.core.llm import get_usage_summary
from app.verifier.evaluation import evaluate_file
from app.verifier.ports import platform_core


def main() -> int:
    corpus = Path("data/seed/verifier/eval.jsonl")
    settings = get_settings()
    report = {
        "corpus": corpus.as_posix(),
        "corpus_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
        "labelled_rows": len(corpus.read_text(encoding="utf-8").splitlines()),
        "model": settings.openrouter_default_model,
        "target_f1": 0.80,
    }
    try:
        if not settings.openrouter_api_key.strip():
            raise ConfigurationError("OPENROUTER_API_KEY is not configured")
        metrics = evaluate_file(corpus, platform_core())
    except (ConfigurationError, ExternalServiceError) as exc:
        # Provider exception bodies can contain untrusted text. Log only the type;
        # the missing-key case has a fixed, safe diagnostic.
        reason = (
            "OPENROUTER_API_KEY is not configured"
            if not settings.openrouter_api_key.strip()
            else type(exc).__name__
        )
        print(
            json.dumps(
                {
                    **report,
                    "status": "blocked",
                    "reason": reason,
                    "f1": None,
                    "usage": get_usage_summary(),
                },
                indent=2,
            )
        )
        return 2
    print(
        json.dumps(
            {
                **report,
                "status": "completed",
                **asdict(metrics),
                "f1": metrics.f1,
                "usage": get_usage_summary(),
            },
            indent=2,
        )
    )
    return 0 if metrics.f1 >= 0.80 else 1


if __name__ == "__main__":
    raise SystemExit(main())
