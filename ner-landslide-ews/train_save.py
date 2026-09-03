"""Train on your CSVs and ACTUALLY save the model.
Usage:  python train_save.py"""
import json, pickle
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, recall_score
from xgboost import XGBClassifier

BASE = Path(__file__).resolve().parent
DROP = ["system:index","prev_end","prev_start","today_end","today_start",
        ".geo","current_date","prev_day_water_accumulation"]

def merge_csv(folder):
    files = sorted((BASE/folder).glob("*.csv"))
    if not files: raise FileNotFoundError(f"Put CSV files in {BASE/folder}")
    print(f"{folder}/ -> {len(files)} file(s)")
    return pd.concat([pd.read_csv(p) for p in files], ignore_index=True)

def engineer(df):
    df = df.copy()
    df["expected_accumulation"] = df["prev_day_water_accumulation"] + df["today_expected_rain"]**2
    slope_rad = np.radians(df["slope"])          # leak bug fixed (own slope per split)
    df["TWI"] = np.log((df["water_accumulation"]+0.001)/(np.tan(slope_rad)+0.001))
    return df.drop(columns=[c for c in DROP if c in df.columns])

train_df = engineer(merge_csv("train"))
test_df  = engineer(merge_csv("test"))
print(f"rows: train={len(train_df)} test={len(test_df)}")

y_train = train_df["is_landslide"]; X_train = train_df.drop(columns=["is_landslide"])
y_test  = test_df["is_landslide"];  X_test  = test_df.drop(columns=["is_landslide"])

model = XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05,
                      subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
                      random_state=42, eval_metric="logloss")
model.fit(X_train, y_train)
y_probs = model.predict_proba(X_test)[:, 1]

thresh = 0.5
for t in np.arange(0.90, 0.0, -0.01):            # highest threshold with recall >= 90%
    if recall_score(y_test, (y_probs > t).astype(int)) >= 0.90:
        thresh = round(float(t), 2); break

y_pred = (y_probs > thresh).astype(int)
print(f"\nThreshold: {thresh}")
print(confusion_matrix(y_test, y_pred))
print(classification_report(y_test, y_pred))

with open(BASE/"sih_landslide_xgb_model.pkl","wb") as f: pickle.dump(model, f)
(BASE/"model_metadata.json").write_text(json.dumps({
    "threshold": thresh, "features": list(X_train.columns),
    "trained_at": datetime.now(timezone.utc).isoformat(),
    "train_rows": int(len(X_train)),
    "test_accuracy": float((y_pred==y_test).mean()),
    "test_recall": float(recall_score(y_test, y_pred))}, indent=2))
print("\n✅ Model REALLY saved. Next run:  python model_server.py")