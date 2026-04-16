import os
import shutil
from fastapi import UploadFile, Request

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def save_uploaded_file(upload_file: UploadFile, prefix=""):
    file_path = os.path.join(UPLOAD_DIR, f"{prefix}{upload_file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return file_path

def get_output_url(filename: str, request: Request = None):
    """Build output URL dynamically based on the incoming request host."""
    if request:
        # Use the actual host the request came from (works on cloud + local)
        return f"{request.url.scheme}://{request.headers.get('host')}/outputs/{filename}"
    # Fallback: use environment variable or default
    base = os.getenv("BASE_URL", "http://localhost:8000")
    return f"{base}/outputs/{filename}"
