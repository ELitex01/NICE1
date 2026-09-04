"""MQTT listener for IoT sensors. Topic: sensors/{district}/{type}/{sensor_id}"""
import json
import paho.mqtt.client as mqtt
from sqlalchemy import text
from backend.app.database import SessionLocal

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
        parts = msg.topic.split("/")          # sensors/5/soil_moisture/SM-001
        _, district_id, sensor_type, sensor_id = parts
        db = SessionLocal()
        db.execute(text("""
            INSERT INTO sensor_readings(ts, sensor_id, district_id, sensor_type, value, unit)
            VALUES (now(), :sid, :d, :t, :v, :u)
        """), {"sid": sensor_id, "d": int(district_id), "t": sensor_type,
               "v": payload["value"], "u": payload.get("unit")})
        db.commit(); db.close()
    except Exception as e:
        print("sensor parse error:", e)

def start():
    c = mqtt.Client()
    c.on_message = on_message
    c.connect("mosquitto", 1883)
    c.subscribe("sensors/#")
    c.loop_forever()