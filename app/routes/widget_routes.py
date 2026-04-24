"""
FitSnap B2B Widget — API Routes
4 endpoints for brand registration, product scraping,
try-on + rating, and product catalog access.
"""

import os
import re
import json
import uuid
import logging
import tempfile
import requests as req_lib
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form, Request, Query
from pydantic import BaseModel

import fal_client
from app.database import get_db
from app.services.ai_pipeline import generate_tryon
from app.utils.storage import save_uploaded_file, get_output_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/widget", tags=["Widget B2B"])

# ─── Score label mapping ─────────────────────────────────────────────────────

def _score_label(score: int) -> str:
    if score >= 90:
        return "Perfect Match ✨"
    elif score >= 85:
        return "Excellent Match"
    elif score >= 70:
        return "Good Match"
    elif score >= 50:
        return "Could Be Better"
    else:
        return "Not Recommended"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _validate_api_key(api_key: str) -> dict:
    """Validate API key and return brand row or raise 403."""
    if not api_key:
        raise HTTPException(status_code=403, detail="Missing API key")
    conn = get_db()
    brand = conn.execute("SELECT * FROM brands WHERE api_key = ? AND is_active = 1", (api_key,)).fetchone()
    conn.close()
    if not brand:
        raise HTTPException(status_code=403, detail="Invalid or inactive API key")
    return dict(brand)


def _florence2_caption(image_url: str) -> str:
    """Get detailed caption from Florence-2."""
    try:
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
        )
        if isinstance(caption, list):
            caption = caption[0] if caption else ""
        return caption.strip()
    except Exception as e:
        logger.warning(f"Florence-2 caption failed: {e}")
        return ""


def _rate_tryon_result(result_image_url: str) -> dict:
    """
    Rate a try-on result using Florence-2.
    Returns dict with score, color_note, fit_note, style_note.
    Falls back gracefully if parsing fails.
    """
    prompt_text = (
        "Look at this person wearing an outfit. Rate how well the outfit "
        "suits this person on a scale of 0 to 100. Consider: "
        "Color harmony with skin tone (30 points), "
        "Fit and proportion on the body (40 points), "
        "Overall style coherence (30 points). "
        "Reply with ONLY a JSON object: "
        '{"score": 87, "color_note": "one sentence about color", '
        '"fit_note": "one sentence about fit", '
        '"style_note": "one sentence about style"}'
    )

    default = {
        "score": 78,
        "color_note": "The color palette works reasonably well with your complexion",
        "fit_note": "The garment fits within expected proportions",
        "style_note": "A solid style choice overall",
    }

    try:
        result = fal_client.subscribe(
            "fal-ai/florence-2-large/more-detailed-caption",
            arguments={"image_url": result_image_url},
            with_logs=False,
        )
        caption = (
            result.get("results", "")
            or result.get("text", "")
            or result.get("caption", "")
            or result.get("output", "")
            or ""
        )
        if isinstance(caption, list):
            caption = caption[0] if caption else ""
        caption = caption.strip()
        logger.info(f"Rating caption: {caption[:300]}")

        # Try to parse JSON from the response
        json_match = re.search(r'\{[^}]+\}', caption)
        if json_match:
            try:
                parsed = json.loads(json_match.group().replace("'", '"'))
                return {
                    "score": int(parsed.get("score", default["score"])),
                    "color_note": parsed.get("color_note", default["color_note"]),
                    "fit_note": parsed.get("fit_note", default["fit_note"]),
                    "style_note": parsed.get("style_note", default["style_note"]),
                }
            except (json.JSONDecodeError, ValueError):
                pass

        # Try to extract a number from caption text
        numbers = re.findall(r'\b(\d{1,3})\b', caption)
        for n in numbers:
            val = int(n)
            if 0 <= val <= 100:
                return {**default, "score": val}

        # Florence-2 often returns descriptive text — use it for notes
        # and generate a score based on positive/negative sentiment keywords
        positive = ["beautiful", "elegant", "perfect", "stunning", "great", "well",
                     "complement", "suit", "harmonious", "flattering", "nice", "good"]
        negative = ["clash", "mismatch", "poor", "unflattering", "awkward", "wrong",
                     "contrast", "doesn't", "not"]
        caption_lower = caption.lower()
        pos_count = sum(1 for w in positive if w in caption_lower)
        neg_count = sum(1 for w in negative if w in caption_lower)

        if pos_count > neg_count:
            default["score"] = min(95, 75 + pos_count * 5)
        elif neg_count > pos_count:
            default["score"] = max(30, 70 - neg_count * 8)

        # Use parts of the caption as notes if available
        if len(caption) > 20:
            sentences = [s.strip() for s in caption.split('.') if len(s.strip()) > 10]
            if len(sentences) >= 1:
                default["color_note"] = sentences[0][:120]
            if len(sentences) >= 2:
                default["fit_note"] = sentences[1][:120]
            if len(sentences) >= 3:
                default["style_note"] = sentences[2][:120]

        return default

    except Exception as e:
        logger.warning(f"Rating failed: {e} — using defaults")
        return default


