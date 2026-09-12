from sqlalchemy import Column, Integer, Float, Boolean, String, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum

class RiskStatus(enum.Enum):
    APPROVED = "approved"
    UNDER_INVESTIGATION = "under_investigation"
    REJECTED = "rejected"
    PENDING = "pending"

class Risk(Base):
    __tablename__ = "risks"

    id = Column(Integer, primary_key=True, index=True)
    ocr_confidence = Column(Float, nullable=True)
    mrz_validation = Column(Boolean, nullable=True)
    reasons = Column(Text, nullable=True)
    tampering_probability = Column(Float, nullable=True)
    face_match_score = Column(Float, nullable=True)
    database_verification = Column(Boolean, nullable=True)
    approved = Column(Boolean, nullable=True)
    status = Column(Enum(RiskStatus), default=RiskStatus.PENDING)
    description = Column(Text, nullable=True)
    
    # Foreign Keys
    veri_id = Column(Integer, ForeignKey("verification_entries.id"), nullable=False)
    officer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    verifier_admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    doc_id = Column(Integer, ForeignKey("documents.id"), nullable=True)

    # Relationships
    verification = relationship("VerificationEntry", back_populates="risk_entries")
    officer = relationship("User", foreign_keys=[officer_id], back_populates="risk_entries")
    verifier_admin = relationship("User", foreign_keys=[verifier_admin_id], back_populates="risk_verifications")
    document = relationship("Document", back_populates="risk_entries")