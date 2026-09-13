from __future__ import annotations

from typing import Any

import cv2
import numpy as np


OUTPUT_WIDTH = 1200
OUTPUT_HEIGHT = 760


def _decode_image(
    image_source: str | bytes | bytearray,
) -> np.ndarray:

    if isinstance(image_source, str):

        image = cv2.imread(
            image_source
        )

    elif isinstance(
        image_source,
        (bytes, bytearray)
    ):

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


def _normalize_panel(
    panel: np.ndarray,
) -> np.ndarray:

    return cv2.resize(
        panel,
        (
            OUTPUT_WIDTH,
            OUTPUT_HEIGHT,
        ),
        interpolation=cv2.INTER_AREA,
    )


def _calculate_row_features(
    image: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    # Mild blur removes tiny text noise.
    blurred = cv2.GaussianBlur(
        gray,
        (11, 11),
        0,
    )

    # Edge information.
    edges = cv2.Canny(
        blurred,
        40,
        120,
    )

    edge_density = np.mean(
        edges > 0,
        axis=1,
    )

    # Average brightness per row.
    brightness = np.mean(
        blurred,
        axis=1,
    )

    return (
        edge_density,
        brightness,
    )


def _find_best_split(
    image: np.ndarray,
) -> tuple[int | None, float]:

    height, width = image.shape[:2]

    if height < 800:
        return None, 0.0

    edge_density, brightness = (
        _calculate_row_features(image)
    )

    # Smooth the row signals.
    smooth_kernel = max(
        15,
        int(height * 0.02) | 1,
    )

    kernel = np.ones(
        smooth_kernel,
        dtype=np.float32,
    ) / smooth_kernel

    edge_signal = np.convolve(
        edge_density,
        kernel,
        mode="same",
    )

    brightness_signal = np.convolve(
        brightness,
        kernel,
        mode="same",
    )

    # Aadhaar front/back stacked vertically should have
    # two reasonably large panels.
    #
    # Avoid the extreme top and bottom areas.
    min_split = int(
        height * 0.35
    )

    max_split = int(
        height * 0.65
    )

    if min_split >= max_split:
        return None, 0.0

    best_y = None
    best_score = -1.0

    global_edge_median = float(
        np.median(edge_signal)
    )

    brightness_gradient = np.abs(
        np.gradient(
            brightness_signal
        )
    )

    gradient_median = float(
        np.median(brightness_gradient)
    )

    for y in range(
        min_split,
        max_split,
    ):

        # -------------------------------------------------
        # Evaluate a small region around candidate split.
        # -------------------------------------------------

        window = max(
            8,
            int(height * 0.015),
        )

        y1 = max(
            0,
            y - window,
        )

        y2 = min(
            height,
            y + window,
        )

        local_edge = float(
            np.mean(
                edge_signal[y1:y2]
            )
        )

        # A separation region often has lower internal
        # edge activity than the document panels.
        if global_edge_median > 0:

            gap_score = max(
                0.0,
                1.0
                - (
                    local_edge
                    / global_edge_median
                ),
            )

        else:

            gap_score = 0.0

        # -------------------------------------------------
        # Brightness transition.
        # -------------------------------------------------

        gradient_score = 0.0

        if gradient_median > 0:

            gradient_score = min(
                brightness_gradient[y],
                gradient_median * 5,
            ) / (
                gradient_median * 5
            )

        # -------------------------------------------------
        # Geometry score.
        #
        # We want both panels to have reasonable heights.
        # -------------------------------------------------

        top_height = y
        bottom_height = (
            height - y
        )

        top_ratio = width / top_height
        bottom_ratio = width / bottom_height

        # Individual Aadhaar panels are normally landscape.
        top_geometry = max(
            0.0,
            1.0
            - abs(
                top_ratio - 1.586
            )
            / 1.0,
        )

        bottom_geometry = max(
            0.0,
            1.0
            - abs(
                bottom_ratio - 1.586
            )
            / 1.0,
        )

        geometry_score = (
            top_geometry
            + bottom_geometry
        ) / 2.0

        # -------------------------------------------------
        # Balance score.
        #
        # Front/back images are usually similar in size.
        # -------------------------------------------------

        height_difference = abs(
            top_height
            - bottom_height
        ) / height

        balance_score = max(
            0.0,
            1.0 - height_difference * 2,
        )

        # -------------------------------------------------
        # Final split score.
        # -------------------------------------------------

        score = (
            0.35 * gap_score
            + 0.20 * gradient_score
            + 0.25 * geometry_score
            + 0.20 * balance_score
        )

        if score > best_score:

            best_score = score
            best_y = y

    return best_y, float(
        best_score
    )


def _validate_panels(
    top: np.ndarray,
    bottom: np.ndarray,
) -> bool:

    top_height, top_width = (
        top.shape[:2]
    )

    bottom_height, bottom_width = (
        bottom.shape[:2]
    )

    if (
        top_height <= 0
        or bottom_height <= 0
    ):
        return False

    if (
        top_width <= 0
        or bottom_width <= 0
    ):
        return False

    top_ratio = (
        top_width / top_height
    )

    bottom_ratio = (
        bottom_width / bottom_height
    )

    # Allow reasonable camera/scanner variation.
    if not (
        1.20
        <= top_ratio
        <= 2.20
    ):
        return False

    if not (
        1.20
        <= bottom_ratio
        <= 2.20
    ):
        return False

    width_difference = abs(
        top_width
        - bottom_width
    ) / max(
        top_width,
        bottom_width,
    )

    if width_difference > 0.15:
        return False

    return True


def detect_aadhaar_panels(
    image_source: str | bytes | bytearray,
) -> dict[str, Any]:

    result: dict[str, Any] = {

        "success": False,

        "panel_count": 0,

        "layout": "unknown",

        "panels": {
            "front": None,
            "back": None,
        },

        "panel_boxes": {
            "front": None,
            "back": None,
        },

        "original_size": None,

        "split_score": 0.0,

        "error": None,
    }

    # =====================================================
    # STEP 1
    # Decode image
    # =====================================================

    try:

        image = _decode_image(
            image_source
        )

    except Exception as exc:

        result["error"] = str(exc)

        return result

    height, width = image.shape[:2]

    result["original_size"] = {
        "width": int(width),
        "height": int(height),
    }

    # =====================================================
    # STEP 2
    # Find vertical stacked layout
    # =====================================================

    split_y, split_score = (
        _find_best_split(image)
    )

    result["split_score"] = float(
        split_score
    )

    # =====================================================
    # STEP 3
    # Validate candidate
    # =====================================================

    if split_y is not None:

        # Keep a small gap away from both panels.
        margin = max(
            3,
            int(height * 0.005),
        )

        top_end = max(
            1,
            split_y - margin,
        )

        bottom_start = min(
            height - 1,
            split_y + margin,
        )

        top_panel = image[
            0:top_end,
            :
        ]

        bottom_panel = image[
            bottom_start:height,
            :
        ]

        if _validate_panels(
            top_panel,
            bottom_panel,
        ):

            result["success"] = True

            result["panel_count"] = 2

            result["layout"] = (
                "vertical_front_back"
            )

            result["panels"]["front"] = (
                _normalize_panel(
                    top_panel
                )
            )

            result["panels"]["back"] = (
                _normalize_panel(
                    bottom_panel
                )
            )

            result["panel_boxes"]["front"] = {
                "x": 0,
                "y": 0,
                "width": int(width),
                "height": int(top_end),
            }

            result["panel_boxes"]["back"] = {
                "x": 0,
                "y": int(bottom_start),
                "width": int(width),
                "height": int(
                    height - bottom_start
                ),
            }

            return result

    # =====================================================
    # STEP 4
    # Single landscape panel fallback
    # =====================================================

    if width > height:

        ratio = (
            width / height
        )

        if 1.20 <= ratio <= 2.20:

            result["success"] = True

            result["panel_count"] = 1

            result["layout"] = (
                "single_panel"
            )

            result["panels"]["front"] = (
                _normalize_panel(image)
            )

            result["panel_boxes"]["front"] = {
                "x": 0,
                "y": 0,
                "width": int(width),
                "height": int(height),
            }

            return result

    # =====================================================
    # STEP 5
    # Failure
    # =====================================================

    result["error"] = (
        "Could not reliably identify "
        "Aadhaar panel layout"
    )

    return result