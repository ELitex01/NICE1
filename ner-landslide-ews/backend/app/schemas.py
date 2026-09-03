from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class PredictRequest(BaseModel):
    latitude: float
    longitude: float
    features: dict = Field(..., description="feature name → value")

class PredictResponse(BaseModel):
    probability: float
    risk_band: str                     # LOW | MEDIUM | HIGH
    threshold_used: float
    model_version: str
    top_drivers: List[dict]            # SHAP-derived trigger analysis
    scored_at: datetime

class DistrictRisk(BaseModel):
    district_id: int
    name: str
    state: str
    lat: float
    lon: float
    risk: float
    band: str
    rain72: Optional[float]
    soilMoist: Optional[float]
    slope: Optional[float]
    elev: Optional[float]
    trigger: str
    model_version: str
    updated_at: datetime
    feed_staleness: dict               # {weather: secs, satellite: secs, sensor: secs}

class FieldReport(BaseModel):
    latitude: float
    longitude: float
    report_type: str
    severity: int = Field(ge=1, le=5)
    description: Optional[str]
    photo_b64: Optional[str]
    device_id: str
    client_ts: datetime                # from offline device clock