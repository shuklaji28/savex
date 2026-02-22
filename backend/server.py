from fastapi import FastAPI, APIRouter, UploadFile, File, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
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
mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.getenv('DB_NAME', 'savex_db')]

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
    "milk": {"days": 2, "category": "dairy"}, "curd": {"days": 5, "category": "dairy"},
    "yogurt": {"days": 5, "category": "dairy"}, "paneer": {"days": 4, "category": "dairy"},
    "bread": {"days": 4, "category": "grain"}, "mushroom": {"days": 3, "category": "vegetable"},
    "banana": {"days": 4, "category": "fruit"}, "strawberry": {"days": 3, "category": "fruit"},
    "grape": {"days": 5, "category": "fruit"}, "tofu": {"days": 4, "category": "dairy"},
    "cheese": {"days": 5, "category": "dairy"}, "cream": {"days": 4, "category": "dairy"},
    "butter": {"days": 30, "category": "dairy"}, "egg": {"days": 21, "category": "egg"},
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
    "apple": {"days": 7, "category": "fruit"}, "cabbage": {"days": 14, "category": "vegetable"},
    "beetroot": {"days": 14, "category": "vegetable"}, "radish": {"days": 10, "category": "vegetable"},
    "sweet potato": {"days": 14, "category": "vegetable"}, "pumpkin": {"days": 14, "category": "vegetable"},
    # Dry goods (30-180 days)
    "rice": {"days": 180, "category": "grain"}, "flour": {"days": 90, "category": "grain"},
    "atta": {"days": 90, "category": "grain"}, "maida": {"days": 90, "category": "grain"},
    "besan": {"days": 90, "category": "grain"}, "sooji": {"days": 90, "category": "grain"},
    "suji": {"days": 90, "category": "grain"}, "poha": {"days": 90, "category": "grain"},
    "dal": {"days": 180, "category": "grain"}, "lentil": {"days": 180, "category": "grain"},
    "moong dal": {"days": 180, "category": "grain"}, "toor dal": {"days": 180, "category": "grain"},
    "chana dal": {"days": 180, "category": "grain"}, "urad dal": {"days": 180, "category": "grain"},
    "rajma": {"days": 180, "category": "grain"}, "chana": {"days": 180, "category": "grain"},
    "kabuli chana": {"days": 180, "category": "grain"}, "oats": {"days": 180, "category": "grain"},
    "sugar": {"days": 365, "category": "grain"}, "salt": {"days": 365, "category": "grain"},
    "oil": {"days": 180, "category": "other"}, "ghee": {"days": 180, "category": "dairy"},
    "maggi": {"days": 180, "category": "snack"}, "noodle": {"days": 180, "category": "snack"},
    "pasta": {"days": 180, "category": "grain"}, "vermicelli": {"days": 180, "category": "grain"},
    "biscuit": {"days": 90, "category": "snack"}, "chips": {"days": 60, "category": "snack"},
    "tea": {"days": 180, "category": "beverage"}, "coffee": {"days": 90, "category": "beverage"},
    "juice": {"days": 7, "category": "beverage"}, "soda": {"days": 90, "category": "beverage"},
    "vinegar": {"days": 365, "category": "other"}, "honey": {"days": 365, "category": "other"},
    "ketchup": {"days": 30, "category": "other"}, "sauce": {"days": 14, "category": "other"},
    "jam": {"days": 30, "category": "other"},
    # Spices — ground (60 days = 2 months conservative; actual is longer but user-mentioned)
    "masala": {"days": 60, "category": "spice"},
    "garam masala": {"days": 60, "category": "spice"},
    "chaat masala": {"days": 60, "category": "spice"},
    "sambhar masala": {"days": 60, "category": "spice"},
    "pav bhaji masala": {"days": 60, "category": "spice"},
    "rajma masala": {"days": 60, "category": "spice"},
    "chole masala": {"days": 60, "category": "spice"},
    "biryani masala": {"days": 60, "category": "spice"},
    "kitchen king masala": {"days": 60, "category": "spice"},
    "turmeric": {"days": 60, "category": "spice"}, "haldi": {"days": 60, "category": "spice"},
    "cumin": {"days": 60, "category": "spice"}, "jeera": {"days": 60, "category": "spice"},
    "coriander powder": {"days": 60, "category": "spice"}, "dhania": {"days": 60, "category": "spice"},
    "red chilli": {"days": 60, "category": "spice"}, "mirch": {"days": 60, "category": "spice"},
    "lal mirch": {"days": 60, "category": "spice"}, "chilli powder": {"days": 60, "category": "spice"},
    "pepper": {"days": 60, "category": "spice"}, "black pepper": {"days": 60, "category": "spice"},
    "amchur": {"days": 60, "category": "spice"}, "dry mango powder": {"days": 60, "category": "spice"},
    # Whole spices (last longer — 365 days)
    "hing": {"days": 365, "category": "spice"}, "asafoetida": {"days": 365, "category": "spice"},
    "mustard": {"days": 365, "category": "spice"}, "mustard seed": {"days": 365, "category": "spice"},
    "rai": {"days": 365, "category": "spice"}, "methi seed": {"days": 365, "category": "spice"},
    "cardamom": {"days": 365, "category": "spice"}, "elaichi": {"days": 365, "category": "spice"},
    "cinnamon": {"days": 365, "category": "spice"}, "dalchini": {"days": 365, "category": "spice"},
    "clove": {"days": 365, "category": "spice"}, "laung": {"days": 365, "category": "spice"},
    "bay leaf": {"days": 365, "category": "spice"}, "tej patta": {"days": 365, "category": "spice"},
    "star anise": {"days": 365, "category": "spice"}, "saunf": {"days": 365, "category": "spice"},
    "fennel": {"days": 365, "category": "spice"}, "ajwain": {"days": 365, "category": "spice"},
    "kalonji": {"days": 365, "category": "spice"}, "sesame": {"days": 365, "category": "spice"},
    "til": {"days": 365, "category": "spice"},
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

