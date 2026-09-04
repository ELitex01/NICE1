"""Productionize the same GEE export that produced the training CSVs."""
import ee
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from backend.app.database import SessionLocal

ee.Initialize()   # uses GEE_SERVICE_ACCOUNT + key

def build_image_collection(start, end):
    sentinel = (ee.ImageCollection("COPERNICUS/S2_SR")
                .filterDate(start, end).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)))
    era5 = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterDate(start, end)
    dem = ee.Image("USGS/SRTMGL1_003")
    ndvi = sentinel.median().normalizedDifference(["B8", "B4"]).rename("ndvi")
    slope = ee.Terrain.slope(dem.select("elevation"))
    aspect = ee.Terrain.aspect(dem.select("elevation"))
    soil = era5.select("volumetric_soil_water_layer_1").median()
    return ee.Image.cat([ndvi, slope, aspect, soil, dem.select("elevation")])

def accumulate_to_water(img):
    """Flow accumulation proxy from elevation (simplified)."""
    return img  # replace with full hydro model if available

def export_district_features():
    db = SessionLocal()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=3)
    img = build_image_collection(start.isoformat(), end.isoformat())

    districts = db.execute(text(
        "SELECT id, ST_AsGeoJSON(boundary::geometry) gj FROM districts"
    )).all()

    for d_id, gj in districts:
        feat = ee.Feature(ee.Geometry(ee.Geometry.MultiPolygon(
            __import__("json").loads(gj)["coordinates"])))
        stats = img.reduceRegion(ee.Reducer.mean(), feat.geometry(), 30)
        vals = stats.getInfo()

        db.execute(text("""
            INSERT INTO satellite_features
              (ts, district_id, ndvi, soil_moisture, soil_temperature_k,
               elevation_m, slope_deg, aspect_deg, twi)
            VALUES (now(),:d,:ndvi,:sm,NULL,:el,:sl,:asp,NULL)
        """), {"d": d_id, "ndvi": vals.get("ndvi"),
               "sm": vals.get("volumetric_soil_water_layer_1"),
               "el": vals.get("elevation"), "sl": vals.get("slope"),
               "asp": vals.get("aspect")})
    db.commit(); db.close()