"""
DESCRIPTION: Food registry — loads from foods.yaml, supports fuzzy matching,
and never hard-fails on an unrecognised ingredient name.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import List, Optional, Tuple

import yaml
from rapidfuzz import fuzz, process

from recipe_core.recipe_lib import Food, FoodType

logger = logging.getLogger(__name__)

_FOODS_YAML = os.path.join(os.path.dirname(__file__), "foods.yaml")

# Similarity threshold for fuzzy matching (0–100).
# Raise to require a closer match; lower to be more permissive.
FUZZY_THRESHOLD = 85


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------

def _load_registry(path: str = _FOODS_YAML) -> List[Food]:
    """Load and validate the food registry from YAML."""
    with open(path) as f:
        raw = yaml.safe_load(f)
    return [Food(**entry) for entry in raw]


@lru_cache(maxsize=1)
def _get_registry() -> List[Food]:
    """Return the registry, cached after the first load."""
    return _load_registry()


def _build_alias_index() -> List[Tuple[str, Food]]:
    """Flat list of (alias, Food) pairs — used for fuzzy search."""
    return [(alias, food) for food in _get_registry() for alias in food.names]


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

def get_food(name: str) -> Food:
    """
    Return the Food matching *name* from the registry.

    Resolution order:
      1. Exact match (case-insensitive) against all aliases.
      2. Fuzzy match — if the best candidate scores >= FUZZY_THRESHOLD.
      3. Soft fallback — return a default Food(Other) and log a warning.

    Never raises; the shopping list pipeline always gets a usable Food back.
    """
    normalised = name.lower().strip()
    registry = _get_registry()

    # 1. Exact match
    for food in registry:
        if food.has_name(normalised):
            return food

    # 2. Fuzzy match
    alias_index = _build_alias_index()
    candidates = [alias for alias, _ in alias_index]

    result = process.extractOne(
        normalised,
        candidates,
        scorer=fuzz.token_sort_ratio,
    )

    if result is not None:
        matched_alias, score, idx = result
        if score >= FUZZY_THRESHOLD:
            matched_food = alias_index[idx][1]
            logger.info(
                "Fuzzy matched '%s' → '%s' (score=%d)",
                name,
                matched_food.get_name(),
                score,
            )
            return matched_food

    # 3. Soft fallback
    return Food.default(name)


def reload_registry():
    """Force a reload of the food registry (e.g. after editing foods.yaml)."""
    _get_registry.cache_clear()
