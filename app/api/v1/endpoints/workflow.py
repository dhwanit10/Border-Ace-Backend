from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.workflow import (
    DocumentUploadResponse, 
    VerifyPersonResponse, 
    UpdateStatusRequest, 
    UpdateStatusResponse,
    ExtractedDocumentData,
    RequestDocumentData
)
from app.models.document import Document, DocumentTypeEnum
from app.models.risk import Risk, RiskStatus
from app.models.verification import VerificationEntry
from app.models.system import Session as SystemSession
from app.models.user import User
from app.core.ocr_parser import process_document_image
import json
from app.core.face_matcher import match_faces, match_faces_with_cropping

from app.blockchain.hash_utils import generate_document_hash
from app.blockchain.service import register_document, verify_document

from app.models.blockchain_document import BlockchainDocument

router = APIRouter()


@router.post("/upload-document", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user_id: int = Form(...),
    db: Session = Depends(get_db)
):
    try:
        image_bytes = await file.read()
        
        # 1. Perform OCR using rapidocr
        ocr_result = process_document_image(image_bytes)
        
        doc_number = ocr_result.get("doc_number", "Unknown")
        
        # 2. Check if Document exists to avoid Unique Constraint violation
        # existing_doc = None
        # if doc_number != "Unknown":
        #     existing_doc = db.query(Document).filter(Document.doc_number == doc_number).first()
            
        # if existing_doc:
        #     existing_doc.full_name = ocr_result.get("full_name", "Unknown")
        #     existing_doc.doc_type = ocr_result.get("doc_type", DocumentTypeEnum.UNKNOWN)
        #     existing_doc.dob = ocr_result.get("dob", None)
        #     existing_doc.gender = ocr_result.get("gender", None)
        #     existing_doc.issue_date = ocr_result.get("issue_date", None)
        #     existing_doc.address = ocr_result.get("address", None)
        #     existing_doc.expiry_date = ocr_result.get("expiry_date", None)
        #     existing_doc.nationality = ocr_result.get("nationality", None)
        #     existing_doc.mrz_no = ocr_result.get("mrz_no", None)
        #     existing_doc.doc_photo = image_bytes
        #     existing_doc.user_id = user_id
        #     db.commit()
        #     db.refresh(existing_doc)
        #     new_doc = existing_doc
        # else:
        
        new_doc = Document(
            full_name=ocr_result.get("full_name", "Unknown"),
            doc_number=doc_number,
            doc_type=ocr_result.get("doc_type", DocumentTypeEnum.UNKNOWN),
            dob=ocr_result.get("dob", None),
            gender=ocr_result.get("gender", None),
            issue_date=ocr_result.get("issue_date", None),
            address=ocr_result.get("address", None),
            expiry_date=ocr_result.get("expiry_date", None),
            nationality=ocr_result.get("nationality", None),
            mrz_no=ocr_result.get("mrz_no", None),
            doc_photo=image_bytes,
            user_id=user_id 
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)
            
        extracted_data = ExtractedDocumentData(
            full_name=new_doc.full_name,
            doc_number=new_doc.doc_number,
            doc_type=new_doc.doc_type,
            dob=new_doc.dob,
            gender=new_doc.gender,
            issue_date=new_doc.issue_date,
            address=new_doc.address,
            expiry_date=new_doc.expiry_date,
            nationality=new_doc.nationality,
            mrz_no=new_doc.mrz_no
        )
        
        return DocumentUploadResponse(
            doc_id=new_doc.id,
            extracted_data=extracted_data,
            ocr_confidence=ocr_result.get("ocr_confidence", 0.0)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to process document: {str(e)}")

@router.post("/verify-person", response_model=VerifyPersonResponse)
async def verify_person(
    doc_id: int = Form(...),
    doc_data: str = Form(...),  # JSON string  # JSON string of ExtractedDocumentData
    person_image: UploadFile = File(...),
    officer_id: int = Form(...),
    session_id: int = Form(...),
    ocr_confidence: float = Form(...),
    db: Session = Depends(get_db)
):

    try:
        extracted_data = ExtractedDocumentData.parse_raw(doc_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    
    person_image_bytes = await person_image.read()
    
    doc = db.query(Document).filter(
       Document.id == doc_id
    ).first()
    
    if not doc:
        # Create new document if not exists
        doc = Document(
            doc_type=extracted_data.doc_type,
            doc_number=extracted_data.doc_number
        )
        db.add(doc)
        db.flush()  # Get the ID without committing
    
    # 2. Update doc with all extracted data
    doc.full_name = extracted_data.full_name
    doc.doc_number = extracted_data.doc_number
    # doc.doc_type = extracted_data.doc_type
    doc.gender = extracted_data.gender
    doc.nationality = extracted_data.nationality
    doc.dob = extracted_data.dob
    doc.issue_date = extracted_data.issue_date
    doc.expiry_date = extracted_data.expiry_date
    doc.mrz_no = extracted_data.mrz_no
    doc.address = extracted_data.address
    doc.person_image = person_image_bytes
    
    db.commit()
    db.refresh(doc)

    #blockchain verification
    blockchain_document = (
                db.query(BlockchainDocument)
                .filter(
                    BlockchainDocument.doc_number == doc.doc_number
                )
                .first()
            )
    result = False
    if not blockchain_document:
        result = False
        blockchain_face_score = 0.0
    else:
        document_hash, canonical_string = generate_document_hash(
            doc_type=doc.doc_type.value,
            doc_number=doc.doc_number,
            full_name=doc.full_name,
            dob=doc.dob,
            gender=doc.gender,
            nationality=doc.nationality
        )

        try:
            result = verify_document(
                    document_id=str(blockchain_document.id),
                    document_hash=document_hash
                )
            print(result)

            # Use match_faces for simple matching
            blockchain_face_score, blockchain_is_match = match_faces(blockchain_document.person_image, doc.doc_photo)

        except ValueError as e:
            # If face matching fails, set default values
            blockchain_face_score = 0.0
            result = False
            print(f"Face matching failed: {str(e)}")


    # 3. Match face using the new face matcher
    try:
        # Use match_faces for simple matching
        face_score, is_match = match_faces(person_image_bytes, doc.doc_photo)
        face_match_result = {
            "score": face_score,
            "match": is_match
        }
        
        # Alternative: Use match_faces_with_cropping for more details including cropped images
        # face_match_result = match_faces_with_cropping(person_image_bytes, doc.doc_photo)
        # face_score = face_match_result["score"]
        
    except ValueError as e:
        # If face matching fails, set default values
        face_score = 0.0
        # Optionally log the error or handle differently
        print(f"Face matching failed: {str(e)}")
    
    # 4. Create Verification Entry
    verification = VerificationEntry(
        doc_id=doc.id,
        officer_id=officer_id,
        session_id=session_id
    )
    db.add(verification)
    db.commit()
    db.refresh(verification)

    mrz = False
    if extracted_data.doc_type == "passport":
        mrz = True

    verification_confidence = (
        0.45 * face_score
        + 0.20 * blockchain_face_score
        + 0.25 * (1.0 if result else 0.0)
        + 0.10 * ocr_confidence
    )
    # 5. Create Risk Entry
    risk = Risk(
        ocr_confidence=ocr_confidence,
        mrz_validation=mrz,
        face_match_score=face_score,
        database_verification=True,
        approved=False,
        tampering_probability=(1.0 - verification_confidence) * 100, 
        status=RiskStatus.PENDING,
        veri_id=verification.id,
        officer_id=officer_id,
        doc_id=doc.id
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)

    
    
    return VerifyPersonResponse(
        verification_id=verification.id,
        risk_id=risk.id,
        face_match_score=risk.face_match_score,
        mrz_validation=mrz,
        ocr_confidence=risk.ocr_confidence,
        tampering_probability=risk.tampering_probability,
        status=risk.status,
        blockchain_verification=result,
        transaction_link=f"https://sepolia.etherscan.io/tx/{blockchain_document.transaction_hash}",
        blockchain_face_score=blockchain_face_score
    )

@router.post("/update-status", response_model=UpdateStatusResponse)
async def update_status(
    request: UpdateStatusRequest,
    db: Session = Depends(get_db)
):
    # 1. Update Risk
    risk = db.query(Risk).filter(Risk.id == request.risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk entry not found")
        
    risk.status = request.status
    if(risk.status == RiskStatus.APPROVED):
        risk.approved= True
    
    if request.description:
        risk.description = request.description
        
    # 2. Update Session
    session = db.query(SystemSession).filter(SystemSession.id == request.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session.no_of_cases = (session.no_of_cases or 0) + 1
    
    db.commit()
    db.refresh(risk)
    db.refresh(session)
    
    return UpdateStatusResponse(
        success=True,
        risk_id=risk.id,
        status=risk.status,
        session_cases=session.no_of_cases
    )
