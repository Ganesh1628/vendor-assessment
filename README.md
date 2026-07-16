# AI-Powered Vendor Matching Engine

This project implements a simplified but presentation-ready version of the assessment design using FastAPI, SQLAlchemy, and a lightweight frontend.

## What is included

- Requirement creation API
- Rule-based vendor matching with weighted scoring
- Async-style matching via FastAPI `BackgroundTasks`
- Diversity pass to reduce near-identical top results
- Cold-start baseline scoring for vendors without ratings
- Wave-based vendor invitations with expiry timestamps
- Explainable match reasons for each vendor
- Vendor invitation flow
- Recommendation listing after vendor responses
- Operational and model-health admin endpoints
- Keyword-based theme parsing stub for future LLM integration
- Simple browser-based UI for demoing the experience
- Basic SQLite database schema for the core entities

## Core files

- [app/main.py](app/main.py) - FastAPI app, models, matching logic, and endpoints
- [tests/test_main.py](tests/test_main.py) - End-to-end tests for creation, matching, invitation, and recommendation flow
- [requirements.txt](requirements.txt) - Python dependencies

## Run locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start the app:
   ```bash
   uvicorn app.main:app --reload
   ```

3. Open the browser at:
   ```text
   http://127.0.0.1:8000/
   ```

4. Run tests:
   ```bash
   pytest -q
   ```

## Main API endpoints

- POST /api/requirements/ - create a requirement and queue background matching
- GET /api/requirements/{id}/matches/ - view ranked matches
- POST /api/requirements/{id}/invite/ - invite the first wave of top vendors
- POST /api/requirements/{id}/invite-next-wave/ - invite the next wave of vendors
- POST /api/invitations/{id}/respond/ - accept or decline an invitation
- GET /api/requirements/{id}/recommendations/ - show accepted recommendations
- GET /admin/operational - show stuck requirements and underperforming vendors
- GET /admin/model-health - show recent score breakdowns and averages

## Sample input

Use this payload for `POST /api/requirements/`:

```json
{
  "category": "wedding",
  "city": "Chennai",
  "budget": 150000,
  "guest_count": 500,
  "theme_tags": ["traditional", "south indian", "wedding"],
  "description": "Traditional South Indian wedding decor for 500 guests with floral lighting"
}
```

The create response returns immediately with `matching_status: "queued"`. Then call:

```text
GET /api/requirements/{id}/matches/
```

Invitations are sent in waves of 3 vendors. Each invitation includes `wave_number` and `expires_at` so the vendor-facing view can show a countdown.
