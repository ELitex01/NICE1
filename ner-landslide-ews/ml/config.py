"""Central ML config. Single source of truth for features, thresholds, paths."""
from pathlib import Path

MODEL_DIR = Path("/data/models")
FEATURE_COLS = [
    "Map", "NDVI", "aspect", "elevation",
    "max_water_accumulation", "slope", "soil_temperature",
    "today_expected_rain", "today_rain_probability",
    "volumetric_soil_moisture", "water_accumulation",
    "expected_accumulation", "TWI",
]
TARGET_COL = "is_landslide"

# Regularized config — replaces the default-prone notebook settings
XGB_PARAMS = dict(
    n_estimators=400,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=3,
    reg_alpha=0.1,
    reg_lambda=1.0,
    scale_pos_weight=1.0,      # data is balanced 5000/5000
    eval_metric="logloss",
    random_state=42,
    n_jobs=-1,
)

RECALL_TARGET = 0.90           # early-warning objective
THRESHOLD_SEARCH = (0.95, 0.01)  # start, step