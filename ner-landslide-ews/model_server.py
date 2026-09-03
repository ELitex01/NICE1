"""Serves dashboard AND your trained model at http://localhost:8000
Usage:  python model_server.py   (same Anaconda prompt you trained in)"""
import json, math, pickle
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
DASHBOARD = BASE / "dashboard"
MODEL = None
META = {"threshold": 0.71, "features": ["Map","NDVI","aspect","elevation",
        "max_water_accumulation","slope","soil_temperature","today_expected_rain",
        "today_rain_probability","volumetric_soil_moisture","water_accumulation",
        "expected_accumulation","TWI"]}
try:
    MODEL = pickle.load(open(BASE/"sih_landslide_xgb_model.pkl","rb"))
    META.update(json.loads((BASE/"model_metadata.json").read_text()))
    print("✅ Model loaded")
except FileNotFoundError:
    print("⚠️ No model yet — run: python train_save.py")

def build_features(d):
    slope=float(d.get("slope",20)); rain=float(d.get("today_expected_rain",0))
    prev=float(d.get("prev_day_water_accumulation",0)); wa=float(d.get("water_accumulation",1))
    f={"Map":float(d.get("Map",10)),"NDVI":float(d.get("NDVI",0.3)),
       "aspect":float(d.get("aspect",180)),"elevation":float(d.get("elevation",500)),
       "max_water_accumulation":float(d.get("max_water_accumulation",max(wa,1))),
       "slope":slope,"soil_temperature":float(d.get("soil_temperature",297)),
       "today_expected_rain":rain,"today_rain_probability":float(d.get("today_rain_probability",0)),
       "volumetric_soil_moisture":float(d.get("volumetric_soil_moisture",0.35)),
       "water_accumulation":wa}
    f["expected_accumulation"]=prev+rain*rain
    f["TWI"]=math.log((wa+0.001)/(math.tan(math.radians(slope))+0.001))
    return f

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(DASHBOARD),**kw)
    def _json(self,obj,code=200):
        b=json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers(); self.wfile.write(b)
    def do_OPTIONS(self): self._json({})
    def do_GET(self):
        if self.path=="/api/health":
            self._json({"model_loaded":MODEL is not None,"threshold":META["threshold"]})
        else: super().do_GET()
    def do_POST(self):
        if self.path!="/api/predict": self._json({"error":"not found"},404); return
        if MODEL is None: self._json({"error":"model not trained — run train_save.py"},503); return
        n=int(self.headers.get("Content-Length",0))
        d=json.loads(self.rfile.read(n) or b"{}")
        X=pd.DataFrame([build_features(d)])[META["features"]]
        p=float(MODEL.predict_proba(X)[0,1]); t=META["threshold"]
        self._json({"probability":round(p,4),
                    "risk_band":"HIGH" if p>=t else ("MEDIUM" if p>=0.40 else "LOW"),
                    "threshold":t})
    def log_message(self,*a): pass

print("🌐 Open  http://localhost:8000")
HTTPServer(("0.0.0.0",8000), Handler).serve_forever()