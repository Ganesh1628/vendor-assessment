from __future__ import annotations

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Float, Integer, DateTime, JSON, ForeignKey, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = BASE_DIR.parent / "assessment.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE.as_posix()}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
WAVE_SIZE = 3
MATCH_LIMIT = 5
WAVE_RESPONSE_WINDOW_MINUTES = 60
COLD_START_AVG_RATING = 4.0
COLD_START_RESPONSE_TIME_HOURS = 2.0
COLD_START_ACCEPTANCE_RATE = 0.65
ADMIN_STUCK_AFTER_MINUTES = 60
UNDERPERFORMING_ACCEPTANCE_RATE = 0.5


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")

    profile: Mapped[Optional["VendorProfile"]] = relationship(back_populates="vendor", uselist=False)
    performance: Mapped[Optional["VendorPerformance"]] = relationship(back_populates="vendor", uselist=False)
    invitations: Mapped[List["Invitation"]] = relationship(back_populates="vendor")
    matches: Mapped[List["Match"]] = relationship(back_populates="vendor")


class VendorProfile(Base):
    __tablename__ = "vendor_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False, unique=True)
    categories: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    service_areas: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    price_band: Mapped[str] = mapped_column(String(50), nullable=False)
    portfolio: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    vendor: Mapped[Vendor] = relationship(back_populates="profile")


class VendorPerformance(Base):
    __tablename__ = "vendor_performances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False, unique=True)
    avg_rating: Mapped[float] = mapped_column(Float, default=0.0)
    response_time: Mapped[float] = mapped_column(Float, default=0.0)
    acceptance_rate: Mapped[float] = mapped_column(Float, default=0.0)

    vendor: Mapped[Vendor] = relationship(back_populates="performance")


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    budget: Mapped[int] = mapped_column(Integer, nullable=False)
    guest_count: Mapped[int] = mapped_column(Integer, nullable=False)
    theme_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    matches: Mapped[List["Match"]] = relationship(back_populates="requirement")
    invitations: Mapped[List["Invitation"]] = relationship(back_populates="requirement")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id"), nullable=False)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    score_breakdown: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    requirement: Mapped[Requirement] = relationship(back_populates="matches")
    vendor: Mapped[Vendor] = relationship(back_populates="matches")


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id"), nullable=False)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    wave_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    quote_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    requirement: Mapped[Requirement] = relationship(back_populates="invitations")
    vendor: Mapped[Vendor] = relationship(back_populates="invitations")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id"), nullable=False)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    final_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


def ensure_schema_columns():
    with engine.begin() as connection:
        invitation_columns = {
            row[1] for row in connection.execute(text("PRAGMA table_info(invitations)")).fetchall()
        }
        if "expires_at" not in invitation_columns:
            connection.execute(text("ALTER TABLE invitations ADD COLUMN expires_at DATETIME"))


ensure_schema_columns()

app = FastAPI(title="AI-Powered Vendor Matching Engine")


@app.on_event("startup")
def startup_event():
    init_sample_data()


@app.get("/")
def serve_frontend():
    return FileResponse(BASE_DIR / "static" / "home.html")

@app.get("/match")
def serve_match_page():
    return FileResponse(BASE_DIR / "static" / "index.html")


class RequirementCreateRequest(BaseModel):
    category: str
    city: str
    budget: int
    guest_count: int
    theme_tags: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class InvitationCreateRequest(BaseModel):
    wave_number: int = 1


class NextWaveRequest(BaseModel):
    wave_number: int


class InvitationResponseRequest(BaseModel):
    status: str
    quote_amount: Optional[int] = None


class RequirementResponse(BaseModel):
    requirement_id: int
    matching_status: str = "queued"
    matches: List[dict]


class RecommendationResponse(BaseModel):
    requirement_id: int
    recommendations: List[dict]


class InvitationResponse(BaseModel):
    id: int
    status: str


