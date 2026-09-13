from __future__ import annotations
import base64
from pathlib import Path
from typing import Any
import cv2
import numpy as np
from .copy_move import analyze_copy_move
from .ela import analyze_ela
from .text_forensics import analyze_text_forensics
from .metadata import analyze_metadata
from .aadhaar.panel_detector import detect_aadhaar_panels
from .aadhaar.region_detector import detect_aadhaar_regions

def _heatmap_file(heatmap_png: str | None, output_path: str | Path) -> str:
    if not heatmap_png:
        raise ValueError("ELA did not return heatmap data")
    encoded = heatmap_png
    if "," in encoded and encoded.startswith("data:"):
        encoded = encoded.split(",", 1)[1]
    data = base64.b64decode(encoded, validate=True)
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("ELA heatmap data is not a valid image")
    red_mask = (image[:, :, 2] > image[:, :, 1] * 1.25) & (image[:, :, 2] > image[:, :, 0] * 1.25)
    image[red_mask] = (0, 0, 255)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)
    return str(path)

def _load_image(source: str | Path | bytes | bytearray) -> np.ndarray:
    if isinstance(source, (bytes, bytearray)):
        return cv2.imdecode(np.frombuffer(source, np.uint8), cv2.IMREAD_COLOR)
    return cv2.imread(str(source), cv2.IMREAD_COLOR)

def _encode_jpeg(image: np.ndarray) -> bytes:
    success, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not success:
        raise ValueError("Unable to encode region image.")
    return encoded.tobytes()

def _analyze_single_region(region_name: str, region_image: np.ndarray, side: str) -> dict[str, Any]:
    if region_image is None or region_image.size == 0:
        return {"success": False, "score": 0.0, "regions": [], "error": "Image unavailable"}

    region_bytes = _encode_jpeg(region_image)
    try: ela_res = analyze_ela(region_bytes)
    except: ela_res = {"success": False, "score": 0.0, "regions": []}
    try: cm_res = analyze_copy_move(region_bytes)
    except: cm_res = {"success": False, "score": 0.0, "regions": []}
    try: tx_res = analyze_text_forensics(region_bytes)
    except: tx_res = {"success": False, "score": 0.0, "regions": []}
    try: md_res = analyze_metadata(region_bytes)
    except: md_res = {"success": False, "score": 0.0, "regions": []}

    e_s = float(ela_res.get("score", 0.0))
    c_s = float(cm_res.get("score", 0.0))
    t_s = float(tx_res.get("score", 0.0))
    m_s = float(md_res.get("score", 0.0))

    score = round(np.clip(e_s * 0.35 + c_s * 0.30 + t_s * 0.25 + m_s * 0.10, 0, 100), 2)

    suspicious = []
    for name, res in [("ELA", ela_res), ("COPY_MOVE", cm_res), ("TEXT", tx_res)]:
        for reg in res.get("regions", []):
            suspicious.append({"side": side, "document_region": region_name, "detector": name, "region": reg})

    return {"success": True, "score": score, "suspicious_regions": suspicious}

def detect_physical_tempering(image_source: str | Path | bytes | bytearray, heatmap_path: str | Path = "physical_heatmap.png") -> dict[str, Any]:
    try:
        original_image = _load_image(image_source)
        if original_image is None: raise ValueError("Could not load image")

        # Aadhaar Panel detection
        if isinstance(image_source, (bytes, bytearray)):
            img_bytes = bytes(image_source)
        else:
            img_bytes = Path(image_source).read_bytes()

        panels = detect_aadhaar_panels(img_bytes)
        if not panels.get("success"): raise ValueError(panels.get("error", "Panel detection failed"))

        front_panel = panels["panels"]["front"]
        back_panel = panels["panels"].get("back")

        # Region detection
        detected = detect_aadhaar_regions(front_panel, back_panel)
        if not detected.get("success"): raise ValueError(detected.get("error", "Region detection failed"))

        all_region_results = {}
        # Process Front
        for name, data in detected["front"].get("regions", {}).items():
            box = data.get("box")
            if not box: continue
            crop = original_image[box["y"]:box["y"]+box["height"], box["x"]:box["x"]+box["width"]]
            all_region_results[name] = _analyze_single_region(name, crop, "front")

        # Process Back
        if back_panel is not None:
            for name, data in detected["back"].get("regions", {}).items():
                box = data.get("box")
                if not box: continue
                # Note: this assumes back_panel is already cropped from original_image.
                # For simplicity and to match existing code, we use the cropped panels provided by detect_aadhaar_panels.
                # However, to be safe we use the panel itself for cropping.
                crop = back_panel[box["y"]:box["y"]+box["height"], box["x"]:box["x"]+box["width"]]
                all_region_results[name] = _analyze_single_region(name, crop, "back")

        # Probability Calculation (Weighted Average of existing regions)
        scores = [r["score"] for r in all_region_results.values() if r["success"]]
        probability = round(np.mean(scores), 2) if scores else 0.0

        suspicious_regions = []
        for r in all_region_results.values():
            if r["success"]: suspicious_regions.extend(r["suspicious_regions"])

        # Heatmap from global ELA
        ela_global = analyze_ela(image_source)
        h_path = _heatmap_file(ela_global.get("heatmap_png"), heatmap_path) if ela_global.get("success") else None

        return {
            "success": True,
            "tempering_probability": probability,
            # "tempering_regions": suspicious_regions,
            "heatmap_path": h_path,
        }
    except Exception as exc:
        return {"success": False, "tempering_probability": None, "tempering_regions": [], "heatmap_path": None, "error": str(exc)}
