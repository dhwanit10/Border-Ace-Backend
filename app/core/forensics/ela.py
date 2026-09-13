# app/core/forensics/ela.py

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import cv2
import numpy as np


# ============================================================
# IMAGE LOADING
# ============================================================

def _load_image(
    image_source: str | Path | bytes | bytearray,
) -> np.ndarray:
    """
    Load an image from either a file path or image bytes.
    """

    if isinstance(
        image_source,
        (bytes, bytearray),
    ):

        image_array = np.frombuffer(
            image_source,
            dtype=np.uint8,
        )

        image = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR,
        )

        if image is None:
            raise ValueError(
                "Unable to decode image bytes."
            )

        return image

    image_path = Path(
        image_source
    )

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    image = cv2.imread(
        str(image_path),
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise ValueError(
            f"Unable to read image: {image_path}"
        )

    return image


# ============================================================
# JPEG RE-COMPRESSION
# ============================================================

def _recompress_image(
    image: np.ndarray,
    quality: int = 90,
) -> np.ndarray:
    """
    Re-compress image using JPEG.
    """

    quality = int(
        np.clip(
            quality,
            50,
            100,
        )
    )

    success, encoded = cv2.imencode(
        ".jpg",
        image,
        [
            cv2.IMWRITE_JPEG_QUALITY,
            quality,
        ],
    )

    if not success:
        raise ValueError(
            "JPEG re-compression failed."
        )

    recompressed = cv2.imdecode(
        encoded,
        cv2.IMREAD_COLOR,
    )

    if recompressed is None:
        raise ValueError(
            "Unable to decode recompressed image."
        )

    return recompressed


# ============================================================
# ELA MAP
# ============================================================

def _calculate_ela_map(
    original: np.ndarray,
    recompressed: np.ndarray,
) -> np.ndarray:
    """
    Calculate pixel-level Error Level Analysis map.

    Output shape:
        height x width
    """

    original_float = original.astype(
        np.float32
    )

    recompressed_float = recompressed.astype(
        np.float32
    )

    difference = cv2.absdiff(
        original_float,
        recompressed_float,
    )

    # Average difference across BGR channels.
    ela_map = np.mean(
        difference,
        axis=2,
    )

    return ela_map


# ============================================================
# BORDER INFORMATION
# ============================================================

def _get_border(
    shape: tuple[int, int],
    border_ratio: float,
) -> tuple[int, int]:
    """
    Calculate border size.
    """

    height, width = shape

    border_y = int(
        height * border_ratio
    )

    border_x = int(
        width * border_ratio
    )

    return border_y, border_x


# ============================================================
# ROBUST THRESHOLD
# ============================================================

def _robust_threshold(
    ela_map: np.ndarray,
    sensitivity: float = 3.0,
) -> float:
    """
    Calculate threshold using median + MAD.
    """

    values = ela_map.astype(
        np.float32
    ).flatten()

    if values.size == 0:
        return 0.0

    median = float(
        np.median(values)
    )

    mad = float(
        np.median(
            np.abs(
                values - median
            )
        )
    )

    robust_sigma = (
        1.4826 * mad
    )

    threshold = (
        median
        + sensitivity * robust_sigma
    )

    return float(threshold)


# ============================================================
# FULL-SIZE SUSPICIOUS MASK
# ============================================================

def _create_suspicious_mask(
    ela_map: np.ndarray,
    threshold: float,
    border_ratio: float = 0.02,
) -> np.ndarray:
    """
    Create a suspicious mask having EXACTLY the same
    height and width as the ELA map.

    This avoids the shape mismatch that occurred earlier.
    """

    mask = np.zeros(
        ela_map.shape,
        dtype=np.uint8,
    )

    mask[
        ela_map > threshold
    ] = 255

    # --------------------------------------------------------
    # Ignore border
    # --------------------------------------------------------

    border_y, border_x = _get_border(
        ela_map.shape,
        border_ratio,
    )

    if border_y > 0:

        mask[
            :border_y,
            :
        ] = 0

        mask[
            -border_y:,
            :
        ] = 0

    if border_x > 0:

        mask[
            :,
            :border_x
        ] = 0

        mask[
            :,
            -border_x:
        ] = 0

    return mask


# ============================================================
# MASK CLEANING
# ============================================================

def _clean_mask(
    mask: np.ndarray,
    min_area: int = 20,
) -> np.ndarray:
    """
    Remove small isolated regions.
    """

    kernel = np.ones(
        (3, 3),
        dtype=np.uint8,
    )

    # Remove small noise.
    cleaned = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel,
    )

    # Connect nearby suspicious pixels.
    cleaned = cv2.morphologyEx(
        cleaned,
        cv2.MORPH_CLOSE,
        kernel,
    )

    # --------------------------------------------------------
    # Remove small connected components
    # --------------------------------------------------------

    num_labels, labels, stats, _ = (
        cv2.connectedComponentsWithStats(
            cleaned,
            connectivity=8,
        )
    )

    result = np.zeros_like(
        cleaned
    )

    for label in range(
        1,
        num_labels,
    ):

        area = stats[
            label,
            cv2.CC_STAT_AREA,
        ]

        if area >= min_area:

            result[
                labels == label
            ] = 255

    return result


