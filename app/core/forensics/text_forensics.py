from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _load_image(
    image_source: str | Path | bytes | bytearray,
) -> np.ndarray:
    """
    Load an image from:
    - file path
    - bytes
    - bytearray
    """

    if isinstance(image_source, (str, Path)):
        image = cv2.imread(str(image_source))

    elif isinstance(image_source, (bytes, bytearray)):
        buffer = np.frombuffer(image_source, dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)

    else:
        raise TypeError(
            "image_source must be a file path, bytes, or bytearray"
        )

    if image is None:
        raise ValueError("Unable to decode image")

    return image


def _encode_png(image: np.ndarray) -> str:
    """
    Convert an OpenCV image to base64 PNG.
    """

    success, encoded = cv2.imencode(".png", image)

    if not success:
        raise ValueError("Unable to encode heatmap")

    return base64.b64encode(encoded.tobytes()).decode("utf-8")


def _detect_text_regions(
    image: np.ndarray,
) -> list[dict[str, Any]]:
    """
    Detect text-line-like regions using connected components.

    This intentionally uses a simple deterministic approach rather
    than relying on OCR or fragile contour heuristics.
    """

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Slight blur removes tiny image noise.
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Dark pixels become foreground.
    binary = cv2.threshold(
        gray,
        200,
        255,
        cv2.THRESH_BINARY_INV,
    )[1]

    # Connect characters belonging to the same text line.
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (12, 3),
    )

    connected = cv2.morphologyEx(
        binary,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=1,
    )

    # Small dilation makes individual characters form stable lines.
    connected = cv2.dilate(
        connected,
        cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (5, 2),
        ),
        iterations=1,
    )

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        connected,
        connectivity=8,
    )

    height, width = gray.shape

    regions: list[dict[str, Any]] = []

    for label in range(1, num_labels):

        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        w = int(stats[label, cv2.CC_STAT_WIDTH])
        h = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])

        # Ignore tiny noise.
        if area < 20:
            continue

        # Ignore extremely small components.
        if w < 8 or h < 3:
            continue

        # Ignore giant document/background regions.
        if w > width * 0.95 and h > height * 0.95:
            continue

        # Text lines are generally wider than they are tall.
        # But allow shorter words too.
        aspect_ratio = w / max(h, 1)

        if aspect_ratio < 1.2:
            continue

        # Prevent extremely tall non-text objects.
        if h > height * 0.15:
            continue

        regions.append(
            {
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "area": w * h,
                "aspect_ratio": round(aspect_ratio, 3),
            }
        )

    # Sort from top to bottom.
    regions.sort(
        key=lambda r: (r["y"], r["x"])
    )

    return regions


def _region_features(
    gray: np.ndarray,
    region: dict[str, Any],
) -> dict[str, float]:

    x = region["x"]
    y = region["y"]
    w = region["width"]
    h = region["height"]

    crop = gray[
        y:y + h,
        x:x + w,
    ]

    if crop.size == 0:
        return {
            "mean": 0.0,
            "std": 0.0,
            "edge_density": 0.0,
        }

    mean_value = float(np.mean(crop))
    std_value = float(np.std(crop))

    edges = cv2.Canny(
        crop,
        50,
        150,
    )

    edge_density = float(
        np.count_nonzero(edges) / crop.size
    )

    return {
        "mean": mean_value,
        "std": std_value,
        "edge_density": edge_density,
    }


def _calculate_inconsistency(
    features: list[dict[str, float]],
) -> float:

    if len(features) < 2:
        return 0.0

    std_values = np.array(
        [item["std"] for item in features],
        dtype=np.float32,
    )

    edge_values = np.array(
        [item["edge_density"] for item in features],
        dtype=np.float32,
    )

    std_mean = float(np.mean(std_values))
    edge_mean = float(np.mean(edge_values))

    if std_mean > 0:
        std_variation = float(
            np.std(std_values) / std_mean
        )
    else:
        std_variation = 0.0

    if edge_mean > 0:
        edge_variation = float(
            np.std(edge_values) / edge_mean
        )
    else:
        edge_variation = 0.0

    inconsistency = (
        0.6 * std_variation
        + 0.4 * edge_variation
    )

    return float(
        np.clip(
            inconsistency * 100.0,
            0.0,
            100.0,
        )
    )


