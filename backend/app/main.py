import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

logging.basicConfig(level=os.getenv("FIW_LOG_LEVEL", "INFO"))

app = FastAPI(
    title="Finance Intelligence Workbench API",
    description="AI reasoning + deterministic financial computation + audit-grade traceability (POC).",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("FIW_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