# Default weight per single unit (grams) — used when user says "I have jeera" with no qty
WEIGHT_ESTIMATES = {
    # produce (per piece)
    "egg": 50, "banana": 120, "apple": 180, "orange": 200, "tomato": 100,
    "potato": 150, "onion": 120, "lemon": 60, "mango": 250, "cucumber": 200,
    "carrot": 80, "capsicum": 150, "bread": 400, "mushroom": 100,
    # dairy / proteins (per pack/piece)
    "milk": 500, "curd": 400, "paneer": 200, "butter": 500, "ghee": 500,
    "cheese": 200, "egg": 50,
    # dry staples (per typical packet)
    "rice": 1000, "atta": 1000, "maida": 1000, "besan": 500, "flour": 1000,
    "dal": 500, "moong dal": 500, "toor dal": 500, "urad dal": 500,
    "chana dal": 500, "rajma": 500, "chana": 500, "oats": 500,
    "sugar": 1000, "salt": 1000, "poha": 500, "sooji": 500, "suji": 500,
    # spices — ground (standard small packet ~100g)
    "masala": 100, "garam masala": 100, "haldi": 100, "turmeric": 100,
    "jeera": 100, "cumin": 100, "dhania": 100, "coriander powder": 100,
    "mirch": 100, "red chilli": 100, "chilli powder": 100, "lal mirch": 100,
    "pepper": 100, "black pepper": 100, "amchur": 100,
    "chaat masala": 100, "sambhar masala": 100, "biryani masala": 100,
    "pav bhaji masala": 100, "chole masala": 100, "kitchen king masala": 100,
    # whole spices (small quantities ~50g)
    "hing": 50, "asafoetida": 50, "mustard": 100, "rai": 100,
    "cardamom": 50, "elaichi": 50, "cinnamon": 50, "dalchini": 50,
    "clove": 50, "laung": 50, "saunf": 100, "fennel": 100,
    "ajwain": 100, "til": 100, "sesame": 100, "kalonji": 50,
    # oils / liquid staples (per bottle)
    "oil": 1000, "vinegar": 500, "honey": 500,
    # snacks / packaged
    "maggi": 70, "noodle": 70, "biscuit": 150, "chips": 50,
    "bread": 400,
}

# ─── INDIAN PRICE LOOKUP (per standard unit) ───
INDIAN_PRICE_DB = {
    # beverages
    "diet coke": 40, "coke": 40, "pepsi": 40, "sprite": 40, "thumbs up": 40,
    "limca": 35, "maaza": 30, "frooti": 20, "paper boat": 30,
    "mineral water": 20, "water bottle": 20,
    "tea": 30, "coffee": 50, "milk": 25,  # per 200ml/250ml
    "juice": 40, "coconut water": 35,
    # dairy
    "curd": 25, "yogurt": 25, "paneer": 80, "butter": 55, "ghee": 150,
    "cheese": 80, "cream": 60,
    # grains / staples
    "bread": 40, "pav": 25, "bun": 25, "roti": 5, "paratha": 15,
    "maggi": 14, "instant noodle": 14, "noodle": 14, "pasta": 50,
    "rice": 50, "atta": 40, "maida": 35, "dal": 80, "poha": 30,
    "suji": 30, "besan": 50, "oats": 60,
    # eggs
    "egg": 7,
    # vegetables (per piece/100g estimate)
    "onion": 5, "tomato": 8, "potato": 6, "garlic": 10, "ginger": 15,
    "spinach": 20, "coriander": 10, "mint": 10, "methi": 15,
    "capsicum": 20, "carrot": 10, "cucumber": 15, "radish": 10,
    "cabbage": 25, "cauliflower": 30, "broccoli": 40, "peas": 30,
    "ladies finger": 20, "bhindi": 20, "brinjal": 15, "baingan": 15,
    "mushroom": 40, "corn": 15, "beetroot": 20,
    # fruits
    "banana": 8, "apple": 20, "orange": 15, "mango": 20, "papaya": 20,
    "watermelon": 10, "grapes": 30, "pomegranate": 30, "guava": 10,
    "lemon": 5, "lime": 5, "pineapple": 40, "strawberry": 100,
    # snacks
    "biscuit": 10, "namkeen": 20, "chips": 20, "kurkure": 10,
    "chocolate": 40, "candy": 5,
    # meat
    "chicken": 80, "mutton": 120, "fish": 100, "prawn": 150,
}


def _infer_storage_multiplier(storage_location: str) -> float:
    """Map free-text storage location to a shelf-life multiplier."""
    loc = (storage_location or "").lower()
    if "freezer" in loc:
        return 3.0
    if "fridge" in loc or "refrigerator" in loc or "cold" in loc:
        return 1.5
    if "pantry" in loc or "shelf" in loc or "rack" in loc or "cupboard" in loc or "almirah" in loc:
        return 1.0
    return 0.85  # bag, purse, office, car, counter, etc. — room temp default