class MatchResponse(BaseModel):
    requirement_id: int
    matches: List[dict]


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_sample_data():
    """Initialize the database with a richer sample vendor catalog for broader city coverage."""
    db = SessionLocal()
    try:
        existing_vendors = db.query(Vendor).count()
        if existing_vendors >= 40:
            return

        seed_data = [
            {"name": "Sree Wedding Decor", "city": "Chennai", "categories": ["wedding", "decor"], "service_areas": ["Chennai", "Coimbatore"], "price_band": "medium", "portfolio": "Traditional South Indian", "avg_rating": 4.8, "response_time": 1.2, "acceptance_rate": 0.86},
            {"name": "Royal Banquet Works", "city": "Chennai", "categories": ["wedding", "catering"], "service_areas": ["Chennai", "Madurai"], "price_band": "high", "portfolio": "Luxury wedding", "avg_rating": 4.7, "response_time": 1.5, "acceptance_rate": 0.78},
            {"name": "Pearl Events", "city": "Bangalore", "categories": ["wedding", "decor"], "service_areas": ["Bangalore", "Hyderabad"], "price_band": "medium", "portfolio": "Modern wedding setup", "avg_rating": 4.2, "response_time": 2.1, "acceptance_rate": 0.69},
            {"name": "Modern Wedding Co", "city": "Bangalore", "categories": ["modern", "wedding", "decor"], "service_areas": ["Bangalore", "Mysuru"], "price_band": "medium", "portfolio": "Contemporary designs", "avg_rating": 4.6, "response_time": 1.3, "acceptance_rate": 0.82},
            {"name": "Auro Photography Studio", "city": "Mumbai", "categories": ["photography", "wedding"], "service_areas": ["Mumbai", "Pune"], "price_band": "high", "portfolio": "Cinematic wedding photography", "avg_rating": 4.9, "response_time": 1.0, "acceptance_rate": 0.9},
            {"name": "Bloom & Glow Decor", "city": "Mumbai", "categories": ["decor", "floral"], "service_areas": ["Mumbai", "Delhi"], "price_band": "high", "portfolio": "Floral luxury styling", "avg_rating": 4.5, "response_time": 1.4, "acceptance_rate": 0.8},
            {"name": "Elite Event House", "city": "Delhi", "categories": ["wedding", "event_management"], "service_areas": ["Delhi", "Gurgaon"], "price_band": "high", "portfolio": "Premium destination events", "avg_rating": 4.7, "response_time": 1.3, "acceptance_rate": 0.84},
            {"name": "The Grand Atelier", "city": "Delhi", "categories": ["decor", "luxury"], "service_areas": ["Delhi", "Noida"], "price_band": "high", "portfolio": "Luxury themed decor", "avg_rating": 4.6, "response_time": 1.6, "acceptance_rate": 0.79},
            {"name": "Silk & Sage", "city": "Hyderabad", "categories": ["wedding", "decor"], "service_areas": ["Hyderabad", "Vizag"], "price_band": "medium", "portfolio": "Elegant traditional setup", "avg_rating": 4.4, "response_time": 1.7, "acceptance_rate": 0.74},
            {"name": "Nivasa Banquets", "city": "Hyderabad", "categories": ["catering", "wedding"], "service_areas": ["Hyderabad", "Warangal"], "price_band": "medium", "portfolio": "Large banquet services", "avg_rating": 4.3, "response_time": 2.0, "acceptance_rate": 0.72},
            {"name": "Tropic Festive Co", "city": "Kochi", "categories": ["wedding", "decor"], "service_areas": ["Kochi", "Trivandrum"], "price_band": "medium", "portfolio": "Coastal wedding decor", "avg_rating": 4.1, "response_time": 2.3, "acceptance_rate": 0.68},
            {"name": "Ocean Pearl Events", "city": "Kochi", "categories": ["photography", "wedding"], "service_areas": ["Kochi", "Alappuzha"], "price_band": "medium", "portfolio": "Beach wedding photography", "avg_rating": 4.2, "response_time": 1.9, "acceptance_rate": 0.71},
            {"name": "Mosaic Moments", "city": "Pune", "categories": ["decor", "event_management"], "service_areas": ["Pune", "Mumbai"], "price_band": "medium", "portfolio": "Modern event storytelling", "avg_rating": 4.5, "response_time": 1.5, "acceptance_rate": 0.77},
            {"name": "Urban Aura Events", "city": "Pune", "categories": ["wedding", "decor"], "service_areas": ["Pune", "Nashik"], "price_band": "medium", "portfolio": "Minimalist luxury decor", "avg_rating": 4.4, "response_time": 1.8, "acceptance_rate": 0.75},
            {"name": "Jaipur Royal Decor", "city": "Jaipur", "categories": ["wedding", "decor"], "service_areas": ["Jaipur", "Udaipur"], "price_band": "high", "portfolio": "Rajasthani heritage styling", "avg_rating": 4.8, "response_time": 1.1, "acceptance_rate": 0.85},
            {"name": "Desert Bloom Studio", "city": "Jaipur", "categories": ["floral", "decor"], "service_areas": ["Jaipur", "Jodhpur"], "price_band": "medium", "portfolio": "Desert floral installations", "avg_rating": 4.3, "response_time": 1.9, "acceptance_rate": 0.7},
            {"name": "Ahemdabad Event Lab", "city": "Ahmedabad", "categories": ["event_management", "decor"], "service_areas": ["Ahmedabad", "Surat"], "price_band": "medium", "portfolio": "Corporate and wedding planning", "avg_rating": 4.2, "response_time": 2.1, "acceptance_rate": 0.69},
            {"name": "Vibrant Vows", "city": "Ahmedabad", "categories": ["wedding", "photography"], "service_areas": ["Ahmedabad", "Vadodara"], "price_band": "medium", "portfolio": "Creative wedding coverage", "avg_rating": 4.4, "response_time": 1.6, "acceptance_rate": 0.73},
            {"name": "Festival Frame", "city": "Kolkata", "categories": ["decor", "wedding"], "service_areas": ["Kolkata", "Bhubaneswar"], "price_band": "low", "portfolio": "Classic festive setups", "avg_rating": 4.0, "response_time": 2.7, "acceptance_rate": 0.66},
            {"name": "The Wedding Lane", "city": "Kolkata", "categories": ["wedding", "catering"], "service_areas": ["Kolkata", "Durgapur"], "price_band": "medium", "portfolio": "Budget-friendly banquet planning", "avg_rating": 4.1, "response_time": 2.4, "acceptance_rate": 0.67},
            {"name": "Noble Moments", "city": "Chandigarh", "categories": ["decor", "wedding"], "service_areas": ["Chandigarh", "Mohali"], "price_band": "medium", "portfolio": "Elegant modern decor", "avg_rating": 4.3, "response_time": 1.8, "acceptance_rate": 0.74},
            {"name": "Bluebell Events", "city": "Chandigarh", "categories": ["event_management", "photography"], "service_areas": ["Chandigarh", "Ludhiana"], "price_band": "medium", "portfolio": "Full-service event coordination", "avg_rating": 4.5, "response_time": 1.4, "acceptance_rate": 0.78},
            {"name": "Horizon Banquets", "city": "Lucknow", "categories": ["catering", "wedding"], "service_areas": ["Lucknow", "Kanpur"], "price_band": "medium", "portfolio": "Royal banquet experience", "avg_rating": 4.2, "response_time": 2.0, "acceptance_rate": 0.7},
            {"name": "Golden Thread Decor", "city": "Lucknow", "categories": ["decor", "luxury"], "service_areas": ["Lucknow", "Agra"], "price_band": "high", "portfolio": "Luxury floral arrangements", "avg_rating": 4.6, "response_time": 1.3, "acceptance_rate": 0.81},
            {"name": "Cedar & Co", "city": "Bhopal", "categories": ["event_management", "decor"], "service_areas": ["Bhopal", "Indore"], "price_band": "low", "portfolio": "Budget-friendly event styling", "avg_rating": 4.0, "response_time": 2.6, "acceptance_rate": 0.64},
            {"name": "Madhav Events", "city": "Bhopal", "categories": ["wedding", "catering"], "service_areas": ["Bhopal", "Jabalpur"], "price_band": "medium", "portfolio": "Local wedding catering", "avg_rating": 4.1, "response_time": 2.4, "acceptance_rate": 0.67},
            {"name": "Glamour Grove", "city": "Indore", "categories": ["decor", "wedding"], "service_areas": ["Indore", "Ujjain"], "price_band": "medium", "portfolio": "Premium decor curation", "avg_rating": 4.4, "response_time": 1.7, "acceptance_rate": 0.73},
            {"name": "Studio 27 Photography", "city": "Indore", "categories": ["photography", "wedding"], "service_areas": ["Indore", "Bhopal"], "price_band": "medium", "portfolio": "Natural wedding photography", "avg_rating": 4.5, "response_time": 1.5, "acceptance_rate": 0.76},
            {"name": "The Celebration Desk", "city": "Nagpur", "categories": ["event_management", "wedding"], "service_areas": ["Nagpur", "Amravati"], "price_band": "low", "portfolio": "Complete event planning", "avg_rating": 4.0, "response_time": 2.8, "acceptance_rate": 0.62},
            {"name": "Vivid Moments", "city": "Nagpur", "categories": ["decor", "floral"], "service_areas": ["Nagpur", "Wardha"], "price_band": "medium", "portfolio": "Creative bridal decor", "avg_rating": 4.2, "response_time": 2.1, "acceptance_rate": 0.69},
            {"name": "Silver Leaf Events", "city": "Surat", "categories": ["event_management", "decor"], "service_areas": ["Surat", "Rajkot"], "price_band": "medium", "portfolio": "High-energy festive events", "avg_rating": 4.3, "response_time": 1.9, "acceptance_rate": 0.71},
            {"name": "Navy & Ivory", "city": "Surat", "categories": ["decor", "wedding"], "service_areas": ["Surat", "Vadodara"], "price_band": "medium", "portfolio": "Elegant minimal decor", "avg_rating": 4.4, "response_time": 1.6, "acceptance_rate": 0.73},
            {"name": "Canvas & Candles", "city": "Goa", "categories": ["decor", "photography"], "service_areas": ["Goa", "Panjim"], "price_band": "high", "portfolio": "Beachside luxury weddings", "avg_rating": 4.7, "response_time": 1.2, "acceptance_rate": 0.83},
            {"name": "Sunset Soirée", "city": "Goa", "categories": ["event_management", "wedding"], "service_areas": ["Goa", "Margao"], "price_band": "high", "portfolio": "Destination wedding planner", "avg_rating": 4.6, "response_time": 1.4, "acceptance_rate": 0.8},
            {"name": "The Event Orchard", "city": "Bengaluru", "categories": ["event_management", "decor"], "service_areas": ["Bengaluru", "Mysuru"], "price_band": "medium", "portfolio": "Premium city event planning", "avg_rating": 4.5, "response_time": 1.5, "acceptance_rate": 0.76},
            {"name": "Luxe Legacy Studios", "city": "Bengaluru", "categories": ["photography", "wedding"], "service_areas": ["Bengaluru", "Coorg"], "price_band": "high", "portfolio": "Editorial wedding photography", "avg_rating": 4.8, "response_time": 1.1, "acceptance_rate": 0.87},
        ]

        for seed in seed_data:
            existing = db.query(Vendor).filter(Vendor.name == seed["name"]).first()
            if existing:
                continue

            vendor = Vendor(name=seed["name"], city=seed["city"], status="active")
            db.add(vendor)
            db.flush()

            profile = VendorProfile(
                vendor_id=vendor.id,
                categories=seed["categories"],
                service_areas=seed["service_areas"],
                price_band=seed["price_band"],
                portfolio=seed["portfolio"],
            )
            db.add(profile)

            perf = VendorPerformance(
                vendor_id=vendor.id,
                avg_rating=seed["avg_rating"],
                response_time=seed["response_time"],
                acceptance_rate=seed["acceptance_rate"],
            )
            db.add(perf)

        db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def parse_theme_from_text(description: str) -> list[str]:
    # Production can replace this stub with an LLM call to OpenAI, Anthropic, or another parser.
    keywords = {
        "traditional": ["traditional", "classic", "heritage"],
        "south indian": ["south indian", "temple", "mandap"],
        "modern": ["modern", "contemporary", "minimal"],
        "floral": ["floral", "flower", "flowers"],
        "lighting": ["lighting", "lights", "ambient"],
        "luxury": ["luxury", "premium", "royal"],
    }
    text_value = description.lower()
    return [
        theme
        for theme, terms in keywords.items()
        if any(term in text_value for term in terms)
    ]


