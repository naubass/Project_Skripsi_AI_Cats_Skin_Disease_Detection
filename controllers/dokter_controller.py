"""
controllers/dokter_controller.py — Route panel dokter: dashboard, daftar
pasien, detail riwayat pasien (+catatan dokter), dan kelola disease_info.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import math

from database import (
    get_db, get_disease_info_dict, log_activity,
    add_doctor_note, delete_doctor_note, get_doctor_notes_for_predictions,
    confirm_visit,
)
from core.state import templates
from core.dependencies import require_role

router = APIRouter(tags=["dokter"])


@router.get("/dokter", response_class=HTMLResponse)
async def dokter_dashboard(request: Request):
    user = require_role(request, ["dokter"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    disease_info = get_disease_info_dict()

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) AS c FROM predictions")
        total_predictions = cursor.fetchone()["c"]

        cursor.execute("SELECT COUNT(DISTINCT user_id) AS c FROM predictions")
        total_patients = cursor.fetchone()["c"]

        week_ago = datetime.now() - timedelta(days=7)
        cursor.execute("SELECT COUNT(*) AS c FROM predictions WHERE created_at >= %s", (week_ago,))
        this_week = cursor.fetchone()["c"]

        cursor.execute("SELECT AVG(confidence) AS avg_c FROM predictions")
        avg_row = cursor.fetchone()
        avg_confidence = round(avg_row["avg_c"], 1) if avg_row["avg_c"] else 0

        cursor.execute("""
            SELECT predicted_class, COUNT(*) AS cnt
            FROM predictions
            GROUP BY predicted_class
        """)
        dist_rows = cursor.fetchall()

        cursor.execute("""
            SELECT p.label, p.confidence, u.name AS user_name
            FROM predictions p
            JOIN users u ON p.user_id = u.id
            ORDER BY p.created_at DESC
            LIMIT 10
        """)
        recent_predictions = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    distribution = []
    for row in dist_rows:
        info = disease_info.get(row["predicted_class"], {})
        percent = round((row["cnt"] / total_predictions) * 100, 1) if total_predictions else 0
        distribution.append({
            "label": info.get("label", row["predicted_class"]),
            "emoji": info.get("emoji", "❓"),
            "color": info.get("color", "#888"),
            "count": row["cnt"],
            "percent": percent,
        })
    distribution.sort(key=lambda x: x["count"], reverse=True)

    stats = {
        "total_predictions": total_predictions,
        "total_patients": total_patients,
        "this_week": this_week,
        "avg_confidence": avg_confidence,
    }

    return templates.TemplateResponse("dokter/index.html", {
        "request": request, "user": user, "stats": stats,
        "distribution": distribution, "recent_predictions": recent_predictions,
        "active_page": "dashboard"
    })


@router.get("/dokter/patients", response_class=HTMLResponse)
async def dokter_patients_page(request: Request, page: int = 1, per_page: int = 20):
    user = require_role(request, ["dokter"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    query = request.query_params.get("q", "").strip()
    
    if page < 1:
        page = 1

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        # Hitung Total Data untuk Pagination
        if query:
            cursor.execute("""
                SELECT COUNT(id) AS total FROM users 
                WHERE role = 'user' AND (name LIKE %s OR email LIKE %s)
            """, (f"%{query}%", f"%{query}%"))
        else:
            cursor.execute("SELECT COUNT(id) AS total FROM users WHERE role = 'user'")
            
        total_data = cursor.fetchone()["total"]
        total_pages = math.ceil(total_data / per_page) if total_data > 0 else 1
        
        # Hitung Offset
        offset = (page - 1) * per_page

        # Ambil Data Sesuai Halaman (LIMIT & OFFSET)
        if query:
            cursor.execute("""
                SELECT u.id, u.name, u.email, COUNT(p.id) AS total_predictions
                FROM users u
                LEFT JOIN predictions p ON p.user_id = u.id
                WHERE u.role = 'user' AND (u.name LIKE %s OR u.email LIKE %s)
                GROUP BY u.id
                ORDER BY total_predictions DESC
                LIMIT %s OFFSET %s
            """, (f"%{query}%", f"%{query}%", per_page, offset))
        else:
            cursor.execute("""
                SELECT u.id, u.name, u.email, COUNT(p.id) AS total_predictions
                FROM users u
                LEFT JOIN predictions p ON p.user_id = u.id
                WHERE u.role = 'user'
                GROUP BY u.id
                ORDER BY total_predictions DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            
        patients = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    return templates.TemplateResponse("dokter/patients.html", {
        "request": request, "user": user, "patients": patients,
        "active_page": "patients", "query": query,
        "page": page, "total_pages": total_pages, "total_data": total_data
    })


