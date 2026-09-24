from __future__ import annotations
import re
from difflib import SequenceMatcher
from datetime import date, datetime
from pathlib import Path
from typing import Any
import cv2
import numpy as np
from .aadhaar.qr_localizer import localize_aadhaar_qr
from .aadhaar.qr_decoder import decode_aadhaar_qr
from .aadhaar.qr_payload_decoder import decode_decimal_payload
from .aadhaar.qr_data_parser import extract_qr_identity_data

def _image(source: str | Path | bytes | bytearray) -> np.ndarray:
    if isinstance(source, (bytes, bytearray)):
        image = cv2.imdecode(np.frombuffer(source, np.uint8), cv2.IMREAD_COLOR)
    else:
        image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode Aadhaar image")
    return image

def _text(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())

def _date(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat() if hasattr(value, 'isoformat') else str(value)
    raw = str(value or "").strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return _text(value)

def _match(field: str, left: Any, right: Any) -> dict[str, Any]:
    if field == "doc_number":
       a, b = _text(left), _text(right)
       if len(a) < 4 or len(b) < 4:
           return {"match": None, "reason": None}
       matched = a[-4:] == b[:4]
       return {"match": matched, "reason": None if matched else f"{field} does not match"}

    if field == "gender":
        a, b = _text(left), _text(right)
        if(b != None):
            matched = a[0].lower() == b[0].lower()
        return {"match": matched, "reason": None if matched else f"{field} does not match"}

    a, b = (_date(left), _date(right)) if field == "dob" else (_text(left), _text(right))
    if not a or not b:
        return {"match": None, "reason": None}
    score = 100.0 if a == b else round(SequenceMatcher(None, a, b).ratio() * 100, 2)
    matched = score >= (90.0 if field == "full_name" else 100.0)
    return {"match": matched, "reason": None if matched else f"{field} does not match"}

def _photo_match(left: Any, right: Any) -> dict[str, Any]:
    if not left or not right:
        return {"match": None, "reason": None}
    img1 = cv2.imdecode(np.frombuffer(bytes(left), np.uint8), cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imdecode(np.frombuffer(bytes(right), np.uint8), cv2.IMREAD_GRAYSCALE)
    if img1 is None or img2 is None:
        return {"match": None, "reason": "person image could not be compared"}
    img1 = cv2.resize(img1, (64, 64)).astype(np.float32)
    img2 = cv2.resize(img2, (64, 64)).astype(np.float32)
    score = round(max(0.0, 100.0 - float(np.mean(cv2.absdiff(img1, img2))) / 2.55), 2)
    matched = score >= 70.0
    return {"match": matched, "reason": None if matched else "person image does not match"}

def verify_aadhaar_qr(image_source: str | Path | bytes | bytearray, ocr_data: dict[str, Any]) -> dict[str, Any]:
    try:
        localized = localize_aadhaar_qr(image_source)
        if not localized.get("qr_localized"):
            return {"success": False, "valid": False, "tempering_probability": None, "reasons": ["Aadhaar QR could not be located"]}

        decoded = decode_aadhaar_qr(localized["localized_image"])
        if not decoded.get("qr_decoded"):
            return {"success": False, "valid": False, "tempering_probability": None, "reasons": ["Aadhaar QR could not be decoded"]}

        binary = decode_decimal_payload(decoded["payload"]).get("binary")
        qr = extract_qr_identity_data(binary)
    except Exception as exc:
        return {"success": False, "valid": False, "tempering_probability": None, "reasons": [f"Aadhaar QR verification failed: {exc}"]}

    ocr_data = ocr_data if isinstance(ocr_data, dict) else {}
    field_map = {
        "full_name": qr.get("full_name"),
        "doc_number": qr.get("aadhaar_number") or qr.get("reference_id"),
        "dob": qr.get("dob"),
        "gender": qr.get("gender"),
    }
    print(field_map)
    checks = {field: _match(field, ocr_data.get(field), value) for field, value in field_map.items()}
    

    mismatches = [c["reason"] for c in checks.values() if c["reason"]]
    compared = [c for c in checks.values() if c["match"] is not None]
    matched_count = sum(1 for c in compared if c["match"])

    probability = round((1.0 - matched_count / len(compared)) * 100, 2) if compared else None

    return {
        "success": True,
        "valid": bool(compared) and not mismatches,
        "tempering_probability": probability,
        "reasons": mismatches,
    }
