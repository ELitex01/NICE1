"""Loads the ACTIVE model version and caches it; exposes predict + SHAP."""
import json
from functools import lru_cache
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import shap
from ..settings import settings

@lru_cache(maxsize=1)
def _load():
    active = (Path(settings.model_dir) / "ACTIVE").read_text().strip()
    d = Path(settings.model_dir) / active
    model = joblib.load(d / "model.pkl")
    meta = json.loads((d / "metadata.json").read_text())
    explainer = shap.TreeExplainer(model)
    return model, meta, explainer

def model_info():
    _, meta, _ = _load()
    return meta

def predict_proba(feature_dict: dict) -> float:
    model, meta, _ = _load()
    X = pd.DataFrame([feature_dict])[meta["feature_cols"]]
    return float(model.predict_proba(X)[0, 1])

def explain(feature_dict: dict, top_n: int = 4):
    model, meta, explainer = _load()
    X = pd.DataFrame([feature_dict])[meta["feature_cols"]]
    sv = explainer.shap_values(X)[0]
    ranked = sorted(zip(meta["feature_cols"], sv), key=lambda kv: -abs(kv[1]))
    return [{"feature": f, "impact": round(float(v), 4)} for f, v in ranked[:top_n]]

def band(p: float, meta) -> str:
    hi = meta["threshold"]
    med = settings.medium_risk_threshold
    return "HIGH" if p >= hi else ("MEDIUM" if p >= med else "LOW")