from fastapi.testclient import TestClient
from app.main import app, Base, engine, SessionLocal

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        from app.main import Vendor, VendorProfile, VendorPerformance

        vendors = [
            Vendor(name="Sree Wedding Decor", city="Chennai", status="active"),
            Vendor(name="Royal Banquet Works", city="Chennai", status="active"),
            Vendor(name="Pearl Events", city="Bangalore", status="active"),
        ]
        db.add_all(vendors)
        db.flush()

        profiles = [
            VendorProfile(vendor_id=vendors[0].id, categories=["wedding", "decor"], service_areas=["Chennai"], price_band="medium", portfolio="Traditional South Indian"),
            VendorProfile(vendor_id=vendors[1].id, categories=["wedding", "decor"], service_areas=["Chennai"], price_band="high", portfolio="Luxury wedding decor"),
            VendorProfile(vendor_id=vendors[2].id, categories=["wedding", "catering"], service_areas=["Bangalore"], price_band="medium", portfolio="Modern wedding setup"),
        ]
        performances = [
            VendorPerformance(vendor_id=vendors[0].id, avg_rating=4.8, response_time=1.2, acceptance_rate=0.86),
            VendorPerformance(vendor_id=vendors[1].id, avg_rating=4.7, response_time=1.5, acceptance_rate=0.78),
            VendorPerformance(vendor_id=vendors[2].id, avg_rating=4.2, response_time=2.1, acceptance_rate=0.69),
        ]
        db.add_all(profiles)
        db.add_all(performances)
        db.commit()


def test_requirement_creation_generates_matches():
    response = client.post(
        "/api/requirements/",
        json={
            "category": "wedding",
            "city": "Chennai",
            "budget": 150000,
            "guest_count": 500,
            "theme_tags": ["traditional", "south indian", "wedding"],
            "description": "Traditional South Indian wedding decor for 500 guests"
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requirement_id"] is not None
    assert len(body["matches"]) >= 1
    assert body["matches"][0]["vendor_name"] == "Sree Wedding Decor"


def test_recommendations_and_response_flow():
    create_response = client.post(
        "/api/requirements/",
        json={
            "category": "wedding",
            "city": "Chennai",
            "budget": 150000,
            "guest_count": 500,
            "theme_tags": ["traditional", "south indian", "wedding"],
            "description": "Traditional South Indian wedding decor for 500 guests"
        },
    )
    requirement_id = create_response.json()["requirement_id"]

    matches_response = client.get(f"/api/requirements/{requirement_id}/matches/")
    assert matches_response.status_code == 200
    assert len(matches_response.json()["matches"]) >= 1

    invite_response = client.post(f"/api/requirements/{requirement_id}/invite/", json={"wave_number": 1})
    assert invite_response.status_code == 200

    invitation_id = invite_response.json()["invitations"][0]["id"]
    respond_response = client.post(f"/api/invitations/{invitation_id}/respond/", json={"status": "accepted", "quote_amount": 140000})
    assert respond_response.status_code == 200

    rec_response = client.get(f"/api/requirements/{requirement_id}/recommendations/")
    assert rec_response.status_code == 200
    assert len(rec_response.json()["recommendations"]) >= 1
