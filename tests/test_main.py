from datetime import datetime, timedelta

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
            Vendor(name="Elegant Decor Studio", city="Chennai", status="active"),
            Vendor(name="Classic Mandap Co", city="Chennai", status="active"),
            Vendor(name="Heritage Celebrations", city="Chennai", status="active"),
            Vendor(name="Floral Frame Studio", city="Chennai", status="active"),
            Vendor(name="Feast Makers", city="Chennai", status="active"),
        ]
        db.add_all(vendors)
        db.flush()

        profiles = [
            VendorProfile(vendor_id=vendors[0].id, categories=["wedding", "decor"], service_areas=["Chennai"], price_band="medium", portfolio="Traditional South Indian"),
            VendorProfile(vendor_id=vendors[1].id, categories=["wedding", "decor"], service_areas=["Chennai"], price_band="high", portfolio="Luxury wedding decor"),
            VendorProfile(vendor_id=vendors[2].id, categories=["wedding", "catering"], service_areas=["Bangalore"], price_band="medium", portfolio="Modern wedding setup"),
            VendorProfile(vendor_id=vendors[3].id, categories=["wedding", "decor"], service_areas=["Chennai"], price_band="medium", portfolio="Elegant floral styling"),
            VendorProfile(vendor_id=vendors[4].id, categories=["wedding", "decor"], service_areas=["Chennai"], price_band="medium", portfolio="Classic mandap builds"),
            VendorProfile(vendor_id=vendors[5].id, categories=["wedding", "decor"], service_areas=["Chennai"], price_band="medium", portfolio="Heritage-inspired decor"),
            VendorProfile(vendor_id=vendors[6].id, categories=["wedding", "floral"], service_areas=["Chennai"], price_band="medium", portfolio="Fresh floral installs"),
            VendorProfile(vendor_id=vendors[7].id, categories=["wedding", "catering"], service_areas=["Chennai"], price_band="medium", portfolio="Banquet service"),
        ]
        performances = [
            VendorPerformance(vendor_id=vendors[0].id, avg_rating=4.8, response_time=1.2, acceptance_rate=0.86),
            VendorPerformance(vendor_id=vendors[1].id, avg_rating=4.7, response_time=1.5, acceptance_rate=0.78),
            VendorPerformance(vendor_id=vendors[2].id, avg_rating=4.2, response_time=2.1, acceptance_rate=0.69),
            VendorPerformance(vendor_id=vendors[3].id, avg_rating=4.6, response_time=1.1, acceptance_rate=0.82),
            VendorPerformance(vendor_id=vendors[4].id, avg_rating=4.5, response_time=1.3, acceptance_rate=0.8),
            VendorPerformance(vendor_id=vendors[5].id, avg_rating=4.4, response_time=1.4, acceptance_rate=0.77),
            VendorPerformance(vendor_id=vendors[6].id, avg_rating=4.3, response_time=1.2, acceptance_rate=0.75),
            VendorPerformance(vendor_id=vendors[7].id, avg_rating=4.1, response_time=1.6, acceptance_rate=0.72),
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
    assert body["matching_status"] == "queued"
    assert body["matches"] == []

    matches_response = client.get(f"/api/requirements/{body['requirement_id']}/matches/")
    assert matches_response.status_code == 200
    matches = matches_response.json()["matches"]
    assert len(matches) >= 1
    assert any(match["vendor_name"] == "Sree Wedding Decor" for match in matches)


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


def test_wave_based_invitations():
    """Test that wave-based invitations only invite vendors not previously invited."""
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

    wave1_response = client.post(
        f"/api/requirements/{requirement_id}/invite/",
        json={"wave_number": 1}
    )
    assert wave1_response.status_code == 200
    wave1_invitations = wave1_response.json()["invitations"]
    assert len(wave1_invitations) <= 3
    assert wave1_response.json()["wave_number"] == 1
    assert datetime.fromisoformat(wave1_invitations[0]["expires_at"]) > datetime.utcnow()

    wave2_response = client.post(
        f"/api/requirements/{requirement_id}/invite-next-wave/",
        json={"wave_number": 2}
    )
    assert wave2_response.status_code == 200
    wave2_invitations = wave2_response.json()["invitations"]
    assert wave2_response.json()["wave_number"] == 2
    
    wave1_vendor_ids = {inv["vendor_id"] for inv in wave1_invitations}
    wave2_vendor_ids = {inv["vendor_id"] for inv in wave2_invitations}
    
    assert len(wave1_vendor_ids.intersection(wave2_vendor_ids)) == 0, "Wave 2 should not invite vendors from Wave 1"


def test_diversity_pass_limits_near_duplicates():
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
    matches_response = client.get(f"/api/requirements/{response.json()['requirement_id']}/matches/")
    assert matches_response.status_code == 200
    duplicate_group_names = {
        "Sree Wedding Decor",
        "Elegant Decor Studio",
        "Classic Mandap Co",
        "Heritage Celebrations",
    }
    duplicate_group_count = sum(
        1 for match in matches_response.json()["matches"] if match["vendor_name"] in duplicate_group_names
    )
    assert duplicate_group_count <= 2


def test_cold_start_vendor_uses_baseline_quality_score():
    with SessionLocal() as db:
        from app.main import Requirement, Vendor, VendorProfile, score_vendor

        vendor = Vendor(name="New Decor Collective", city="Chennai", status="active")
        db.add(vendor)
        db.flush()
        db.add(
            VendorProfile(
                vendor_id=vendor.id,
                categories=["wedding", "lighting"],
                service_areas=["Chennai"],
                price_band="medium",
                portfolio="New launch wedding lighting",
            )
        )
        requirement = Requirement(
            category="wedding",
            city="Chennai",
            budget=150000,
            guest_count=500,
            theme_tags=["lighting", "wedding"],
            description="Wedding lighting and decor for 500 guests",
        )
        db.add(requirement)
        db.commit()
        db.refresh(vendor)
        db.refresh(requirement)

        result = score_vendor(requirement, vendor)

    assert result["score"] > 0
    assert result["breakdown"]["cold_start"] is True


def test_admin_operational_view_flags_stuck_requirements_and_low_acceptance_vendors():
    with SessionLocal() as db:
        from app.main import Requirement, Vendor, VendorPerformance

        stuck_requirement = Requirement(
            category="wedding",
            city="Chennai",
            budget=150000,
            guest_count=500,
            theme_tags=["wedding"],
            description="Old requirement with no progress",
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        low_vendor = Vendor(name="Slow Response Events", city="Chennai", status="active")
        db.add_all([stuck_requirement, low_vendor])
        db.flush()
        db.add(VendorPerformance(vendor_id=low_vendor.id, avg_rating=3.8, response_time=4.0, acceptance_rate=0.2))
        stuck_requirement_id = stuck_requirement.id
        db.commit()

    response = client.get("/admin/operational")

    assert response.status_code == 200
    body = response.json()
    assert any(item["requirement_id"] == stuck_requirement_id for item in body["stuck_requirements"])
    assert any(item["vendor_name"] == "Slow Response Events" for item in body["underperforming_vendors"])


def test_admin_model_health_view_shows_recent_score_breakdowns():
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
    assert len(matches_response.json()["matches"]) > 0

    response = client.get("/admin/model-health")

    assert response.status_code == 200
    body = response.json()
    assert body["recent_match_count"] > 0
    assert "budget_fit" in body["average_score_breakdown"]
    assert len(body["score_breakdowns"]) > 0


def test_parse_theme_from_text_extracts_keyword_tags():
    from app.main import parse_theme_from_text

    tags = parse_theme_from_text("Traditional South Indian mandap with floral lighting")

    assert "traditional" in tags
    assert "south indian" in tags
    assert "floral" in tags
    assert "lighting" in tags