def get_shelf_life(name: str, storage: str) -> int:
    normalized = name.lower().strip()
    info = SHELF_LIFE_DB.get(normalized)
    base_days = info["days"] if info else 5
    multiplier = _infer_storage_multiplier(storage)
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

def _lookup_unit_price(name: str) -> float | None:
    """Check INDIAN_PRICE_DB with exact then partial match."""
    normalized = name.lower().strip()
    if normalized in INDIAN_PRICE_DB:
        return INDIAN_PRICE_DB[normalized]
    for key, price in INDIAN_PRICE_DB.items():
        if key in normalized or normalized in key:
            return price
    return None

async def get_user_price(name: str) -> float | None:
    """Check user-taught price memory for this item."""
    doc = await db.price_memory.find_one({"normalized_name": name.lower().strip()}, {"_id": 0, "price_inr": 1})
    return doc["price_inr"] if doc else None

async def save_user_price(name: str, price_inr: float):
    """Save or update user-taught price in price_memory collection."""
    await db.price_memory.update_one(
        {"normalized_name": name.lower().strip()},
        {"$set": {"normalized_name": name.lower().strip(), "price_inr": price_inr,
                  "source": "user_taught", "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    logger.info(f"Price memory saved: {name} = ₹{price_inr}")

async def estimate_cost_inr_smart(name: str, weight_grams: float, category: str, price_mentioned: float | None = None) -> float:
    """Resolve price: user_mention > price_memory > INDIAN_PRICE_DB > category estimate."""
    if price_mentioned and price_mentioned > 0:
        return round(price_mentioned, 2)
    user_price = await get_user_price(name)
    if user_price:
        return round(user_price, 2)
    unit_price = _lookup_unit_price(name)
    if unit_price:
        return round(unit_price, 2)
    cost_per_500 = COST_PER_500G.get(category, 50)
    return round((weight_grams / 500) * cost_per_500, 2)

# keep old function for non-async contexts
def estimate_cost_inr(weight_grams: float, category: str) -> float:
    cost_per_500 = COST_PER_500G.get(category, 50)
    return round((weight_grams / 500) * cost_per_500, 2)


# ─── GEMINI EXTRACTION PROMPT ───
EXTRACTION_SYSTEM_PROMPT = """You are a food inventory management assistant. Extract food items from user speech and classify each item's INTENT.

INTENT TYPES:
- "add": User bought, got, picked up, has, or is adding this item to their inventory
- "mark_used": User consumed, finished, used up, ate, or cooked with this item
- "mark_wasted": User says item expired, went bad, spoiled, had to throw away, couldn't use, was wasted
- "metadata_update": User is correcting or adding details to an EXISTING item (e.g. location, price, expiry, quantity)

INTENT DETECTION:
- Adding → "bought", "got", "picked up", "have", "purchased", "from market", "stocked up", "I have X in my Y"
- Used → "used", "finished", "ate", "consumed", "cooked with", "used up", "done with"
- Wasted → "expired", "went bad", "spoiled", "threw away", "wasted", "couldn't use", "rotten", "not able to use"
- Update → "actually", "correction", "by the way", "the X costs", "X is in my Y", "update", "change", "X expires on", "X generally costs"

IMPORTANT RULES:
1. storage_location = EXACT words user said (e.g. "office bag", "kitchen red jar", "car", "purse", "top shelf", "drawer"). Do NOT change to unknown if user mentioned a location.
2. If no location mentioned, use "unknown"
3. price_mentioned = numeric price in INR if user states it (e.g. "costs 40", "₹14", "14 rupees"). Null otherwise.
4. voice_note = a short summary of exactly what the user said about this item (1 sentence max)
5. Normalize names to singular lowercase (tomatoes→tomato, eggs→egg)
6. Convert relative dates: "today"=current_date, "yesterday"=current_date-1day
7. Handle Indian foods: paneer, curd, atta, dal, ghee, maggi, etc.
8. For "metadata_update" intent, set fields_to_update with ONLY the fields user mentioned changing
9. category must be one of: vegetable, fruit, dairy, grain, spice, snack, beverage, meat, egg, other

Return ONLY valid JSON, no markdown, no explanation:
{
  "items": [
    {
      "intent": "add|mark_used|mark_wasted|metadata_update",
      "item_name": "original name as spoken",
      "normalized_name": "singular lowercase",
      "quantity": 1,
      "unit": "count",
      "approximate_quantity": false,
      "storage_location": "exact location user mentioned, or unknown",
      "added_date": "YYYY-MM-DD",
      "expiry_date_mentioned": "YYYY-MM-DD or null",
      "expiry_relative_days": null,
      "category": "vegetable|fruit|dairy|grain|spice|snack|beverage|meat|egg|other",
      "price_mentioned": null,
      "voice_note": "brief summary of what user said about this item",
      "fields_to_update": null
    }
  ]
}

For metadata_update intent, fields_to_update should be an object with only changed fields, e.g.:
{"storage_location": "office bag", "price_inr": 40, "expiry_date": "2026-03-30"}"""

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


async def build_inventory_context() -> str:
    """Fetch active inventory and format as context for Gemini so it can distinguish add vs update."""
    active = await db.food_items.find(
        {"status": "active"},
        {"_id": 0, "normalized_name": 1, "item_name": 1, "storage_location": 1,
         "expiry_date": 1, "quantity": 1, "unit": 1, "batch_number": 1}
    ).to_list(200)

    if not active:
        return "Current inventory: (empty)"

    lines = []
    for item in active:
        loc = item.get("storage_location", "unknown")
        batch = item.get("batch_number", 1)
        batch_tag = f" [batch #{batch}]" if batch > 1 else ""
        expiry = item.get("expiry_date", "?")
        qty = f"{item.get('quantity',1)} {item.get('unit','count')}"
        lines.append(f"- {item['normalized_name']}{batch_tag} | {qty} | location: {loc} | expiry: {expiry}")

    return "Current inventory (already exists — use this to classify intent correctly):\n" + "\n".join(lines)


async def find_active_item_by_name(name: str) -> dict | None:
    """Find active inventory item by normalized name — exact match then partial."""
    item = await db.food_items.find_one({"normalized_name": name, "status": "active"}, {"_id": 0})
    if item:
        return item
    item = await db.food_items.find_one(
        {"normalized_name": {"$regex": name, "$options": "i"}, "status": "active"}, {"_id": 0}
    )
    if item:
        return item
    all_active = await db.food_items.find({"status": "active"}, {"_id": 0, "id": 1, "normalized_name": 1}).to_list(500)
    for doc in all_active:
        stored = doc.get("normalized_name", "")
        if stored and stored in name:
            return await db.food_items.find_one({"id": doc["id"]}, {"_id": 0})
    return None



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


async def _send_duplicate_whatsapp_nudge(duplicates: list[str]):
    """Fire-and-forget WhatsApp nudge when user adds items already in inventory."""
    names = ", ".join(d.capitalize() for d in duplicates)
    body = (
        f"🛒 *savex — heads up!*\n\n"
        f"You already have *{names}* in your inventory.\n\n"
        f"Double-check before buying more — open savex to see what's already there! 🌱"
    )
    _send_whatsapp(body)


async def process_extracted_items(items_list: list):
    """Route extracted items to add or update flows based on intent."""
    added_items = []
    updated_items = []
    not_found = []
    warnings = []   # duplicate batch warnings
    now_iso = datetime.now(timezone.utc).isoformat()
    today_iso = date.today().isoformat()
    duplicate_names = []

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

        elif intent == "metadata_update":
            matched = await find_active_item_by_name(name)
            if matched:
                fields = item_data.get("fields_to_update") or {}
                update_set = {"updated_at": now_iso}
                if "storage_location" in fields:
                    update_set["storage_location"] = fields["storage_location"]
                if "price_inr" in fields and fields["price_inr"]:
                    update_set["estimated_cost_inr"] = fields["price_inr"]
                    asyncio.create_task(save_user_price(name, fields["price_inr"]))
                if "expiry_date" in fields and fields["expiry_date"]:
                    update_set["expiry_date"] = fields["expiry_date"]
                if "quantity" in fields:
                    update_set["quantity"] = fields["quantity"]
                if "unit" in fields:
                    update_set["unit"] = fields["unit"]
                voice_note = item_data.get("voice_note", "")
                if voice_note:
                    update_set["voice_note"] = voice_note
                # also save user-mentioned price from top-level price_mentioned
                pm = item_data.get("price_mentioned")
                if pm and pm > 0:
                    update_set["estimated_cost_inr"] = pm
                    asyncio.create_task(save_user_price(name, pm))
                await db.food_items.update_one({"id": matched["id"]}, {"$set": update_set})
                matched.update(update_set)
                matched.pop("_id", None)
                updated_items.append(matched)
            else:
                not_found.append({"name": name, "intent": intent})
        else:
            # ADD flow — check for duplicates first
            existing_batches = await db.food_items.find(
                {"normalized_name": name, "status": "active"}, {"_id": 0, "id": 1, "added_date": 1, "batch_number": 1}
            ).to_list(100)
            batch_number = len(existing_batches) + 1

            if batch_number > 1:
                oldest_added = existing_batches[0].get("added_date", "")
                warnings.append({
                    "name": name,
                    "existing_batches": len(existing_batches),
                    "oldest_added": oldest_added,
                    "new_batch": batch_number,
                })
                duplicate_names.append(name)

            expiry = compute_expiry(item_data)
            days_remaining, urgency = compute_urgency(expiry)
            qty = item_data.get("quantity", 1)
            unit = item_data.get("unit", "count")
            category = item_data.get("category", get_category(name))
            weight = estimate_weight_grams(name, qty, unit)
            price_mentioned = item_data.get("price_mentioned")
            cost = await estimate_cost_inr_smart(name, weight, category, price_mentioned)
            storage = item_data.get("storage_location", "unknown") or "unknown"
            voice_note = item_data.get("voice_note", "")
            display_name = f"{item_data.get('item_name', name)} #{batch_number}" if batch_number > 1 else item_data.get("item_name", name)

            # If user mentioned a price, save to price memory for future use
            if price_mentioned and price_mentioned > 0:
                asyncio.create_task(save_user_price(name, price_mentioned))

            food_doc = {
                "id": str(uuid.uuid4()),
                "item_name": display_name,
                "normalized_name": name,
                "batch_number": batch_number,
                "quantity": qty,
                "unit": unit,
                "approximate_quantity": item_data.get("approximate_quantity", False),
                "storage_location": storage,
                "category": category,
                "added_date": item_data.get("added_date", today_iso),
                "expiry_date": expiry,
                "status": "active",
                "action_date": None,
                "estimated_weight_grams": weight,
                "estimated_cost_inr": cost,
                "voice_note": voice_note,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            await db.food_items.insert_one(food_doc)
            food_doc["days_remaining"] = days_remaining
            food_doc["urgency_level"] = urgency
            food_doc.pop("_id", None)
            added_items.append(food_doc)

    # Fire WhatsApp nudge if any duplicates were added (non-blocking)
    if duplicate_names:
        asyncio.create_task(_send_duplicate_whatsapp_nudge(duplicate_names))

    return added_items, updated_items, not_found, warnings


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

        # 2. Extract entities with Gemini (inventory-aware)
        inventory_context = await build_inventory_context()
        session_id = str(uuid.uuid4())
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=EXTRACTION_SYSTEM_PROMPT
        ).with_model("gemini", "gemini-3-flash-preview")

        prompt = f"Current date: {date.today().isoformat()}\n\n{inventory_context}\n\nTranscript: \"{transcript}\""
        response = await chat.send_message(UserMessage(text=prompt))
        logger.info(f"Gemini response: {response}")
        extracted = parse_json_from_llm(response)
        items_list = extracted.get("items", [])

        # 3. Process and save each item (handles add + mark_used + mark_wasted)
        added, updated, not_found, warnings = await process_extracted_items(items_list)

        return {
            "transcript": transcript,
            "items": added,
            "updated_items": updated,
            "not_found": not_found,
            "warnings": warnings,
            "count": len(added) + len(updated),
        }

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
        inventory_context = await build_inventory_context()
        session_id = str(uuid.uuid4())
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=EXTRACTION_SYSTEM_PROMPT
        ).with_model("gemini", "gemini-3-flash-preview")

        prompt = f"Current date: {date.today().isoformat()}\n\n{inventory_context}\n\nTranscript: \"{transcript}\""
        response = await chat.send_message(UserMessage(text=prompt))
        logger.info(f"Gemini response: {response}")
        extracted = parse_json_from_llm(response)
        items_list = extracted.get("items", [])

        added, updated, not_found, warnings = await process_extracted_items(items_list)

        return {
            "transcript": transcript,
            "items": added,
            "updated_items": updated,
            "not_found": not_found,
            "warnings": warnings,
            "count": len(added) + len(updated),
        }
    except Exception as e:
        logger.error(f"Error processing text: {e}", exc_info=True)
        return {"error": str(e), "transcript": transcript, "items": [], "updated_items": [], "warnings": [], "count": 0}


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

    if not items:
        return {"recipes": [], "expiring_items": []}

    # Build a list of all active items sorted by days remaining — exclude already expired
    all_with_urgency = []
    for item in items:
        days_remaining, urgency = compute_urgency(item.get("expiry_date", ""))
        if days_remaining <= 0:
            continue  # skip expired items — nothing to cook with
        all_with_urgency.append({
            "name": item["normalized_name"],
            "quantity": item["quantity"],
            "unit": item["unit"],
            "days_remaining": days_remaining,
            "urgency": urgency,
        })
    all_with_urgency.sort(key=lambda x: x["days_remaining"])

    # Prefer truly near-expiry items; fall back to the 5 soonest-to-expire fresh items
    expiring = [i for i in all_with_urgency if i["urgency"] in ("critical", "urgent", "upcoming")]
    if not expiring:
        expiring = all_with_urgency[:5]  # use soonest fresh items if nothing is urgent

    expiring = expiring[:10]

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

    # Streak = consecutive days going back from today where nothing was wasted
    # Only count days AFTER the user first added an item (no app = no streak)
    first_item = await db.food_items.find_one(sort=[("created_at", 1)])
    app_start = today  # default: started today
    if first_item and first_item.get("created_at"):
        try:
            app_start = date.fromisoformat(first_item["created_at"][:10])
        except Exception:
            pass

    current_streak = 0
    check_date = today
    while check_date >= app_start:
        if check_date.isoformat() in waste_dates:
            break
        current_streak += 1
        check_date -= timedelta(days=1)

    # Longest streak (scan full history)
    longest_streak = current_streak
    if first_item and first_item.get("created_at"):
        try:
            start = app_start
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


# ─── WHATSAPP NOTIFICATION SYSTEM ───

TWILIO_SID   = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
WA_FROM      = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
WA_TO        = os.environ.get("USER_WHATSAPP_TO", "")

def _send_whatsapp(body: str) -> bool:
    """Send a WhatsApp message via Twilio. Returns True on success."""
    if not (TWILIO_SID and TWILIO_TOKEN and WA_TO):
        logger.warning("Twilio credentials not configured — skipping WhatsApp send")
        return False
    try:
        from twilio.rest import Client as TwilioClient
        tc = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
        msg = tc.messages.create(body=body, from_=WA_FROM, to=WA_TO)
        logger.info(f"WhatsApp sent: {msg.sid}")
        return True
    except Exception as e:
        logger.error(f"Twilio error: {e}")
        return False


async def _job_expiry_alert():
    """Evening job (8 PM IST): alert for items expiring within 3 days with reply-to-update support."""
    try:
        items = await db.food_items.find({"status": "active"}, {"_id": 0}).to_list(1000)
        urgent_items = []
        for item in items:
            days, urgency = compute_urgency(item.get("expiry_date", ""))
            if urgency in ("critical", "urgent") and days > 0:
                urgent_items.append({
                    "item_id": item["id"],
                    "name": item["normalized_name"],
                    "display": item.get("item_name", item["normalized_name"]),
                    "days": days,
                    "location": item.get("storage_location", "unknown"),
                })

        if not urgent_items:
            logger.info("Expiry alert: no urgent items, skipping WhatsApp")
            return

        # Save alert session so webhook can look up "1", "2", etc.
        session_doc = {
            "session_id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
            "from_number": WA_TO,
            "items": [{"index": i + 1, **it} for i, it in enumerate(urgent_items)],
        }
        await db.alert_sessions.insert_one(session_doc)
        logger.info(f"Alert session saved: {session_doc['session_id']}")

        # Build message
        lines = []
        cook_names = []
        for it in session_doc["items"]:
            label = "expires *today*" if it["days"] == 1 else f"expires in *{it['days']} days*"
            loc_hint = f" (📍 {it['location']})" if it["location"] and it["location"] != "unknown" else ""
            lines.append(f"{it['index']}️⃣ {it['display'].capitalize()}{loc_hint} — {label}")
            cook_names.append(it["name"])

        cook_hint = ""
        if cook_names:
            cook_hint = f"\n\n💡 *Tip:* Cook with {', '.join(cook_names[:3])} tonight — open savex > Cook tab!"

        reply_hint = (
            "\n\n↩️ *Reply to update:*\n"
            "Just tell me what happened — e.g:\n"
            "• _\"used the paneer\"_\n"
            "• _\"threw away 1\"_\n"
            "• _\"all used\"_\n"
            "savex will update your inventory automatically 🙂"
        )

        body = (
            "🚨 *savex — Expiry Alert*\n\n"
            "These items need your attention:\n"
            + "\n".join(lines)
            + cook_hint
            + reply_hint
        )
        _send_whatsapp(body)
    except Exception as e:
        logger.error(f"Expiry alert job error: {e}")


async def _interpret_whatsapp_reply(user_message: str, session_items: list) -> list:
    """Use Gemini to interpret a free-text WhatsApp reply against alert session items."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage as LLMUserMessage
    api_key = os.environ.get("EMERGENT_LLM_KEY")

    items_context = "\n".join(
        [f"{it['index']}. {it['display']} (id: {it['item_id']})" for it in session_items]
    )

    system_prompt = """You parse WhatsApp replies to food expiry alerts and extract update actions.

The user was shown a numbered list of expiring food items and replied with what happened to them.

Return ONLY valid JSON — no markdown, no explanation:
{
  "actions": [
    {"item_id": "<exact id from context>", "item_name": "<name>", "action": "used|wasted"}
  ],
  "mark_all": "used|wasted|null"
}

Rules:
- "used", "ate", "consumed", "finished", "cooked", "done" → action: "used"
- "wasted", "threw", "expired", "bad", "rotten", "couldn't use", "discarded", "gone" → action: "wasted"
- "all used" / "everything used" → mark_all: "used", actions: []
- "all wasted" / "all gone bad" → mark_all: "wasted", actions: []
- Numbers like "1 used" or "2 wasted" → match by index from items list
- Item names like "paneer used" or "used the chicken" → match by name
- If unclear for an item, skip it
- Return empty actions if nothing is clear"""

    chat = LlmChat(
        api_key=api_key,
        session_id=str(uuid.uuid4()),
        system_message=system_prompt
    ).with_model("gemini", "gemini-3-flash-preview")

    response = await chat.send_message(LLMUserMessage(
        text=f"Items in this alert:\n{items_context}\n\nUser replied: \"{user_message}\""
    ))
    parsed = parse_json_from_llm(response)
    return parsed


@api_router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    """Receive ANY WhatsApp message — full inventory control via chat."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage as LLMUserMessage
    try:
        form = await request.form()
        user_message = (form.get("Body") or "").strip()
        from_number = form.get("From", "")
        logger.info(f"WhatsApp message from {from_number}: {user_message}")

        if not user_message:
            return {"status": "ignored"}

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        today_iso = date.today().isoformat()

        # ── Step 0: Detect inventory queries FIRST, before full extraction ──
        pre_check = await LlmChat(
            api_key=api_key,
            session_id=str(uuid.uuid4()),
            system_message=(
                "Classify if this WhatsApp message is asking what the user already has in their fridge/pantry/inventory. "
                "Return JSON only: {\"is_query\": true/false, \"items_asked\": [\"item1\"]}. "
                "is_query=true ONLY for questions: 'do I have X?', 'is there Y?', 'what do I have?', 'do I need to buy X?', 'check if I have X'. "
                "is_query=false for action statements: 'I bought X', 'used X', 'threw X', 'X is in the fridge'."
            )
        ).with_model("gemini", "gemini-3-flash-preview").send_message(
            LLMUserMessage(text=f"Message: \"{user_message}\"")
        )
        qdata = parse_json_from_llm(pre_check)

        if qdata.get("is_query"):
            items_asked = qdata.get("items_asked", [])
            if not items_asked:
                active = await db.food_items.find({"status": "active"}, {"_id": 0}).to_list(100)
                if not active:
                    _send_whatsapp("📦 *savex:* Your inventory is currently empty!")
                else:
                    lines = []
                    for item in sorted(active, key=lambda x: x.get("expiry_date", "")):
                        days, urgency = compute_urgency(item.get("expiry_date", ""))
                        icon = "🔴" if urgency == "critical" else "🟡" if urgency == "urgent" else "🟢"
                        loc = item.get("storage_location", "")
                        loc_hint = f" (📍 {loc})" if loc and loc != "unknown" else ""
                        lines.append(f"{icon} {item['item_name'].capitalize()}{loc_hint} — {days}d left")
                    _send_whatsapp("📦 *savex — Your Inventory:*\n\n" + "\n".join(lines))
            else:
                lines = []
                for asked in items_asked:
                    matched = await find_active_item_by_name(asked.lower().strip())
                    if matched:
                        days, urgency = compute_urgency(matched.get("expiry_date", ""))
                        loc = matched.get("storage_location", "")
                        loc_hint = f" (📍 {loc})" if loc and loc != "unknown" else ""
                        urgency_hint = " ⚠️ expiring soon!" if urgency in ("critical", "urgent") else f", {days}d left"
                        lines.append(f"✅ Yes, *{matched['item_name'].capitalize()}*{loc_hint}{urgency_hint} — no need to buy!")
                    else:
                        lines.append(f"❌ No *{asked}* in inventory — safe to buy!")
                _send_whatsapp("🔍 *savex inventory check:*\n\n" + "\n".join(lines))
            return {"status": "ok", "type": "inventory_query"}

        # ── Step 1: Run full Gemini extraction for add/update/mark operations ──
        inventory_context = await build_inventory_context()
        
        chat = LlmChat(
            api_key=api_key,
            session_id=str(uuid.uuid4()),
            system_message=EXTRACTION_SYSTEM_PROMPT
        ).with_model("gemini", "gemini-3-flash-preview")

        response = await chat.send_message(LLMUserMessage(
            text=f"Current date: {today_iso}\n\n{inventory_context}\n\nUser message: {user_message}"
        ))
        extracted = parse_json_from_llm(response)
        items_list = extracted.get("items", [])

        if not items_list:
            # Check if it's an inventory question ("do I have X?", "is there paneer?")
            query_check = await LlmChat(
                api_key=api_key,
                session_id=str(uuid.uuid4()),
                system_message="You detect if a message is asking about what the user has in their inventory/fridge/pantry. Return JSON only: {\"is_query\": true/false, \"items_asked\": [\"item1\", \"item2\"]}"
            ).with_model("gemini", "gemini-3-flash-preview").send_message(
                LLMUserMessage(text=f"Message: \"{user_message}\"")
            )
            qdata = parse_json_from_llm(query_check)
            if qdata.get("is_query") and qdata.get("items_asked"):
                lines = []
                for asked in qdata["items_asked"]:
                    matched = await find_active_item_by_name(asked.lower().strip())
                    if matched:
                        days, urgency = compute_urgency(matched.get("expiry_date", ""))
                        loc = matched.get("storage_location", "")
                        loc_hint = f" (📍 {loc})" if loc and loc != "unknown" else ""
                        urgency_hint = " ⚠️ expiring soon!" if urgency in ("critical", "urgent") else f", {days}d left"
                        lines.append(f"✅ Yes, you have *{matched['item_name'].capitalize()}*{loc_hint}{urgency_hint}")
                    else:
                        lines.append(f"❌ No *{asked}* found in your inventory — safe to buy!")
                _send_whatsapp("🔍 *savex inventory check:*\n\n" + "\n".join(lines))
                return {"status": "ok", "type": "inventory_query"}

            _send_whatsapp(
                "🤔 *savex* couldn't find any food items in that.\n\n"
                "Try:\n• _\"do I have paneer?\"_\n• _\"used the milk\"_\n• _\"bought eggs and spinach\"_"
            )
            return {"status": "no_items_found"}

        # Process using the same pipeline as /api/process-text
        added, updated, not_found, warnings = await process_extracted_items(items_list)

        # Build reply
        lines = []
        if added:
            for item in added:
                loc = item.get("storage_location", "")
                loc_hint = f" (📍 {loc})" if loc and loc != "unknown" else ""
                lines.append(f"➕ *{item['item_name'].capitalize()}* added{loc_hint} — {item.get('days_remaining','?')}d left")
        if updated:
            for item in updated:
                st = item.get("status", "")
                icon = "✅" if st == "used" else "🗑️"
                lines.append(f"{icon} *{item.get('normalized_name','').capitalize()}* → {st}")
        if warnings:
            for w in warnings:
                lines.append(f"⚠️ *{w['name'].capitalize()}* already in inventory (added as batch #{w['new_batch']})")
        if not_found:
            for nf in not_found:
                lines.append(f"❓ *{nf['name'].capitalize()}* — not found in inventory")

        _send_whatsapp("📦 *savex updated!*\n\n" + "\n".join(lines) + "\n\nInventory synced 🌱")
        return {"status": "ok", "added": len(added), "updated": len(updated)}

    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}", exc_info=True)
        _send_whatsapp("⚠️ savex had a hiccup. Please try again!")
        return {"status": "error", "detail": str(e)}


async def _job_daily_recipe():
    """Morning job (8 AM IST): WhatsApp recipe suggestion using expiring items."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    try:
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        items = await db.food_items.find({"status": "active"}, {"_id": 0}).to_list(1000)

        # Pick items to cook with: near-expiry first, else soonest 5
        candidates = []
        for item in items:
            days, urgency = compute_urgency(item.get("expiry_date", ""))
            if days > 0:
                candidates.append((days, urgency, item["normalized_name"], item["quantity"], item["unit"]))
        candidates.sort(key=lambda x: x[0])

        near_expiry = [(d, u, n, q, un) for d, u, n, q, un in candidates if u in ("critical", "urgent", "upcoming")]
        use_these = near_expiry[:5] if near_expiry else candidates[:5]

        if not use_these:
            logger.info("Daily recipe: no active items, skipping")
            return

        items_text = "\n".join([f"- {n} ({q} {un}, {d} days left)" for d, u, n, q, un in use_these])

        WHATSAPP_RECIPE_PROMPT = """You are a home cook assistant. Suggest ONE simple recipe using the provided ingredients.
Keep it under 15 minutes. Format your reply EXACTLY like this (plain text, no JSON):

Recipe: <name>
Time: <X> min
Uses: <comma-separated expiring items>
Needs: <other basic pantry items>
Steps:
1. <step>
2. <step>
3. <step>
Tip: <one quick tip>

Keep it concise and practical."""

        chat = LlmChat(
            api_key=api_key,
            session_id=str(uuid.uuid4()),
            system_message=WHATSAPP_RECIPE_PROMPT
        ).with_model("gemini", "gemini-3-flash-preview")

        response = await chat.send_message(UserMessage(
            text=f"Today is {date.today().strftime('%A, %d %B %Y')}.\n\nItems to use up:\n{items_text}"
        ))

        body = (
            "🍳 *savex — Good Morning! Here's what to cook today:*\n\n"
            + response.strip()
            + "\n\n_Open savex > Cook tab for more recipe ideas!_ 🌱"
        )
        _send_whatsapp(body)
    except Exception as e:
        logger.error(f"Daily recipe job error: {e}")


async def _job_meal_suggestion(meal: str = "dinner"):
    """Send a meal-specific recipe suggestion (breakfast / lunch / dinner)."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    meal_emoji = {"breakfast": "🌅", "lunch": "☀️", "dinner": "🌙"}.get(meal, "🍽️")
    try:
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        items = await db.food_items.find({"status": "active"}, {"_id": 0}).to_list(1000)

        candidates = []
        for item in items:
            days, urgency = compute_urgency(item.get("expiry_date", ""))
            if days > 0:
                candidates.append((days, urgency, item["normalized_name"], item["quantity"], item["unit"]))
        candidates.sort(key=lambda x: x[0])

        near_expiry = [(d, u, n, q, un) for d, u, n, q, un in candidates if u in ("critical", "urgent", "upcoming")]
        use_these = near_expiry[:5] if near_expiry else candidates[:5]

        if not use_these:
            logger.info(f"{meal} suggestion: no active items, skipping")
            return

        items_text = "\n".join([f"- {n} ({q} {un}, {d} days left)" for d, u, n, q, un in use_these])

        # Also list other available (fresh) items for context
        fresh_names = [n for d, u, n, q, un in candidates if (d, u, n, q, un) not in use_these][:5]
        fresh_context = f"\nOther items available: {', '.join(fresh_names)}" if fresh_names else ""

        WHATSAPP_RECIPE_PROMPT = f"""You are a home cook assistant helping reduce food waste. 
Suggest ONE simple {meal} recipe that uses the priority expiring items listed.
Keep it practical for an Indian household and under 15 minutes if possible.
Format your reply EXACTLY like this (plain text, no JSON, no markdown headers):

Recipe: <name>
Time: <X> min
Uses: <comma-separated expiring items from the list>
Also needs: <1-2 basic pantry items max>
Steps:
1. <step>
2. <step>
3. <step>
Tip: <one quick waste-saving tip>

Keep it under 180 words. Be warm and personal."""

        chat = LlmChat(
            api_key=api_key,
            session_id=str(uuid.uuid4()),
            system_message=WHATSAPP_RECIPE_PROMPT
        ).with_model("gemini", "gemini-3-flash-preview")

        expiry_label = "near-expiry" if near_expiry else "soonest to expire"
        response = await chat.send_message(UserMessage(
            text=f"Today is {date.today().strftime('%A, %d %B %Y')}.\n\nPriority items to use ({expiry_label}):\n{items_text}{fresh_context}\n\nSuggest a {meal} recipe."
        ))

        body = (
            f"{meal_emoji} *savex — What to cook for {meal.capitalize()} tonight:*\n\n"
            + response.strip()
            + "\n\n_Open savex > Cook tab for more ideas!_ 🌱"
        )
        _send_whatsapp(body)
    except Exception as e:
        logger.error(f"{meal} suggestion job error: {e}")


@api_router.post("/notifications/test")
async def test_notification(req: dict):
    """Trigger WhatsApp notifications manually. type: expiry | recipe | dinner | both"""
    ntype = req.get("type", "both")
    results = {}
    if ntype in ("expiry", "both"):
        await _job_expiry_alert()
        results["expiry"] = "triggered"
    if ntype in ("recipe", "both"):
        await _job_daily_recipe()
        results["recipe"] = "triggered"
    if ntype == "dinner":
        await _job_meal_suggestion("dinner")
        results["dinner"] = "triggered"
    return {"status": "ok", "triggered": results}


# ─── SCHEDULER SETUP ───

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

_scheduler = AsyncIOScheduler(timezone=pytz.timezone("Asia/Kolkata"))


# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def start_scheduler():
    # 8:00 AM IST — morning recipe suggestion
    _scheduler.add_job(
        _job_daily_recipe, CronTrigger(hour=8, minute=0, timezone=pytz.timezone("Asia/Kolkata")),
        id="daily_recipe", replace_existing=True
    )
    # 8:00 PM IST — evening expiry alert
    _scheduler.add_job(
        _job_expiry_alert, CronTrigger(hour=20, minute=0, timezone=pytz.timezone("Asia/Kolkata")),
        id="expiry_alert", replace_existing=True
    )
    _scheduler.start()
    logger.info("Notification scheduler started (8 AM recipe + 8 PM expiry alert, IST)")

@app.on_event("shutdown")
async def shutdown_db_client():
    _scheduler.shutdown(wait=False)
    client.close()

