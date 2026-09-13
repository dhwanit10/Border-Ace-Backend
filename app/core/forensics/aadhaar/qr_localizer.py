from __future__ import annotations

from typing import Any

import cv2
import numpy as np


QR_OUTPUT_SIZE = 900


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


def _find_qr_candidate(
    panel: np.ndarray,
) -> tuple[dict[str, int] | None, float]:

    """
    Search for the QR region inside an Aadhaar back panel.

    The search is restricted to the right side of the panel
    because the Aadhaar QR is located there in the target
    document layout.

    This is a localization function only.
    """

    height, width = panel.shape[:2]

    gray = cv2.cvtColor(
        panel,
        cv2.COLOR_BGR2GRAY,
    )

    # -----------------------------------------------------
    # Restrict search to the right portion of the back side.
    # -----------------------------------------------------

    x_start = int(width * 0.55)
    x_end = int(width * 0.99)

    y_start = int(height * 0.15)
    y_end = int(height * 0.95)

    roi = gray[
        y_start:y_end,
        x_start:x_end,
    ]

    # -----------------------------------------------------
    # Look for bright QR background.
    # -----------------------------------------------------

    blurred = cv2.GaussianBlur(
        roi,
        (5, 5),
        0,
    )

    best_box = None
    best_score = 0.0

    for threshold in (
        130,
        145,
        160,
        175,
        190,
        205,
        220,
    ):

        _, binary = cv2.threshold(
            blurred,
            threshold,
            255,
            cv2.THRESH_BINARY,
        )

        # Join the QR white background into one region.
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (15, 15),
        )

        closed = cv2.morphologyEx(
            binary,
            cv2.MORPH_CLOSE,
            kernel,
        )

        contours, _ = cv2.findContours(
            closed,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        for contour in contours:

            x, y, w, h = cv2.boundingRect(
                contour
            )

            if w <= 0 or h <= 0:
                continue

            area = w * h

            ratio = w / h

            # QR background is approximately square.
            if not (
                0.80
                <= ratio
                <= 1.25
            ):
                continue

            # Candidate should be reasonably large.
            if area < (
                roi.shape[0]
                * roi.shape[1]
                * 0.08
            ):
                continue

            # But shouldn't occupy almost the whole ROI.
            if area > (
                roi.shape[0]
                * roi.shape[1]
                * 0.85
            ):
                continue

            # -------------------------------------------------
            # Edge density inside candidate.
            #
            # QR contains a very high density of small
            # black/white transitions.
            # -------------------------------------------------

            candidate_gray = roi[
                y:y + h,
                x:x + w,
            ]

            candidate_edges = cv2.Canny(
                candidate_gray,
                50,
                150,
            )

            edge_density = float(
                np.mean(
                    candidate_edges > 0
                )
            )

            # QR-like region should have substantial
            # high-frequency structure.
            edge_score = min(
                1.0,
                edge_density / 0.25,
            )

            # -------------------------------------------------
            # Square score.
            # -------------------------------------------------

            square_score = max(
                0.0,
                1.0
                - abs(
                    1.0 - ratio
                ) * 4.0,
            )

            # -------------------------------------------------
            # Size score.
            # -------------------------------------------------

            area_ratio = (
                area
                / (
                    roi.shape[0]
                    * roi.shape[1]
                )
            )

            size_score = min(
                1.0,
                area_ratio / 0.30,
            )

            # -------------------------------------------------
            # Right-side preference.
            # -------------------------------------------------

            absolute_x = (
                x + x_start
            )

            right_position = (
                absolute_x
                / width
            )

            right_score = max(
                0.0,
                min(
                    1.0,
                    (
                        right_position
                        - 0.55
                    )
                    / 0.40,
                ),
            )

            score = (
                0.35 * square_score
                + 0.35 * edge_score
                + 0.20 * size_score
                + 0.10 * right_score
            )

            if score > best_score:

                best_score = score

                best_box = {
                    "x": int(
                        x + x_start
                    ),
                    "y": int(
                        y + y_start
                    ),
                    "width": int(w),
                    "height": int(h),
                }

    return (
        best_box,
        float(best_score),
    )


def _fallback_region(
    panel: np.ndarray,
) -> dict[str, int]:

    """
    Conservative fallback covering the expected QR area.
    """

    height, width = panel.shape[:2]

    return {
        "x": int(width * 0.62),
        "y": int(height * 0.22),
        "width": int(width * 0.34),
        "height": int(height * 0.68),
    }


def _add_padding(
    box: dict[str, int],
    image_shape: tuple[int, ...],
) -> dict[str, int]:

    height, width = image_shape[:2]

    x = box["x"]
    y = box["y"]
    w = box["width"]
    h = box["height"]

    padding_x = int(
        w * 0.08
    )

    padding_y = int(
        h * 0.08
    )

    x1 = max(
        0,
        x - padding_x,
    )

    y1 = max(
        0,
        y - padding_y,
    )

    x2 = min(
        width,
        x + w + padding_x,
    )

    y2 = min(
        height,
        y + h + padding_y,
    )

    return {
        "x": int(x1),
        "y": int(y1),
        "width": int(
            x2 - x1
        ),
        "height": int(
            y2 - y1
        ),
    }


def _normalize_qr(
    crop: np.ndarray,
) -> np.ndarray:

    if crop.size == 0:

        raise ValueError(
            "QR crop is empty"
        )

    height, width = crop.shape[:2]

    size = max(
        height,
        width,
    )

    canvas = np.full(
        (
            size,
            size,
            3,
        ),
        255,
        dtype=np.uint8,
    )

    offset_x = (
        size - width
    ) // 2

    offset_y = (
        size - height
    ) // 2

    canvas[
        offset_y:
        offset_y + height,
        offset_x:
        offset_x + width,
    ] = crop

    return cv2.resize(
        canvas,
        (
            QR_OUTPUT_SIZE,
            QR_OUTPUT_SIZE,
        ),
        interpolation=cv2.INTER_CUBIC,
    )


def localize_aadhaar_qr(
    image_source: str | bytes | bytearray,
) -> dict[str, Any]:

    """
    Localize the QR on an Aadhaar image.

    Pipeline:

        Full image
            ↓
        Aadhaar panel detector
            ↓
        Back panel
            ↓
        Right-side QR search
            ↓
        QR crop

    This does NOT decode the QR and does NOT verify
    the UIDAI cryptographic signature.
    """

    result: dict[str, Any] = {

        "success": False,

        "qr_localized": False,

        "qr_box": None,

        "localized_image": None,

        "localization_score": 0.0,

        "detection_method": None,

        "original_size": None,

        "back_panel_size": None,

        "error": None,
    }

    try:

        image = _decode_image(
            image_source
        )

        height, width = image.shape[:2]

        result["original_size"] = {
            "width": int(width),
            "height": int(height),
        }

        # =================================================
        # STEP 1
        # Detect stacked Aadhaar panels.
        # =================================================

        from app.core.forensics.aadhaar.panel_detector import (
            detect_aadhaar_panels,
        )

        panel_result = detect_aadhaar_panels(
            image_source
        )

        if (
            panel_result["success"]
            and panel_result["panel_count"] == 2
        ):

            back_panel = (
                panel_result["panels"]["back"]
            )

            result["back_panel_size"] = {
                "width": int(
                    back_panel.shape[1]
                ),
                "height": int(
                    back_panel.shape[0]
                ),
            }

            # Search inside normalized back panel.
            box, score = _find_qr_candidate(
                back_panel
            )

            if box is not None:

                result[
                    "detection_method"
                ] = "back_panel_qr_search"

                result[
                    "localization_score"
                ] = float(score)

            else:

                box = _fallback_region(
                    back_panel
                )

                result[
                    "detection_method"
                ] = "back_panel_fallback"

                result[
                    "localization_score"
                ] = 0.30

            padded = _add_padding(
                box,
                back_panel.shape,
            )

            crop = (
                back_panel[
                    padded["y"]:
                    padded["y"]
                    + padded["height"],
                    padded["x"]:
                    padded["x"]
                    + padded["width"],
                ]
                .copy()
            )

            normalized = _normalize_qr(
                crop
            )

            result["success"] = True

            result["qr_localized"] = True

            result["qr_box"] = padded

            result[
                "localized_image"
            ] = normalized

            return result

        # =================================================
        # STEP 2
        # If panel detection isn't available,
        # use full-image fallback.
        # =================================================

        box, score = _find_qr_candidate(
            image
        )

        if box is None:

            box = _fallback_region(
                image
            )

            result[
                "detection_method"
            ] = "full_image_fallback"

            score = 0.20

        else:

            result[
                "detection_method"
            ] = "full_image_qr_search"

        padded = _add_padding(
            box,
            image.shape,
        )

        crop = _crop_box(
            image,
            padded,
        )

        normalized = _normalize_qr(
            crop
        )

        result["success"] = True

        result["qr_localized"] = True

        result["qr_box"] = padded

        result[
            "localized_image"
        ] = normalized

        result[
            "localization_score"
        ] = float(score)

        return result

    except Exception as exc:

        result["error"] = str(exc)

        return result


def _crop_box(
    image: np.ndarray,
    box: dict[str, int],
) -> np.ndarray:

    return image[
        box["y"]:
        box["y"] + box["height"],
        box["x"]:
        box["x"] + box["width"],
    ].copy()