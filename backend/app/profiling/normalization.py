"""Shared "missing token" normalization.

Every downstream Phase 2 analyzer wants values like `""`, `"N/A"`, `"null"`,
`"None"` treated as missing. Doing this once at the top of the pipeline is
cheaper and more consistent than re-implementing it in each module.

We return a NEW DataFrame — the caller's original data is never mutated.
"""

from __future__ import annotations

from typing import FrozenSet

import numpy as np
import pandas as pd
from pandas.api import types as ptypes


# Common textual placeholders that should count as missing.
MISSING_TOKENS: FrozenSet[str] = frozenset(
    {
        "",
        "na",
        "n/a",
        "n.a",
        "n/a.",
        "none",
        "null",
        "nil",
        "nan",
        "-",
        "--",
        "?",
        "unknown",
        "missing",
    }
)


def normalize_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of `df` with common missing-token strings replaced by NaN.

    Numeric / boolean / datetime columns are left untouched — the tokens can
    only appear inside object / string columns.
    """
    if df.empty:
        return df.copy()

    out = df.copy()
    for col in out.columns:
        series = out[col]
        if not (ptypes.is_object_dtype(series) or ptypes.is_string_dtype(series)):
            continue
        try:
            stripped = series.astype("object").where(series.notna(), other=np.nan)
            # Only touch actual strings; leave dicts / lists / other objects alone
            def _to_missing(v):
                if isinstance(v, str):
                    if v.strip().lower() in MISSING_TOKENS:
                        return np.nan
                return v

            out[col] = stripped.map(_to_missing)
        except Exception:  # noqa: BLE001
            # Never let a normalization glitch abort the pipeline
            continue
    return out