def get_current_wave_cutoff(reference_time: Optional[datetime] = None) -> datetime:
    return (reference_time or datetime.utcnow()) - timedelta(minutes=WAVE_RESPONSE_WINDOW_MINUTES)


def get_invited_vendor_ids(db: Session, requirement_id: int) -> set[int]:
    invited_vendor_ids = db.query(Invitation.vendor_id).filter(
        Invitation.requirement_id == requirement_id
    ).distinct().all()
    return {row[0] for row in invited_vendor_ids}


def invite_matches_for_wave(
    db: Session,
    requirement_id: int,
    wave_number: int,
    matches: list[Match],
) -> list[dict]:
    invited_vendor_ids = get_invited_vendor_ids(db, requirement_id)
    available_matches = [match for match in matches if match.vendor_id not in invited_vendor_ids]

    invitations = []
    for match in available_matches[:WAVE_SIZE]:
        expires_at = datetime.utcnow() + timedelta(minutes=WAVE_RESPONSE_WINDOW_MINUTES)
        invitation = Invitation(
            requirement_id=requirement_id,
            vendor_id=match.vendor_id,
            wave_number=wave_number,
            status="pending",
            expires_at=expires_at,
        )
        db.add(invitation)
        db.commit()
        db.refresh(invitation)
        invitations.append(
            {
                "id": invitation.id,
                "vendor_id": invitation.vendor_id,
                "status": invitation.status,
                "wave_number": invitation.wave_number,
                "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else None,
            }
        )
    return invitations


