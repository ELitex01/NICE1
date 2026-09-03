"""Track live recall against confirmed events; alert if < 90 %."""
from sqlalchemy import text
from ..database import SessionLocal

def check_live_recall(window_days=30):
    db = SessionLocal()
    rows = db.execute(text("""
        SELECT gt.occurred_at, gt.district_id,
               (SELECT max(probability) FROM risk_scores rs
                WHERE rs.district_id=gt.district_id
                  AND rs.ts BETWEEN gt.occurred_at - interval '24 hours'
                                AND gt.occurred_at) AS max_prob
        FROM ground_truth_events gt
        WHERE gt.confirmed=true AND gt.occurred_at > now() - :w
    """), {"w": f"{window_days} days"}).mappings().all()

    if not rows: return None
    hits = sum(1 for r in rows if (r["max_prob"] or 0) >= 0.70)
    recall = hits / len(rows)

    if recall < 0.90:
        # trigger ops alert (PagerDuty / email / internal SMS)
        print(f"⚠️ Live recall {recall:.2f} below target 0.90 — retrain needed")
    return recall