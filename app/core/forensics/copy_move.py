# app/core/forensics/copy_move.py

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


# ============================================================
# IMAGE LOADING
# ============================================================

def _load_image(
    image_source: str | bytes | bytearray,
) -> np.ndarray:
    """
    Load an image from a file path or image bytes.
    """

    if isinstance(
        image_source,
        (bytes, bytearray),
    ):
        buffer = np.frombuffer(
            image_source,
            dtype=np.uint8,
        )

        image = cv2.imdecode(
            buffer,
            cv2.IMREAD_COLOR,
        )

        if image is None:
            raise ValueError(
                "Unable to decode image bytes."
            )

        return image

    image = cv2.imread(
        str(image_source),
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise ValueError(
            f"Unable to read image: {image_source}"
        )

    return image


# ============================================================
# FEATURE DETECTOR
# ============================================================

def _create_orb(
    max_features: int = 4000,
) -> cv2.ORB:
    """
    Create ORB feature detector.
    """

    return cv2.ORB_create(
        nfeatures=max_features,
        scaleFactor=1.2,
        nlevels=8,
        edgeThreshold=31,
        firstLevel=0,
        WTA_K=2,
        scoreType=cv2.ORB_HARRIS_SCORE,
        patchSize=31,
        fastThreshold=10,
    )


# ============================================================
# FEATURE EXTRACTION
# ============================================================

def _extract_features(
    image: np.ndarray,
    max_features: int = 4000,
) -> tuple[
    list[cv2.KeyPoint],
    np.ndarray | None,
]:
    """
    Extract ORB keypoints and descriptors.
    """

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    orb = _create_orb(
        max_features=max_features
    )

    keypoints, descriptors = (
        orb.detectAndCompute(
            gray,
            None,
        )
    )

    return keypoints, descriptors


# ============================================================
# SELF MATCHING
# ============================================================

def _find_duplicate_matches(
    descriptors: np.ndarray,
    keypoints: list[cv2.KeyPoint],
    ratio_threshold: float = 0.72,
    min_spatial_distance: float = 30.0,
) -> list[tuple[cv2.DMatch, cv2.DMatch]]:
    """
    Find potentially duplicated feature locations within
    the same document.

    We use KNN matching and reject:
        - weak matches
        - features matching themselves
        - features that are too close spatially
    """

    if descriptors is None:
        return []

    if len(descriptors) < 3:
        return []

    matcher = cv2.BFMatcher(
        cv2.NORM_HAMMING,
        crossCheck=False,
    )

    matches = matcher.knnMatch(
        descriptors,
        descriptors,
        k=3,
    )

    duplicate_matches = []

    for candidates in matches:

        if len(candidates) < 2:
            continue

        best = candidates[0]

        second = candidates[1]

        # Ignore exact self-match.
        if best.queryIdx == best.trainIdx:
            candidates = [
                m
                for m in candidates
                if m.queryIdx != m.trainIdx
            ]

            if len(candidates) < 2:
                continue

            best = candidates[0]
            second = candidates[1]

        # Lowe ratio test.
        if second.distance <= 0:
            continue

        ratio = (
            best.distance
            / second.distance
        )

        if ratio > ratio_threshold:
            continue

        point1 = np.array(
            keypoints[
                best.queryIdx
            ].pt,
            dtype=np.float32,
        )

        point2 = np.array(
            keypoints[
                best.trainIdx
            ].pt,
            dtype=np.float32,
        )

        distance = float(
            np.linalg.norm(
                point1 - point2
            )
        )

        # Ignore nearby points. Copy-move should involve
        # spatially separated locations.
        if distance < min_spatial_distance:
            continue

        duplicate_matches.append(
            (best, second)
        )

    return duplicate_matches


# ============================================================
# BETTER SELF MATCHING
# ============================================================

def _collect_candidate_pairs(
    descriptors: np.ndarray,
    keypoints: list[cv2.KeyPoint],
    ratio_threshold: float = 0.75,
    min_spatial_distance: float = 40.0,
) -> list[cv2.DMatch]:
    """
    Collect candidate duplicate matches.

    Uses the second-best descriptor to perform a
    conservative ratio test.
    """

    if descriptors is None:
        return []

    if len(descriptors) < 4:
        return []

    matcher = cv2.BFMatcher(
        cv2.NORM_HAMMING,
        crossCheck=False,
    )

    raw_matches = matcher.knnMatch(
        descriptors,
        descriptors,
        k=4,
    )

    candidates: list[
        cv2.DMatch
    ] = []

    for group in raw_matches:

        # Remove self-match.
        group = [
            m
            for m in group
            if m.queryIdx != m.trainIdx
        ]

        if len(group) < 2:
            continue

        group.sort(
            key=lambda m: m.distance
        )

        best = group[0]
        second = group[1]

        if second.distance <= 0:
            continue

        ratio = (
            best.distance
            / second.distance
        )

        if ratio > ratio_threshold:
            continue

        p1 = np.array(
            keypoints[
                best.queryIdx
            ].pt,
            dtype=np.float32,
        )

        p2 = np.array(
            keypoints[
                best.trainIdx
            ].pt,
            dtype=np.float32,
        )

        spatial_distance = float(
            np.linalg.norm(
                p1 - p2
            )
        )

        if (
            spatial_distance
            < min_spatial_distance
        ):
            continue

        candidates.append(
            best
        )

    return candidates


# ============================================================
# RANSAC VERIFICATION
# ============================================================

def _verify_with_ransac(
    matches: list[cv2.DMatch],
    keypoints: list[cv2.KeyPoint],
    reprojection_threshold: float = 5.0,
) -> tuple[
    int,
    np.ndarray | None,
]:
    """
    Verify duplicate matches using a geometric transform.

    RANSAC helps reject random feature matches.
    """

    if len(matches) < 4:
        return 0, None

    source_points = np.float32(
        [
            keypoints[
                m.queryIdx
            ].pt
            for m in matches
        ]
    ).reshape(
        -1,
        1,
        2,
    )

    destination_points = np.float32(
        [
            keypoints[
                m.trainIdx
            ].pt
            for m in matches
        ]
    ).reshape(
        -1,
        1,
        2,
    )

    # Estimate affine transformation.
    matrix, inlier_mask = (
        cv2.estimateAffinePartial2D(
            source_points,
            destination_points,
            method=cv2.RANSAC,
            ransacReprojThreshold=(
                reprojection_threshold
            ),
            maxIters=3000,
            confidence=0.99,
        )
    )

    if matrix is None:
        return 0, None

    if inlier_mask is None:
        return 0, None

    inlier_mask = (
        inlier_mask.ravel()
        .astype(bool)
    )

    inlier_count = int(
        np.count_nonzero(
            inlier_mask
        )
    )

    return (
        inlier_count,
        inlier_mask,
    )


# ============================================================
# DUPLICATE REGIONS
# ============================================================

def _build_regions(
    matches: list[cv2.DMatch],
    inlier_mask: np.ndarray | None,
    keypoints: list[cv2.KeyPoint],
    image_shape: tuple[int, ...],
) -> list[dict[str, Any]]:
    """
    Convert RANSAC inliers into suspicious bounding boxes.
    """

    if (
        inlier_mask is None
        or len(matches) == 0
    ):
        return []

    height, width = (
        image_shape[:2]
    )

    points_a = []
    points_b = []

    for index, match in enumerate(
        matches
    ):

        if not inlier_mask[index]:
            continue

        points_a.append(
            keypoints[
                match.queryIdx
            ].pt
        )

        points_b.append(
            keypoints[
                match.trainIdx
            ].pt
        )

    if len(points_a) < 4:
        return []

    def make_box(
        points: list[tuple[float, float]],
    ) -> dict[str, Any]:

        xs = [
            p[0]
            for p in points
        ]

        ys = [
            p[1]
            for p in points
        ]

        x1 = max(
            0,
            int(min(xs)),
        )

        y1 = max(
            0,
            int(min(ys)),
        )

        x2 = min(
            width - 1,
            int(max(xs)),
        )

        y2 = min(
            height - 1,
            int(max(ys)),
        )

        return {
            "x": x1,
            "y": y1,
            "width": max(
                1,
                x2 - x1,
            ),
            "height": max(
                1,
                y2 - y1,
            ),
            "area": max(
                1,
                (x2 - x1)
                * (y2 - y1),
            ),
        }

    return [
        {
            "source": make_box(
                points_a
            ),
            "duplicate": make_box(
                points_b
            ),
            "match_count": len(
                points_a
            ),
        }
    ]


# ============================================================
# SCORE
# ============================================================

def _calculate_score(
    inlier_count: int,
    keypoint_count: int,
) -> float:
    """
    Calculate a 0-100 copy-move evidence score.

    This is an anomaly score, NOT a probability of forgery.
    """

    if keypoint_count <= 0:
        return 0.0

    # A handful of verified duplicate features should
    # produce a small signal. More verified matches
    # increase the signal progressively.
    raw_score = (
        inlier_count
        / max(
            1,
            keypoint_count * 0.02,
        )
    ) * 100.0

    return float(
        np.clip(
            raw_score,
            0.0,
            100.0,
        )
    )


# ============================================================
# MAIN COPY-MOVE ANALYSIS
# ============================================================

def analyze_copy_move(
    image_source: str | bytes | bytearray,
    max_features: int = 4000,
    ratio_threshold: float = 0.75,
    min_spatial_distance: float = 150.0,
    reprojection_threshold: float = 5.0,
) -> dict[str, Any]:
    """
    Detect possible copy-move manipulation.

    Workflow:

        Image
          ↓
        ORB features
          ↓
        Self matching
          ↓
        Spatial filtering
          ↓
        RANSAC
          ↓
        Verified duplicate regions
    """

    try:

        # ====================================================
        # 1. LOAD IMAGE
        # ====================================================

        image = _load_image(
            image_source
        )

        # ====================================================
        # 2. EXTRACT FEATURES
        # ====================================================

        keypoints, descriptors = (
            _extract_features(
                image,
                max_features=max_features,
            )
        )

        keypoint_count = len(
            keypoints
        )

        # ====================================================
        # 3. CHECK FEATURE COUNT
        # ====================================================

        if (
            descriptors is None
            or keypoint_count < 4
        ):

            return {
                "success": True,
                "method": "COPY_MOVE",
                "score": 0.0,
                "signal": 0.0,
                "keypoint_count": (
                    keypoint_count
                ),
                "candidate_match_count": 0,
                "inlier_count": 0,
                "regions": [],
                "region_count": 0,
                "interpretation": (
                    "insufficient_features"
                ),
            }

        # ====================================================
        # 4. FIND CANDIDATE DUPLICATES
        # ====================================================

        matches = _collect_candidate_pairs(
            descriptors,
            keypoints,
            ratio_threshold=ratio_threshold,
            min_spatial_distance=(
                min_spatial_distance
            ),
        )

        candidate_count = len(
            matches
        )

        # ====================================================
        # 5. RANSAC
        # ====================================================

        inlier_count, inlier_mask = (
            _verify_with_ransac(
                matches,
                keypoints,
                reprojection_threshold=(
                    reprojection_threshold
                ),
            )
        )

        # ====================================================
        # 6. BUILD REGIONS
        # ====================================================

        regions = _build_regions(
            matches,
            inlier_mask,
            keypoints,
            image.shape,
        )

        # ====================================================
        # 7. SCORE
        # ====================================================

        score = _calculate_score(
            inlier_count,
            keypoint_count,
        )

        # ====================================================
        # 8. INTERPRETATION
        # ====================================================

        if inlier_count < 5:

            interpretation = (
                "no_strong_copy_move_evidence"
            )

        elif inlier_count < 15:

            interpretation = (
                "weak_copy_move_evidence"
            )

        elif inlier_count < 30:

            interpretation = (
                "moderate_copy_move_evidence"
            )

        else:

            interpretation = (
                "strong_copy_move_evidence"
            )

        # ====================================================
        # 9. RETURN
        # ====================================================

        return {
            "success": True,

            "method": "COPY_MOVE",

            "score": round(
                score,
                4,
            ),

            "signal": round(
                score,
                4,
            ),

            "keypoint_count": (
                keypoint_count
            ),

            "candidate_match_count": (
                candidate_count
            ),

            "inlier_count": (
                inlier_count
            ),

            "region_count": len(
                regions
            ),

            "regions": regions,

            "interpretation": (
                interpretation
            ),
        }

    except Exception as exc:

        return {
            "success": False,

            "method": "COPY_MOVE",

            "score": 0.0,

            "signal": 0.0,

            "keypoint_count": 0,

            "candidate_match_count": 0,

            "inlier_count": 0,

            "region_count": 0,

            "regions": [],

            "interpretation": (
                "analysis_failed"
            ),

            "error": str(exc),
        }


# ============================================================
# SIMPLE SIGNAL FUNCTION
# ============================================================

def get_copy_move_signal(
    image_source: str | bytes | bytearray,
) -> float:
    """
    Return only the copy-move evidence score.
    """

    result = analyze_copy_move(
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
    "analyze_copy_move",
    "get_copy_move_signal",
]