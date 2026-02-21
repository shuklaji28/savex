from fastapi import FastAPI, APIRouter, UploadFile, File
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import tempfile
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, date, timedelta, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ─── SHELF LIFE DATABASE (days at room temp / fridge) ───
SHELF_LIFE_DB = {
    # Very Perishable (1-2 days)
    "spinach": {"days": 2, "category": "vegetable"}, "lettuce": {"days": 2, "category": "vegetable"},
    "coriander": {"days": 2, "category": "vegetable"}, "cilantro": {"days": 2, "category": "vegetable"},
    "mint": {"days": 2, "category": "vegetable"}, "methi": {"days": 2, "category": "vegetable"},
    "cooked rice": {"days": 1, "category": "grain"}, "leftover": {"days": 1, "category": "other"},
    "cut fruit": {"days": 1, "category": "fruit"}, "dosa batter": {"days": 2, "category": "grain"},
    # Perishable (3-5 days)
    "milk": {"days": 4, "category": "dairy"}, "curd": {"days": 5, "category": "dairy"},
    "yogurt": {"days": 5, "category": "dairy"}, "paneer": {"days": 4, "category": "dairy"},
    "bread": {"days": 4, "category": "grain"}, "mushroom": {"days": 3, "category": "vegetable"},
    "banana": {"days": 4, "category": "fruit"}, "strawberry": {"days": 3, "category": "fruit"},
    "grape": {"days": 5, "category": "fruit"}, "tofu": {"days": 4, "category": "dairy"},
    "cheese": {"days": 5, "category": "dairy"}, "cream": {"days": 4, "category": "dairy"},
    "butter": {"days": 14, "category": "dairy"}, "egg": {"days": 14, "category": "egg"},
    "chicken": {"days": 2, "category": "meat"}, "fish": {"days": 2, "category": "meat"},
    "mutton": {"days": 2, "category": "meat"}, "prawn": {"days": 2, "category": "meat"},
    # Moderate (5-10 days)
    "tomato": {"days": 7, "category": "vegetable"}, "cucumber": {"days": 7, "category": "vegetable"},
    "capsicum": {"days": 7, "category": "vegetable"}, "bell pepper": {"days": 7, "category": "vegetable"},
    "carrot": {"days": 10, "category": "vegetable"}, "beans": {"days": 5, "category": "vegetable"},
    "broccoli": {"days": 5, "category": "vegetable"}, "cauliflower": {"days": 7, "category": "vegetable"},
    "peas": {"days": 5, "category": "vegetable"}, "okra": {"days": 5, "category": "vegetable"},
    "bhindi": {"days": 5, "category": "vegetable"}, "ladyfinger": {"days": 5, "category": "vegetable"},
    "mango": {"days": 5, "category": "fruit"}, "orange": {"days": 10, "category": "fruit"},
    "lemon": {"days": 10, "category": "fruit"}, "ketchup": {"days": 30, "category": "other"},
    "sauce": {"days": 14, "category": "other"}, "jam": {"days": 30, "category": "other"},
    # Long lasting (10-30 days)
    "potato": {"days": 21, "category": "vegetable"}, "onion": {"days": 21, "category": "vegetable"},
    "garlic": {"days": 21, "category": "vegetable"}, "ginger": {"days": 21, "category": "vegetable"},
    "apple": {"days": 21, "category": "fruit"}, "cabbage": {"days": 14, "category": "vegetable"},
    "beetroot": {"days": 14, "category": "vegetable"}, "radish": {"days": 10, "category": "vegetable"},
    "sweet potato": {"days": 14, "category": "vegetable"}, "pumpkin": {"days": 14, "category": "vegetable"},
    # Dry goods (30-180 days)
    "rice": {"days": 180, "category": "grain"}, "flour": {"days": 90, "category": "grain"},
    "atta": {"days": 90, "category": "grain"}, "dal": {"days": 180, "category": "grain"},
    "lentil": {"days": 180, "category": "grain"}, "sugar": {"days": 365, "category": "grain"},
    "salt": {"days": 365, "category": "grain"}, "oil": {"days": 180, "category": "other"},
    "ghee": {"days": 180, "category": "dairy"}, "maggi": {"days": 180, "category": "snack"},
    "noodle": {"days": 180, "category": "snack"}, "biscuit": {"days": 90, "category": "snack"},
    "chips": {"days": 60, "category": "snack"}, "masala": {"days": 180, "category": "spice"},
    "turmeric": {"days": 180, "category": "spice"}, "cumin": {"days": 180, "category": "spice"},
    "tea": {"days": 180, "category": "beverage"}, "coffee": {"days": 90, "category": "beverage"},
    "juice": {"days": 7, "category": "beverage"}, "soda": {"days": 90, "category": "beverage"},
}

