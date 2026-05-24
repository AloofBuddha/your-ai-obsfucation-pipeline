"""Obfuscation strategies — Strategy pattern over the ABC.

Adding a new strategy:
  1. Implement `ObfuscationStrategy` in a new file.
  2. Register it in `_STRATEGIES` below.
That's it. The engine, pipeline, vault, and detection are unchanged.
"""
from __future__ import annotations

from obfuscation.strategies.base import ObfuscationStrategy
from obfuscation.strategies.pseudonymization import PseudonymizationStrategy
from obfuscation.strategies.tokenization import TokenizationStrategy

_STRATEGIES: dict[str, type[ObfuscationStrategy]] = {
    TokenizationStrategy.name: TokenizationStrategy,
    PseudonymizationStrategy.name: PseudonymizationStrategy,
}


def make_strategy(name: str) -> ObfuscationStrategy:
    """Build a strategy by name. Used by the pipeline at session start.

    Strategy is per-session — pseudonymization holds Faker state that should
    not be shared across sessions (and across sessions we *want* fresh
    surrogates for the cross-session irreversibility property).
    """
    try:
        cls = _STRATEGIES[name]
    except KeyError as e:
        raise ValueError(
            f"Unknown obfuscation strategy {name!r}. Known: {list(_STRATEGIES)}"
        ) from e
    return cls()


def available_strategies() -> list[str]:
    return list(_STRATEGIES.keys())


__all__ = [
    "ObfuscationStrategy",
    "PseudonymizationStrategy",
    "TokenizationStrategy",
    "available_strategies",
    "make_strategy",
]
