"""Committed, version-controlled finance policy: the default number of decimal
places for money values. Lives in `settings.json` at the repo root (committed,
unlike the gitignored `config.json`) so the value is identical on every machine
and any change shows up in git history — the audit trail finance needs.

`decimal_places` is a *default*: a per-call `places=` argument still overrides it
for a specific column (e.g. FX rates at 4 places).

Rounding mode is deliberately NOT configurable — it is hardcoded to half-up (see
functions/_rounding.py). Making it swappable would let the same data round two
different ways depending on a setting, which would quietly change reconciled
financials and make tests depend on environment.
"""

import json

from engine.loader import _find_project_root

_settings_cache: dict | None = None


def _load_settings() -> dict:
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache

    path = _find_project_root() / "settings.json"
    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    places = data.get("decimal_places")
    if not isinstance(places, int) or isinstance(places, bool) or places < 0:
        raise ValueError(
            f"settings.json: 'decimal_places' must be a non-negative integer, "
            f"got {places!r}."
        )

    _settings_cache = {"decimal_places": places}
    return _settings_cache


def get_default_places() -> int:
    """The default number of decimal places for money values."""
    return _load_settings()["decimal_places"]
