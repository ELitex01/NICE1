from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from ..schemas import PredictRequest, PredictResponse
from ..services import model_registry as mr
from ..auth import get_current_user
from ..database import SessionLocal
from ..services.audit import log_prediction

router = APIRouter(prefix="/api/predict", tags=["predict"])

@router.post("", response_model=PredictResponse)
def predict(req: PredictRequest, _=Depends(get_current_user)):
    meta = mr.model_info()
    prob = mr.predict_proba(req.features)
    drivers = mr.explain(req.features)
    risk_band = mr.band(prob, meta)

    db = SessionLocal()
    log_prediction(db, req, prob, risk_band, meta["version"], drivers)
    db.close()

    return PredictResponse(
        probability=prob, risk_band=risk_band,
        threshold_used=meta["threshold"], model_version=meta["version"],
        top_drivers=drivers, scored_at=datetime.now(timezone.utc),
    )