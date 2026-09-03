from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import districts, predict, reports, alerts, health, admin

app = FastAPI(title="NER Landslide EWS API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

for r in (districts.router, predict.router, reports.router,
          alerts.router, health.router, admin.router):
    app.include_router(r)