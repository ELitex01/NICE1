"""
train_save.py — v2 (upgraded to match model.ipynb)

CHANGES vs v1 (all taken from model.ipynb):
  1. prev_day_water_accumulation is now KEPT as a feature (14 features).
  2. TWI computed with each split's OWN slope (leak fix).
  3. DT / RF / GB / XGB tuned with RandomizedSearchCV (same grids as notebook).
  4. Per-model threshold optimizer: scan 0.70→0.90, maximise F1.
  5. Soft-voting ENSEMBLE of the 4 tuned models.
  6. Saves ensemble as sih_landslide.pkl + model_metadata.json.

Usage:  python train_save.py   (~10-20 min with the search)
"""
import json, pickle, warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np, pandas as pd
from sklearn.ensemble import (GradientBoostingClassifier,
                              RandomForestClassifier, VotingClassifier)
from sklearn.metrics import (classification_report, confusion_matrix,
                             f1_score, recall_score)
from sklearn.model_selection import RandomizedSearchCV
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")
BASE = Path(__file__).resolve().parent

# NOTE: prev_day_water_accumulation is NO LONGER dropped (it is a feature now)
DROP = ["system:index", "prev_end", "prev_start", "today_end",
        "today_start", ".geo", "current_date"]

def merge_csv(folder):
    files = sorted((BASE / folder).glob("*.csv"))
    if not files: raise FileNotFoundError(f"No CSV files found in {BASE / folder}")
    print(f"{folder}/ -> {len(files)} file(s)")
    return pd.concat([pd.read_csv(p) for p in files], ignore_index=True)

def engineer(df):
    df = df.copy()
    df["expected_accumulation"] = (df["prev_day_water_accumulation"]
                                   + df["today_expected_rain"] ** 2)
    slope_rad = np.radians(df["slope"])          # ← df's OWN slope (leak fix)
    df["TWI"] = np.log((df["water_accumulation"] + 0.001)
                       / (np.tan(slope_rad) + 0.001))
    return df.drop(columns=[c for c in DROP if c in df.columns])

print("Loading data...")
train_df = engineer(merge_csv("train"))
test_df  = engineer(merge_csv("test"))
print(f"rows: train={len(train_df)} test={len(test_df)}")

y_train = train_df["is_landslide"]; X_train = train_df.drop(columns=["is_landslide"])
y_test  = test_df["is_landslide"];  X_test  = test_df.drop(columns=["is_landslide"])

# ── 1. models + grids (identical to model.ipynb) ────────────────────────
models = {
    "Decision Tree":  DecisionTreeClassifier(random_state=42),
    "Random Forest":  RandomForestClassifier(random_state=42),
    "Gradient Boost": GradientBoostingClassifier(random_state=42),
    "XGBoost":        XGBClassifier(random_state=42, eval_metric="logloss"),
}
params = {
    "Decision Tree": {"criterion": ["gini","entropy"],
        "max_depth": [3,5,7,10,15,None], "min_samples_split": [2,5,10,20],
        "min_samples_leaf": [1,2,5,10], "max_features": [None,"sqrt","log2"],
        "class_weight": [None,"balanced"]},
    "Random Forest": {"n_estimators": [100,200,300,500],
        "max_depth": [5,10,15,20,None], "min_samples_split": [2,5,10],
        "min_samples_leaf": [1,2,4], "max_features": ["sqrt","log2",None],
        "bootstrap": [True,False],
        "class_weight": [None,"balanced","balanced_subsample"]},
    "Gradient Boost": {"n_estimators": [100,200,300,500],
        "learning_rate": [0.01,0.05,0.1,0.2], "max_depth": [3,5,7,9],
        "subsample": [0.6,0.8,1.0], "min_samples_split": [2,5,10],
        "min_samples_leaf": [1,2,4], "max_features": ["sqrt","log2",None]},
    "XGBoost": {"n_estimators": [300,500], "learning_rate": [0.05,0.1],
        "max_depth": [5,7], "scale_pos_weight": [0.5,0.75,1.0],
        "subsample": [0.6,0.8,1.0], "colsample_bytree": [0.6,0.8,1.0],
        "min_child_weight": [1,3,5,7], "gamma": [0,0.1,0.2,0.3],
        "reg_alpha": [0,0.01,0.1,1,10], "reg_lambda": [0,0.01,0.1,1,10]},
}