STORAGE_MULTIPLIER = {
    "freezer": 3.0,
    "fridge": 1.0,
    "kitchen_counter": 0.7,
    "pantry_shelf": 1.2,
    "unknown": 0.85,
}

# Weight estimates (grams)
WEIGHT_ESTIMATES = {
    "egg": 50, "banana": 120, "apple": 180, "orange": 200, "tomato": 100,
    "potato": 150, "onion": 120, "lemon": 60, "mango": 250, "cucumber": 200,
    "carrot": 80, "capsicum": 150, "bread": 400, "mushroom": 100,
}
UNIT_TO_GRAMS = {"kg": 1000, "gram": 1, "g": 1, "liter": 1000, "litre": 1000, "l": 1000, "ml": 1, "dozen": 600}

# Cost per 500g in INR by category
COST_PER_500G = {
    "vegetable": 40, "fruit": 60, "dairy": 70, "grain": 40,
    "spice": 80, "snack": 80, "beverage": 60, "meat": 150, "egg": 40, "other": 50,
}

def get_shelf_life(name: str, storage: str) -> int:
    normalized = name.lower().strip()
    info = SHELF_LIFE_DB.get(normalized)
    base_days = info["days"] if info else 5
    multiplier = STORAGE_MULTIPLIER.get(storage, 0.85)
    return max(1, int(base_days * multiplier))

def get_category(name: str) -> str:
    normalized = name.lower().strip()
    info = SHELF_LIFE_DB.get(normalized)
    return info["category"] if info else "other"

def estimate_weight_grams(name: str, quantity: float, unit: str) -> float:
    normalized = name.lower().strip()
    if unit in UNIT_TO_GRAMS:
        return quantity * UNIT_TO_GRAMS[unit]
    if unit in ("packet", "pack"):
        return quantity * 250
    per_item = WEIGHT_ESTIMATES.get(normalized, 200)
    return quantity * per_item

def estimate_cost_inr(weight_grams: float, category: str) -> float:
    cost_per_500 = COST_PER_500G.get(category, 50)
    return round((weight_grams / 500) * cost_per_500, 2)


# ─── GEMINI EXTRACTION PROMPT ───
EXTRACTION_SYSTEM_PROMPT = """You are a food inventory management assistant. Extract food items from user speech and classify their INTENT.

INTENT TYPES:
- "add": User bought, got, picked up, has, or is adding this item to their pantry/fridge
- "mark_used": User consumed, used, finished, ate, cooked with, or completed using this item
- "mark_wasted": User says item expired, spoiled, went bad, had to throw away, couldn't use, was wasted, or is rotten

INTENT DETECTION KEYWORDS:
- Adding → "bought", "got", "picked up", "have", "purchased", "from market", "stocked up"
- Used → "used", "finished", "ate", "consumed", "cooked with", "finished the", "used up", "done with"
- Wasted → "expired", "went bad", "spoiled", "threw away", "had to throw", "wasted", "couldn't use", "rotten", "not able to use", "went off", "discarded"

RULES:
- Extract EVERY food item mentioned
- Normalize names to singular lowercase (tomatoes→tomato, eggs→egg)
- Convert relative dates: "today"=current_date, "yesterday"=current_date-1day
- If no date reference, assume today
- If no storage location mentioned, set "unknown"
- If quantity not specified, set quantity=1, approximate_quantity=true
- Handle Indian foods: paneer, curd, atta, dal, ghee, maggi, roti, dosa, idli, etc.
- If user mentions explicit expiry ("expires on 13th march", "expiry in 3 days"), capture it
- category must be one of: vegetable, fruit, dairy, grain, spice, snack, beverage, meat, egg, other
- For "mark_used" or "mark_wasted" intents, still provide normalized_name accurately — it will be used to find the item in inventory

Return ONLY valid JSON, no markdown, no explanation:
{
  "items": [
    {
      "intent": "add|mark_used|mark_wasted",
      "item_name": "original name as spoken",
      "normalized_name": "singular lowercase",
      "quantity": 1,
      "unit": "count",
      "approximate_quantity": false,
      "storage_location": "fridge|freezer|kitchen_counter|pantry_shelf|unknown",
      "added_date": "YYYY-MM-DD",
      "expiry_date_mentioned": "YYYY-MM-DD or null",
      "expiry_relative_days": null,
      "category": "vegetable|fruit|dairy|grain|spice|snack|beverage|meat|egg|other"
    }
  ]
}"""

