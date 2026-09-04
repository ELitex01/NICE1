"""MSG91 transactional SMS — DLT-compliant for India bulk SMS."""
import requests
from backend.app.settings import settings

DLT_TEMPLATES = {"HIGH": "MSG91_DLT_TEMPLATE_ID_HIGH",
                 "MEDIUM": "MSG91_DLT_TEMPLATE_ID_MED"}

def send_sms(phone: str, message: str, band: str) -> bool:
    try:
        r = requests.post("https://control.msg91.com/api/v5/flow/", json={
            "flow_id": settings.msg91_dlt_template_id_high if band == "HIGH"
                       else settings.msg91_dlt_template_id_med,
            "sender": settings.msg91_sender,
            "recipients": [{"mobiles": phone, "message": message}],
        }, headers={"authkey": settings.msg91_auth_key}, timeout=10)
        return r.status_code == 200
    except Exception:
        return False