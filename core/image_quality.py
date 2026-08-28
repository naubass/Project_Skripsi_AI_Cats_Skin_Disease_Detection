"""
core/image_quality.py — Validasi kualitas gambar sebelum diproses model AI.
Deteksi blur (Variance of Laplacian) dan pencahayaan (Mean Luminance).
"""

import cv2
import numpy as np

BLUR_THRESHOLD = 100.0
DARK_THRESHOLD = 40.0
BRIGHT_THRESHOLD = 220.0


def _bytes_to_cv2_image(image_bytes: bytes):
    np_arr = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)


def check_blur(image_bytes: bytes):
    """Return (is_blur, variance_laplacian)."""
    img = _bytes_to_cv2_image(image_bytes)
    if img is None:
        return False, 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return variance < BLUR_THRESHOLD, variance


def check_brightness(image_bytes: bytes):
    """Return (status, mean_intensity). status: 'gelap' | 'terang' | 'normal'."""
    img = _bytes_to_cv2_image(image_bytes)
    if img is None:
        return "normal", 128.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean_val = float(np.mean(gray))
    if mean_val < DARK_THRESHOLD:
        return "gelap", mean_val
    elif mean_val > BRIGHT_THRESHOLD:
        return "terang", mean_val
    return "normal", mean_val


def validate_image_quality(image_bytes: bytes) -> dict:
    """
    Validasi lengkap kualitas gambar sebelum masuk ke model.
    Return dict: {"valid": bool, "reason": str|None, "message": str|None, "details": {...}}
    """
    is_blur, blur_var = check_blur(image_bytes)
    brightness_status, brightness_val = check_brightness(image_bytes)

    details = {
        "blur_variance": round(blur_var, 2),
        "brightness_mean": round(brightness_val, 2),
    }

    if is_blur:
        return {
            "valid": False,
            "reason": "blur",
            "message": "Gambar terdeteksi buram/blur. Pastikan kamera fokus dan tangan tidak bergetar saat memotret, lalu unggah ulang.",
            "details": details,
        }

    if brightness_status == "gelap":
        return {
            "valid": False,
            "reason": "gelap",
            "message": "Pencahayaan gambar terlalu gelap sehingga detail kulit kucing tidak terlihat jelas. Silakan foto ulang di tempat yang lebih terang.",
            "details": details,
        }

    if brightness_status == "terang":
        return {
            "valid": False,
            "reason": "terang",
            "message": "Pencahayaan gambar terlalu terang/overexposed sehingga detail kulit kucing tidak terlihat jelas. Silakan foto ulang dengan pencahayaan yang lebih seimbang.",
            "details": details,
        }

    return {"valid": True, "reason": None, "message": None, "details": details}