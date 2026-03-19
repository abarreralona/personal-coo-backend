"""
IOlabs AI SDR Platform — FastAPI Application Entry Point
Stage 14 fully implemented. Routers registered here.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import webhooks, triggers, admin

app = FastAPI(
    title="IOlabs AI SDR Platform",
    version="2.0.0",
    description="Fully automated, multi-tenant outbound SDR platform.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to known origins in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(webhooks.router)
app.include_router(triggers.router)
app.include_router(admin.router)
