"""Celery beat — the heartbeat of the whole system."""
from celery import Celery
from celery.schedules import crontab
from backend.app.settings import settings

app = Celery("scheduler", broker=settings.redis_url)

app.conf.beat_schedule = {
    "imd-every-30m":   {"task": "ingest_imd",     "schedule": crontab(minute="*/30")},
    "gee-every-6h":    {"task": "ingest_gee",     "schedule": crontab(minute=0, hour="*/6")},
    "score-every-3h":  {"task": "score_all_districts", "schedule": crontab(minute=0, hour="*/3")},
    "drift-check-daily": {"task": "check_drift",  "schedule": crontab(hour=6, minute=0)},
}

@app.task(name="ingest_imd")
def ingest_imd():
    from imd_fetcher import fetch_and_store; fetch_and_store()

@app.task(name="ingest_gee")
def ingest_gee():
    from gee_pipeline import export_district_features; export_district_features()