def diversity_key(requirement: Requirement, vendor: Vendor) -> tuple[str, str]:
    profile = vendor.profile
    if not profile:
        return ("unknown", "unknown")

    categories = [item.lower() for item in profile.categories]
    requirement_category = requirement.category.lower()
    sub_category = next((item for item in categories if item != requirement_category), categories[0] if categories else "unknown")
    return (sub_category, profile.price_band.lower())


def apply_diversity_pass(
    requirement: Requirement,
    ranked_matches: list[tuple[Vendor, dict]],
    limit: int = MATCH_LIMIT,
    max_per_group: int = 2,
) -> list[tuple[Vendor, dict]]:
    selected: list[tuple[Vendor, dict]] = []
    overflow: list[tuple[Vendor, dict]] = []
    group_counts: dict[tuple[str, str], int] = {}

    for vendor, result in ranked_matches:
        key = diversity_key(requirement, vendor)
        if group_counts.get(key, 0) < max_per_group:
            selected.append((vendor, result))
            group_counts[key] = group_counts.get(key, 0) + 1
        else:
            overflow.append((vendor, result))

    if len(selected) < limit:
        selected.extend(overflow[: limit - len(selected)])

    return selected[:limit]


def serialize_match(db: Session, match: Match) -> dict:
    vendor = db.get(Vendor, match.vendor_id)
    return {
        "vendor_id": match.vendor_id,
        "vendor_name": vendor.name if vendor else "Unknown vendor",
        "score": match.score,
        "match_reason": match.score_breakdown.get("reason", "matched"),
        "score_breakdown": match.score_breakdown,
    }