def _find_suspicious_regions(
    regions: list[dict[str, Any]],
    features: list[dict[str, float]],
) -> list[dict[str, Any]]:

    if not regions:
        return []

    if len(features) != len(regions):
        return []

    std_values = np.array(
        [item["std"] for item in features],
        dtype=np.float32,
    )

    edge_values = np.array(
        [item["edge_density"] for item in features],
        dtype=np.float32,
    )

    std_median = float(np.median(std_values))
    edge_median = float(np.median(edge_values))

    suspicious = []

    for region, feature in zip(
        regions,
        features,
    ):

        std_difference = abs(
            feature["std"] - std_median
        )

        edge_difference = abs(
            feature["edge_density"] - edge_median
        )

        std_threshold = max(
            8.0,
            std_median * 0.45,
        )

        edge_threshold = max(
            0.015,
            edge_median * 0.50,
        )

        if (
            std_difference > std_threshold
            or edge_difference > edge_threshold
        ):

            suspicious_region = dict(region)

            suspicious_region["std"] = round(
                feature["std"],
                3,
            )

            suspicious_region["edge_density"] = round(
                feature["edge_density"],
                5,
            )

            suspicious.append(
                suspicious_region
            )

    return suspicious


def _generate_heatmap(
    image: np.ndarray,
    suspicious_regions: list[dict[str, Any]],
) -> str:

    overlay = image.copy()

    for region in suspicious_regions:

        x = region["x"]
        y = region["y"]
        w = region["width"]
        h = region["height"]

        cv2.rectangle(
            overlay,
            (x, y),
            (x + w, y + h),
            (0, 0, 255),
            3,
        )

    return _encode_png(overlay)


def analyze_text_forensics(
    image_source: str | Path | bytes | bytearray,
) -> dict[str, Any]:
    """
    Analyze text regions for visual inconsistency.

    Important:
    The returned score is a forensic evidence signal,
    NOT a calibrated probability that a document is forged.
    """

    try:

        image = _load_image(
            image_source
        )

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY,
        )

        regions = _detect_text_regions(
            image
        )

        features = [
            _region_features(
                gray,
                region,
            )
            for region in regions
        ]

        suspicious_regions = (
            _find_suspicious_regions(
                regions,
                features,
            )
        )

        inconsistency_score = (
            _calculate_inconsistency(
                features
            )
        )

        # Make the evidence score conservative.
        score = float(
            np.clip(
                inconsistency_score,
                0.0,
                100.0,
            )
        )

        if score >= 70:
            interpretation = (
                "strong_text_inconsistency"
            )

        elif score >= 40:
            interpretation = (
                "moderate_text_inconsistency"
            )

        elif score >= 15:
            interpretation = (
                "weak_text_inconsistency"
            )

        else:
            interpretation = (
                "low_text_inconsistency"
            )

        heatmap = _generate_heatmap(
            image,
            suspicious_regions,
        )

        output_regions = []

        for region, feature in zip(
            regions,
            features,
        ):

            item = dict(region)

            item["mean_intensity"] = round(
                feature["mean"],
                3,
            )

            item["std_intensity"] = round(
                feature["std"],
                3,
            )

            item["edge_density"] = round(
                feature["edge_density"],
                5,
            )

            output_regions.append(item)

        return {
            "success": True,
            "method": "TEXT_FORENSICS",
            "score": score,
            "signal": score,
            "region_count": len(regions),
            "suspicious_region_count": len(
                suspicious_regions
            ),
            "regions": output_regions,
            "suspicious_regions": suspicious_regions,
            "interpretation": interpretation,
            "heatmap_png": heatmap,
        }

    except Exception as exc:

        return {
            "success": False,
            "method": "TEXT_FORENSICS",
            "score": 0.0,
            "signal": 0.0,
            "region_count": 0,
            "suspicious_region_count": 0,
            "regions": [],
            "suspicious_regions": [],
            "interpretation": "analysis_failed",
            "heatmap_png": None,
            "error": str(exc),
        }


def get_text_forensics_signal(
    image_source: str | Path | bytes | bytearray,
) -> float:

    result = analyze_text_forensics(
        image_source
    )

    return float(
        result.get(
            "score",
            0.0,
        )
    )