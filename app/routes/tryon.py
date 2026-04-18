from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from app.services.ai_pipeline import generate_tryon
from app.utils.storage import save_uploaded_file, get_output_url
import os
import random
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter()

# Thread pool for parallel try-on generation
_executor = ThreadPoolExecutor(max_workers=3)


@router.post("/tryon/")
async def try_on_endpoint(
    request: Request,
    user_image: UploadFile = File(...),
    cloth_image: UploadFile = File(...),
    garment_description: str = Form(""),
):
    try:
        # Save uploads temporarily
        user_img_path = save_uploaded_file(user_image, prefix="user_")
        cloth_img_path = save_uploaded_file(cloth_image, prefix="cloth_")
        
        # Call AI Pipeline with garment description
        output_filename = generate_tryon(user_img_path, cloth_img_path, garment_description)
        
        # Clean up input images to free up space
        if os.path.exists(user_img_path):
            os.remove(user_img_path)
        if os.path.exists(cloth_img_path):
            os.remove(cloth_img_path)
            
        # Return URL — dynamically built from the request host
        image_url = get_output_url(output_filename, request)
        return {"success": True, "image_url": image_url}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tryon/multi/")
async def try_on_multi_endpoint(
    request: Request,
    user_image: UploadFile = File(...),
    cloth_image: UploadFile = File(...),
    garment_description: str = Form(""),
    num_variations: int = Form(3),
):
    """Generate multiple try-on variations with different seeds."""
    try:
        # Clamp variations to 1-5
        num_variations = max(1, min(num_variations, 5))
        
        # Save uploads temporarily
        user_img_path = save_uploaded_file(user_image, prefix="user_")
        cloth_img_path = save_uploaded_file(cloth_image, prefix="cloth_")
        
        # Generate different seeds for each variation
        seeds = [random.randint(0, 999999) for _ in range(num_variations)]
        
        # Run all variations (sequentially to avoid memory issues on free tier)
        image_urls = []
        for seed in seeds:
            output_filename = generate_tryon(
                user_img_path, cloth_img_path, garment_description, seed=seed
            )
            image_url = get_output_url(output_filename, request)
            image_urls.append(image_url)
        
        # Clean up input images
        if os.path.exists(user_img_path):
            os.remove(user_img_path)
        if os.path.exists(cloth_img_path):
            os.remove(cloth_img_path)
            
        return {"success": True, "image_urls": image_urls}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
