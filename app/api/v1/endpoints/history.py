from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from app.models.system import Session as SystemSession
from app.core.database import get_db
from app.models.verification import VerificationEntry
from app.schemas.history import HistoryResponse, HistoryItemResponse
import json
from app.schemas.history import (
    HistoryResponse,
    HistoryItemResponse,
    HistoryRiskResponse,
)
router = APIRouter()


def build_history_response(verifications):
    data = []

    for verification in verifications:
        session = verification.session

        risks = []

        for risk in verification.risk_entries:
            reasons = []

            if risk.reasons:
                try:
                    reasons = json.loads(risk.reasons)
                except (json.JSONDecodeError, TypeError):
                    reasons = []

            risks.append(
                HistoryRiskResponse(
                    id=risk.id,
                    ocr_confidence=risk.ocr_confidence,
                    document_specific_validation=risk.document_specific_validation,
                    validation_type=risk.validation_type,
                    reasons=reasons,
                    tampering_probability=risk.tampering_probability,
                    face_match_score=risk.face_match_score,
                    database_verification=risk.database_verification,
                    approved=risk.approved,
                    status=risk.status,
                    description=risk.description,
                    verifier_admin_id=risk.verifier_admin_id,
                )
            )

        data.append(
            HistoryItemResponse(
                verification_id=verification.id,
                date_time_recorded=verification.date_time_recorded,
                document=verification.document,
                risks=risks,
                officer=verification.officer,
                session=session,
                system=session.system if session else None
            )
        )

    return HistoryResponse(
        total=len(data),
        data=data
    )


# @router.get("/history", response_model=HistoryResponse)
# async def get_history(
#     db: Session = Depends(get_db)
# ):
#     verifications = (
#         db.query(VerificationEntry)
#         .options(
#             joinedload(VerificationEntry.document),
#             joinedload(VerificationEntry.officer),
#             joinedload(VerificationEntry.risk_entries),
#             joinedload(VerificationEntry.session)
#             .joinedload("system")
#         )
#         .order_by(VerificationEntry.date_time_recorded.desc())
#         .all()
#     )

#     return build_history_response(verifications)


# @router.get("/history/officer/{officer_id}", response_model=HistoryResponse)
# async def get_officer_history(
#     officer_id: int,
#     db: Session = Depends(get_db)
# ):
#     verifications = (
#         db.query(VerificationEntry)
#         .options(
#             joinedload(VerificationEntry.document),
#             joinedload(VerificationEntry.officer),
#             joinedload(VerificationEntry.risk_entries),
#             joinedload(VerificationEntry.session)
#             .joinedload("system")
#         )
#         .filter(
#             VerificationEntry.officer_id == officer_id
#         )
#         .order_by(VerificationEntry.date_time_recorded.desc())
#         .all()
#     )

#     return build_history_response(verifications)

@router.get("/history", response_model=HistoryResponse)
async def get_history(
    officer_id: int | None = Query(None),
    db: Session = Depends(get_db)
):
    query = (
        db.query(VerificationEntry)
        .options(
            joinedload(VerificationEntry.document),
            joinedload(VerificationEntry.officer),
            joinedload(VerificationEntry.risk_entries),
            joinedload(VerificationEntry.session)
            .joinedload(SystemSession.system)
        )
    )

    if officer_id is not None:
        query = query.filter(
            VerificationEntry.officer_id == officer_id
        )

    verifications = (
        query
        .order_by(VerificationEntry.date_time_recorded.desc())
        .all()
    )

    return build_history_response(verifications)