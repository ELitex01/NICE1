from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from ..database import get_db
from ..schemas import FieldReport
from ..auth import require_role

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.post("")
def submit_report(rep: FieldReport, db=Depends(get_db),
                  user=Depends(require_role("resident"))):
    """Idempotent by (device_id, client_ts) so offline replays don't duplicate."""
    dup = db.execute(text("""
        SELECT id FROM field_reports
        WHERE device_id=:dev AND ts=:ts LIMIT 1
    """), {"dev": rep.device_id, "ts": rep.client_ts}).first()
    if dup:
        return {"status": "already_synced", "id": str(dup[0])}

    row = db.execute(text("""
        INSERT INTO field_reports
          (user_id, district_id, ts, location, report_type, severity,
           description, device_id, offline_queued, synced_at)
        VALUES (:u,
                (SELECT id FROM districts
                 WHERE ST_Intersects(boundary, ST_SetSRID(ST_MakePoint(:lon,:lat),4326))
                 LIMIT 1),
                :ts, ST_SetSRID(ST_MakePoint(:lon,:lat),4326),
                :rt, :sev, :desc, :dev, :off, now())
        RETURNING id
    """), {
        "u": user.get("sub"), "lon": rep.longitude, "lat": rep.latitude,
        "ts": rep.client_ts, "rt": rep.report_type, "sev": rep.severity,
        "desc": rep.description, "dev": rep.device_id,
        "off": rep.client_ts < datetime.now(timezone.utc),
    })
    db.commit()
    return {"status": "created", "id": str(row.scalar())}

@router.get("")
def list_reports(district_id: int = None, db=Depends(get_db),
                 _=Depends(require_role("field_officer"))):
    q = "SELECT * FROM field_reports"
    params = {}
    if district_id:
        q += " WHERE district_id=:d"; params["d"] = district_id
    q += " ORDER BY ts DESC LIMIT 200"
    return [dict(r) for r in db.execute(text(q), params).mappings()]