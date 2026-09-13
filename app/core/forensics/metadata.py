from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image
from PIL.ExifTags import TAGS


def _load_image(image_source: str | Path | bytes | bytearray):
    if isinstance(image_source, (str, Path)):
        return Image.open(image_source)

    if isinstance(image_source, (bytes, bytearray)):
        from io import BytesIO
        return Image.open(BytesIO(image_source))

    raise TypeError(
        "image_source must be a file path, bytes, or bytearray"
    )


def analyze_metadata(
    image_source: str | Path | bytes | bytearray,
) -> dict[str, Any]:

    try:
        image = _load_image(image_source)

        exif = image.getexif()

        metadata = {}

        for tag_id, value in exif.items():
            tag_name = TAGS.get(
                tag_id,
                str(tag_id),
            )

            metadata[tag_name] = str(value)

        suspicious_keywords = [
            "photoshop",
            "gimp",
            "adobe",
            "paint.net",
            "snapseed",
            "lightroom",
            "canva",
        ]

        software = metadata.get(
            "Software",
            "",
        ).lower()

        editing_software_detected = any(
            keyword in software
            for keyword in suspicious_keywords
        )

        exif_present = len(metadata) > 0

        if editing_software_detected:
            score = 80.0
            interpretation = (
                "editing_software_detected"
            )

        elif exif_present:
            score = 10.0
            interpretation = (
                "metadata_present"
            )

        else:
            score = 20.0
            interpretation = (
                "metadata_missing"
            )

        return {
            "success": True,
            "method": "METADATA",
            "score": score,
            "signal": score,
            "exif_present": exif_present,
            "metadata_count": len(metadata),
            "metadata": metadata,
            "software": metadata.get(
                "Software"
            ),
            "editing_software_detected":
                editing_software_detected,
            "interpretation": interpretation,
        }

    except Exception as exc:

        return {
            "success": False,
            "method": "METADATA",
            "score": 0.0,
            "signal": 0.0,
            "exif_present": False,
            "metadata_count": 0,
            "metadata": {},
            "software": None,
            "editing_software_detected": False,
            "interpretation": "analysis_failed",
            "error": str(exc),
        }


def get_metadata_signal(
    image_source: str | Path | bytes | bytearray,
) -> float:

    result = analyze_metadata(
        image_source
    )

    return float(
        result.get("score", 0.0)
    )