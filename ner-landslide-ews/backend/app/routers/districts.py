from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from ..database import get_db
from ..auth import get_current_user, require_role

router = APIRouter(prefix="/api/districts", tags=["districts"])

@router.get("/risk")
def current_risk(db=Depends(get_db), _=Depends(get_current_user)):
    """Live risk for every district — replaces the hardcoded JS array."""
    q = text("""
        SELECT d.id, d.name, s.code AS state,
               ST_Y(d.centroid::geometry) lat, ST_X(d.centroid::geometry) lon,
               r.probability risk, r.risk_band band, r.model_version,
               r.scored_at updated_at,
               w.rain_72h_mm, sf.soil_moisture, sf.slope_deg, sf.elevation_m,
               r.shap_top
        FROM mv_latest_risk r
        JOIN districts d ON d.id = r.district_id
        JOIN states s ON s.id = d.state_id
        LEFT JOIN LATERAL (
            SELECT rain_72h_mm FROM weather_features
            WHERE district_id=d.id ORDER BY ts DESC LIMIT 1) w ON true
        LEFT JOIN LATERAL (
            SELECT soil_moisture, slope_deg, elevation_m FROM satellite_features
            WHERE district_id=d.id ORDER BY ts DESC LIMIT 1) sf ON true
        ORDER BY r.probability DESC
    """)
    rows = db.execute(q).mappings().all()
    return [dict(r) for r in rows]

@router.get("/risk/history")
def risk_history(district_id: int, hours: int = Query(72, le=168),
                 db=Depends(get_db), _=Depends(get_current_user)):
    """For the 72 h time slider."""
    q = text("""
        SELECT ts, probability, risk_band FROM risk_scores
        WHERE district_id=:d AND ts > now() - make_interval(hours=>:h)
        ORDER BY ts
    """)
    return [dict(r) for r in db.execute(q, {"d": district_id, "h": hours}).mappings()]

@router.get("/feed-status")
def feed_status(db=Depends(get_db), _=Depends(get_current_user)):
    """Staleness per upstream source — drives the dashboard indicators."""
    q = text("""
      SELECT 'weather' src, EXTRACT(EPOCH FROM now()-max(fetched_at)) age FROM weather_features
      UNION ALL
      SELECT 'satellite', EXTRACT(EPOCH FROM now()-max(fetched_at)) FROM satellite_features
      UNION ALL
      SELECT 'sensor', EXTRACT(EPOCH FROM now()-max(received_at)) FROM sensor_readings
    """)
    return {r["src"]: {"age_seconds": r["age"]} for r in db.execute(q).mappings()}

@router.get("/boundaries")
def boundaries(db=Depends(get_db)):
    """District GeoJSON for the choropleth heatmap layer."""
    q = text("""
        SELECT json_build_object(
          'type','FeatureCollection',
          'features', json_agg(json_build_object(
            'type','Feature',
            'properties', json_build_object('id', id, 'name', name),
            'geometry', ST_AsGeoJSON(boundary::geometry)::json))
        ) FROM districts
    """)
    return db.execute(q).scalar()