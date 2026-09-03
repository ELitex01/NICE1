"""Pull IMD rainfall/forecast and map station → district."""
import requests
from datetime import datetime, timezone
from sqlalchemy import text
from backend.app.database import SessionLocal
from backend.app.settings import settings

IMD_RAIN = f"{settings.IMD_API_BASE}/weather/rainfall"
IMD_FORECAST = f"{settings.IMD_API_BASE}/weather/forecast"

def fetch_and_store():
    db = SessionLocal()
    districts = db.execute(text(
        "SELECT id, name, ST_Y(centroid::geometry) lat, ST_X(centroid::geometry) lon FROM districts"
    )).mappings().all()

    for d in districts:
        try:
            r = requests.get(IMD_RAIN, params={
                "lat": d["lat"], "lon": d["lon"], "window": "72h"
            }, headers={"Authorization": f"Bearer {settings.IMD_API_KEY}"}, timeout=15)
            data = r.json()

            db.execute(text("""
                INSERT INTO weather_features
                  (ts, district_id, source, rain_24h_mm, rain_72h_mm,
                   rain_forecast_mm, rain_probability)
                VALUES (:ts,:d,'imd',:r24,:r72,:rf,:rp)
                ON CONFLICT DO UPDATE SET
                  rain_24h_mm=EXCLUDED.rain_24h_mm,
                  rain_72h_mm=EXCLUDED.rain_72h_mm,
                  rain_forecast_mm=EXCLUDED.rain_forecast_mm,
                  rain_probability=EXCLUDED.rain_probability
            """), {
                "ts": datetime.now(timezone.utc), "d": d["id"],
                "r24": data.get("rain_24h"), "r72": data.get("rain_72h"),
                "rf": data.get("forecast_mm"), "rp": data.get("probability"),
            })
        except Exception as e:
            print(f"IMD fetch failed for {d['name']}: {e}")
    db.commit(); db.close()