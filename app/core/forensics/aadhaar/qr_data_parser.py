"""
Aadhaar Secure QR Identity Data Parser

Supports automatic detection of multiple observed Aadhaar QR
structures and returns a unified identity-data representation.

Supported structures:

1. Legacy / original Secure QR structure
   indicator
   reference_id
   name
   dob
   gender
   ...
   photo
   hashes
   signature

2. V2 Secure QR structure
   V2
   indicator
   reference_id
   name
   dob
   gender
   ...
   additional binary/photo section
   signature

Important:
    This parser extracts QR data.
    It does NOT claim cryptographic signature verification.
"""

from __future__ import annotations

import gzip
from typing import Any


# ============================================================
# CONSTANTS
# ============================================================

DELIMITER = 0xFF

SIGNATURE_LENGTH = 256
HASH_LENGTH = 32

LEGACY_FIELD_COUNT = 16
V2_FIELD_COUNT = 17

SUPPORTED_V2_MARKER = "V2"


# Unified identity field names.
#
# The first field differs between formats:
#
# Legacy:
#     indicator
#     reference_id
#
# V2:
#     version
#     indicator
#     reference_id
#
# Everything after that is normalized into the same names.
# ============================================================

LEGACY_FIELD_NAMES = [
    "indicator",
    "reference_id",
    "full_name",
    "dob",
    "gender",
    "care_of",
    "district",
    "landmark",
    "house",
    "location",
    "pin_code",
    "post_office",
    "state",
    "street",
    "sub_district",
    "vtc",
]


V2_FIELD_NAMES = [
    "version",
    "indicator",
    "reference_id",
    "full_name",
    "dob",
    "gender",
    "care_of",
    "district",
    "landmark",
    "house",
    "location",
    "pin_code",
    "post_office",
    "state",
    "street",
    "sub_district",
    "vtc",
]


# ============================================================
# TEXT DECODER
# ============================================================

def _decode_text(
    value: bytes,
) -> str:
    """
    Decode QR text safely.

    Aadhaar QR text is normally UTF-8.
    Invalid bytes are replaced instead of crashing
    the verification process.
    """

    if not value:
        return ""

    return value.decode(
        "utf-8",
        errors="replace",
    ).strip()


# ============================================================
# DECOMPRESSION
# ============================================================

def _decompress_if_needed(
    raw: bytes,
) -> bytes:
    """
    Decompress GZIP data when required.

    The decimal QR payload normally converts to a
    GZIP-compressed binary blob.

    If data is already decompressed, return it unchanged.
    """

    if not raw:
        raise ValueError(
            "QR binary data is empty."
        )

    if raw[:2] == b"\x1f\x8b":

        return gzip.decompress(
            raw
        )

    return raw


# ============================================================
# SIGNATURE SPLIT
# ============================================================

def _split_signature(
    data: bytes,
) -> tuple[bytes, bytes]:
    """
    Split the final 256-byte RSA signature from the
    decompressed Aadhaar QR payload.

    Returns:

        signed_data
        signature
    """

    if len(data) < SIGNATURE_LENGTH:

        raise ValueError(
            "QR data is shorter than the expected "
            "256-byte signature."
        )

    return (
        data[:-SIGNATURE_LENGTH],
        data[-SIGNATURE_LENGTH:],
    )


# ============================================================
# DELIMITED FIELD EXTRACTION
# ============================================================

def _extract_fields(
    data: bytes,
    field_count: int,
) -> tuple[list[str], int]:
    """
    Extract a fixed number of 0xFF-delimited text fields.

    Important:
        Only the requested number of fields is extracted.

        We do NOT split the complete payload because the
        photograph/binary section can itself contain 0xFF
        bytes.
    """

    fields: list[str] = []

    start = 0

    for _ in range(
        field_count
    ):

        delimiter_position = data.find(
            bytes([DELIMITER]),
            start,
        )

        if delimiter_position == -1:

            raise ValueError(
                f"Unable to locate all "
                f"{field_count} Aadhaar QR text fields."
            )

        field_bytes = data[
            start:delimiter_position
        ]

        fields.append(
            _decode_text(
                field_bytes
            )
        )

        start = (
            delimiter_position
            + 1
        )

    return (
        fields,
        start,
    )


