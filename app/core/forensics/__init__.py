from .ela import (
    analyze_ela,
    get_ela_signal,
)

from .copy_move import (
    analyze_copy_move,
    get_copy_move_signal,
)
from .text_forensics import (
    analyze_text_forensics,
    get_text_forensics_signal,
)
from .metadata import (
    analyze_metadata,
    get_metadata_signal,
)
# from .tampering_engine import (
#     analyze_tampering,
#     get_tampering_signal,
# )
# from .physical_document_pipeline import detect_physical_tempering
# from .digital_document_pipeline import detect_digital_tempering
# from .aadhaar_pipeline import verify_aadhaar_qr
__all__ = [
    "analyze_ela",
    "get_ela_signal",
    "analyze_copy_move",
    "get_copy_move_signal",
    "analyze_text_forensics",
    "get_text_forensics_signal",
    "analyze_metadata",
    "get_metadata_signal",
    "analyze_tampering",
    "get_tampering_signal",
    "detect_physical_tempering",
    "detect_digital_tempering",
    "verify_aadhaar_qr",
]