def generate_matches_for_requirement(requirement_id: int) -> None:
    """Run matching outside the request path; Celery could enqueue this in production."""
    db = SessionLocal()
    try:
        requirement = db.get(Requirement, requirement_id)
        if not requirement:
            return

        db.query(Match).filter(Match.requirement_id == requirement_id).delete()
        vendors = db.query(Vendor).all()
        scored = []
        for vendor in vendors:
            if vendor.status != "active":
                continue
            if vendor.city and vendor.city.lower() != requirement.city.lower():
                continue
            result = score_vendor(requirement, vendor)
            scored.append((vendor, result))

        scored.sort(key=lambda item: item[1]["score"], reverse=True)
        top_matches = apply_diversity_pass(requirement, scored)

        for vendor, result in top_matches:
            match = Match(
                requirement_id=requirement.id,
                vendor_id=vendor.id,
                score=result["score"],
                score_breakdown=result["breakdown"],
            )
            db.add(match)
        db.commit()
    finally:
        db.close()


def score_vendor(requirement: Requirement, vendor: Vendor) -> dict:
    profile = vendor.profile
    performance = vendor.performance
    if not profile:
        return {"score": 0.0, "breakdown": {"reason": "missing-profile"}}

    cold_start = not performance or performance.avg_rating <= 0
    avg_rating = COLD_START_AVG_RATING if cold_start else performance.avg_rating
    response_time = COLD_START_RESPONSE_TIME_HOURS if cold_start else performance.response_time
    acceptance_rate = COLD_START_ACCEPTANCE_RATE if cold_start else performance.acceptance_rate

    budget_fit_score = 0.0
    if requirement.budget <= 100000:
        budget_fit_score = 0.9 if profile.price_band == "low" else 0.7 if profile.price_band == "medium" else 0.5
    elif requirement.budget <= 200000:
        budget_fit_score = 0.7 if profile.price_band == "medium" else 0.85 if profile.price_band == "high" else 0.6
    else:
        budget_fit_score = 0.8 if profile.price_band == "high" else 0.6

    performance_score = (avg_rating / 5.0) * 0.6 + (1.0 - min(response_time / 5.0, 1.0)) * 0.2 + acceptance_rate * 0.2

    theme_hits = [tag for tag in requirement.theme_tags if tag.lower() in [item.lower() for item in profile.categories]]
    capability_score = 0.0
    if theme_hits:
        capability_score += 0.6
    if any(area.lower() == requirement.city.lower() for area in profile.service_areas):
        capability_score += 0.4

    experience_score = 0.9 if "decor" in [item.lower() for item in profile.categories] else 0.6
    availability_score = 0.8 if acceptance_rate > 0.75 else 0.6
    platform_score = 0.75 if acceptance_rate > 0.8 else 0.6

    total = (
        budget_fit_score * 0.25
        + performance_score * 0.25
        + capability_score * 0.20
        + experience_score * 0.10
        + availability_score * 0.10
        + platform_score * 0.10
    )

    reasons = []
    if theme_hits:
        reasons.append(f"strong theme alignment for {', '.join(theme_hits)}")
    if any(area.lower() == requirement.city.lower() for area in profile.service_areas):
        reasons.append("operates in the requested city")
    if avg_rating >= 4.5:
        reasons.append("high customer rating")
    if profile.price_band == "medium" and requirement.budget <= 200000:
        reasons.append("budget-friendly fit")
    if cold_start:
        reasons.append("uses baseline quality score while ratings build up")

    breakdown = {
        "budget_fit": round(budget_fit_score, 3),
        "performance": round(performance_score, 3),
        "capability": round(capability_score, 3),
        "experience": round(experience_score, 3),
        "availability": round(availability_score, 3),
        "platform_intelligence": round(platform_score, 3),
        "cold_start": cold_start,
        "reason": " | ".join(reasons) if reasons else "matches core filters",
    }
    return {"score": round(total, 3), "breakdown": breakdown}