# ============================================================
# INDICATOR
# ============================================================

def _parse_indicator(
    value: str,
) -> int:
    """
    Parse the Aadhaar QR mobile/email presence indicator.

    Valid values:

        0 = neither
        1 = email only
        2 = mobile only
        3 = both
    """

    value = value.strip()

    if value not in {
        "0",
        "1",
        "2",
        "3",
    }:

        raise ValueError(
            "Invalid Aadhaar QR mobile/email indicator."
        )

    return int(
        value
    )


# ============================================================
# FORMAT DETECTION
# ============================================================

def _detect_format(
    data: bytes,
) -> str:
    """
    Detect the QR structure automatically.

    Returns:

        LEGACY
        V2
        UNKNOWN
    """

    # --------------------------------------------------------
    # Read the first field only.
    # --------------------------------------------------------

    delimiter_position = data.find(
        bytes([DELIMITER])
    )

    if delimiter_position == -1:

        return "UNKNOWN"

    first_field = _decode_text(
        data[
            :delimiter_position
        ]
    )

    # --------------------------------------------------------
    # V2
    # --------------------------------------------------------

    if first_field.upper() == SUPPORTED_V2_MARKER:

        return "V2"

    # --------------------------------------------------------
    # Legacy / original format
    # --------------------------------------------------------

    if first_field in {
        "0",
        "1",
        "2",
        "3",
    }:

        return "LEGACY"

    # --------------------------------------------------------
    # Unknown structure
    # --------------------------------------------------------

    return "UNKNOWN"


# ============================================================
# ADDRESS
# ============================================================

def _build_address(
    fields: dict[str, Any],
) -> str:
    """
    Build a readable address from QR address components.

    Empty components are ignored.
    """

    components = [
        fields.get("house"),
        fields.get("street"),
        fields.get("location"),
        fields.get("landmark"),
        fields.get("vtc"),
        fields.get("sub_district"),
        fields.get("district"),
        fields.get("post_office"),
        fields.get("state"),
        fields.get("pin_code"),
    ]

    values = []

    for value in components:

        if value is None:
            continue

        value = str(
            value
        ).strip()

        if value:
            values.append(
                value
            )

    return ", ".join(
        values
    )


# ============================================================
# HASH HANDLING
# ============================================================

def _split_hashes(
    content: bytes,
    indicator: int,
) -> tuple[bytes, bytes | None, bytes | None]:
    """
    Split photo/hash content according to the indicator.

    Returns:

        photo_bytes
        mobile_hash
        email_hash

    The parser only separates the fixed-size hash area.
    It does not attempt to claim that the hashes are valid.
    """

    if indicator == 0:

        hash_count = 0

    elif indicator in {
        1,
        2,
    }:

        hash_count = 1

    else:

        hash_count = 2

    expected_hash_bytes = (
        hash_count
        * HASH_LENGTH
    )

    if len(content) < expected_hash_bytes:

        raise ValueError(
            "QR binary section is shorter than "
            "the expected hash area."
        )

    photo_end = (
        len(content)
        - expected_hash_bytes
    )

    photo_bytes = content[
        :photo_end
    ]

    hash_bytes = content[
        photo_end:
    ]

    mobile_hash = None
    email_hash = None

    if indicator == 1:

        email_hash = hash_bytes[
            :HASH_LENGTH
        ]

    elif indicator == 2:

        mobile_hash = hash_bytes[
            :HASH_LENGTH
        ]

    elif indicator == 3:

        mobile_hash = hash_bytes[
            :HASH_LENGTH
        ]

        email_hash = hash_bytes[
            HASH_LENGTH:
            HASH_LENGTH * 2
        ]

    return (
        photo_bytes,
        mobile_hash,
        email_hash,
    )


# ============================================================
# LEGACY PARSER
# ============================================================

