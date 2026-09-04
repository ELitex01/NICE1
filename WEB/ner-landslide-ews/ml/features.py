"""Feature engineering. Fixes the test-set TWI leakage bug from the notebook."""
import numpy as np
import pandas as pd


def expected_accumulation(df: pd.DataFrame) -> pd.Series:
    return df["prev_day_water_accumulation"] + df["today_expected_rain"] ** 2


def topographic_wetness_index(df: pd.DataFrame) -> pd.Series:
    """TWI = ln((accumulation + eps) / tan(slope) + eps).

    NOTE: the notebook computed test TWI using *train* slopes because it did
        slope_rad = np.radians(train_data['slope'])
    twice. Here slope is always read from the SAME frame being transformed.
    """
    slope_rad = np.radians(df["slope"].to_numpy(dtype=float))
    acc = df["water_accumulation"].to_numpy(dtype=float)
    return np.log((acc + 0.001) / (np.tan(slope_rad) + 0.001))


DROP_COLS = [
    "system:index", "prev_end", "prev_start", "today_end",
    "today_start", ".geo", "current_date", "prev_day_water_accumulation",
]


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Deterministic, leak-free feature builder used for train AND test."""
    df = raw.copy()
    df["expected_accumulation"] = expected_accumulation(df)
    df["TWI"] = topographic_wetness_index(df)
    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns], errors="ignore")
    return df