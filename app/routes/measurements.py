from fastapi import APIRouter, UploadFile, File, HTTPException
import fal_client
import logging
import tempfile
import os

router = APIRouter()
logger = logging.getLogger(__name__)

# Size charts for popular brands (chest in inches)
BRAND_SIZE_CHARTS = {
    "Khaadi": {"S": "36-38", "M": "38-40", "L": "40-42", "XL": "42-44"},
    "Gul Ahmed": {"S": "36-38", "M": "38-40", "L": "40-42", "XL": "42-44"},
    "Bonanza": {"S": "34-36", "M": "36-38", "L": "38-40", "XL": "40-42"},
    "Sapphire": {"S": "36-38", "M": "38-40", "L": "40-42", "XL": "42-44"},
    "Zara": {"S": "34-36", "M": "36-38", "L": "38-40", "XL": "40-42"},
    "H&M": {"S": "34-36", "M": "36-38", "L": "38-40", "XL": "40-42"},
}

# Body type mapping from keywords
BODY_TYPE_KEYWORDS = {
    "slim": ["thin", "slim", "slender", "lean", "narrow"],
    "athletic": ["athletic", "fit", "muscular", "toned", "built", "strong"],
    "average": ["average", "medium", "regular", "normal"],
    "broad": ["broad", "wide", "heavy", "large", "big", "stocky", "plus"],
}


def _detect_body_from_caption(caption: str) -> dict:
    """Parse Florence-2 caption to estimate body type and size."""
    caption_lower = caption.lower()
    
    # Detect body type
    body_type = "average"
    for btype, keywords in BODY_TYPE_KEYWORDS.items():
        if any(kw in caption_lower for kw in keywords):
            body_type = btype
            break
    
    # Map body type to estimated size
    size_map = {
        "slim": "S",
        "athletic": "M",
        "average": "M",
        "broad": "L",
    }
    estimated_size = size_map.get(body_type, "M")
    
    # Gender detection
    gender = "unisex"
    if any(kw in caption_lower for kw in ["woman", "female", "girl", "she", "her", "lady"]):
        gender = "female"
    elif any(kw in caption_lower for kw in ["man", "male", "boy", "he ", "his", "guy"]):
        gender = "male"
    
    # Generate brand recommendations
    brand_sizes = {}
    for brand, chart in BRAND_SIZE_CHARTS.items():
        brand_sizes[brand] = {
            "recommended_size": estimated_size,
            "measurement_range": chart.get(estimated_size, "38-40"),
        }
    
    return {
        "body_type": body_type.capitalize(),
        "estimated_size": estimated_size,
        "gender": gender,
        "brand_recommendations": brand_sizes,
        "caption": caption[:300],
    }


@router.post("/measurements/")
async def estimate_measurements(
    person_image: UploadFile = File(...),
):
    """Estimate body measurements from a person photo using Florence-2."""
    try:
        # Save upload temporarily
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        content = await person_image.read()
        tmp.write(content)
        tmp.close()
        
        # Upload to fal CDN
        image_url = fal_client.upload_file(tmp.name)
        os.remove(tmp.name)
        
        # Get detailed caption from Florence-2
        logger.info("Running Florence-2 for body measurement estimation...")
        result = fal_client.subscribe(
            "fal-ai/florence-2-large/more-detailed-caption",
            arguments={"image_url": image_url},
            with_logs=False,
        )
        
        caption = (
            result.get("results", "")
            or result.get("text", "")
            or result.get("caption", "")
            or result.get("output", "")
            or ""
        ).strip()
        
        logger.info(f"Florence-2 body caption: '{caption[:200]}'")
        
        # Parse caption to body measurements
        measurements = _detect_body_from_caption(caption)
        
        return {"success": True, **measurements}
        
    except Exception as e:
        logger.error(f"Measurement estimation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
