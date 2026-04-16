from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routes import tryon
from app.routes import store_routes
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

# Mount outputs directory to serve generated images
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

app.include_router(tryon.router)
app.include_router(store_routes.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to FitSnap AI Try-On API"}
