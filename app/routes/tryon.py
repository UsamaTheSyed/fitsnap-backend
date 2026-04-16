from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from app.services.ai_pipeline import generate_tryon
from app.utils.storage import save_uploaded_file, get_output_url
import os

router = APIRouter()

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