@router.get("/dokter/patients/{patient_id}", response_class=HTMLResponse)
async def dokter_patient_detail(request: Request, patient_id: int, page: int = 1, per_page: int = 10):
    user = require_role(request, ["dokter"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    disease_info = get_disease_info_dict()

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, name, email, created_at FROM users WHERE id = %s AND role = 'user'", (patient_id,))
        patient = cursor.fetchone()
        if not patient:
            raise HTTPException(status_code=404, detail="Pasien tidak ditemukan.")

        if patient.get("created_at") and isinstance(patient["created_at"], datetime):
            patient["created_at"] = patient["created_at"].strftime("%d %b %Y")

        # Ambil data prediksi beserta info booking dari laporan_kunjungan
        cursor.execute(
            """SELECT p.id, p.predicted_class, p.label, p.confidence, p.description, p.created_at,
                      p.visit_confirmed, p.visit_confirmed_at,
                      lk.status AS visit_status, lk.visit_date AS booking_datetime, lk.catatan_kunjungan
               FROM predictions p
               LEFT JOIN laporan_kunjungan lk ON lk.prediction_id = p.id
               WHERE p.user_id = %s ORDER BY p.created_at DESC""",
            (patient_id,)
        )
        all_raw = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    total_data = len(all_raw)
    total_pages = math.ceil(total_data / per_page) if total_data > 0 else 1
    if page < 1: page = 1
    offset = (page - 1) * per_page
    
    # 1. Konversi ALL_RECORDS untuk JS Chart & JSON Serialization
    all_records = []
    for r in all_raw:
        info = disease_info.get(r["predicted_class"], {})
        row = dict(r)
        row["emoji"] = info.get("emoji", "❓")
        row["color"] = info.get("color", "#888")
        row["visit_confirmed"] = bool(row.get("visit_confirmed"))

        # Konversi SEMUA tipe datetime ke string agar aman untuk JSON
        if row.get("created_at") and isinstance(row["created_at"], datetime):
            row["created_at"] = row["created_at"].strftime("%Y-%m-%d %H:%M")
        if row.get("visit_confirmed_at") and isinstance(row["visit_confirmed_at"], datetime):
            row["visit_confirmed_at"] = row["visit_confirmed_at"].strftime("%d %b %Y, %H:%M")
        if row.get("booking_datetime") and isinstance(row["booking_datetime"], datetime):
            row["booking_datetime"] = row["booking_datetime"].strftime("%Y-%m-%d %H:%M")

        all_records.append(row)

    # 2. Slice Data untuk Tabel (Paginated)
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
        
        # Konversi objek datetime untuk tampilan tabel
        if row.get("booking_datetime") and isinstance(row["booking_datetime"], datetime):
            b_dt = row["booking_datetime"]
            row["booking_date_formatted"] = b_dt.strftime("%d %b %Y")
            row["booking_time_formatted"] = b_dt.strftime("%H:%M WIB")
            row["booking_full_formatted"] = b_dt.strftime("%d %b %Y, %H:%M WIB")
            row["booking_datetime"] = b_dt.strftime("%Y-%m-%d %H:%M")
        else:
            row["booking_date_formatted"] = "Belum Memilih Tanggal"
            row["booking_time_formatted"] = "-"
            row["booking_full_formatted"] = "Belum ada jadwal booking dari user"
            row["booking_datetime"] = ""

        if row.get("visit_confirmed_at") and isinstance(row["visit_confirmed_at"], datetime):
            row["visit_confirmed_at"] = row["visit_confirmed_at"].strftime("%d %b %Y, %H:%M")
        if row.get("created_at") and isinstance(row["created_at"], datetime):
            row["created_at"] = row["created_at"].strftime("%Y-%m-%d %H:%M")
            
        records.append(row)

    notes_map = get_doctor_notes_for_predictions(prediction_ids) if prediction_ids else {}
    for r in records:
        notes = notes_map.get(r["id"], [])
        for n in notes:
            if n.get("created_at") and isinstance(n["created_at"], datetime):
                n["created_at"] = n["created_at"].strftime("%d %b %Y, %H:%M")
        r["doctor_notes"] = notes

    return templates.TemplateResponse("dokter/patient_detail.html", {
        "request": request, "user": user, "patient": patient,
        "records": records, "all_records": all_records, 
        "active_page": "patients",
        "page": page, "total_pages": total_pages, "total_data": total_data
    })


@router.post("/dokter/patients/{patient_id}/notes/{prediction_id}")
async def dokter_add_note(
    request: Request,
    patient_id: int,
    prediction_id: int,
    note: str = Form(...),
    need_visit: str = Form(None),
):
    """Dokter menambahkan catatan ke satu record riwayat prediksi pasien."""
    user = require_role(request, ["dokter"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    note = note.strip()
    if not note:
        return RedirectResponse(f"/dokter/patients/{patient_id}", status_code=302)
    need_visit_flag = bool(need_visit)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        # Pastikan prediction_id memang milik pasien ini, supaya dokter
        # tidak bisa menambah catatan ke record milik pasien lain.
        cursor.execute(
            "SELECT id FROM predictions WHERE id = %s AND user_id = %s",
            (prediction_id, patient_id)
        )
        valid = cursor.fetchone()
    finally:
        cursor.close()
        db.close()

    if not valid:
        raise HTTPException(status_code=404, detail="Riwayat prediksi tidak ditemukan.")

    add_doctor_note(prediction_id, user["id"], note, need_visit_flag)
    log_activity(user["id"], "doctor_note", f"Menambahkan catatan pada prediksi #{prediction_id}")

    return RedirectResponse(f"/dokter/patients/{patient_id}#record-{prediction_id}", status_code=302)


@router.post("/dokter/patients/{patient_id}/confirm-visit/{prediction_id}")
async def dokter_confirm_visit(
    request: Request,
    patient_id: int,
    prediction_id: int,
    catatan: str = Form(""),
):
    """Dokter menyetujui jadwal booking dan meneruskannya ke Laporan Owner."""
    user = require_role(request, ["dokter"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    confirm_visit(prediction_id, patient_id, user["id"], catatan.strip() or None)
    log_activity(user["id"], "confirm_visit", f"Mengonfirmasi kunjungan #{prediction_id}")

    return RedirectResponse(f"/dokter/patients/{patient_id}#record-{prediction_id}", status_code=302)

@router.post("/dokter/patients/{patient_id}/reschedule-visit/{prediction_id}")
async def dokter_reschedule_visit(
    request: Request,
    patient_id: int,
    prediction_id: int,
    catatan: str = Form(""),
):
    """Dokter meminta reschedule. Status di-set 'batal' dengan penanda khusus."""
    user = require_role(request, ["dokter"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        # Gunakan penanda [RESCHEDULE_DOKTER] agar frontend bisa membedakannya dengan mutlak
        pesan_reschedule = f"[RESCHEDULE_DOKTER] {catatan.strip()}" if catatan.strip() else "[RESCHEDULE_DOKTER] Dokter meminta Anda untuk memilih jadwal kunjungan ulang."
        
        cursor.execute("SELECT id FROM laporan_kunjungan WHERE prediction_id = %s", (prediction_id,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute(
                """UPDATE laporan_kunjungan 
                   SET status = 'batal', confirmed_by = NULL, catatan_kunjungan = %s 
                   WHERE prediction_id = %s""",
                (pesan_reschedule, prediction_id)
            )
        else:
            cursor.execute(
                """INSERT INTO laporan_kunjungan (prediction_id, user_id, patient_id, confirmed_by, status, catatan_kunjungan, created_at)
                   VALUES (%s, %s, %s, NULL, 'batal', %s, NOW())""",
                (prediction_id, patient_id, patient_id, pesan_reschedule)
            )
        db.commit()
    finally:
        cursor.close()
        db.close()

    if catatan.strip():
        add_doctor_note(prediction_id, user["id"], f"⚠️ Mohon Reschedule Kunjungan: {catatan.strip()}", need_visit=True)

    log_activity(user["id"], "reschedule_visit", f"Meminta reschedule kunjungan #{prediction_id}")

    return RedirectResponse(f"/dokter/patients/{patient_id}#record-{prediction_id}", status_code=302)


@router.post("/dokter/notes/{note_id}/delete")
async def dokter_delete_note(request: Request, note_id: int, patient_id: int = Form(...)):
    """Dokter menghapus catatan miliknya sendiri."""
    user = require_role(request, ["dokter"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    delete_doctor_note(note_id, user["id"])
    return RedirectResponse(f"/dokter/patients/{patient_id}", status_code=302)


@router.get("/dokter/disease-info", response_class=HTMLResponse)
async def dokter_disease_info_page(request: Request):
    user = require_role(request, ["dokter"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT di.*, u.name AS updated_by_name
            FROM disease_info di
            LEFT JOIN users u ON di.updated_by = u.id
            ORDER BY di.id ASC
        """)
        diseases = cursor.fetchall()
        for d in diseases:
            d["advice_raw"] = d.get("advice") or ""
    finally:
        cursor.close()
        db.close()

    msg = request.query_params.get("msg")
    return templates.TemplateResponse("dokter/disease_info.html", {
        "request": request, "user": user, "diseases": diseases,
        "active_page": "disease_info", "msg": msg
    })


@router.post("/dokter/disease-info/{disease_id}/update")
async def dokter_update_disease_info(
    request: Request,
    disease_id: int,
    label: str = Form(...),
    emoji: str = Form("🐱"),
    color: str = Form("#888888"),
    description: str = Form(""),
    advice: str = Form(""),
):
    user = require_role(request, ["dokter"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """UPDATE disease_info
               SET label=%s, emoji=%s, color=%s, description=%s, advice=%s, updated_by=%s, updated_at=%s
               WHERE id=%s""",
            (label, emoji, color, description, advice, user["id"], datetime.now(), disease_id)
        )
        db.commit()
    finally:
        cursor.close()
        db.close()

    return RedirectResponse(f"/dokter/disease-info?msg=Info '{label}' berhasil diperbarui", status_code=302)