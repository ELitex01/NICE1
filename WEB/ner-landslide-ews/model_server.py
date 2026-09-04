"""Serves the ENSEMBLE model (sih_landslide.pkl) + dashboard at http://localhost:8000
Usage: python model_server.py   (same Anaconda env you trained in)"""
import json, math, pickle
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
DASHBOARD = BASE / "dashboard"

MODEL_FILE = BASE / "sih_landslide.pkl"      # ← NEW ensemble model
_meta_p = BASE / "model_metadata.json"
THRESHOLD = float(json.loads(_meta_p.read_text()).get("threshold", 0.70)) if _meta_p.exists() else 0.70                             # ← ensemble optimal threshold

# 14 features in EXACT training order (prev_day_water_accumulation added)
FEATURES = [
    "Map","NDVI","aspect","elevation","max_water_accumulation",
    "prev_day_water_accumulation","slope","soil_temperature",
    "today_expected_rain","today_rain_probability",
    "volumetric_soil_moisture","water_accumulation",
    "expected_accumulation","TWI",
]

MODEL = None
try:
    with open(MODEL_FILE, "rb") as f:
        MODEL = pickle.load(f)
    print(" Ensemble model loaded (DT+RF+GB+XGB):", MODEL_FILE.name)
except FileNotFoundError:
    print("sih_landslide.pkl not found — run all cells of model.ipynb first")

def build_features(d):
    slope = float(d.get("slope", 20))
    rain  = float(d.get("today_expected_rain", 0))
    prev  = float(d.get("prev_day_water_accumulation", 0))
    wa    = float(d.get("water_accumulation", 1))
    f = {
        "Map": float(d.get("Map", 10)),
        "NDVI": float(d.get("NDVI", 0.3)),
        "aspect": float(d.get("aspect", 180)),
        "elevation": float(d.get("elevation", 500)),
        "max_water_accumulation": float(d.get("max_water_accumulation", max(wa, 1))),
        "prev_day_water_accumulation": prev,
        "slope": slope,
        "soil_temperature": float(d.get("soil_temperature", 297)),
        "today_expected_rain": rain,
        "today_rain_probability": float(d.get("today_rain_probability", 0)),
        "volumetric_soil_moisture": float(d.get("volumetric_soil_moisture", 0.35)),
        "water_accumulation": wa,
    }
    f["expected_accumulation"] = prev + rain * rain      # same formula as notebook
    f["TWI"] = math.log((wa + 0.001) / (math.tan(math.radians(slope)) + 0.001))
    return f

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DASHBOARD), **kw)

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self): self._json({})

    def do_GET(self):
        if self.path == "/api/health":
            self._json({"model_loaded": MODEL is not None,
                        "model": "Ensemble (DT+RF+GB+XGB, soft voting)",
                        "threshold": THRESHOLD})
        else:
            super().do_GET()

    def do_POST(self):
        if self.path != "/api/predict":
            self._json({"error": "not found"}, 404); return
        if MODEL is None:
            self._json({"error": "model not trained — run model.ipynb first"}, 503); return
        n = int(self.headers.get("Content-Length", 0))
        d = json.loads(self.rfile.read(n) or b"{}")
        X = pd.DataFrame([build_features(d)])[FEATURES]   # enforce column order
        p = float(MODEL.predict_proba(X)[0, 1])
        self._json({
            "probability": round(p, 4),
            "risk_band": "HIGH" if p >= THRESHOLD else ("MEDIUM" if p >= 0.40 else "LOW"),
            "threshold": THRESHOLD,
        })

    def log_message(self, *a): pass

print("🌐 Open http://localhost:8000")
HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()