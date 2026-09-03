"""Train, tune, threshold, and version the landslide classifier.

Fixes vs. the notebook:
  1. TWI computed on each split independently (no cross-frame leakage).
  2. Model actually persisted with joblib + a metadata JSON (versioned).
  3. Regularized hyperparameters; optional Optuna CV search.
  4. Proper train/val/test split; threshold tuned on VAL, reported on TEST.
  5. SHAP importances saved for the explainability service.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.metrics import (classification_report, confusion_matrix,
                             recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler

from config import (FEATURE_COLS, MODEL_DIR, RECALL_TARGET, TARGET_COL,
                    THRESHOLD_SEARCH, XGB_PARAMS)
from features import build_features


def load_split(folder: str) -> pd.DataFrame:
    """merge_csv equivalent — reads every CSV under data/{folder}."""
    frames = [pd.read_csv(p) for p in Path("data").joinpath(folder).glob("*.csv")]
    return pd.concat(frames, ignore_index=True)


def find_threshold(model, X, y, target_recall=RECALL_TARGET):
    """Highest threshold that still hits the recall target (minimize false alarms)."""
    probs = model.predict_proba(X)[:, 1]
    best = 0.5
    for t in np.arange(*THRESHOLD_SEARCH, -0.01):
        if recall_score(y, (probs > t).astype(int)) >= target_recall:
            best = round(float(t), 2)
            break
    return best, probs


def main(cv_search: bool = False):
    # ── 1. Load & engineer features (leak-free) ─────────────────────────
    train_raw, test_raw = load_split("train"), load_split("test")
    train_df, test_df = build_features(train_raw), build_features(test_raw)

    X = train_df.drop(columns=[TARGET_COL])
    y = train_df[TARGET_COL]
    X_test = test_df.drop(columns=[TARGET_COL])
    y_test = test_df[TARGET_COL]

    # ── 2. Split train into train/val for threshold tuning ──────────────
    X_tr, X_val, y_tr, y_val = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42)

    # ── 3. Optional Optuna hyperparameter search ───────────────────────
    params = XGB_PARAMS
    if cv_search:
        import optuna
        def objective(trial):
            p = dict(
                n_estimators=trial.suggest_int("n_estimators", 200, 800),
                max_depth=trial.suggest_int("max_depth", 3, 6),
                learning_rate=trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                subsample=trial.suggest_float("subsample", 0.6, 1.0),
                colsample_bytree=trial.suggest_float("colsample_bytree", 0.6, 1.0),
                min_child_weight=trial.suggest_int("min_child_weight", 1, 5),
                reg_alpha=trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
                reg_lambda=trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
                eval_metric="logloss", random_state=42, n_jobs=-1,
            )
            model = xgb.XGBClassifier(**p)
            skf = StratifiedKFold(3, shuffle=True, random_state=42)
            recalls = []
            for tr_i, va_i in skf.split(X_tr, y_tr):
                model.fit(X_tr.iloc[tr_i], y_tr.iloc[tr_i],
                          eval_set=[(X_tr.iloc[va_i], y_tr.iloc[va_i])],
                          verbose=False)
                preds = model.predict(X_tr.iloc[va_i])
                recalls.append(recall_score(y_tr.iloc[va_i], preds))
            return np.mean(recalls)
        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=40, show_progress_bar=True)
        params = {**XGB_PARAMS, **study.best_params,
                  "eval_metric": "logloss", "random_state": 42, "n_jobs": -1}
        print("Best CV recall:", study.best_value, "| params:", study.best_params)

    # ── 4. Fit final model on full training split ──────────────────────
    model = xgb.XGBClassifier(**params)
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

    # ── 5. Threshold on validation, then freeze ────────────────────────
    threshold, _ = find_threshold(model, X_val, y_val)
    print(f"Chosen threshold (val recall ≥ {RECALL_TARGET}): {threshold}")

    # ── 6. Test-set evaluation (honest, post-fix) ──────────────────────
    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob > threshold).astype(int)
    print("\n=== TEST SET (leak-free) ===")
    print(confusion_matrix(y_test, y_pred))
    print(classification_report(y_test, y_pred))
    print("ROC-AUC:", roc_auc_score(y_test, y_prob))

    # ── 7. SHAP global + sample explanation ────────────────────────────
    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(X_test[:200])
    mean_abs = np.abs(shap_vals).mean(axis=0)
    shap_summary = {f: float(v) for f, v in
                    sorted(zip(FEATURE_COLS, mean_abs), key=lambda kv: -kv[1])}

    # ── 8. Persist — the notebook NEVER did this ───────────────────────
    version = datetime.now(timezone.utc).strftime("v%Y.%m.%d-") + uuid.uuid4().hex[:6]
    out_dir = MODEL_DIR / version
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_dir / "model.pkl")
    joblib.dump({"cols": FEATURE_COLS}, out_dir / "preprocessor.pkl")

    meta = {
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "threshold": threshold,
        "recall_target": RECALL_TARGET,
        "val_recall": float(recall_score(y_val, (model.predict_proba(X_val)[:,1] > threshold).astype(int))),
        "test_recall": float(recall_score(y_test, y_pred)),
        "test_precision": float((y_pred[y_test==1]==1).mean()) if y_pred.sum() else 0.0,
        "roc_auc": float(roc_auc_score(y_test, y_prob)),
        "hyperparams": params,
        "feature_cols": FEATURE_COLS,
        "shap_importance": shap_summary,
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    (MODEL_DIR / "ACTIVE").write_text(version)      # pointer for the API
    print(f"\nModel saved → {out_dir}  (ACTIVE → {version})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cv-search", action="store_true",
                    help="run Optuna CV hyperparameter search")
    main(ap.parse_args().cv_search)