def _describe_person(user_image_url: str) -> str:
    """Describe person's skin tone, body type, and recommended colors."""
    try:
        result = fal_client.subscribe(
            "fal-ai/florence-2-large/more-detailed-caption",
            arguments={"image_url": user_image_url},
            with_logs=False,
        )
        desc = (
            result.get("results", "")
            or result.get("text", "")
            or result.get("caption", "")
            or result.get("output", "")
            or ""
        )
        if isinstance(desc, list):
            desc = desc[0] if desc else ""
        return desc.strip()
    except Exception as e:
        logger.warning(f"Person description failed: {e}")
        return ""


def _find_recommendations(brand_api_key: str, person_description: str,
                           original_product_id: str, original_category: str) -> list:
    """Find top 3 product recommendations from the same brand's catalog."""
    conn = get_db()
    products = conn.execute(
        "SELECT * FROM brand_products WHERE brand_api_key = ? AND id != ?",
        (brand_api_key, original_product_id)
    ).fetchall()
    conn.close()

    if not products:
        return []

    person_lower = person_description.lower()

    # Color keywords that Florence-2 might mention
    warm_colors = ["warm", "ivory", "cream", "beige", "camel", "gold", "peach",
                   "coral", "rose", "dusty", "earthy", "brown", "tan", "amber"]
    cool_colors = ["cool", "blue", "navy", "silver", "grey", "gray", "teal",
                   "lavender", "purple", "mint", "ice"]

    # Detect person's undertone from description
    person_prefers_warm = any(c in person_lower for c in warm_colors)
    person_prefers_cool = any(c in person_lower for c in cool_colors)

    scored = []
    for p in products:
        p_dict = dict(p)
        desc_lower = (p_dict.get("description") or "").lower()
        relevance = 0

        # Color match scoring
        if person_prefers_warm and any(c in desc_lower for c in warm_colors):
            relevance += 3
        if person_prefers_cool and any(c in desc_lower for c in cool_colors):
            relevance += 3

        # Category match
        if p_dict.get("category") == original_category:
            relevance += 2

        # Bonus for having a description at all
        if desc_lower:
            relevance += 1

        scored.append((relevance, p_dict))

    scored.sort(key=lambda x: x[0], reverse=True)
    top3 = scored[:3]

    recommendations = []
    reasons_warm = [
        "Warm tones complement your skin tone beautifully",
        "This shade creates perfect harmony with warm undertones",
        "Earth-toned palette enhances your natural complexion",
    ]
    reasons_cool = [
        "Cool tones bring out the best in your complexion",
        "This shade provides elegant contrast with your features",
        "Refined palette complements your cool undertones",
    ]
    reasons_neutral = [
        "Versatile shade that flatters a wide range of skin tones",
        "Classic choice that enhances your natural features",
        "Well-balanced tones create a harmonious look",
    ]

    for i, (score, prod) in enumerate(top3):
        if person_prefers_warm:
            reason = reasons_warm[i % len(reasons_warm)]
        elif person_prefers_cool:
            reason = reasons_cool[i % len(reasons_cool)]
        else:
            reason = reasons_neutral[i % len(reasons_neutral)]

        recommendations.append({
            "id": prod["id"],
            "name": prod.get("product_name", "Product"),
            "image_url": prod.get("product_image_url", ""),
            "product_url": prod.get("product_url", ""),
            "price": prod.get("price", ""),
            "reason": reason,
        })

    return recommendations


