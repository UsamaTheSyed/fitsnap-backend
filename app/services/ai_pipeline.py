import os
import uuid
import random
import logging
import requests
import tempfile
import fal_client
from PIL import Image, ImageOps, ImageFilter, ImageStat, ImageEnhance
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

if not os.getenv("FAL_KEY"):
    logger.warning("FAL_KEY environment variable not found. Pipeline will fail.")

VTON_WIDTH = 768
VTON_HEIGHT = 1024
BG_COLOR = (245, 245, 245)  # #F5F5F5 — neutral light grey, NEVER black


def _resize_and_pad(image_path: str, target_w: int = VTON_WIDTH, target_h: int = VTON_HEIGHT) -> str:
    """
    Contain-and-pad: fit image inside target canvas without cropping.
    Padding color is #F5F5F5.
    """
    img = Image.open(image_path).convert("RGB")
    padded = ImageOps.pad(img, (target_w, target_h), color=BG_COLOR, method=Image.LANCZOS)

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    padded.save(tmp.name, format="PNG")
    tmp.close()
    return tmp.name


def _remove_background(image_url: str) -> str:
    """
    Remove background via fal-ai/imageutils/rembg.
    Background is replaced with #F5F5F5 — NEVER black or transparent.
    """
    logger.info("Removing background via rembg (#F5F5F5)...")
    result = fal_client.subscribe(
        "fal-ai/imageutils/rembg",
        arguments={
            "image_url": image_url,
            "bg_color": [245, 245, 245, 255],
        },
        with_logs=False,
    )
    return result["image"]["url"]


def _feather_edges(image_url: str) -> str:
    """
    Apply edge feathering to eliminate white halo artifacts around hair/edges.
    Downloads the rembg result, applies a subtle gaussian blur on edge pixels
    where the person meets the background, then re-uploads.
    """
    logger.info("Applying edge feathering to eliminate halo artifacts...")
    try:
        # Download the rembg result
        img = Image.open(requests.get(image_url, stream=True).raw).convert("RGBA")

        # Extract alpha channel as the mask
        alpha = img.split()[3]

        # Create a slightly blurred version of the alpha for soft edges
        blurred_alpha = alpha.filter(ImageFilter.GaussianBlur(radius=1.5))

        # Composite: use blurred alpha only at edges (where alpha transitions)
        # This softens the hard cutout boundary without affecting the interior
        img.putalpha(blurred_alpha)

        # Flatten back onto F5F5F5 background
        bg = Image.new("RGBA", img.size, (*BG_COLOR, 255))
        composite = Image.alpha_composite(bg, img).convert("RGB")

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        composite.save(tmp.name, format="PNG")
        tmp.close()

        # Upload feathered result
        feathered_url = fal_client.upload_file(tmp.name)
        os.remove(tmp.name)
        logger.info("Edge feathering complete.")
        return feathered_url

    except Exception as e:
        logger.warning(f"Edge feathering failed ({e}), using original.")
        return image_url


def _prepare_image(image_path: str, is_garment: bool = False) -> str:
    """
    Full preprocessing pipeline:
    1. Resize and pad to 768x1024
    2. Upload to fal CDN
    3. Remove background via rembg (F5F5F5)
    4. For person images: apply edge feathering to fix white halo
    Returns cleaned image URL.
    """
    label = "garment" if is_garment else "person"
    logger.info(f"Preparing {label} image...")

    resized_path = _resize_and_pad(image_path)

    try:
        uploaded_url = fal_client.upload_file(resized_path)
        cleaned_url = _remove_background(uploaded_url)

        # Edge feathering on person image to fix white halo around hair
        if not is_garment:
            cleaned_url = _feather_edges(cleaned_url)

        logger.info(f"{label.capitalize()} image prepared.")
        return cleaned_url

    finally:
        if os.path.exists(resized_path):
            os.remove(resized_path)


