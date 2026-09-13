from __future__ import annotations

from typing import Any

import cv2
import numpy as np


# Normalized Aadhaar panel dimensions
PANEL_WIDTH = 1200
PANEL_HEIGHT = 760


def _decode_image(
    image_source: str | bytes | bytearray,
) -> np.ndarray:

    if isinstance(image_source, str):

        image = cv2.imread(image_source)

    elif isinstance(image_source, (bytes, bytearray)):

        buffer = np.frombuffer(
            image_source,
            dtype=np.uint8,
        )

        image = cv2.imdecode(
            buffer,
            cv2.IMREAD_COLOR,
        )

    else:

        raise TypeError(
            "image_source must be a file path, "
            "bytes, or bytearray"
        )

    if image is None:

        raise ValueError(
            "Could not decode image"
        )

    return image


def _clip_box(
    x: int,
    y: int,
    width: int,
    height: int,
    image_width: int,
    image_height: int,
) -> dict[str, int]:

    x = max(0, min(x, image_width - 1))
    y = max(0, min(y, image_height - 1))

    width = max(
        1,
        min(width, image_width - x),
    )

    height = max(
        1,
        min(height, image_height - y),
    )

    return {
        "x": int(x),
        "y": int(y),
        "width": int(width),
        "height": int(height),
    }


def _box_from_relative(
    panel: np.ndarray,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> dict[str, int]:

    height, width = panel.shape[:2]

    x = int(width * x1)
    y = int(height * y1)

    box_width = int(
        width * (x2 - x1)
    )

    box_height = int(
        height * (y2 - y1)
    )

    return _clip_box(
        x,
        y,
        box_width,
        box_height,
        width,
        height,
    )


def _crop_box(
    image: np.ndarray,
    box: dict[str, int],
) -> np.ndarray:

    x = box["x"]
    y = box["y"]
    width = box["width"]
    height = box["height"]

    return image[
        y:y + height,
        x:x + width,
    ].copy()


def detect_front_regions(
    front_panel: np.ndarray,
) -> dict[str, Any]:

    """
    Detect important forensic regions on the front side.

    These are intentionally broad regions rather than
    exact pixel-level field detectors.

    They provide stable ROIs for later forensic analysis.
    """

    height, width = front_panel.shape[:2]

    regions: dict[str, dict[str, Any]] = {}

    # -----------------------------------------------------
    # Photograph
    # -----------------------------------------------------

    photo_box = _box_from_relative(
        front_panel,
        0.055,
        0.30,
        0.30,
        0.72,
    )

    regions["photo"] = {
        "box": photo_box,
        "image": _crop_box(
            front_panel,
            photo_box,
        ),
        "purpose": (
            "Photo replacement and image "
            "manipulation analysis"
        ),
    }

    # -----------------------------------------------------
    # Identity / demographic text
    # -----------------------------------------------------

    identity_box = _box_from_relative(
        front_panel,
        0.30,
        0.20,
        0.82,
        0.70,
    )

    regions["identity_text"] = {
        "box": identity_box,
        "image": _crop_box(
            front_panel,
            identity_box,
        ),
        "purpose": (
            "Text manipulation and "
            "layout consistency analysis"
        ),
    }

    # -----------------------------------------------------
    # Aadhaar number / identifier region
    # -----------------------------------------------------

    identifier_box = _box_from_relative(
        front_panel,
        0.25,
        0.68,
        0.82,
        0.87,
    )

    regions["identifier"] = {
        "box": identifier_box,
        "image": _crop_box(
            front_panel,
            identifier_box,
        ),
        "purpose": (
            "Identifier text manipulation analysis"
        ),
    }

    # -----------------------------------------------------
    # Security / logo region
    # -----------------------------------------------------

    security_box = _box_from_relative(
        front_panel,
        0.02,
        0.02,
        0.28,
        0.25,
    )

    regions["security"] = {
        "box": security_box,
        "image": _crop_box(
            front_panel,
            security_box,
        ),
        "purpose": (
            "Logo, microtext and security "
            "feature consistency analysis"
        ),
    }

    # -----------------------------------------------------
    # Full text area
    # -----------------------------------------------------

    text_box = _box_from_relative(
        front_panel,
        0.28,
        0.12,
        0.96,
        0.90,
    )

    regions["text_area"] = {
        "box": text_box,
        "image": _crop_box(
            front_panel,
            text_box,
        ),
        "purpose": (
            "Text-level forensic analysis"
        ),
    }

    return {
        "success": True,
        "side": "front",
        "regions": regions,
    }


def detect_back_regions(
    back_panel: np.ndarray,
) -> dict[str, Any]:

    """
    Detect important forensic regions on the back side.
    """

    height, width = back_panel.shape[:2]

    regions: dict[str, dict[str, Any]] = {}

    # -----------------------------------------------------
    # QR region
    # -----------------------------------------------------

    qr_box = _box_from_relative(
        back_panel,
        0.04,
        0.12,
        0.42,
        0.72,
    )

    regions["qr"] = {
        "box": qr_box,
        "image": _crop_box(
            back_panel,
            qr_box,
        ),
        "purpose": (
            "QR detection and authenticity "
            "verification"
        ),
    }

    # -----------------------------------------------------
    # Address region
    # -----------------------------------------------------

    address_box = _box_from_relative(
        back_panel,
        0.40,
        0.15,
        0.96,
        0.65,
    )

    regions["address_text"] = {
        "box": address_box,
        "image": _crop_box(
            back_panel,
            address_box,
        ),
        "purpose": (
            "Address text manipulation analysis"
        ),
    }

    # -----------------------------------------------------
    # Bottom security / issuer area
    # -----------------------------------------------------

    security_box = _box_from_relative(
        back_panel,
        0.35,
        0.65,
        0.96,
        0.92,
    )

    regions["security"] = {
        "box": security_box,
        "image": _crop_box(
            back_panel,
            security_box,
        ),
        "purpose": (
            "Security feature consistency "
            "analysis"
        ),
    }

    # -----------------------------------------------------
    # Full back-side text area
    # -----------------------------------------------------

    text_box = _box_from_relative(
        back_panel,
        0.35,
        0.08,
        0.97,
        0.93,
    )

    regions["text_area"] = {
        "box": text_box,
        "image": _crop_box(
            back_panel,
            text_box,
        ),
        "purpose": (
            "Text-level forensic analysis"
        ),
    }

    return {
        "success": True,
        "side": "back",
        "regions": regions,
    }


def detect_aadhaar_regions(
    front_panel: np.ndarray,
    back_panel: np.ndarray | None = None,
) -> dict[str, Any]:

    """
    Detect forensic regions from normalized Aadhaar panels.
    """

    result: dict[str, Any] = {
        "success": False,
        "front": None,
        "back": None,
        "region_count": 0,
        "error": None,
    }

    try:

        front_result = detect_front_regions(
            front_panel
        )

        result["front"] = front_result

        result["region_count"] = len(
            front_result["regions"]
        )

        if back_panel is not None:

            back_result = detect_back_regions(
                back_panel
            )

            result["back"] = back_result

            result["region_count"] += len(
                back_result["regions"]
            )

        result["success"] = True

        return result

    except Exception as exc:

        result["error"] = str(exc)

        return result