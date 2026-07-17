"""
controllers/home_controller.py — Route utama untuk user biasa:
halaman analisis (index), submit prediksi, ambil gambar hasil prediksi,
dan halaman riwayat.
"""

from datetime import datetime

import numpy as np
from fastapi import APIRouter, Request, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from database import (
    get_db, get_disease_info_dict, log_activity,
    get_clinic_info, get_doctor_notes_for_predictions,
)
from core.state import templates
from core.dependencies import get_current_user
from core.model import preprocess_image, predict_tflite, CLASS_NAMES

router = APIRouter(tags=["home"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@router.post("/predict")
async def predict(request: Request, file: UploadFile = File(...)):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu.")
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File harus berupa gambar.")

    disease_info = get_disease_info_dict()

    image_bytes = await file.read()
    img_array   = preprocess_image(image_bytes)
    probs       = predict_tflite(img_array)
    idx         = int(np.argmax(probs))
    predicted_key = CLASS_NAMES[idx]
    confidence    = float(probs[idx]) * 100
    info          = disease_info.get(predicted_key, {
        "emoji": "❓", "label": predicted_key, "color": "#888888",
        "description": "Informasi tidak tersedia.", "advice": []
    })

    all_probs = [
        {
            "class": CLASS_NAMES[i],
            "label": disease_info.get(CLASS_NAMES[i], {}).get("label", CLASS_NAMES[i]),
            "prob": round(float(probs[i]) * 100, 2),
            "color": disease_info.get(CLASS_NAMES[i], {}).get("color", "#888888"),
        }
        for i in range(len(CLASS_NAMES))
    ]
    all_probs.sort(key=lambda x: x["prob"], reverse=True)

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """INSERT INTO predictions
            (user_id, predicted_class, label, confidence, description, image_data, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (user["id"], predicted_key, info["label"], round(confidence, 2),
             info["description"], image_bytes, datetime.now())
        )
        db.commit()
        prediction_id = cursor.lastrowid
        cursor.close()
        db.close()
        log_activity(user["id"], "predict", f"Hasil: {info['label']} ({round(confidence,1)}%)")
    except Exception as e:
        print(f"Warning: Gagal menyimpan ke DB: {e}")
        prediction_id = None

    return JSONResponse({
        "predicted_class": predicted_key, "label": info["label"], "emoji": info["emoji"],
        "color": info["color"], "confidence": round(confidence, 2), "description": info["description"],
        "advice": info["advice"], "all_probs": all_probs, "prediction_id": prediction_id,
    })


@router.get("/predictions/{prediction_id}/image")
async def get_prediction_image(request: Request, prediction_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        if user["role"] in ("dokter", "admin"):
            cursor.execute("SELECT image_data FROM predictions WHERE id = %s", (prediction_id,))
        else:
            cursor.execute(
                "SELECT image_data FROM predictions WHERE id = %s AND user_id = %s",
                (prediction_id, user["id"])
            )
        row = cursor.fetchone()
    finally:
        cursor.close()
        db.close()

    if not row or not row["image_data"]:
        raise HTTPException(status_code=404, detail="Gambar tidak ditemukan.")

    return Response(content=row["image_data"], media_type="image/jpeg")


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, predicted_class, label, confidence, description, created_at, visit_confirmed FROM predictions WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
            (user["id"],)
        )
        records = cursor.fetchall()
        disease_info = get_disease_info_dict()
        for r in records:
            info = disease_info.get(r["predicted_class"], {})
            r["emoji"] = info.get("emoji", "❓")
            r["color"] = info.get("color", "#888")
            r["advice"] = info.get("advice", [])
    finally:
        cursor.close()
        db.close()

    notes_map = get_doctor_notes_for_predictions([r["id"] for r in records])
    for r in records:
        notes = notes_map.get(r["id"], [])
        r["doctor_notes"] = notes
        r["need_visit"] = any(n["need_visit"] for n in notes)

    return templates.TemplateResponse("history.html", {
        "request": request, "user": user, "records": records,
        "clinic": get_clinic_info(),
    })