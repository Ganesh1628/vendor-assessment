from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Float, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session, sessionmaker

DATABASE_URL = "sqlite:///./assessment.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


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

app = FastAPI(title="AI-Powered Vendor Matching Engine")


@app.on_event("startup")
def startup_event():
    init_sample_data()


@app.get("/")
def serve_frontend():
    return FileResponse("app/static/index.html")


class RequirementCreateRequest(BaseModel):
    category: str
    city: str
    budget: int
    guest_count: int
    theme_tags: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class InvitationCreateRequest(BaseModel):
    wave_number: int = 1


class InvitationResponseRequest(BaseModel):
    status: str
    quote_amount: Optional[int] = None


class RequirementResponse(BaseModel):
    requirement_id: int
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
    """Initialize the database with sample vendors if empty."""
    db = SessionLocal()
    try:
        existing_vendors = db.query(Vendor).count()
        if existing_vendors > 0:
            return
        
        vendors_data = [
            {"name": "Sree Wedding Decor", "city": "Chennai"},
            {"name": "Royal Banquet Works", "city": "Chennai"},
            {"name": "Pearl Events", "city": "Bangalore"},
            {"name": "Modern Wedding Co", "city": "Bangalore"},
        ]
        
        for vendor_data in vendors_data:
            vendor = Vendor(name=vendor_data["name"], city=vendor_data["city"], status="active")
            db.add(vendor)
        db.flush()
        
        profiles_data = [
            {"vendor_name": "Sree Wedding Decor", "categories": ["wedding", "decor"], "service_areas": ["Chennai"], "price_band": "medium", "portfolio": "Traditional South Indian"},
            {"vendor_name": "Royal Banquet Works", "categories": ["wedding", "catering"], "service_areas": ["Chennai"], "price_band": "high", "portfolio": "Luxury wedding"},
            {"vendor_name": "Pearl Events", "categories": ["wedding", "decor"], "service_areas": ["Bangalore"], "price_band": "medium", "portfolio": "Modern wedding setup"},
            {"vendor_name": "Modern Wedding Co", "categories": ["modern", "wedding", "decor"], "service_areas": ["Bangalore"], "price_band": "medium", "portfolio": "Contemporary designs"},
        ]
        
        performance_data = [
            {"vendor_name": "Sree Wedding Decor", "avg_rating": 4.8, "response_time": 1.2, "acceptance_rate": 0.86},
            {"vendor_name": "Royal Banquet Works", "avg_rating": 4.7, "response_time": 1.5, "acceptance_rate": 0.78},
            {"vendor_name": "Pearl Events", "avg_rating": 4.2, "response_time": 2.1, "acceptance_rate": 0.69},
            {"vendor_name": "Modern Wedding Co", "avg_rating": 4.6, "response_time": 1.3, "acceptance_rate": 0.82},
        ]
        
        all_vendors = db.query(Vendor).all()
        
        for profile_data in profiles_data:
            vendor = next(v for v in all_vendors if v.name == profile_data["vendor_name"])
            profile = VendorProfile(
                vendor_id=vendor.id,
                categories=profile_data["categories"],
                service_areas=profile_data["service_areas"],
                price_band=profile_data["price_band"],
                portfolio=profile_data["portfolio"],
            )
            db.add(profile)
        db.flush()
        
        for perf_data in performance_data:
            vendor = next(v for v in all_vendors if v.name == perf_data["vendor_name"])
            perf = VendorPerformance(
                vendor_id=vendor.id,
                avg_rating=perf_data["avg_rating"],
                response_time=perf_data["response_time"],
                acceptance_rate=perf_data["acceptance_rate"],
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


def score_vendor(requirement: Requirement, vendor: Vendor) -> dict:
    profile = vendor.profile
    performance = vendor.performance
    if not profile or not performance:
        return {"score": 0.0, "breakdown": {"reason": "missing-profile"}}

    budget_fit_score = 0.0
    if requirement.budget <= 100000:
        budget_fit_score = 0.9 if profile.price_band == "low" else 0.7 if profile.price_band == "medium" else 0.5
    elif requirement.budget <= 200000:
        budget_fit_score = 0.7 if profile.price_band == "medium" else 0.85 if profile.price_band == "high" else 0.6
    else:
        budget_fit_score = 0.8 if profile.price_band == "high" else 0.6

    performance_score = (performance.avg_rating / 5.0) * 0.6 + (1.0 - min(performance.response_time / 5.0, 1.0)) * 0.2 + performance.acceptance_rate * 0.2

    theme_hits = [tag for tag in requirement.theme_tags if tag.lower() in [item.lower() for item in profile.categories]]
    capability_score = 0.0
    if theme_hits:
        capability_score += 0.6
    if any(area.lower() == requirement.city.lower() for area in profile.service_areas):
        capability_score += 0.4

    experience_score = 0.9 if "decor" in [item.lower() for item in profile.categories] else 0.6
    availability_score = 0.8 if performance.acceptance_rate > 0.75 else 0.6
    platform_score = 0.75 if performance.acceptance_rate > 0.8 else 0.6

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
    if performance.avg_rating >= 4.5:
        reasons.append("high customer rating")
    if profile.price_band == "medium" and requirement.budget <= 200000:
        reasons.append("budget-friendly fit")

    breakdown = {
        "budget_fit": round(budget_fit_score, 3),
        "performance": round(performance_score, 3),
        "capability": round(capability_score, 3),
        "experience": round(experience_score, 3),
        "availability": round(availability_score, 3),
        "platform_intelligence": round(platform_score, 3),
        "reason": " | ".join(reasons) if reasons else "matches core filters",
    }
    return {"score": round(total, 3), "breakdown": breakdown}


@app.post("/api/requirements/", response_model=RequirementResponse)
def create_requirement(payload: RequirementCreateRequest):
    db = SessionLocal()
    try:
        requirement = Requirement(
            category=payload.category,
            city=payload.city,
            budget=payload.budget,
            guest_count=payload.guest_count,
            theme_tags=payload.theme_tags,
            description=payload.description,
        )
        db.add(requirement)
        db.commit()
        db.refresh(requirement)

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
        top_matches = scored[:5]

        for vendor, result in top_matches:
            match = Match(
                requirement_id=requirement.id,
                vendor_id=vendor.id,
                score=result["score"],
                score_breakdown=result["breakdown"],
            )
            db.add(match)
        db.commit()

        return RequirementResponse(
            requirement_id=requirement.id,
            matches=[
                {
                    "vendor_id": vendor.id,
                    "vendor_name": vendor.name,
                    "score": result["score"],
                    "match_reason": result["breakdown"]["reason"],
                    "score_breakdown": result["breakdown"],
                }
                for vendor, result in top_matches
            ],
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
            matches=[
                {
                    "vendor_id": item.vendor_id,
                    "vendor_name": db.get(Vendor, item.vendor_id).name,
                    "score": item.score,
                    "match_reason": item.score_breakdown.get("reason", "matched"),
                    "score_breakdown": item.score_breakdown,
                }
                for item in matches
            ],
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
        invitations = []
        for match in matches[:3]:
            invitation = Invitation(
                requirement_id=requirement_id,
                vendor_id=match.vendor_id,
                wave_number=request.wave_number,
                status="pending",
            )
            db.add(invitation)
            db.commit()
            db.refresh(invitation)
            invitations.append({"id": invitation.id, "vendor_id": invitation.vendor_id, "status": invitation.status})
        return {"requirement_id": requirement_id, "invitations": invitations}
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