# ── 2. master tuning loop + F1 threshold optimiser ──────────────────────
results_list, best_models = [], {}
print("Starting Master Hyperparameter Search...")
for name in models:
    print(f"--- Tuning {name} ---")
    search = RandomizedSearchCV(estimator=models[name],
        param_distributions=params[name], n_iter=20, scoring="roc_auc",
        cv=3, n_jobs=-1, random_state=42)
    search.fit(X_train, y_train)
    best_models[name] = search.best_estimator_

    y_probs = best_models[name].predict_proba(X_test)[:, 1]
    best_thresh, best_f1 = 0.70, 0.0
    for thresh in np.arange(0.70, 0.91, 0.01):
        f1 = f1_score(y_test, (y_probs > thresh).astype(int))
        if f1 > best_f1: best_f1, best_thresh = f1, float(thresh)

    print(f"✅ Best Params: {search.best_params_}")
    print(f"✅ Optimal Threshold: {best_thresh:.2f} (F1: {best_f1:.4f})\n")
    results_list.append({"Model": name, "Best F1 Score": best_f1,
                         "Optimal Threshold": best_thresh})

leaderboard = pd.DataFrame(results_list).sort_values("Best F1 Score", ascending=False)
print("🏆 FINAL MODEL LEADERBOARD ( >= 0.70 THRESHOLD ) 🏆")
print(leaderboard.to_string(index=False))

# ── 3. feature importances (tuned XGBoost, like the notebook plot) ──────
importance_df = pd.DataFrame({
    "Feature": X_train.columns,
    "Importance": best_models["XGBoost"].feature_importances_,
}).sort_values("Importance", ascending=False)
print("\n--- Geospatial Feature Importance (tuned XGBoost) ---")
print(importance_df.to_string(index=False))

# ── 4. soft-voting ensemble of the 4 tuned models ───────────────────────
print("\n🤝 BUILDING ENSEMBLE (SOFT VOTING) 🤝")
ensemble_model = VotingClassifier(
    estimators=[(n, m) for n, m in best_models.items()],
    voting="soft", n_jobs=-1)
print("Training the Ensemble Model...")
ensemble_model.fit(X_train, y_train)

y_probs_ensemble = ensemble_model.predict_proba(X_test)[:, 1]
best_ensemble_thresh, best_ensemble_f1 = 0.70, 0.0
for thresh in np.arange(0.70, 0.91, 0.01):
    f1 = f1_score(y_test, (y_probs_ensemble > thresh).astype(int))
    if f1 > best_ensemble_f1:
        best_ensemble_f1, best_ensemble_thresh = f1, float(thresh)

final_preds = (y_probs_ensemble > best_ensemble_thresh).astype(int)
print(f"\n✅ Optimal Ensemble Threshold: {best_ensemble_thresh:.2f}")
print("--- FINAL ENSEMBLE PERFORMANCE ---")
print(confusion_matrix(y_test, final_preds))
print(classification_report(y_test, final_preds))

# ── 5. SAVE ensemble + metadata (what the server loads) ─────────────────
with open(BASE / "sih_landslide.pkl", "wb") as f:
    pickle.dump(ensemble_model, f)

meta = {
    "model_type": "SoftVotingEnsemble(DT+RF+GB+XGB)",
    "trained_at": datetime.now(timezone.utc).isoformat(),
    "threshold": best_ensemble_thresh,
    "features": list(X_train.columns),
    "train_rows": int(len(X_train)),
    "ensemble_accuracy": float((final_preds == y_test).mean()),
    "ensemble_recall": float(recall_score(y_test, final_preds)),
    "ensemble_f1": float(best_ensemble_f1),
    "leaderboard": results_list,
    "feature_importance": dict(zip(importance_df.Feature,
                                   importance_df.Importance.round(4))),
}
(BASE / "model_metadata.json").write_text(json.dumps(meta, indent=2))
print(f"\n✅ Ensemble saved as sih_landslide.pkl (+ model_metadata.json)")
print("Next: restart model_server.py")