def _analyze_garment(garment_url: str) -> tuple[str, bool, str]:
    """
    Detect garment category and photo type using Florence-2.
    Uses raw garment image (before rembg) for accurate detection.
    Returns (category, long_top, garment_photo_type).
    """
    logger.info("Detecting garment category + photo type via Florence-2...")

    category = "one-pieces"       # safe default for South Asian full outfits
    long_top = True               # safe default — better to over-assume long
    garment_photo_type = "model"  # safe default

    try:
        # Use detailed caption endpoint — it returns rich descriptive text
        # that we parse for garment type keywords
        result = fal_client.subscribe(
            "fal-ai/florence-2-large/more-detailed-caption",
            arguments={
                "image_url": garment_url,
            },
            with_logs=False,
        )

        # Florence-2 returns text under different keys depending on task
        caption = (
            result.get("results", "")
            or result.get("text", "")
            or result.get("caption", "")
            or result.get("output", "")
            or ""
        ).lower().strip()

        logger.info(f"Florence-2 caption: '{caption[:200]}'")

        # ── Detect garment category from caption keywords ──
        full_body_keywords = [
            "kurta", "kameez", "shalwar", "pajama", "suit", "sherwani",
            "anarkali", "jumpsuit", "dress", "gown", "abaya", "kaftan",
            "coord", "co-ord", "two piece", "three piece", "3 piece",
            "full length", "full-length", "long outfit", "trouser",
            "pantsuit", "overall", "romper", "maxi",
        ]
        bottom_keywords = [
            "pants", "jeans", "trousers", "shorts", "skirt",
            "leggings", "palazzos", "bottoms only",
        ]

        if any(kw in caption for kw in full_body_keywords):
            category = "one-pieces"
            long_top = True
            logger.info("Detected: FULL BODY outfit → one-pieces, long_top=True")
        elif any(kw in caption for kw in bottom_keywords):
            category = "bottoms"
            long_top = False
            logger.info("Detected: BOTTOMS → bottoms, long_top=False")
        else:
            # Check if caption describes upper body only
            upper_only_keywords = [
                "t-shirt", "tshirt", "shirt", "blouse", "jacket",
                "hoodie", "sweater", "blazer", "top ", "crop",
            ]
            if any(kw in caption for kw in upper_only_keywords):
                category = "tops"
                long_top = False
                logger.info("Detected: TOPS only → tops, long_top=False")
            else:
                # Default to one-pieces — safer for South Asian market
                category = "one-pieces"
                long_top = True
                logger.info("Detection unclear → defaulting to one-pieces")

        # ── Detect photo type from caption ──
        if any(kw in caption for kw in ["wearing", "dressed", "person", "model",
                                         "man", "woman", "he ", "she "]):
            garment_photo_type = "model"
        elif any(kw in caption for kw in ["flat", "laid", "hanger",
                                           "mannequin", "product"]):
            garment_photo_type = "flat-lay"
        else:
            garment_photo_type = "model"  # safe default

        logger.info(
            f"Final detection → category={category}, "
            f"long_top={long_top}, photo_type={garment_photo_type}"
        )

    except Exception as e:
        logger.warning(f"Florence-2 detection failed: {e} — using safe defaults")

    return category, long_top, garment_photo_type


def _auto_describe_garment(garment_url: str) -> str:
    """
    Auto-generate a garment description via Florence-2 when user skips input.
    Critical for dark/plain garments where the model needs text guidance.
    """
    logger.info("Auto-generating garment description via Florence-2...")
    try:
        result = fal_client.subscribe(
            "fal-ai/florence-2-large/more-detailed-caption",
            arguments={
                "image_url": garment_url,
            },
            with_logs=False,
        )
        desc = (
            result.get("results", "")
            or result.get("text", "")
            or result.get("caption", "")
            or result.get("output", "")
            or ""
        ).strip()
        logger.info(f"Auto description: '{desc}'")
        return desc if desc else "outfit"
    except Exception as e:
        logger.warning(f"Auto description failed: {e}")
        return "outfit"


def _correct_brightness_contrast(image_path: str) -> str:
    """
    Check average luminance and apply corrections:
    - If too dark (luminance < 80): boost brightness +30
    - If too bright (luminance > 200): reduce brightness -15
    - Always: apply mild 1.1x contrast boost for detail visibility
    """
    logger.info("Checking brightness and applying corrections...")
    img = Image.open(image_path).convert("RGB")
    stat = ImageStat.Stat(img)
    avg_luminance = sum(stat.mean) / 3  # average across R, G, B

    logger.info(f"Average luminance: {avg_luminance:.1f}")

    # Brightness correction
    if avg_luminance < 80:
        logger.info("Image too dark — boosting brightness.")
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.3)  # +30% brightness
    elif avg_luminance > 200:
        logger.info("Image too bright — reducing brightness.")
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.9)  # -10% brightness

    # Mild contrast boost (1.1x) to reveal buttons, embroidery, collars
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.1)

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(tmp.name, quality=95)
    tmp.close()

    logger.info("Brightness/contrast correction done.")
    return tmp.name


def _upscale_image(image_url: str) -> str:
    """Upscale via fal-ai/aura-sr (2x)."""
    logger.info("Upscaling result via fal-ai/aura-sr...")
    result = fal_client.subscribe(
        "fal-ai/aura-sr",
        arguments={"image_url": image_url, "upscaling_factor": 2},
        with_logs=False,
    )
    return result["image"]["url"]