def _parse_legacy(
    data: bytes,
) -> dict[str, Any]:
    """
    Parse the observed legacy/original Aadhaar QR format.
    """

    field_values, binary_start = _extract_fields(
        data,
        LEGACY_FIELD_COUNT,
    )

    fields = dict(
        zip(
            LEGACY_FIELD_NAMES,
            field_values,
        )
    )

    indicator = _parse_indicator(
        fields["indicator"]
    )

    binary_section = data[
        binary_start:
    ]

    if len(binary_section) < SIGNATURE_LENGTH:

        raise ValueError(
            "QR binary section is too short."
        )

    signature = binary_section[
        -SIGNATURE_LENGTH:
    ]

    content_before_signature = (
        binary_section[
            :-SIGNATURE_LENGTH
        ]
    )

    (
        photo_bytes,
        mobile_hash,
        email_hash,
    ) = _split_hashes(
        content_before_signature,
        indicator,
    )

    if not photo_bytes:

        raise ValueError(
            "QR photograph data is empty."
        )

    return {
        "success": True,
        "format": "LEGACY",

        "version": None,

        "indicator": indicator,

        "reference_id": fields[
            "reference_id"
        ],

        "full_name": fields[
            "full_name"
        ],

        "dob": fields[
            "dob"
        ],

        "gender": fields[
            "gender"
        ],

        "care_of": fields[
            "care_of"
        ],

        "district": fields[
            "district"
        ],

        "landmark": fields[
            "landmark"
        ],

        "house": fields[
            "house"
        ],

        "location": fields[
            "location"
        ],

        "pin_code": fields[
            "pin_code"
        ],

        "post_office": fields[
            "post_office"
        ],

        "state": fields[
            "state"
        ],

        "street": fields[
            "street"
        ],

        "sub_district": fields[
            "sub_district"
        ],

        "vtc": fields[
            "vtc"
        ],

        "address": _build_address(
            fields
        ),

        "photo_bytes": photo_bytes,

        "photo_length": len(
            photo_bytes
        ),

        "mobile_hash": mobile_hash,

        "email_hash": email_hash,

        "signature": signature,

        "signature_length": len(
            signature
        ),

        "cryptographic_status": (
            "UNVERIFIED"
        ),

        "error": None,
    }


# ============================================================
# V2 PARSER
# ============================================================

def _parse_v2(
    data: bytes,
) -> dict[str, Any]:
    """
    Parse the observed V2 Aadhaar QR format.

    Observed structure:

        V2
        indicator
        reference_id
        full_name
        dob
        gender
        care_of
        district
        landmark
        house
        location
        pin_code
        post_office
        state
        street
        sub_district
        vtc
        binary/photo section
        signature
    """

    field_values, binary_start = _extract_fields(
        data,
        V2_FIELD_COUNT,
    )

    fields = dict(
        zip(
            V2_FIELD_NAMES,
            field_values,
        )
    )

    # --------------------------------------------------------
    # Confirm version
    # --------------------------------------------------------

    version = fields[
        "version"
    ].upper().strip()

    if version != SUPPORTED_V2_MARKER:

        raise ValueError(
            "Unsupported Aadhaar QR version marker."
        )

    # --------------------------------------------------------
    # Parse indicator
    # --------------------------------------------------------

    indicator = _parse_indicator(
        fields["indicator"]
    )

    # --------------------------------------------------------
    # Binary section
    # --------------------------------------------------------

    binary_section = data[
        binary_start:
    ]

    if len(binary_section) < SIGNATURE_LENGTH:

        raise ValueError(
            "V2 QR binary section is too short."
        )

    signature = binary_section[
        -SIGNATURE_LENGTH:
    ]

    content_before_signature = (
        binary_section[
            :-SIGNATURE_LENGTH
        ]
    )

    # --------------------------------------------------------
    # V2 observed payload
    #
    # We preserve the binary/photo content instead of assuming
    # that every 0xFF byte after the text section is a delimiter.
    #
    # Hash separation is attempted using the indicator, but
    # photo bytes are never treated as text.
    # --------------------------------------------------------

    (
        photo_bytes,
        mobile_hash,
        email_hash,
    ) = _split_hashes(
        content_before_signature,
        indicator,
    )

    if not photo_bytes:

        raise ValueError(
            "V2 QR photograph/binary data is empty."
        )

    return {
        "success": True,
        "format": "V2",

        "version": version,

        "indicator": indicator,

        "reference_id": fields[
            "reference_id"
        ],

        "full_name": fields[
            "full_name"
        ],

        "dob": fields[
            "dob"
        ],

        "gender": fields[
            "gender"
        ],

        "care_of": fields[
            "care_of"
        ],

        "district": fields[
            "district"
        ],

        "landmark": fields[
            "landmark"
        ],

        "house": fields[
            "house"
        ],

        "location": fields[
            "location"
        ],

        "pin_code": fields[
            "pin_code"
        ],

        "post_office": fields[
            "post_office"
        ],

        "state": fields[
            "state"
        ],

        "street": fields[
            "street"
        ],

        "sub_district": fields[
            "sub_district"
        ],

        "vtc": fields[
            "vtc"
        ],

        "address": _build_address(
            fields
        ),

        "photo_bytes": photo_bytes,

        "photo_length": len(
            photo_bytes
        ),

        "mobile_hash": mobile_hash,

        "email_hash": email_hash,

        "signature": signature,

        "signature_length": len(
            signature
        ),

        "cryptographic_status": (
            "UNVERIFIED"
        ),

        "error": None,
    }