# ============================================================
# SUSPICIOUS REGIONS
# ============================================================

def _find_suspicious_regions(
    mask: np.ndarray,
    min_area: int = 20,
    max_regions: int = 20,
) -> list[dict[str, Any]]:
    """
    Find bounding boxes around suspicious regions.
    """

    num_labels, labels, stats, _ = (
        cv2.connectedComponentsWithStats(
            mask,
            connectivity=8,
        )
    )

    regions: list[
        dict[str, Any]
    ] = []

    for label in range(
        1,
        num_labels,
    ):

        x = int(
            stats[
                label,
                cv2.CC_STAT_LEFT,
            ]
        )

        y = int(
            stats[
                label,
                cv2.CC_STAT_TOP,
            ]
        )

        width = int(
            stats[
                label,
                cv2.CC_STAT_WIDTH,
            ]
        )

        height = int(
            stats[
                label,
                cv2.CC_STAT_HEIGHT,
            ]
        )

        area = int(
            stats[
                label,
                cv2.CC_STAT_AREA,
            ]
        )

        if area < min_area:
            continue

        regions.append(
            {
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "area": area,
            }
        )

    regions.sort(
        key=lambda item: item["area"],
        reverse=True,
    )

    return regions[
        :max_regions
    ]


# ============================================================
# HEATMAP
# ============================================================

def _generate_heatmap_png(
    ela_map: np.ndarray,
    suspicious_mask: np.ndarray,
) -> str:
    """
    Generate an ELA heatmap.

    Returns:
        Base64 encoded PNG.
    """

    # --------------------------------------------------------
    # Normalize ELA map
    # --------------------------------------------------------

    normalized = cv2.normalize(
        ela_map,
        None,
        0,
        255,
        cv2.NORM_MINMAX,
    )

    normalized = normalized.astype(
        np.uint8
    )

    # --------------------------------------------------------
    # Apply heatmap
    # --------------------------------------------------------

    heatmap = cv2.applyColorMap(
        normalized,
        cv2.COLORMAP_JET,
    )

    # --------------------------------------------------------
    # Create soft suspicious mask
    # --------------------------------------------------------

    soft_mask = cv2.GaussianBlur(
        suspicious_mask,
        (0, 0),
        sigmaX=3,
    )

    alpha = (
        soft_mask.astype(
            np.float32
        )
        / 255.0
    )

    alpha = alpha[
        :,
        :,
        np.newaxis,
    ]

    # --------------------------------------------------------
    # Make suspicious areas brighter
    # --------------------------------------------------------

    output = (
        heatmap.astype(
            np.float32
        )
        * (
            0.25
            + 0.75 * alpha
        )
    )

    output = np.clip(
        output,
        0,
        255,
    ).astype(
        np.uint8
    )

    # --------------------------------------------------------
    # Encode PNG
    # --------------------------------------------------------

    success, encoded = cv2.imencode(
        ".png",
        output,
    )

    if not success:
        raise ValueError(
            "Unable to encode ELA heatmap."
        )

    # --------------------------------------------------------
    # Base64
    # --------------------------------------------------------

    return base64.b64encode(
        encoded.tobytes()
    ).decode(
        "utf-8"
    )


# ============================================================
# SCORE
# ============================================================

def _calculate_score(
    suspicious_fraction: float,
) -> float:
    """
    Calculate ELA anomaly score from 0 to 100.

    This is an anomaly/evidence score.

    It is NOT a calibrated probability of forgery.
    """

    score = (
        suspicious_fraction * 100.0
    )

    return float(
        np.clip(
            score,
            0.0,
            100.0,
        )
    )


# ============================================================
# MAIN ELA ANALYSIS
# ============================================================

