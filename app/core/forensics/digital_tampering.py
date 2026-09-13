from __future__ import annotations
from pathlib import Path
from typing import Any
from .copy_move import analyze_copy_move
from .ela import analyze_ela
from .metadata import analyze_metadata
from .text_forensics import analyze_text_forensics

def _get_reasons(results: dict[str, dict[str, Any]]) -> list[str]:
    reasons = []
    if results["ela"].get("score", 0) >= 40:
        reasons.append("ELA shows unusual recompression differences")
    if results["copy_move"].get("score", 0) >= 40:
        reasons.append("Repeated visual patterns suggest copy-move editing")
    if results["text"].get("score", 0) >= 40:
        reasons.append("Text regions have inconsistent visual characteristics")
    if results["metadata"].get("editing_software_detected"):
        reasons.append("Metadata identifies image editing software")
    return reasons if reasons else ["No strong digital tampering evidence detected"]

def detect_digital_tempering(image_source: str | Path | bytes | bytearray) -> dict[str, Any]:
    # Run detectors
    results = {
        "ela": analyze_ela(image_source),
        "copy_move": analyze_copy_move(image_source),
        "text": analyze_text_forensics(image_source),
        "metadata": analyze_metadata(image_source),
    }

    # Extract scores
    scores = {
        "ela": round(float(results["ela"].get("score", 0.0)), 2),
        "copy_move": round(float(results["copy_move"].get("score", 0.0)), 2),
        "text": round(float(results["text"].get("score", 0.0)), 2),
        "metadata": round(float(results["metadata"].get("score", 0.0)), 2),
    }

    # Weighted probability: ELA (35%), Copy-Move (30%), Text (25%), Metadata (10%)
    probability = round(
        min(100.0, scores["ela"] * 0.35 + scores["copy_move"] * 0.30
                  + scores["text"] * 0.25 + scores["metadata"] * 0.10),
        2,
    )

    return {
        "success": all(r.get("success", False) for r in results.values()),
        "tempering_probability": probability,
        "scores": scores,
        "reasons": _get_reasons(results),
    }