RECIPE_SYSTEM_PROMPT = """You are a practical home cook assistant focused on PREVENTING food waste. You suggest quick, easy recipes using ingredients that are about to expire.

RULES:
- Recipes must prioritize the expiring ingredients provided
- Keep recipes simple, under 20 minutes
- Assume basic Indian household pantry (oil, salt, spices, onion, garlic)
- Suggest 2-3 recipes max
- Each recipe must clearly list which expiring items it uses
- Include simple step-by-step instructions
- Categorize each as: quick_meal, snack, or simple_prep

Return ONLY valid JSON:
{
  "recipes": [
    {
      "title": "Recipe Name",
      "type": "quick_meal|snack|simple_prep",
      "prep_time_minutes": 15,
      "expiring_items_used": ["item1", "item2"],
      "other_ingredients": ["oil", "salt"],
      "steps": ["Step 1...", "Step 2..."],
      "tip": "Optional tip"
    }
  ]
}"""


# ─── PYDANTIC MODELS ───
class FoodItemResponse(BaseModel):
    id: str
    item_name: str
    normalized_name: str
    quantity: float
    unit: str
    approximate_quantity: bool = False
    storage_location: str
    category: str
    added_date: str
    expiry_date: str
    status: str = "active"
    action_date: Optional[str] = None
    estimated_weight_grams: float
    estimated_cost_inr: float
    days_remaining: int = 0
    urgency_level: str = "safe"

class UpdateStatusRequest(BaseModel):
    status: str  # "used" or "wasted"


# ─── HELPER FUNCTIONS ───
def compute_expiry(item_data: dict) -> str:
    added = item_data.get("added_date", date.today().isoformat())
    added_date = date.fromisoformat(added)
    if item_data.get("expiry_date_mentioned"):
        try:
            return item_data["expiry_date_mentioned"]
        except Exception:
            pass
    if item_data.get("expiry_relative_days"):
        try:
            days = int(item_data["expiry_relative_days"])
            return (added_date + timedelta(days=days)).isoformat()
        except Exception:
            pass
    shelf_days = get_shelf_life(item_data.get("normalized_name", ""), item_data.get("storage_location", "unknown"))
    return (added_date + timedelta(days=shelf_days)).isoformat()

def compute_urgency(expiry_date_str: str) -> tuple:
    today = date.today()
    try:
        exp = date.fromisoformat(expiry_date_str)
    except Exception:
        return 999, "safe"
    days = (exp - today).days
    if days <= 0:
        return days, "expired"
    elif days == 1:
        return days, "critical"
    elif days <= 3:
        return days, "urgent"
    elif days <= 7:
        return days, "upcoming"
    else:
        return days, "safe"

