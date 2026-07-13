"""Decay scoring — the "forgetting curve" for memories.

The combined score blends three signals so search results favor memories that
are (a) topically similar, (b) tagged like the query, and (c) recent or
frequently used::

    final = w_vec * vec + w_kw * kw + w_dec * decay

The decay component itself combines an exponential recency falloff (half-life
controlled) with a gentle frequency boost, scaled by the memory's importance
so CRITICAL memories never fade.

This module is pure (no I/O) so it's trivially testable.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class DecayParams:
    """Tunable knobs for the decay scoring."""

    half_life_days: float = 30.0
    floor: float = 0.05
    importance_scale: float = 0.1  # extra weight per importance point above 1


def decay_score(
    *,
    created_at: float,
    last_accessed_at: float,
    access_count: int,
    importance: int,
    params: DecayParams,
    now: float | None = None,
) -> float:
    """Compute the decay component of the search score in ``[0, 1]``.

    Args:
        created_at: Memory creation time (unix seconds).
        last_accessed_at: Last time the memory was read/recalled.
        access_count: Number of times the memory was retrieved.
        importance: Importance level (1..10); higher resists decay.
        params: Tunable decay parameters.
        now: Optional override for the current time (testing).
    """
    now = now if now is not None else time.time()
    # Recency: how long since the memory was last touched?
    age_seconds = max(0.0, now - max(created_at, last_accessed_at))
    age_days = age_seconds / 86400.0

    # Exponential decay with the configured half-life.
    half_life_days = max(params.half_life_days, 1e-6)
    recency = 0.5 ** (age_days / half_life_days)

    # Frequency: small boost for often-recalled memories (log-scaled, capped).
    frequency = 1.0 + 0.2 * min(math.log1p(access_count), 4.0)  # up to ~+0.56

    # Importance: CRITICAL (10) memories get a strong buffer against decay.
    imp_buffer = 1.0 + max(0, importance - 1) * params.importance_scale

    raw = recency * frequency * imp_buffer
    # The floor itself scales with importance so CRITICAL memories never sink
    # to the same level as LOW ones, even after their recency has flatlined.
    scaled_floor = min(1.0, params.floor * imp_buffer)
    return max(scaled_floor, min(1.0, raw))


def combine(
    *,
    vector_score: float,
    keyword_score: float,
    decay: float,
    vector_weight: float,
    keyword_weight: float,
    decay_weight: float,
) -> float:
    """Weighted sum of the three score components, clamped to ``[0, 1]``."""
    total = (
        vector_weight * vector_score
        + keyword_weight * keyword_score
        + decay_weight * decay
    )
    return max(0.0, min(1.0, total))


__all__ = ["DecayParams", "combine", "decay_score"]
