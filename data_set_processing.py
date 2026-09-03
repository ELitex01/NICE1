import ee
import pandas as pd
import geopandas as gpd
import random
import math
import concurrent.futures
from tqdm import tqdm
from feature_extraction import extract_model_features

# 1. Authenticate once at the top level
ee.Authenticate(force=True)

def extract_dataframe(start_date, end_date):
    # Initialize Earth Engine
    ee.Initialize(project='meta-imagery-469108-b9')

    print("Loading Shapefile and generating coordinates...")
    gdf = gpd.read_file("Data/GSI_Landslide_Inventory.shp")

    # Limit to the first 10,000 landslides to keep the total dataset at 20,000 rows
    gdf_subset = gdf.head(100)

    # Generate positive samples
    positive_samples = []
    for idx, row in gdf_subset.iterrows():
        positive_samples.append({
            'lat': row.geometry.y,
            'lon': row.geometry.x,
            'start_date': start_date, 
            'end_date': end_date, 
            'is_landslide': 1
        })

    # Generate an equal number of negative (safe) samples (10,000)
    negative_samples = []
    for _ in range(len(positive_samples)):
        negative_samples.append({
            'lat': random.uniform(22.0, 29.5),
            'lon': random.uniform(88.0, 97.5),
            'start_date': start_date,
            'end_date': end_date,
            'is_landslide': 0
        })

    input_data = positive_samples + negative_samples
    random.shuffle(input_data)
    print(f"Total coordinates to process: {len(input_data)}") # Will print exactly 20,000
    # Worker function for threading safely
    def process_row(row):
        try:
            return extract_model_features(
                lat=row['lat'], 
                lon=row['lon'], 
                start_date=row['start_date'], 
                end_date=row['end_date'], 
                is_landslide=row['is_landslide']
            )
        except Exception as e:
            # Silently catch individual point errors so the loop doesn't break
            return None

    results = []
    print("Starting parallel extraction with Google Earth Engine...")
    
    # Using 10 workers to speed things up without triggering Google API rate limits
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_row, row): row for row in input_data}
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(input_data)):
            res = future.result()
            if res is not None:
                results.append(res)

    if results:
        df = pd.concat(results, ignore_index=True) 
        return df
    else:
        print("Extraction failed. Check your internet connection.")
        return None