def parse_json_from_llm(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return {"items": []}


async def find_active_item_by_name(name: str) -> dict | None:
    """Find active inventory item by normalized name — exact match then partial."""
    # Exact match
    item = await db.food_items.find_one({"normalized_name": name, "status": "active"}, {"_id": 0})
    if item:
        return item
    # Partial match: stored name contains query word or vice versa
    item = await db.food_items.find_one(
        {"normalized_name": {"$regex": name, "$options": "i"}, "status": "active"}, {"_id": 0}
    )
    if item:
        return item
    # Reverse partial: query name contains stored name (e.g., "full cream milk" found by "milk")
    all_active = await db.food_items.find({"status": "active"}, {"_id": 0, "id": 1, "normalized_name": 1}).to_list(500)
    for doc in all_active:
        stored = doc.get("normalized_name", "")
        if stored and stored in name:
            return await db.food_items.find_one({"id": doc["id"]}, {"_id": 0})
    return None


async def process_extracted_items(items_list: list):
    """Route extracted items to add or update flows based on intent."""
    added_items = []
    updated_items = []
    not_found = []
    now_iso = datetime.now(timezone.utc).isoformat()
    today_iso = date.today().isoformat()

    for item_data in items_list:
        intent = item_data.get("intent", "add")
        name = item_data.get("normalized_name", item_data.get("item_name", "unknown")).lower().strip()

        if intent in ("mark_used", "mark_wasted"):
            new_status = "used" if intent == "mark_used" else "wasted"
            matched = await find_active_item_by_name(name)
            if matched:
                await db.food_items.update_one(
                    {"id": matched["id"]},
                    {"$set": {"status": new_status, "action_date": today_iso, "updated_at": now_iso}}
                )
                matched["status"] = new_status
                matched["action_date"] = today_iso
                updated_items.append(matched)
            else:
                not_found.append({"name": name, "intent": intent})
        else:
            # ADD flow (existing logic)
            expiry = compute_expiry(item_data)
            days_remaining, urgency = compute_urgency(expiry)
            qty = item_data.get("quantity", 1)
            unit = item_data.get("unit", "count")
            category = item_data.get("category", get_category(name))
            weight = estimate_weight_grams(name, qty, unit)
            cost = estimate_cost_inr(weight, category)

            food_doc = {
                "id": str(uuid.uuid4()),
                "item_name": item_data.get("item_name", name),
                "normalized_name": name,
                "quantity": qty,
                "unit": unit,
                "approximate_quantity": item_data.get("approximate_quantity", False),
                "storage_location": item_data.get("storage_location", "unknown"),
                "category": category,
                "added_date": item_data.get("added_date", today_iso),
                "expiry_date": expiry,
                "status": "active",
                "action_date": None,
                "estimated_weight_grams": weight,
                "estimated_cost_inr": cost,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            await db.food_items.insert_one(food_doc)
            food_doc["days_remaining"] = days_remaining
            food_doc["urgency_level"] = urgency
            food_doc.pop("_id", None)
            added_items.append(food_doc)

    return added_items, updated_items, not_found


# ─── API ENDPOINTS ───

@api_router.get("/")
async def root():
    return {"message": "Sustain API", "date": date.today().isoformat()}

@api_router.post("/process-voice")
async def process_voice(audio: UploadFile = File(...)):
    """Process voice recording: Whisper STT → Gemini extraction → save items"""
    from emergentintegrations.llm.openai import OpenAISpeechToText
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return {"error": "API key not configured"}

    # Save uploaded audio to temp file
    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 1. Transcribe with Whisper
        stt = OpenAISpeechToText(api_key=api_key)
        with open(tmp_path, "rb") as f:
            transcription = await stt.transcribe(file=f, model="whisper-1", response_format="json", language="en")
        transcript = transcription.text
        logger.info(f"Transcript: {transcript}")

        # 2. Extract entities with Gemini
        session_id = str(uuid.uuid4())
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=EXTRACTION_SYSTEM_PROMPT
        ).with_model("gemini", "gemini-3-flash-preview")

        prompt = f"Current date: {date.today().isoformat()}\n\nTranscript: \"{transcript}\""
        response = await chat.send_message(UserMessage(text=prompt))
        logger.info(f"Gemini response: {response}")
        extracted = parse_json_from_llm(response)
        items_list = extracted.get("items", [])

        # 3. Process and save each item
        saved_items = []
        for item_data in items_list:
            expiry = compute_expiry(item_data)
            days_remaining, urgency = compute_urgency(expiry)
            name = item_data.get("normalized_name", item_data.get("item_name", "unknown"))
            qty = item_data.get("quantity", 1)
            unit = item_data.get("unit", "count")
            category = item_data.get("category", get_category(name))
            weight = estimate_weight_grams(name, qty, unit)
            cost = estimate_cost_inr(weight, category)

            food_doc = {
                "id": str(uuid.uuid4()),
                "item_name": item_data.get("item_name", name),
                "normalized_name": name,
                "quantity": qty,
                "unit": unit,
                "approximate_quantity": item_data.get("approximate_quantity", False),
                "storage_location": item_data.get("storage_location", "unknown"),
                "category": category,
                "added_date": item_data.get("added_date", date.today().isoformat()),
                "expiry_date": expiry,
                "status": "active",
                "action_date": None,
                "estimated_weight_grams": weight,
                "estimated_cost_inr": cost,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.food_items.insert_one(food_doc)
            days_remaining, urgency = compute_urgency(expiry)
            food_doc["days_remaining"] = days_remaining
            food_doc["urgency_level"] = urgency
            food_doc.pop("_id", None)
            saved_items.append(food_doc)

        return {"transcript": transcript, "items": saved_items, "count": len(saved_items)}

    except Exception as e:
        logger.error(f"Error processing voice: {e}", exc_info=True)
        return {"error": str(e), "transcript": "", "items": [], "count": 0}
    finally:
        os.unlink(tmp_path)


@api_router.post("/process-text")
async def process_text(req: dict):
    """Process text input directly (fallback for when voice doesn't work)"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return {"error": "API key not configured"}

    transcript = req.get("text", "")
    if not transcript.strip():
        return {"error": "No text provided", "items": [], "count": 0}

    try:
        session_id = str(uuid.uuid4())
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=EXTRACTION_SYSTEM_PROMPT
        ).with_model("gemini", "gemini-3-flash-preview")

        prompt = f"Current date: {date.today().isoformat()}\n\nTranscript: \"{transcript}\""
        response = await chat.send_message(UserMessage(text=prompt))
        logger.info(f"Gemini response: {response}")
        extracted = parse_json_from_llm(response)
        items_list = extracted.get("items", [])

        saved_items = []
        for item_data in items_list:
            expiry = compute_expiry(item_data)
            days_remaining, urgency = compute_urgency(expiry)
            name = item_data.get("normalized_name", item_data.get("item_name", "unknown"))
            qty = item_data.get("quantity", 1)
            unit = item_data.get("unit", "count")
            category = item_data.get("category", get_category(name))
            weight = estimate_weight_grams(name, qty, unit)
            cost = estimate_cost_inr(weight, category)

            food_doc = {
                "id": str(uuid.uuid4()),
                "item_name": item_data.get("item_name", name),
                "normalized_name": name,
                "quantity": qty,
                "unit": unit,
                "approximate_quantity": item_data.get("approximate_quantity", False),
                "storage_location": item_data.get("storage_location", "unknown"),
                "category": category,
                "added_date": item_data.get("added_date", date.today().isoformat()),
                "expiry_date": expiry,
                "status": "active",
                "action_date": None,
                "estimated_weight_grams": weight,
                "estimated_cost_inr": cost,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.food_items.insert_one(food_doc)
            food_doc["days_remaining"] = days_remaining
            food_doc["urgency_level"] = urgency
            food_doc.pop("_id", None)
            saved_items.append(food_doc)

        return {"transcript": transcript, "items": saved_items, "count": len(saved_items)}
    except Exception as e:
        logger.error(f"Error processing text: {e}", exc_info=True)
        return {"error": str(e), "transcript": transcript, "items": [], "count": 0}


@api_router.get("/inventory")
async def get_inventory():
    """Get active inventory items grouped by urgency"""
    items = await db.food_items.find({"status": "active"}, {"_id": 0}).to_list(1000)
    result = []
    for item in items:
        days_remaining, urgency = compute_urgency(item.get("expiry_date", ""))
        item["days_remaining"] = days_remaining
        item["urgency_level"] = urgency
        result.append(item)
    result.sort(key=lambda x: x["days_remaining"])
    return {"items": result}


@api_router.get("/inventory/history")
async def get_history():
    """Get past items (used/wasted)"""
    items = await db.food_items.find(
        {"status": {"$in": ["used", "wasted"]}}, {"_id": 0}
    ).sort("action_date", -1).to_list(1000)
    return {"items": items}


@api_router.put("/inventory/{item_id}/status")
async def update_item_status(item_id: str, req: UpdateStatusRequest):
    """Mark item as used or wasted"""
    if req.status not in ("used", "wasted"):
        return {"error": "Status must be 'used' or 'wasted'"}
    now = datetime.now(timezone.utc).isoformat()
    result = await db.food_items.update_one(
        {"id": item_id},
        {"$set": {"status": req.status, "action_date": date.today().isoformat(), "updated_at": now}}
    )
    if result.modified_count == 0:
        return {"error": "Item not found"}
    return {"success": True, "item_id": item_id, "status": req.status}


@api_router.get("/inventory/{item_id}")
async def get_item(item_id: str):
    """Get single item detail"""
    item = await db.food_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        return {"error": "Not found"}
    days_remaining, urgency = compute_urgency(item.get("expiry_date", ""))
    item["days_remaining"] = days_remaining
    item["urgency_level"] = urgency
    return item


@api_router.get("/recipes")
async def get_recipes():
    """Generate recipe suggestions based on expiring items"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    items = await db.food_items.find({"status": "active"}, {"_id": 0}).to_list(1000)
    expiring = []
    for item in items:
        days_remaining, urgency = compute_urgency(item.get("expiry_date", ""))
        if urgency in ("expired", "critical", "urgent", "upcoming"):
            expiring.append({
                "name": item["normalized_name"],
                "quantity": item["quantity"],
                "unit": item["unit"],
                "days_remaining": days_remaining,
                "urgency": urgency,
            })
    expiring.sort(key=lambda x: x["days_remaining"])
    expiring = expiring[:10]

    if not expiring:
        return {"recipes": [], "expiring_items": []}

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=str(uuid.uuid4()),
            system_message=RECIPE_SYSTEM_PROMPT
        ).with_model("gemini", "gemini-3-flash-preview")

        items_text = "\n".join([f"- {i['name']} ({i['quantity']} {i['unit']}, expires in {i['days_remaining']} days)" for i in expiring])
        prompt = f"These items are expiring soon:\n{items_text}\n\nSuggest practical recipes to use them up."
        response = await chat.send_message(UserMessage(text=prompt))
        data = parse_json_from_llm(response)
        return {"recipes": data.get("recipes", []), "expiring_items": expiring}
    except Exception as e:
        logger.error(f"Recipe generation error: {e}")
        return {"recipes": [], "expiring_items": expiring, "error": str(e)}


@api_router.get("/reports")
async def get_reports():
    """Get impact dashboard metrics"""
    today = date.today()
    week_ago = (today - timedelta(days=7)).isoformat()
    month_ago = (today - timedelta(days=30)).isoformat()

    all_items = await db.food_items.find({"status": {"$in": ["used", "wasted"]}}, {"_id": 0}).to_list(10000)

    overall_saved_weight = 0.0
    overall_wasted_weight = 0.0
    overall_money_saved = 0.0
    category_waste = {}

    weekly = {"items_saved": 0, "items_wasted": 0, "saved_weight_kg": 0, "money_saved_inr": 0, "co2_saved_kg": 0}
    monthly = {"items_saved": 0, "items_wasted": 0, "saved_weight_kg": 0, "money_saved_inr": 0, "co2_saved_kg": 0}

    for item in all_items:
        weight_g = item.get("estimated_weight_grams", 200)
        cost = item.get("estimated_cost_inr", 0)
        action = item.get("action_date", today.isoformat())
        expiry = item.get("expiry_date", today.isoformat())
        status = item["status"]
        cat = item.get("category", "other")

        if status == "used":
            overall_saved_weight += weight_g
            overall_money_saved += cost
            if action >= week_ago:
                weekly["items_saved"] += 1
                weekly["saved_weight_kg"] += weight_g / 1000
                weekly["money_saved_inr"] += cost
            if action >= month_ago:
                monthly["items_saved"] += 1
                monthly["saved_weight_kg"] += weight_g / 1000
                monthly["money_saved_inr"] += cost
        elif status == "wasted":
            overall_wasted_weight += weight_g
            category_waste[cat] = category_waste.get(cat, 0) + weight_g
            if action >= week_ago:
                weekly["items_wasted"] += 1
            if action >= month_ago:
                monthly["items_wasted"] += 1

    saved_kg = overall_saved_weight / 1000
    wasted_kg = overall_wasted_weight / 1000
    co2_saved = round(saved_kg * 2.5, 2)
    total_weight = saved_kg + wasted_kg
    waste_ratio = round(wasted_kg / total_weight, 2) if total_weight > 0 else 0
    most_wasted = max(category_waste, key=category_waste.get) if category_waste else ""

    weekly["co2_saved_kg"] = round(weekly["saved_weight_kg"] * 2.5, 2)
    weekly["saved_weight_kg"] = round(weekly["saved_weight_kg"], 2)
    weekly["money_saved_inr"] = round(weekly["money_saved_inr"], 2)
    monthly["co2_saved_kg"] = round(monthly["saved_weight_kg"] * 2.5, 2)
    monthly["saved_weight_kg"] = round(monthly["saved_weight_kg"], 2)
    monthly["money_saved_inr"] = round(monthly["money_saved_inr"], 2)

    # Streak calculation
    all_wasted = await db.food_items.find(
        {"status": "wasted"}, {"_id": 0, "action_date": 1}
    ).to_list(10000)
    waste_dates = set()
    for w in all_wasted:
        if w.get("action_date"):
            waste_dates.add(w["action_date"])

    current_streak = 0
    check_date = today
    while True:
        if check_date.isoformat() in waste_dates:
            break
        current_streak += 1
        check_date -= timedelta(days=1)
        if current_streak > 365:
            break

    # Get total days tracked
    first_item = await db.food_items.find_one(sort=[("created_at", 1)])
    longest_streak = current_streak
    if first_item and first_item.get("created_at"):
        try:
            start = date.fromisoformat(first_item["created_at"][:10])
            check = start
            streak = 0
            while check <= today:
                if check.isoformat() in waste_dates:
                    longest_streak = max(longest_streak, streak)
                    streak = 0
                else:
                    streak += 1
                check += timedelta(days=1)
            longest_streak = max(longest_streak, streak)
        except Exception:
            pass

    return {
        "overall": {
            "saved_weight_kg": round(saved_kg, 2),
            "wasted_weight_kg": round(wasted_kg, 2),
            "money_saved_inr": round(overall_money_saved, 2),
            "co2_saved_kg": co2_saved,
            "waste_ratio": waste_ratio,
            "most_wasted_category": most_wasted,
            "total_items_tracked": len(all_items),
        },
        "streaks": {
            "current_streak_days": current_streak,
            "longest_streak_days": longest_streak,
        },
        "weekly": weekly,
        "monthly": monthly,
    }


@api_router.get("/notifications")
async def get_notifications():
    """Get items that need attention today"""
    items = await db.food_items.find({"status": "active"}, {"_id": 0}).to_list(1000)
    notify = []
    expired = []
    cook_today = []
    for item in items:
        days_remaining, urgency = compute_urgency(item.get("expiry_date", ""))
        item["days_remaining"] = days_remaining
        item["urgency_level"] = urgency
        if urgency == "expired":
            expired.append(item)
        elif urgency in ("critical", "urgent"):
            notify.append(item)
            cook_today.append(item)
        elif urgency == "upcoming":
            notify.append(item)
    return {"notify_today": notify, "expired_items": expired, "cook_today": cook_today}


# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