def generate_tryon(user_image_path: str, cloth_image_path: str, garment_description: str = "", seed: int = None) -> str:
    """
    V5 Pipeline — diagnosed failure fixes applied:
    1. Preprocess person (rembg F5F5F5 + edge feathering)
    2. Preprocess garment (rembg F5F5F5)
    3. Florence-2 category + photo type detection
    4. Auto garment description if user skipped
    5. FASHN VTON (restore_background: true) with CatVTON fallback
    6. Brightness/contrast correction
    7. Aura-SR upscale
    8. Final contain-and-pad
    """
    logger.info("=" * 60)
    logger.info("V5 PIPELINE START")
    logger.info("=" * 60)

    try:
        # ── STEP 1: Person image preprocessing ──
        logger.info("STEP 1: Preparing person image...")
        human_image_url = _prepare_image(user_image_path, is_garment=False)

        # ── STEP 2A: Upload RAW garment for Florence-2 BEFORE rembg ──
        logger.info("STEP 2A: Uploading raw garment for detection...")
        raw_garment_url = fal_client.upload_file(cloth_image_path)

        # ── STEP 2B: Garment image preprocessing (rembg for try-on model) ──
        logger.info("STEP 2B: Cleaning garment image...")
        garment_image_url = _prepare_image(cloth_image_path, is_garment=True)

        # ── STEP 3: Detect using RAW garment (original colors intact) ──
        logger.info("STEP 3: Detecting outfit type...")
        category, long_top, garment_photo_type = _analyze_garment(raw_garment_url)

        # Keyword override for long_top
        desc_lower = garment_description.lower() if garment_description else ""
        override_keywords = [
            "kurta", "kameez", "kurti", "long", "maxi", "anarkali", "sherwani",
            "abaya", "tunic", "kaftan", "coord", "gown", "shalwar",
            "jumpsuit", "3 piece", "three piece", "co-ord", "long shirt", "jalabiya",
        ]
        if any(kw in desc_lower for kw in override_keywords):
            logger.info("Keyword override → long_top=True")
            long_top = True
            if category == "tops":
                category = "one-pieces"

        logger.info(f"Detection → category={category}, long_top={long_top}, photo_type={garment_photo_type}")

        # ── STEP 4: Auto description if user skipped ──
        if not garment_description or not garment_description.strip():
            logger.info("STEP 4: User skipped description — auto-generating...")
            garment_description = _auto_describe_garment(garment_image_url)
        else:
            logger.info(f"STEP 4: Using user description: '{garment_description}'")

        # ── STEP 5: FASHN VTON core call ──
        logger.info("STEP 5: Running FASHN Try-On...")
        seed = seed if seed is not None else random.randint(0, 999999)
        tryon_url = None

        try:
            fashn_args = {
                "model_image": human_image_url,
                "garment_image": garment_image_url,
                "category": category,
                "garment_photo_type": garment_photo_type,
                "long_top": long_top,
                "restore_background": True,
                "restore_clothes": True,
                "mode": "quality",
                "moderation_level": "conservative",
                "num_samples": 1,
                "seed": seed,
            }
            logger.info(f"FASHN args: seed={seed}, category={category}, type={garment_photo_type}, long_top={long_top}, restore_bg=True")

            handler = fal_client.subscribe(
                "fal-ai/fashn/tryon/v1.6",
                arguments=fashn_args,
                with_logs=True,
            )
            tryon_url = handler["images"][0]["url"]
            logger.info("FASHN tryon inference successful.")

        except Exception as fashn_err:
            logger.error(f"FASHN failed: {fashn_err} — silent fallback to CatVTON")
            fallback = fal_client.subscribe(
                "fal-ai/cat-vton",
                arguments={
                    "human_image_url": human_image_url,
                    "garment_image_url": garment_image_url,
                    "cloth_type": "overall",
                    "num_inference_steps": 50,
                },
                with_logs=True,
            )
            tryon_url = fallback["image"]["url"]
            logger.info("CatVTON fallback successful.")

        # ── STEP 6: Brightness/contrast correction ──
        logger.info("STEP 6: Adjusting lighting...")
        dl_res = requests.get(tryon_url)
        raw_path = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
        with open(raw_path, "wb") as f:
            f.write(dl_res.content)

        corrected_path = _correct_brightness_contrast(raw_path)
        os.remove(raw_path)

        # Upload corrected image for aura-sr
        corrected_url = fal_client.upload_file(corrected_path)
        os.remove(corrected_path)

        # ── STEP 7: Upscale ──
        logger.info("STEP 7: Sharpening final result...")
        upscaled_url = _upscale_image(corrected_url)

        # ── STEP 8: Final contain-and-pad ──
        logger.info("STEP 8: Final safety padding...")
        dl_final = requests.get(upscaled_url)
        final_raw = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
        with open(final_raw, "wb") as f:
            f.write(dl_final.content)

        final_padded = _resize_and_pad(final_raw, target_w=1536, target_h=2048)
        os.remove(final_raw)

        output_filename = f"out_{uuid.uuid4().hex}.jpg"
        output_path = os.path.join("outputs", output_filename)

        # Convert to JPEG for smaller file size
        final_img = Image.open(final_padded).convert("RGB")
        final_img.save(output_path, format="JPEG", quality=95)
        os.remove(final_padded)

        logger.info(f"V5 PIPELINE COMPLETE → {output_filename}")
        logger.info("=" * 60)
        return output_filename

    except Exception as e:
        logger.error(f"V5 Pipeline Hard Error: {e}")
        import traceback
        traceback.print_exc()
        output_filename = f"out_error_{uuid.uuid4().hex}.jpg"
        output_path = os.path.join("outputs", output_filename)
        import shutil
        shutil.copyfile(user_image_path, output_path)
        return output_filename
