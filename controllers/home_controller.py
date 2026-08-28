"""
controllers/home_controller.py — Route utama untuk user biasa:
halaman analisis (index), submit prediksi, ambil gambar hasil prediksi,
dan halaman riwayat.
"""

from datetime import datetime

import numpy as np
from fastapi import APIRouter, Request, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
import math

from database import (
    get_db, get_disease_info_dict, log_activity,
    get_clinic_info, get_doctor_notes_for_predictions,
    get_booked_slots, save_user_booking, cancel_user_booking, auto_update_expired_visits,
    save_user_booking, save_telemed_request, get_pets_by_user
)
from core.state import templates
from core.dependencies import get_current_user
from core.image_quality import validate_image_quality
from core.model import preprocess_image, predict_tflite, CLASS_NAMES

router = APIRouter(tags=["home"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    pets = get_pets_by_user(user["id"])
    return templates.TemplateResponse("index.html", {"request": request, "user": user, "pets": pets})


@router.post("/predict")
async def predict(request: Request, file: UploadFile = File(...), pet_id: str = Form(...)):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu.")
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File harus berupa gambar.")

    if not pet_id or not pet_id.strip().isdigit():
        raise HTTPException(status_code=400, detail="Silakan pilih kucing yang diperiksa terlebih dahulu.")

    # Validasi pet_id memang milik user ini
    db_check = get_db()
    cur_check = db_check.cursor(dictionary=True)
    try:
        cur_check.execute("SELECT id FROM pets WHERE id = %s AND user_id = %s", (int(pet_id), user["id"]))
        valid_pet = cur_check.fetchone()
    finally:
        cur_check.close()
        db_check.close()

    if not valid_pet:
        raise HTTPException(status_code=400, detail="Profil kucing tidak valid atau bukan milik Anda.")

    valid_pet_id = int(pet_id)

    image_bytes = await file.read()

    # ── VALIDASI KUALITAS GAMBAR (Blur & Pencahayaan) ──
    quality_check = validate_image_quality(image_bytes)
    if not quality_check["valid"]:
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "reason": quality_check["reason"],
                "message": quality_check["message"],
                "details": quality_check["details"],
            },
        )

    disease_info = get_disease_info_dict()

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
            (user_id, pet_id, predicted_class, label, confidence, description, image_data, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (user["id"], valid_pet_id, predicted_key, info["label"], round(confidence, 2),
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

@router.get("/api/booked-slots")
async def api_booked_slots(date: str):
    """API untuk mengembalikan daftar jam yang sudah di-booking pada tanggal tertentu."""
    if not date:
        return JSONResponse({"booked_slots": []})
    slots = get_booked_slots(date)
    return JSONResponse({"booked_slots": slots})


@router.post("/predictions/{prediction_id}/book")
async def book_visit_appointment(
    request: Request,
    prediction_id: int,
    visit_date: str = Form(...),
    visit_time: str = Form(...),
    jenis_kunjungan: str = Form("fisik")
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    try:
        dt_str = f"{visit_date.strip()} {visit_time.strip()}"
        booking_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format tanggal atau jam tidak valid.")

    # Tolak kalau waktu yang dipilih sudah lewat
    if booking_dt <= datetime.now():
        return RedirectResponse("/history?error=Maaf, jam yang dipilih sudah lewat. Silakan pilih jadwal lain.", status_code=302)

    # Cek ketersediaan slot jam
    existing_slots = get_booked_slots(visit_date.strip())
    if visit_time.strip() in existing_slots:
        return RedirectResponse("/history?error=Maaf, jam tersebut baru saja di-booking orang lain.", status_code=302)

    # Pilih tipe kunjungan
    if jenis_kunjungan == "online":
        # Simpan ke tabel konsultasi_online
        save_telemed_request(prediction_id, user["id"], booking_dt)
        tipe_log = "Konsultasi Online"
    else:
        # Simpan ke tabel laporan_kunjungan (fisik) seperti biasa
        save_user_booking(prediction_id, user["id"], booking_dt)
        tipe_log = "Kunjungan Fisik"

    # Catat ke log aktivitas dengan tipe yang sesuai
    log_activity(user["id"], "book_visit", f"Pengajuan {tipe_log} #{prediction_id} pada {dt_str}")

    return RedirectResponse(f"/history?msg=Pengajuan {tipe_log} berhasil dikirim!", status_code=302)


@router.post("/predictions/{prediction_id}/cancel-booking")
async def cancel_visit_appointment(request: Request, prediction_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    cancel_user_booking(prediction_id, user["id"])
    log_activity(user["id"], "cancel_booking", f"Membatalkan booking #{prediction_id}")

    return RedirectResponse("/history?msg=Booking kunjungan berhasil dibatalkan.", status_code=302)


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, page: int = 1, per_page: int = 10, pet_id: int = None):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if page < 1:
        page = 1

    auto_update_expired_visits()

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        base_query = """SELECT p.id, p.predicted_class, p.label, p.confidence, p.description, p.created_at, 
                      p.visit_confirmed, p.pet_id, pets.name AS pet_name,
                      lk.status AS visit_status, lk.visit_date AS booking_datetime, lk.catatan_kunjungan,
                      ko.status AS telemed_status, ko.room_id AS telemed_room_id, ko.scheduled_at AS telemed_date
               FROM predictions p
               LEFT JOIN laporan_kunjungan lk ON lk.prediction_id = p.id
               LEFT JOIN konsultasi_online ko ON ko.prediction_id = p.id
               LEFT JOIN pets ON pets.id = p.pet_id
               WHERE p.user_id = %s"""
        params = [user["id"]]

        if pet_id:
            base_query += " AND p.pet_id = %s"
            params.append(pet_id)

        base_query += " ORDER BY p.created_at DESC"
        cursor.execute(base_query, tuple(params))
        all_raw = cursor.fetchall()

        # Ambil daftar pet untuk filter dropdown
        cursor.execute("SELECT id, name FROM pets WHERE user_id = %s ORDER BY name", (user["id"],))
        user_pets = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    total_data = len(all_raw)
    total_pages = math.ceil(total_data / per_page) if total_data > 0 else 1
    offset = (page - 1) * per_page
    
    disease_info = get_disease_info_dict()
    
    # ALL RECORDS untuk JS Chart
    all_records = []
    for r in all_raw:
        info = disease_info.get(r["predicted_class"], {})
        row = dict(r)
        row["emoji"] = info.get("emoji", "❓")
        row["color"] = info.get("color", "#888")
        if row.get("created_at"):
            row["chart_date"] = row["created_at"].strftime("%d/%m %H:%M")
        else:
            row["chart_date"] = "-"
        all_records.append(row)
        
    # RECORDS untuk Tabel HTML
    paginated_raw = all_raw[offset:offset+per_page]
    records = []
    prediction_ids = [r["id"] for r in paginated_raw]
    
    for r in paginated_raw:
        info = disease_info.get(r["predicted_class"], {})
        row = dict(r)
        row["emoji"] = info.get("emoji", "❓")
        row["color"] = info.get("color", "#888")
        row["advice"] = info.get("advice", [])
        row["visit_confirmed"] = bool(row.get("visit_confirmed"))
        
        # 1. Format tanggal & jam booking fisik jika ada (Sebagai Default)
        if row.get("booking_datetime"):
            row["booking_date"] = row["booking_datetime"].strftime("%Y-%m-%d")
            row["booking_time"] = row["booking_datetime"].strftime("%H:%M")
            row["booking_formatted"] = row["booking_datetime"].strftime("%d %b %Y, %H:%M WIB")
            row["scheduled_at"] = row["booking_datetime"]
        else:
            row["booking_date"] = ""
            row["booking_time"] = ""
            row["booking_formatted"] = ""
            row["scheduled_at"] = None

        # 2. Cek status untuk memprioritaskan jadwal mana yang tampil di Front-end
        t_status = row.get("telemed_status")
        v_status = row.get("visit_status")

        # Format tanggal telemed HANYA JIKA telemed masih aktif atau tidak ada jadwal fisik
        if row.get("telemed_date") and t_status not in [None, "batal"]:
            # MENCEGAH OVERWRITE: Jika telemed sudah 'selesai', tapi pasien punya kunjungan fisik 'terjadwal',
            # maka JANGAN ditimpa! Biarkan tanggal kunjungan fisik (05 Agustus) yang tampil.
            if t_status == "selesai" and v_status == "terjadwal":
                pass 
            else:
                row["telemed_date_formatted"] = row["telemed_date"].strftime("%d %b %Y, %H:%M WIB")
                row["scheduled_at"] = row["telemed_date"]
                row["booking_formatted"] = row["telemed_date"].strftime("%d %b %Y, %H:%M WIB")

        records.append(row)

    notes_map = get_doctor_notes_for_predictions(prediction_ids) if prediction_ids else {}
    for r in records:
        notes = notes_map.get(r["id"], [])
        r["doctor_notes"] = notes
        r["need_visit"] = any(n["need_visit"] for n in notes)

    return templates.TemplateResponse("history.html", {
        "request": request, "user": user, 
        "records": records, 
        "all_records": all_records,
        "clinic": get_clinic_info(),
        "pets": user_pets,
        "selected_pet_id": pet_id,
        "page": page, "total_pages": total_pages, "total_data": total_data
    })