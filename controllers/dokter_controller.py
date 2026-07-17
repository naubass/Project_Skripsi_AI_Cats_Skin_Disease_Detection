"""
controllers/dokter_controller.py — Route panel dokter: dashboard, daftar
pasien, detail riwayat pasien (+catatan dokter), dan kelola disease_info.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

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
async def dokter_patients_page(request: Request):
    user = require_role(request, ["dokter"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    query = request.query_params.get("q", "").strip()

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        if query:
            cursor.execute("""
                SELECT u.id, u.name, u.email, COUNT(p.id) AS total_predictions
                FROM users u
                LEFT JOIN predictions p ON p.user_id = u.id
                WHERE u.role = 'user' AND (u.name LIKE %s OR u.email LIKE %s)
                GROUP BY u.id
                ORDER BY total_predictions DESC
            """, (f"%{query}%", f"%{query}%"))
        else:
            cursor.execute("""
                SELECT u.id, u.name, u.email, COUNT(p.id) AS total_predictions
                FROM users u
                LEFT JOIN predictions p ON p.user_id = u.id
                WHERE u.role = 'user'
                GROUP BY u.id
                ORDER BY total_predictions DESC
            """)
        patients = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    return templates.TemplateResponse("dokter/patients.html", {
        "request": request, "user": user, "patients": patients,
        "active_page": "patients", "query": query
    })


@router.get("/dokter/patients/{patient_id}", response_class=HTMLResponse)
async def dokter_patient_detail(request: Request, patient_id: int):
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
            cursor.close()
            db.close()
            raise HTTPException(status_code=404, detail="Pasien tidak ditemukan.")

        if patient.get("created_at"):
            patient["created_at"] = patient["created_at"].strftime("%d %b %Y")

        cursor.execute(
            """SELECT id, predicted_class, label, confidence, description, created_at,
                      visit_confirmed, visit_confirmed_at
               FROM predictions WHERE user_id = %s ORDER BY created_at DESC""",
            (patient_id,)
        )
        records = cursor.fetchall()
        prediction_ids = [r["id"] for r in records]
        for r in records:
            info = disease_info.get(r["predicted_class"], {})
            r["emoji"] = info.get("emoji", "❓")
            r["color"] = info.get("color", "#888")
            r["advice"] = info.get("advice", [])
            r["visit_confirmed"] = bool(r.get("visit_confirmed"))
            if r.get("visit_confirmed_at"):
                r["visit_confirmed_at"] = r["visit_confirmed_at"].strftime("%d %b %Y, %H:%M")
            if r.get("created_at"):
                r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M")
    finally:
        cursor.close()
        db.close()

    notes_map = get_doctor_notes_for_predictions(prediction_ids)
    for r in records:
        notes = notes_map.get(r["id"], [])
        for n in notes:
            if n.get("created_at"):
                n["created_at"] = n["created_at"].strftime("%d %b %Y, %H:%M")
        r["doctor_notes"] = notes

    return templates.TemplateResponse("dokter/patient_detail.html", {
        "request": request, "user": user, "patient": patient,
        "records": records, "active_page": "patients"
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
    """
    Dokter merekomendasikan kunjungan / mengonfirmasi ke sistem.
    Ini membuat baris baru di laporan_kunjungan yang nantinya dikelola
    oleh owner. Dokter akan dikembalikan ke halaman detail pasien.
    """
    user = require_role(request, ["dokter"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
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

    laporan_id = confirm_visit(prediction_id, patient_id, user["id"], catatan.strip() or None)
    log_activity(user["id"], "confirm_visit", f"Meneruskan prediksi #{prediction_id} ke Laporan Kunjungan Owner")

    # Redirect kembali ke halaman pasien (bukan ke halaman laporan owner)
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