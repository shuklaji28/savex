# Sustain - Food Waste Reduction Assistant

## Product Overview
Voice-first household food waste reduction mobile app that helps users reduce food wastage by logging items via natural speech, tracking expiry timelines, suggesting meals using expiring ingredients, and measuring environmental/financial impact.

## Tech Stack
- **Frontend**: React Native (Expo SDK 54) with Expo Router
- **Backend**: Python FastAPI
- **Database**: MongoDB (motor async driver)
- **STT**: OpenAI Whisper-1 (via Emergent LLM key)
- **LLM**: Gemini 3 Flash (extraction + recipes, via Emergent LLM key)
- **Theme**: Dark minimalist (black/grey/cream)

## Core Features (MVP)

### 1. Voice-First Home Screen
- Large animated mic button for instant grocery logging
- Whisper STT transcription → Gemini structured extraction
- Auto-adds items to inventory with computed expiry dates
- Confirmation of added items shown briefly

### 2. Inventory Screen
- Items sorted by nearest expiry, grouped by urgency:
  - Expired (red)
  - Expiring Today (red)
  - Expiring in 1-2 Days (yellow)
  - Expiring This Week (blue)
  - Fresh Items (green)
- Tap to view item detail modal (entry date, expiry, quantity, storage, category, weight, cost)
- Mark items as **Used** or **Wasted** from detail modal
- History view for past items

### 3. What to Cook Screen
- AI-generated recipes using Gemini 3 Flash
- Prioritizes items closest to expiry
- Quick recipes (under 20 min), categorized as meal/snack/simple_prep
- Expandable cards with step-by-step instructions

### 4. Impact Dashboard
- Streak tracker (consecutive days without waste)
- Overall metrics: food saved (kg), money saved (₹), CO₂ avoided (kg), food wasted (kg)
- Waste ratio with visual bar
- Most wasted category identification
- Weekly & monthly summaries

## Backend API Endpoints
| Endpoint | Method | Description |
|---|---|---|
| `/api/` | GET | Health check |
| `/api/process-voice` | POST | Voice → STT → extraction → save |
| `/api/inventory` | GET | Active items sorted by urgency |
| `/api/inventory/{id}` | GET | Single item detail |
| `/api/inventory/{id}/status` | PUT | Mark used/wasted |
| `/api/inventory/history` | GET | Past items |
| `/api/recipes` | GET | AI recipe suggestions |
| `/api/reports` | GET | Impact dashboard metrics |
| `/api/notifications` | GET | Items needing attention |

## Data Model (MongoDB: food_items)
- id, item_name, normalized_name, quantity, unit, storage_location, category
- added_date, expiry_date, status (active/used/wasted), action_date
- estimated_weight_grams, estimated_cost_inr
- Built-in shelf life database with 60+ common foods
- Storage-based expiry adjustments (fridge, freezer, counter, pantry)

## Future Enhancements
- WhatsApp notifications for expiring items (Twilio)
- Email-based auth with WhatsApp number capture
- Push notifications (daily/weekly reminders)
- Manual item editing from inventory
- Barcode scanning for item identification
- Multi-household support with sharing
- Gamification: badges for waste reduction milestones
- Community leaderboard for waste reduction

---

## CHANGELOG

### Feb 2026 — Intent-Based Voice/Text Processing

**Feature: Voice/Text can now update existing inventory items**
- Updated Gemini extraction prompt to classify intent: `add` | `mark_used` | `mark_wasted`
- New `process_extracted_items()` shared function handles both add and update flows
- New `find_active_item_by_name()` with 3-tier fuzzy matching (exact → regex → reverse partial)
- Both `/api/process-voice` and `/api/process-text` now return `updated_items` + `not_found`
- Frontend result card shows separate green "Added N items" and grey "Updated N items" sections
- Not-found items shown in amber so user knows what wasn't matched
- **Testing**: 6/6 backend + 3/3 frontend tests passed ✅
