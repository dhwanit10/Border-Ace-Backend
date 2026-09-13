from pydantic import BaseModel
from typing import Optional
from datetime import date
from app.models.document import DocumentTypeEnum
from app.models.risk import RiskStatus

class ExtractedDocumentData(BaseModel):
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

class RequestDocumentData(BaseModel):
    doc_id:int
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

class DocumentUploadResponse(BaseModel):
    doc_id: int
    extracted_data: ExtractedDocumentData
    ocr_confidence: float

class VerifyPersonResponse(BaseModel):
    verification_id: int
    risk_id: int
    face_match_score: float
    ocr_confidence: float
    document_specific_validation: bool
    validation_type: str
    reasons: list[str]
    tampering_probability: float
    status: RiskStatus
    blockchain_verification: bool
    transaction_link: str
    blockchain_face_score: float

class UpdateStatusRequest(BaseModel):
    risk_id: int
    status: RiskStatus
    description: Optional[str] = None
    session_id: int

class UpdateStatusResponse(BaseModel):
    success: bool
    risk_id: int
    status: RiskStatus
    session_cases: int
