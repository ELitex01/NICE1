"""Alert dispatcher — SMS (MSG91, DLT) + FCM push, multi-language, deduped."""
import json
import celery
from sqlalchemy import text
from ..database import SessionLocal
from ..settings import settings

app = celery.Celery("notify", broker=settings.redis_url)

LANG_MAP = {"as":"assamese","hi":"hindi","en":"english","kha":"khasi",
            "lus":"mizo","mni":"manipuri","nag":"nagamese"}

def load_template(lang: str, band: str) -> str:
    path = f"notifications/templates/{lang}.json"
    try:
        return json.load(open(path))[band]
    except FileNotFoundError:
        return json.load(open("notifications/templates/en.json"))[band]

@app.task(name="dispatch_alert")
def dispatch_alert(district_id, band, prob, model_version, transition, drivers):
    db = SessionLocal()
    district = db.execute(text("SELECT name FROM districts WHERE id=:d"),
                          {"d": district_id}).scalar()

    subs = db.execute(text("""
        SELECT u.phone, u.preferred_lang, s.channel
        FROM subscriptions s JOIN users u ON u.id=s.user_id
        WHERE s.district_id=:d
    """), {"d": district_id}).mappings().all()

    sms_sent = push_sent = 0
    langs_used = set()
    for sub in subs:
        lang = sub["preferred_lang"] or "en"
        msg = load_template(lang, band).format(district=district, prob=int(prob*100))
        langs_used.add(lang)
        if sub["channel"] in ("sms", "both") and sub["phone"]:
            from notifications.sms_msg91 import send_sms
            if send_sms(sub["phone"], msg, band): sms_sent += 1
        if sub["channel"] in ("push", "both"):
            from notifications.push_fcm import send_push
            if send_push(sub["user_id"], f"⚠️ {district}", msg): push_sent += 1

    db.execute(text("""
        INSERT INTO alert_log(district_id,risk_band,probability,model_version,
            transition_type,recipient_count,channels,languages)
        VALUES(:d,:b,:p,:v,:t,:n,:ch,:lg)
    """), {"d": district_id, "b": band, "p": prob, "v": model_version,
           "t": transition, "n": sms_sent + push_sent,
           "ch": ["sms", "push"], "lg": list(langs_used)})
    db.commit()
    db.close()