# ============================================================
# MAIN PARSER
# ============================================================

def parse_aadhaar_qr_text(
    raw: bytes,
) -> dict[str, Any]:
    """
    Automatically detect and parse the supported Aadhaar
    QR structure.

    Unknown formats are returned as UNVERIFIED/INCONCLUSIVE
    instead of being classified as fake.
    """

    try:

        data = _decompress_if_needed(
            raw
        )

    except Exception as exc:

        return {
            "success": False,
            "format": "UNKNOWN",
            "cryptographic_status": "UNVERIFIED",
            "error": (
                "Unable to decompress QR data: "
                + str(exc)
            ),
        }

    if len(data) < (
        SIGNATURE_LENGTH + 1
    ):

        return {
            "success": False,
            "format": "UNKNOWN",
            "cryptographic_status": "UNVERIFIED",
            "error": (
                "QR data is too short."
            ),
        }

    # --------------------------------------------------------
    # Automatic format detection
    # --------------------------------------------------------

    detected_format = _detect_format(
        data
    )

    # --------------------------------------------------------
    # Legacy
    # --------------------------------------------------------

    if detected_format == "LEGACY":

        try:

            return _parse_legacy(
                data
            )

        except Exception as exc:

            return {
                "success": False,
                "format": "LEGACY",
                "cryptographic_status": (
                    "UNVERIFIED"
                ),
                "error": str(
                    exc
                ),
            }

    # --------------------------------------------------------
    # V2
    # --------------------------------------------------------

    if detected_format == "V2":

        try:

            return _parse_v2(
                data
            )

        except Exception as exc:

            return {
                "success": False,
                "format": "V2",
                "cryptographic_status": (
                    "UNVERIFIED"
                ),
                "error": str(
                    exc
                ),
            }

    # --------------------------------------------------------
    # Unknown
    # --------------------------------------------------------

    return {
        "success": False,
        "format": "UNKNOWN",
        "cryptographic_status": (
            "UNVERIFIED"
        ),
        "error": (
            "Unsupported or unrecognized "
            "Aadhaar QR structure."
        ),
    }


# ============================================================
# PUBLIC HELPER
# ============================================================

def extract_qr_identity_data(
    raw: bytes,
) -> dict[str, Any]:
    """
    Public wrapper used by the QR/OCR pipeline.
    """

    return parse_aadhaar_qr_text(
        raw
    )


# ============================================================
# BACKWARD-COMPATIBLE ALIAS
# ============================================================

parse_qr_identity_data = (
    parse_aadhaar_qr_text
)