@app.post("/api/requirements/", response_model=RequirementResponse)
def create_requirement(payload: RequirementCreateRequest, background_tasks: BackgroundTasks):
    db = SessionLocal()
    try:
        requirement = Requirement(
            category=payload.category,
            city=payload.city,
            budget=payload.budget,
            guest_count=payload.guest_count,
            theme_tags=list(dict.fromkeys(payload.theme_tags + parse_theme_from_text(payload.description or ""))),
            description=payload.description,
        )
        db.add(requirement)
        db.commit()
        db.refresh(requirement)

        background_tasks.add_task(generate_matches_for_requirement, requirement.id)

        return RequirementResponse(
            requirement_id=requirement.id,
            matching_status="queued",
            matches=[],
        )
    finally:
        db.close()


@app.get("/api/requirements/{requirement_id}/matches/", response_model=MatchResponse)
def get_matches(requirement_id: int):
    db = SessionLocal()
    try:
        requirement = db.get(Requirement, requirement_id)
        if not requirement:
            raise HTTPException(status_code=404, detail="Requirement not found")
        matches = db.query(Match).filter(Match.requirement_id == requirement_id).order_by(Match.score.desc()).all()
        return MatchResponse(
            requirement_id=requirement_id,
            matches=[serialize_match(db, item) for item in matches],
        )
    finally:
        db.close()


@app.post("/api/requirements/{requirement_id}/invite/", response_model=dict)
def invite_vendors(requirement_id: int, request: InvitationCreateRequest):
    db = SessionLocal()
    try:
        requirement = db.get(Requirement, requirement_id)
        if not requirement:
            raise HTTPException(status_code=404, detail="Requirement not found")
        matches = db.query(Match).filter(Match.requirement_id == requirement_id).order_by(Match.score.desc()).all()
        invitations = invite_matches_for_wave(db, requirement_id, request.wave_number, matches)
        return {"requirement_id": requirement_id, "wave_number": request.wave_number, "invitations": invitations}
    finally:
        db.close()


@app.post("/api/requirements/{requirement_id}/invite-next-wave/", response_model=dict)
def invite_next_wave(requirement_id: int, request: NextWaveRequest):
    """Trigger the next wave of invitations for a requirement.
    
    Invites the next 3 vendors (by rank) in the specified wave number.
    Only invites vendors not yet invited in any previous wave.
    """
    db = SessionLocal()
    try:
        requirement = db.get(Requirement, requirement_id)
        if not requirement:
            raise HTTPException(status_code=404, detail="Requirement not found")
        
        matches = db.query(Match).filter(Match.requirement_id == requirement_id).order_by(Match.score.desc()).all()
        invitations = invite_matches_for_wave(db, requirement_id, request.wave_number, matches)
        return {"requirement_id": requirement_id, "wave_number": request.wave_number, "invitations": invitations}
    finally:
        db.close()


