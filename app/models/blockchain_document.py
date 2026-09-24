from sqlalchemy import Column, Integer, Text, String, LargeBinary, DateTime
from sqlalchemy.sql import func

from app.core.database import Base


class BlockchainDocument(Base):
    __tablename__ = "blockchain_document_registry"

    id = Column(Integer, primary_key=True, index=True)
    doc_number = Column(String(50), unique=True, nullable=False, index=True)
    canonical_string = Column(Text, nullable=False)

    person_image = Column(
        LargeBinary,
        nullable=False
    )

    original_document_image = Column(
        LargeBinary,
        nullable=False
    )

    transaction_hash = Column(
        String(66),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )