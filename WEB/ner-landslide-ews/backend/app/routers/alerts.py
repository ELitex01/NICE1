from fastapi import APIRouter, Depends
from sqlalchemy import text
from ..database import get_db
from ..auth import require_role

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

@router.get("")
def alert_history(district_id: int = None, db=Depends(get_db),
                  _=Depends(require_role("district_admin"))):
    q = "SELECT * FROM alert_log"
    p = {}
    if district_id: q += " WHERE district_id=:d"; p["d"] = district_id
    q += " ORDER BY triggered_at DESC LIMIT 500"
    return [dict(r) for r in db.execute(text(q), p).mappings()]

@router.post("/subscribe")
def subscribe(district_id: int, channel: str = "both",
              db=Depends(get_db), user=Depends(require_role("resident"))):
    db.execute(text("""
        INSERT INTO subscriptions(user_id,district_id,channel)
        VALUES(:u,:d,:c) ON CONFLICT DO UPDATE SET channel=EXCLUDED.channel
    """), {"u": user["sub"], "d": district_id, "c": channel})
    db.commit()
    return {"status": "subscribed"}