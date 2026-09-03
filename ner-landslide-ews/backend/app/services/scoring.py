"""Scheduled job (Celery beat, every 3 h): score all districts, detect band
transitions, and hand off to the notification dispatcher."""
from datetime import datetime, timezone
import celery
from sqlalchemy import text
from ..database import SessionLocal
from . import model_registry as mr
from .notification import dispatch_alert
from ..settings import settings

app = celery.Celery("scoring", broker=settings.redis_url)

@app.task(name="score_all_districts")
def score_all_districts():
    db = SessionLocal()
    meta = mr.model_info()
    districts = db.execute(text("""
        SELECT d.id, d.name,
               COALESCE(jsonb_object_agg(w.k, w.v), '{}'::jsonb) feats
        FROM districts d
        LEFT JOIN LATERAL (
            SELECT 'rain_72h_mm' k, rain_72h_mm v FROM weather_features
            WHERE district_id=d.id ORDER BY ts DESC LIMIT 1) w ON true
        GROUP BY d.id, d.name
    """)).mappings().all()

    for d in districts:
        features = assemble_features(db, d["id"])       # pull latest from each store
        if not features: continue
        prob = mr.predict_proba(features)
        band_now = mr.band(prob, meta)
        drivers = mr.explain(features)
        prev_band = last_band(db, d["id"])

        db.execute(text("""
            INSERT INTO risk_scores(ts,district_id,model_version,probability,
                                    risk_band,features_used,shap_top)
            VALUES(now(),:d,:v,:p,:b,:f,:s)
        """), {"d": d["id"], "v": meta["version"], "p": prob, "b": band_now,
               "f": __import__("json").dumps(features),
               "s": __import__("json").dumps(drivers)})
        db.execute(text("REFRESH MATERIALIZED VIEW mv_latest_risk"))
        db.commit()

        transition = detect_transition(prev_band, band_now, db, d["id"])
        if transition:
            dispatch_alert.delay(d["id"], band_now, prob, meta["version"],
                                 transition, drivers)

def detect_transition(prev, now, db, district_id):
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    if prev is None:
        return "INITIAL" if now != "LOW" else None
    if order[now] > order[prev]:
        return f"RISE_TO_{now}"
    if now == "HIGH" and prev == "HIGH":
        # re-confirmation after cooldown — check last alert time
        last = db.execute(text("""
            SELECT max(triggered_at) FROM alert_log WHERE district_id=:d
        """), {"d": district_id}).scalar()
        if last is None or (datetime.now(timezone.utc) - last).total_seconds()/60 \
                >= settings.alert_cooldown_minutes:
            return "SUSTAINED_HIGH"
    return None

def last_band(db, district_id):
    r = db.execute(text("""
        SELECT risk_band FROM risk_scores
        WHERE district_id=:d ORDER BY ts DESC LIMIT 1 OFFSET 1
    """), {"d": district_id}).first()
    return r[0] if r else None

def assemble_features(db, district_id) -> dict | None:
    """Join latest weather + satellite + sensor into the model's feature dict."""
    row = db.execute(text("""
        SELECT sf.ndvi, sf.soil_moisture volumetric_soil_moisture,
               sf.soil_temperature_k, sf.elevation_m, sf.slope_deg,
               sf.aspect_deg, sf.twi, w.rain_24h_mm, w.rain_72h_mm,
               w.rain_forecast_mm today_expected_rain, w.rain_probability
        FROM satellite_features sf
        JOIN weather_features w USING (district_id)
        WHERE sf.district_id=:d
        ORDER BY sf.ts DESC, w.ts DESC LIMIT 1
    """), {"d": district_id}).mappings().first()
    if not row: return None
    f = dict(row)
    f["Map"] = 10
    f["water_accumulation"] = f["rain_24h_mm"] or 1.0
    f["max_water_accumulation"] = max(f["rain_72h_mm"] or 1.0, 1.0)
    f["expected_accumulation"] = (f["rain_72h_mm"] or 0) + (f["today_expected_rain"] or 0)**2
    f["TWI"] = f["twi"]
    return f