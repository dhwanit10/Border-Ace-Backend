from __future__ import annotations

from typing import Any

import cv2
import numpy as np

import zxingcpp


def _prepare_variants(
    image: np.ndarray,
) -> list[tuple[str, np.ndarray]]:
    """
    Generate QR decoding variants.

    These transformations are intended to improve
    decoding robustness. They do not establish
    document authenticity.
    """

    variants = []

    # -----------------------------------------------------
    # Original
    # -----------------------------------------------------

    variants.append(
        ("original", image)
    )

    # -----------------------------------------------------
    # Grayscale
    # -----------------------------------------------------

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    variants.append(
        ("grayscale", gray)
    )

    # -----------------------------------------------------
    # CLAHE
    # -----------------------------------------------------

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )

    enhanced = clahe.apply(
        gray
    )

    variants.append(
        ("clahe", enhanced)
    )

    # -----------------------------------------------------
    # Gaussian blur
    # -----------------------------------------------------

    blurred = cv2.GaussianBlur(
        enhanced,
        (3, 3),
        0,
    )

    variants.append(
        ("blurred", blurred)
    )

    # -----------------------------------------------------
    # Sharpen
    # -----------------------------------------------------

    sharpen_kernel = np.array(
        [
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0],
        ],
        dtype=np.float32,
    )

    sharpened = cv2.filter2D(
        enhanced,
        -1,
        sharpen_kernel,
    )

    variants.append(
        ("sharpened", sharpened)
    )

    # -----------------------------------------------------
    # Otsu
    # -----------------------------------------------------

    _, otsu = cv2.threshold(
        enhanced,
        0,
        255,
        cv2.THRESH_BINARY
        + cv2.THRESH_OTSU,
    )

    variants.append(
        ("otsu", otsu)
    )

    # -----------------------------------------------------
    # Adaptive threshold
    # -----------------------------------------------------

    adaptive = cv2.adaptiveThreshold(
        enhanced,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        7,
    )

    variants.append(
        ("adaptive", adaptive)
    )

    # -----------------------------------------------------
    # Upscaling
    # -----------------------------------------------------

    for scale in (
        1.5,
        2.0,
        3.0,
    ):

        upscaled = cv2.resize(
            enhanced,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )

        variants.append(
            (
                f"upscaled_{scale}",
                upscaled,
            )
        )

    return variants


def _opencv_decode(
    image: np.ndarray,
) -> dict[str, Any] | None:

    detector = cv2.QRCodeDetector()

    try:

        data, points, _ = (
            detector.detectAndDecode(
                image
            )
        )

        if data:

            return {
                "payload": data,
                "points": (
                    points.tolist()
                    if points is not None
                    else None
                ),
                "decoder": "opencv",
            }

    except Exception:
        pass

    return None


def _zxing_decode(
    image: np.ndarray,
) -> dict[str, Any] | None:

    try:

        # ZXing-C++ works with NumPy arrays.
        results = zxingcpp.read_barcodes(
            image
        )

        if not results:

            return None

        for barcode in results:

            if not barcode.text:

                continue

            position = None

            try:

                position = {
                    "top_left": [
                        barcode.position.top_left.x,
                        barcode.position.top_left.y,
                    ],
                    "top_right": [
                        barcode.position.top_right.x,
                        barcode.position.top_right.y,
                    ],
                    "bottom_right": [
                        barcode.position.bottom_right.x,
                        barcode.position.bottom_right.y,
                    ],
                    "bottom_left": [
                        barcode.position.bottom_left.x,
                        barcode.position.bottom_left.y,
                    ],
                }

            except Exception:
                position = None

            return {
                "payload": barcode.text,
                "points": position,
                "decoder": "zxing_cpp",
                "format": str(
                    barcode.format
                ),
            }

    except Exception:
        pass

    return None


def decode_aadhaar_qr(
    image: np.ndarray,
) -> dict[str, Any]:

    """
    Decode an already-localized Aadhaar QR.

    Decoder order:
        1. OpenCV
        2. ZXing-C++

    Successful decoding does NOT mean the QR or Aadhaar
    is authentic.

    Cryptographic verification is a separate stage.
    """

    result: dict[str, Any] = {

        "success": False,

        "qr_detected": False,

        "qr_decoded": False,

        "payload": None,

        "points": None,

        "method": None,

        "format": None,

        "payload_length": 0,

        "variants_tried": 0,

        "error": None,
    }

    try:

        if image is None:

            raise ValueError(
                "QR image is None"
            )

        if image.size == 0:

            raise ValueError(
                "QR image is empty"
            )

        variants = _prepare_variants(
            image
        )

        result[
            "variants_tried"
        ] = len(variants)

        # =================================================
        # Try OpenCV
        # =================================================

        for method, variant in variants:

            decoded = _opencv_decode(
                variant
            )

            if decoded is not None:

                payload = decoded[
                    "payload"
                ]

                result["success"] = True

                result[
                    "qr_detected"
                ] = True

                result[
                    "qr_decoded"
                ] = True

                result[
                    "payload"
                ] = payload

                result[
                    "payload_length"
                ] = len(payload)

                result[
                    "points"
                ] = decoded["points"]

                result[
                    "method"
                ] = (
                    "opencv_"
                    + method
                )

                return result

        # =================================================
        # Try ZXing-C++
        # =================================================

        for method, variant in variants:

            decoded = _zxing_decode(
                variant
            )

            if decoded is not None:

                payload = decoded[
                    "payload"
                ]

                result["success"] = True

                result[
                    "qr_detected"
                ] = True

                result[
                    "qr_decoded"
                ] = True

                result[
                    "payload"
                ] = payload

                result[
                    "payload_length"
                ] = len(payload)

                result[
                    "points"
                ] = decoded["points"]

                result[
                    "method"
                ] = (
                    "zxing_"
                    + method
                )

                result[
                    "format"
                ] = decoded.get(
                    "format"
                )

                return result

        return result

    except Exception as exc:

        result["error"] = str(exc)

        return result