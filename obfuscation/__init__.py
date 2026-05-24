"""Obfuscation — detect entities and replace them with safe-to-send strings."""
from obfuscation.engine import ObfuscationEngine, ObfuscationResult
from obfuscation.strategies import (
    ObfuscationStrategy,
    available_strategies,
    make_strategy,
)

__all__ = [
    "ObfuscationEngine",
    "ObfuscationResult",
    "ObfuscationStrategy",
    "available_strategies",
    "make_strategy",
]