@app.post("/api/invitations/{invitation_id}/respond/", response_model=InvitationResponse)
def respond_to_invitation(invitation_id: int, request: InvitationResponseRequest):
    db = SessionLocal()
    try:
        invitation = db.get(Invitation, invitation_id)
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")
        invitation.status = request.status
        invitation.quote_amount = request.quote_amount
        db.commit()
        db.refresh(invitation)
        return InvitationResponse(id=invitation.id, status=invitation.status)
    finally:
        db.close()


@app.get("/api/requirements/{requirement_id}/recommendations/", response_model=RecommendationResponse)
def get_recommendations(requirement_id: int):
    db = SessionLocal()
    try:
        requirement = db.get(Requirement, requirement_id)
        if not requirement:
            raise HTTPException(status_code=404, detail="Requirement not found")
        invitations = db.query(Invitation).filter(Invitation.requirement_id == requirement_id).all()
        recommendations = []
        for invitation in invitations:
            vendor = db.get(Vendor, invitation.vendor_id)
            if invitation.status == "accepted":
                recommendations.append({
                    "vendor_id": vendor.id,
                    "vendor_name": vendor.name,
                    "status": invitation.status,
                    "quote_amount": invitation.quote_amount,
                })
        return RecommendationResponse(requirement_id=requirement_id, recommendations=recommendations)
    finally:
        db.close()


@app.get("/admin/operational", response_model=dict)
def admin_operational():
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=ADMIN_STUCK_AFTER_MINUTES)
        old_requirements = db.query(Requirement).filter(Requirement.created_at <= cutoff).all()
        stuck_requirements = []
        for requirement in old_requirements:
            matches_count = db.query(Match).filter(Match.requirement_id == requirement.id).count()
            response_count = db.query(Invitation).filter(
                Invitation.requirement_id == requirement.id,
                Invitation.status.in_(["accepted", "declined"]),
            ).count()
            if matches_count == 0 or response_count == 0:
                stuck_requirements.append(
                    {
                        "requirement_id": requirement.id,
                        "city": requirement.city,
                        "category": requirement.category,
                        "created_at": requirement.created_at.isoformat(),
                        "matches_count": matches_count,
                        "response_count": response_count,
                    }
                )

        underperforming_vendors = []
        performances = db.query(VendorPerformance).filter(
            VendorPerformance.acceptance_rate < UNDERPERFORMING_ACCEPTANCE_RATE
        ).all()
        for performance in performances:
            vendor = db.get(Vendor, performance.vendor_id)
            underperforming_vendors.append(
                {
                    "vendor_id": performance.vendor_id,
                    "vendor_name": vendor.name if vendor else "Unknown vendor",
                    "acceptance_rate": performance.acceptance_rate,
                }
            )

        return {
            "stuck_after_minutes": ADMIN_STUCK_AFTER_MINUTES,
            "stuck_requirements": stuck_requirements,
            "underperforming_vendors": underperforming_vendors,
        }
    finally:
        db.close()


@app.get("/admin/model-health", response_model=dict)
def admin_model_health():
    db = SessionLocal()
    try:
        matches = db.query(Match).order_by(Match.created_at.desc()).limit(25).all()
        score_breakdowns = []
        component_totals: dict[str, float] = {}
        component_counts: dict[str, int] = {}

        for match in matches:
            vendor = db.get(Vendor, match.vendor_id)
            score_breakdowns.append(
                {
                    "match_id": match.id,
                    "requirement_id": match.requirement_id,
                    "vendor_id": match.vendor_id,
                    "vendor_name": vendor.name if vendor else "Unknown vendor",
                    "score": match.score,
                    "score_breakdown": match.score_breakdown,
                }
            )
            for key, value in match.score_breakdown.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    component_totals[key] = component_totals.get(key, 0.0) + float(value)
                    component_counts[key] = component_counts.get(key, 0) + 1

        averages = {
            key: round(component_totals[key] / component_counts[key], 3)
            for key in component_totals
        }
        return {
            "recent_match_count": len(matches),
            "average_score_breakdown": averages,
            "score_breakdowns": score_breakdowns,
        }
    finally:
        db.close()
