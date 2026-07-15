# AI-Powered Vendor Matching Engine

This project implements a simplified but presentation-ready version of the assessment design using FastAPI, SQLAlchemy, and a lightweight frontend.

## What is included

- Requirement creation API
- Rule-based vendor matching with weighted scoring
- Explainable match reasons for each vendor
- Vendor invitation flow
- Recommendation listing after vendor responses
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

- POST /api/requirements/ - create a requirement and generate matches
- GET /api/requirements/{id}/matches/ - view ranked matches
- POST /api/requirements/{id}/invite/ - invite top vendors
- POST /api/invitations/{id}/respond/ - accept or decline an invitation
- GET /api/requirements/{id}/recommendations/ - show accepted recommendations
