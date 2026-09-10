"""Manual smoke test for the model-provider layer.

By default this runs entirely against :class:`MockModelProvider` and makes no
network calls:

    python scripts/model_smoke_test.py

To exercise the real Anthropic provider you must pass ``--live`` *and* configure
the environment:

    MODEL_PROVIDER=anthropic \
    ANTHROPIC_API_KEY=... \
    ANTHROPIC_MODEL=... \
    python scripts/model_smoke_test.py --live

The ``--live`` path sends real requests to the Anthropic API and may incur
charges. It is never run automatically and is not covered by the test suite.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.models.judging import JudgeResult
from app.providers.config import ModelConfig, ModelProviderType
from app.providers.factory import create_model_provider
from app.providers.mock import MockModelProvider
from app.providers.model import ModelProvider

_SYSTEM = "You are a terse assistant for a smoke test."
_USER_TEXT = "Reply with the single word: ok"
_USER_STRUCTURED = (
    "Return a JudgeResult indicating approval with score 0.9 and no other detail."
)


async def _run(provider: ModelProvider) -> None:
    text = await provider.generate_text(system_prompt=_SYSTEM, user_prompt=_USER_TEXT)
    print(f"generate_text     -> {text!r}")

    verdict = await provider.generate_structured(
        system_prompt=_SYSTEM,
        user_prompt=_USER_STRUCTURED,
        response_model=JudgeResult,
    )
    print(f"generate_structured -> {verdict!r}")


def _mock_provider() -> ModelProvider:
    return MockModelProvider(
        text_responses=["ok"],
        structured_responses=[JudgeResult(approved=True, score=0.9)],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Make REAL Anthropic API requests (requires MODEL_PROVIDER=anthropic "
        "and credentials). This may incur API charges.",
    )
    args = parser.parse_args(argv)

    if not args.live:
        print("Running in MOCK mode (no network, no cost).\n")
        asyncio.run(_run(_mock_provider()))
        return 0

    config = ModelConfig.from_env()
    if config.provider is not ModelProviderType.ANTHROPIC:
        print(
            "Refusing to run --live: set MODEL_PROVIDER=anthropic (plus "
            "ANTHROPIC_API_KEY and ANTHROPIC_MODEL) to make live requests.",
            file=sys.stderr,
        )
        return 2

    print(
        "WARNING: --live makes REAL Anthropic API requests that may incur "
        "charges.\n"
        f"         provider={config.provider.value} model={config.model}\n"
    )
    provider = create_model_provider(config)
    asyncio.run(_run(provider))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