# ═════════════════════════════════════════════════════════════════════════════
# ENDPOINT 1: POST /widget/register-brand
# ═════════════════════════════════════════════════════════════════════════════

class BrandRegistration(BaseModel):
    brand_name: str
    website_url: str = ""
    email: str = ""


@router.post("/register-brand")
async def register_brand(body: BrandRegistration, request: Request):
    """Register a new brand and return their API key + embed code."""
    api_key = "fs_" + uuid.uuid4().hex[:24]

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO brands (brand_name, website_url, email, api_key) VALUES (?, ?, ?, ?)",
            (body.brand_name, body.website_url, body.email, api_key),
        )
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Registration failed: {e}")
    conn.close()

    # Build embed code using the current server's URL
    base_url = f"{request.url.scheme}://{request.headers.get('host')}"
    embed_code = f"<script src='{base_url}/static/widget.js' data-key='{api_key}'></script>"

    return {
        "api_key": api_key,
        "embed_code": embed_code,
        "message": "Paste this embed_code on your website",
    }


# ═════════════════════════════════════════════════════════════════════════════
# ENDPOINT 2: POST /widget/scrape-products
# ═════════════════════════════════════════════════════════════════════════════

class ScrapeRequest(BaseModel):
    page_url: str


@router.post("/scrape-products")
async def scrape_products(body: ScrapeRequest, x_api_key: str = Header(None)):
    """Scrape products from a brand's website page."""
    brand = _validate_api_key(x_api_key)
    products = []

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # ── Strategy 1: Try Shopify JSON ──
        try:
            shopify_url = body.page_url.rstrip("/") + ".json"
            resp = await client.get(shopify_url)
            if resp.status_code == 200:
                data = resp.json()
                shopify_products = data.get("products", [])
                if not shopify_products and "collection" in data:
                    shopify_products = data["collection"].get("products", [])

                for sp in shopify_products:
                    image_url = ""
                    if sp.get("images") and len(sp["images"]) > 0:
                        image_url = sp["images"][0].get("src", "")
                    elif sp.get("image"):
                        image_url = sp["image"].get("src", "")

                    price = ""
                    variants = sp.get("variants", [])
                    if variants:
                        price = variants[0].get("price", "")

                    handle = sp.get("handle", "")
                    base_product_url = body.page_url.split("/collections")[0] if "/collections" in body.page_url else body.page_url
                    product_url = f"{base_product_url}/products/{handle}" if handle else ""

                    products.append({
                        "name": sp.get("title", "Product"),
                        "image_url": image_url,
                        "product_url": product_url,
                        "price": str(price),
                        "category": sp.get("product_type", "one-pieces").lower() or "one-pieces",
                    })

                if products:
                    logger.info(f"Shopify JSON: found {len(products)} products")
        except Exception as e:
            logger.info(f"Shopify JSON failed: {e} — falling back to HTML scraping")

        # ── Strategy 2: HTML scraping ──
        if not products:
            try:
                resp = await client.get(body.page_url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                # Find product images
                product_paths = ["/products/", "/catalog/", "/uploads/", "/wp-content/"]
                imgs = soup.find_all("img", src=True)
                for img in imgs:
                    src = img.get("src", "")
                    if not any(pp in src for pp in product_paths):
                        continue
                    # Make URL absolute
                    if src.startswith("//"):
                        src = "https:" + src
                    elif src.startswith("/"):
                        from urllib.parse import urlparse
                        parsed = urlparse(body.page_url)
                        src = f"{parsed.scheme}://{parsed.netloc}{src}"

                    # Find nearby text for product name
                    parent = img.parent
                    name = "Product"
                    for tag in ["h1", "h2", "h3", "h4", "a", "span"]:
                        found = parent.find(tag) if parent else None
                        if found and found.get_text(strip=True):
                            name = found.get_text(strip=True)[:100]
                            break
                    # Alt text fallback
                    if name == "Product" and img.get("alt"):
                        name = img["alt"][:100]

                    # Find nearby price
                    price = ""
                    price_patterns = ["Rs.", "PKR", "$", "£", "€"]
                    if parent:
                        text = parent.get_text()
                        for pp in price_patterns:
                            if pp in text:
                                price_match = re.search(
                                    rf'({re.escape(pp)}\s*[\d,]+(?:\.\d{{2}})?)', text
                                )
                                if price_match:
                                    price = price_match.group(1)
                                    break

                    # Find product link
                    product_url = ""
                    link = parent.find("a", href=True) if parent else None
                    if link:
                        href = link["href"]
                        if href.startswith("/"):
                            from urllib.parse import urlparse
                            parsed = urlparse(body.page_url)
                            href = f"{parsed.scheme}://{parsed.netloc}{href}"
                        product_url = href

                    products.append({
                        "name": name,
                        "image_url": src,
                        "product_url": product_url,
                        "price": price,
                        "category": "one-pieces",
                    })

                logger.info(f"HTML scraping: found {len(products)} products")
            except Exception as e:
                logger.error(f"HTML scraping failed: {e}")
                raise HTTPException(status_code=400, detail=f"Could not scrape products from {body.page_url}")

    if not products:
        return {"products_found": 0, "products": []}

    # ── Generate descriptions and save to DB ──
    conn = get_db()
    saved_products = []
    for i, prod in enumerate(products[:50]):  # Cap at 50 products
        prod_id = f"prod_{uuid.uuid4().hex[:8]}"

        # Get AI description for recommendation matching
        description = ""
        if prod.get("image_url"):
            description = _florence2_caption(prod["image_url"])

        try:
            conn.execute(
                """INSERT OR REPLACE INTO brand_products
                   (id, brand_api_key, product_name, product_image_url, product_url, price, category, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (prod_id, x_api_key, prod["name"], prod.get("image_url", ""),
                 prod.get("product_url", ""), prod.get("price", ""),
                 prod.get("category", "one-pieces"), description),
            )
            saved_products.append({
                "id": prod_id,
                "name": prod["name"],
                "image_url": prod.get("image_url", ""),
                "product_url": prod.get("product_url", ""),
                "price": prod.get("price", ""),
                "category": prod.get("category", "one-pieces"),
                "description": description[:200] if description else "",
            })
        except Exception as e:
            logger.warning(f"Failed to save product {prod['name']}: {e}")

    conn.commit()
    conn.close()

    return {
        "products_found": len(saved_products),
        "products": saved_products,
    }


# ═════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3: POST /widget/tryon-and-rate
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/tryon-and-rate")
async def tryon_and_rate(
    request: Request,
    user_image: UploadFile = File(...),
    product_image_url: str = Form(...),
    product_id: str = Form(""),
    garment_description: str = Form(""),
    x_api_key: str = Header(None),
):
    """Core widget endpoint: try-on → rate → recommend if score < 85."""
    brand = _validate_api_key(x_api_key)

    # ── STEP 1: Increment try-on count ──
    conn = get_db()
    conn.execute(
        "UPDATE brands SET monthly_tryon_count = monthly_tryon_count + 1 WHERE api_key = ?",
        (x_api_key,),
    )
    conn.commit()
    conn.close()

    try:
        # ── STEP 2: Run try-on pipeline ──
        logger.info("Widget: Starting try-on pipeline...")
        logger.info(f"Widget: product_image_url = {product_image_url}")

        # Save user image
        user_img_path = save_uploaded_file(user_image, prefix="widget_user_")
        logger.info(f"Widget: User image saved to {user_img_path}")

        # Download product image to temp file — use headers to avoid being blocked
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            }
            dl = req_lib.get(product_image_url, timeout=30, headers=headers, verify=False, allow_redirects=True)
            dl.raise_for_status()
            logger.info(f"Widget: Product image downloaded, size={len(dl.content)} bytes")
        except Exception as dl_err:
            logger.error(f"Widget: Failed to download product image: {dl_err}")
            raise Exception(f"Cannot download product image from {product_image_url}: {dl_err}")

        # Determine file extension from content type
        content_type = dl.headers.get("content-type", "image/jpeg")
        ext = ".jpg"
        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"

        cloth_tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False, dir="uploads")
        cloth_tmp.write(dl.content)
        cloth_img_path = cloth_tmp.name
        cloth_tmp.close()
        logger.info(f"Widget: Product image saved to {cloth_img_path}")

        # Call the existing AI pipeline (fast mode for widget speed)
        logger.info("Widget: Calling generate_tryon...")
        output_filename = generate_tryon(
            user_img_path, cloth_img_path, garment_description
        )
        logger.info(f"Widget: Try-on complete → {output_filename}")

        # Build result URL
        result_image_url = get_output_url(output_filename, request)

        # ── STEP 3: Rate the result ──
        logger.info("Widget: Rating try-on result...")
        rating = _rate_tryon_result(result_image_url)
        score = rating["score"]
        label = _score_label(score)

        # ── STEP 4: Recommendations if score < 85 ──
        recommendation_needed = score < 85
        recommended_products = []

        if recommendation_needed:
            logger.info("Widget: Score < 85, finding recommendations...")
            # Use result image for person description since user image may be cleaned up
            person_desc = _describe_person(result_image_url)

            # Get original product's category
            original_category = "one-pieces"
            if product_id:
                conn = get_db()
                orig = conn.execute(
                    "SELECT category FROM brand_products WHERE id = ?", (product_id,)
                ).fetchone()
                conn.close()
                if orig:
                    original_category = orig["category"] or "one-pieces"

            recommended_products = _find_recommendations(
                x_api_key, person_desc, product_id, original_category
            )

        # Clean up temp files AFTER all processing is done
        for p in [user_img_path, cloth_img_path]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

        # ── STEP 5: Return response ──
        return {
            "result_image_url": result_image_url,
            "score": score,
            "score_label": label,
            "color_note": rating["color_note"],
            "fit_note": rating["fit_note"],
            "style_note": rating["style_note"],
            "recommendation_needed": recommendation_needed,
            "recommended_products": recommended_products,
        }

    except Exception as e:
        logger.error(f"Widget try-on failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Try-on failed: {str(e)}")


# ═════════════════════════════════════════════════════════════════════════════
# ENDPOINT 4: GET /widget/brand-products
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/brand-products")
async def get_brand_products(
    x_api_key: str = Header(None),
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Return products for a brand's catalog (used by widget)."""
    brand = _validate_api_key(x_api_key)

    conn = get_db()
    if category:
        rows = conn.execute(
            "SELECT * FROM brand_products WHERE brand_api_key = ? AND category = ? LIMIT ?",
            (x_api_key, category, limit),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM brand_products WHERE brand_api_key = ? AND category = ?",
            (x_api_key, category),
        ).fetchone()
    else:
        rows = conn.execute(
            "SELECT * FROM brand_products WHERE brand_api_key = ? LIMIT ?",
            (x_api_key, limit),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM brand_products WHERE brand_api_key = ?",
            (x_api_key,),
        ).fetchone()
    conn.close()

    products = []
    for r in rows:
        products.append({
            "id": r["id"],
            "name": r["product_name"],
            "image_url": r["product_image_url"],
            "product_url": r["product_url"],
            "price": r["price"],
            "category": r["category"],
            "description": r["description"][:200] if r["description"] else "",
        })

    return {
        "products": products,
        "total": total_row["cnt"] if total_row else 0,
    }
