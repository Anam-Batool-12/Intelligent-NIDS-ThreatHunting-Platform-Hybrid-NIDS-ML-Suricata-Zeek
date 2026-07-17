"""
Main FastAPI Application

What this does:
1. Creates the FastAPI app
2. Connects the alerts, timeline, and stats endpoints to it
3. When you run this, it starts a web server on port 8000

Run with:
    uvicorn api.main:app --reload
Then visit http://localhost:8000/docs to see all available endpoints.
"""

from fastapi import FastAPI

from api.routers import alerts, timeline, stats

app = FastAPI(title="NIDS Alert API")

app.include_router(alerts.router)
app.include_router(timeline.router)
app.include_router(stats.router)


@app.get("/")
def home():
    return {
        "message": "NIDS Alert API is running.",
        "available_endpoints": ["/alerts", "/timeline", "/stats", "/docs"]
    }
