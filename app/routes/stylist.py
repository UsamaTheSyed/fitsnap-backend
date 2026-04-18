from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import logging
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


class StylistRequest(BaseModel):
    message: str
    body_type: str = ""
    skin_tone: str = ""
    gender: str = ""
    style_preferences: list[str] = []
    occasions: list[str] = []


SYSTEM_PROMPT = """You are FitSnap AI Stylist — a friendly, expert fashion advisor. 
You give personalized outfit recommendations based on the user's body type, skin tone, 
and style preferences. Keep responses concise (3-5 sentences max), practical, and 
enthusiastic. Include specific outfit suggestions with colors and styles. 
Focus on South Asian and international fashion. Always be encouraging and positive.
Never mention you are an AI unless directly asked."""


@router.post("/stylist/recommend")
async def get_style_recommendation(req: StylistRequest):
    """Get AI-powered style recommendations using Gemini."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    
    try:
        from google import genai
        
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Build context from user profile
        profile_context = ""
        if req.body_type:
            profile_context += f"Body type: {req.body_type}. "
        if req.skin_tone:
            profile_context += f"Skin tone: {req.skin_tone}. "
        if req.gender:
            profile_context += f"Gender: {req.gender}. "
        if req.style_preferences:
            profile_context += f"Style preferences: {', '.join(req.style_preferences)}. "
        if req.occasions:
            profile_context += f"Occasions: {', '.join(req.occasions)}. "
        
        user_message = f"""User profile: {profile_context}

User's question: {req.message}"""
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{user_message}"}]},
            ],
        )
        
        reply = response.text.strip() if response.text else "I'd love to help! Could you tell me more about what you're looking for?"
        
        logger.info(f"Stylist response generated ({len(reply)} chars)")
        return {"success": True, "recommendation": reply}
        
    except ImportError:
        raise HTTPException(status_code=500, detail="google-genai package not installed")
    except Exception as e:
        logger.error(f"Stylist recommendation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
