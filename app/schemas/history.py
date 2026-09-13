from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentTypeEnum
from app.models.risk import RiskStatus
from app.models.user import UserType, UserStatus
from app.models.system import SystemStatus


class HistoryDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    doc_number: str
    doc_type: DocumentTypeEnum
    gender: Optional[str] = None
    nationality: Optional[str] = None
    dob: Optional[date] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    mrz_no: Optional[str] = None
    address: Optional[str] = None


class HistoryRiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ocr_confidence: Optional[float] = None
    document_specific_validation: Optional[bool] = None
    validation_type: Optional[str] = None
    reasons: Optional[list[str]] = None
    tampering_probability: Optional[float] = None
    face_match_score: Optional[float] = None
    database_verification: Optional[bool] = None
    approved: Optional[bool] = None
    status: RiskStatus
    description: Optional[str] = None
    verifier_admin_id: Optional[int] = None


class HistoryOfficerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    user_type: UserType
    status: UserStatus


class HistorySystemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    system_name: str
    status: SystemStatus


class HistorySessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    no_of_cases: Optional[int] = None


class HistoryItemResponse(BaseModel):
    verification_id: int
    date_time_recorded: datetime

    document: HistoryDocumentResponse
    risks: list[HistoryRiskResponse]

    officer: HistoryOfficerResponse
    session: Optional[HistorySessionResponse] = None
    system: Optional[HistorySystemResponse] = None


class HistoryResponse(BaseModel):
    total: int
    data: list[HistoryItemResponse]