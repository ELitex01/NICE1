
import ee
import pandas as pd
import math

def extract_model_features(lat, lon, start_date, end_date, is_landslide):
    """
    Extracts static and daily dynamic features for a coordinate over a specific date range.
    Returns a Pandas DataFrame formatted for training, dropping lat/lon coordinates.
    """
    point = ee.Geometry.Point([lon, lat])
    
    # ==========================================
    # 1. STATIC FEATURES (Topography & Land Cover)
    # ==========================================
    # DEM: Elevation, Slope, Aspect
    glo30_collection = ee.ImageCollection('COPERNICUS/DEM/GLO30')
    glo30_proj = glo30_collection.first().projection()

# Stitch the collection into a single image and maintain its native projection
    dem = glo30_collection.select('DEM').mosaic().setDefaultProjection(glo30_proj)
    terrain = ee.Terrain.products(dem)
    
    topo_stats = terrain.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=point, scale=30
    ).getInfo()
    
    elevation = topo_stats.get('DEM', 0)
    slope = topo_stats.get('slope', 0)
    aspect = topo_stats.get('aspect', 0)
    
    # Approximation of Topographic Wetness Index (TWI)
    # TWI = ln(a / tan(beta)) where 'a' is catchment area and beta is slope.
    # For a point extraction, we approximate using a standard localized constant if a full flow-accumulation raster isn't available.
    slope_rad = math.radians(slope) if slope > 0 else 0.001
    wetness_index = math.log(30 / math.tan(slope_rad)) if slope_rad > 0 else 0
    
    # LULC (ESA WorldCover 10m)
    lulc = ee.ImageCollection("ESA/WorldCover/v100").first()
    lulc_class = lulc.reduceRegion(
        reducer=ee.Reducer.first(), geometry=point, scale=10
    ).getInfo().get('Map', 0)

    # ==========================================
    # 2. DYNAMIC FEATURES (Time-Series over Dates)
    # ==========================================
    # Daily Rainfall (GPM IMERG)
    precip_collection = ee.ImageCollection('NASA/GPM_L3/IMERG_V07') \
        .select('precipitation') \
        .filterBounds(point) \
        .filterDate(start_date, end_date)
        
    # Soil Moisture (ERA5-Land)
    soil_collection = ee.ImageCollection('ECMWF/ERA5_LAND/HOURLY') \
        .select('volumetric_soil_water_layer_1') \
        .filterBounds(point) \
        .filterDate(start_date, end_date)
        
    # NDVI (Sentinel-2, taking the mean over the period as a baseline)
    ndvi_collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterBounds(point) \
        .filterDate(start_date, end_date) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
    
    # Compute mean NDVI for the given period
    if ndvi_collection.size().getInfo() > 0:
        ndvi_img = ndvi_collection.map(lambda img: img.normalizedDifference(['B8', 'B4'])).mean()
        ndvi = ndvi_img.reduceRegion(reducer=ee.Reducer.mean(), geometry=point, scale=10).getInfo().get('nd', 0)
    else:
        ndvi = 0
        
    # Aggregate daily rainfall and soil moisture into lists
    # (In a real pipeline, you would map over the collection to get a daily time-series. 
    # Here we simulate extracting the daily metrics for the requested period).
    
    # For this function, we will pull the mean values for the date range requested. 
    # If the date range is a single day (e.g., the day of the landslide), it pulls that day's exact data.
    rainfall_today = precip_collection.sum().reduceRegion(
        reducer=ee.Reducer.mean(), geometry=point, scale=10000
    ).getInfo().get('precipitation', 0)
    
    volumetric_soil_moisture = soil_collection.mean().reduceRegion(
        reducer=ee.Reducer.mean(), geometry=point, scale=11132
    ).getInfo().get('volumetric_soil_water_layer_1', 0)

    # ==========================================
    # 3. BUILD THE DATAFRAME
    # ==========================================
    feature_dict = {
        'rainfall_today': rainfall_today,
        'volumetric_soil_moisture': volumetric_soil_moisture,
        'wetness_index': wetness_index,
        'NDVI': ndvi,
        'elevation': elevation,
        'slope': slope,
        'aspect': aspect,
        'LULC': lulc_class,
        'is_landslide': is_landslide
    }
    
    # Return as a DataFrame row, explicitly without lat/lon
    return pd.DataFrame([feature_dict])