def analyze_ela(
    image_source: str | Path | bytes | bytearray,
    quality: int = 90,
    sensitivity: float = 3.0,
    border_ratio: float = 0.02,
    min_region_area: int = 20,
) -> dict[str, Any]:
    """
    Perform Error Level Analysis.

    Supports:

        analyze_ela("document.jpg")

    and:

        analyze_ela(image_bytes)
    """

    try:

        # ====================================================
        # 1. LOAD ORIGINAL
        # ====================================================

        original = _load_image(
            image_source
        )

        height, width = (
            original.shape[:2]
        )

        # ====================================================
        # 2. JPEG RE-COMPRESSION
        # ====================================================

        recompressed = _recompress_image(
            original,
            quality=quality,
        )

        # ====================================================
        # 3. ELA MAP
        # ====================================================

        ela_map = _calculate_ela_map(
            original,
            recompressed,
        )

        # ====================================================
        # 4. CALCULATE THRESHOLD
        #
        # Use the inner document area for calculating
        # statistics, but KEEP the final mask full-size.
        # ====================================================

        border_y, border_x = _get_border(
            ela_map.shape,
            border_ratio,
        )

        if (
            border_y > 0
            and border_x > 0
            and border_y * 2 < height
            and border_x * 2 < width
        ):

            analysis_map = ela_map[
                border_y:height - border_y,
                border_x:width - border_x,
            ]

        else:

            analysis_map = ela_map

        # ====================================================
        # 5. THRESHOLD
        # ====================================================

        threshold = _robust_threshold(
            analysis_map,
            sensitivity=sensitivity,
        )

        # ====================================================
        # 6. FULL-SIZE MASK
        # ====================================================

        mask = _create_suspicious_mask(
            ela_map,
            threshold,
            border_ratio=border_ratio,
        )

        # ====================================================
        # 7. CLEAN MASK
        # ====================================================

        mask = _clean_mask(
            mask,
            min_area=min_region_area,
        )

        # ====================================================
        # 8. FIND REGIONS
        # ====================================================

        regions = _find_suspicious_regions(
            mask,
            min_area=min_region_area,
        )

        # ====================================================
        # 9. STATISTICS
        # ====================================================

        # Use the same inner area that was used for
        # threshold calculation.

        if analysis_map.size == 0:

            suspicious_pixels = 0

            suspicious_fraction = 0.0

        else:

            # Crop the cleaned full-size mask to the
            # same dimensions as analysis_map.

            if (
                border_y > 0
                and border_x > 0
                and border_y * 2 < height
                and border_x * 2 < width
            ):

                analysis_mask = mask[
                    border_y:height - border_y,
                    border_x:width - border_x,
                ]

            else:

                analysis_mask = mask

            suspicious_pixels = int(
                np.count_nonzero(
                    analysis_mask
                )
            )

            suspicious_fraction = (
                suspicious_pixels
                / analysis_map.size
            )

        # ====================================================
        # 10. ERROR STATISTICS
        # ====================================================

        mean_error = float(
            np.mean(analysis_map)
        )

        median_error = float(
            np.median(analysis_map)
        )

        max_error = float(
            np.max(analysis_map)
        )

        # ====================================================
        # 11. SCORE
        # ====================================================

        score = _calculate_score(
            suspicious_fraction
        )

        # ====================================================
        # 12. INTERPRETATION
        # ====================================================

        if score < 1.0:

            interpretation = (
                "low_ela_anomaly"
            )

        elif score < 5.0:

            interpretation = (
                "moderate_ela_anomaly"
            )

        else:

            interpretation = (
                "high_ela_anomaly"
            )

        # ====================================================
        # 13. HEATMAP
        # ====================================================

        heatmap_png = (
            _generate_heatmap_png(
                ela_map,
                mask,
            )
        )

        # ====================================================
        # 14. RETURN
        # ====================================================

        return {
            "success": True,

            "method": "ELA",

            "score": round(
                score,
                4,
            ),

            "signal": round(
                score,
                4,
            ),

            "image_width": width,

            "image_height": height,

            "jpeg_quality": quality,

            "sensitivity": sensitivity,

            "threshold": round(
                threshold,
                6,
            ),

            "mean_error": round(
                mean_error,
                6,
            ),

            "median_error": round(
                median_error,
                6,
            ),

            "max_error": round(
                max_error,
                6,
            ),

            "suspicious_pixels": (
                suspicious_pixels
            ),

            "total_pixels": int(
                analysis_map.size
            ),

            "suspicious_fraction": round(
                suspicious_fraction,
                6,
            ),

            "interpretation": (
                interpretation
            ),

            "region_count": len(
                regions
            ),

            "regions": regions,

            "heatmap_png": heatmap_png,

            # Internal arrays.
            "ela_map": ela_map,

            "suspicious_mask": mask,
        }

    except Exception as exc:

        return {
            "success": False,

            "method": "ELA",

            "score": 0.0,

            "signal": 0.0,

            "suspicious_fraction": 0.0,

            "heatmap_png": None,

            "region_count": 0,

            "regions": [],

            "interpretation": (
                "analysis_failed"
            ),

            "error": str(exc),
        }


# ============================================================
# SIMPLE SCORE ACCESSOR
# ============================================================

def get_ela_signal(
    image_source: str | Path | bytes | bytearray,
) -> float:
    """
    Return only the ELA score.
    """

    result = analyze_ela(
        image_source
    )

    return float(
        result.get(
            "score",
            0.0,
        )
    )


# ============================================================
# PUBLIC EXPORTS
# ============================================================

__all__ = [
    "analyze_ela",
    "get_ela_signal",
]