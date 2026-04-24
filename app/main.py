from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routes import tryon
from app.routes import store_routes
from app.routes import measurements
from app.routes import stylist
from app.routes import widget_routes
from app.database import init_db
import os

app = FastAPI(title="FitSnap AI Try-On Backend")

# Allow CORS for Flutter app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure outputs directory exists
OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Ensure static directory exists for widget assets
STATIC_DIR = "static"
os.makedirs(STATIC_DIR, exist_ok=True)

# Initialize widget database
init_db()

# Mount outputs directory to serve generated images
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

# Mount static directory for widget.js and demo page
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(tryon.router)
app.include_router(store_routes.router)
app.include_router(measurements.router)
app.include_router(stylist.router)
app.include_router(widget_routes.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to FitSnap AI Try-On API"}

@app.get("/ping")
def ping():
    """Endpoint used by cron-job.org to keep the Render free tier awake"""
    return {"status": "ok", "message": "pong"}
