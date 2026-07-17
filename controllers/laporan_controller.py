"""
controllers/laporan_controller.py — Route halaman Laporan Kunjungan.

Laporan kunjungan dibuat otomatis ketika dokter menekan tombol "Konfirmasi
Kunjungan" di halaman detail pasien. Halaman ini dikelola penuh oleh 'owner'.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from database import (
    get_all_laporan_kunjungan, get_laporan_kunjungan_by_id,
    update_laporan_kunjungan_status, log_activity, get_pending_recommendations
)
from core.state import templates
from core.dependencies import require_role

router = APIRouter(tags=["laporan"])

# Hak akses untuk melihat laporan (Bisa disesuaikan jika dokter tetap boleh melihat)
LAPORAN_ROLES = ["owner", "dokter"]


@router.get("/laporan", response_class=HTMLResponse)
async def laporan_list(request: Request):
    user = require_role(request, LAPORAN_ROLES)
    if not user:
        return RedirectResponse("/login", status_code=302)

    search_query = request.query_params.get("q", "").strip()
    date_filter = request.query_params.get("date", "").strip() # Format YYYY-MM-DD
    time_filter = request.query_params.get("time", "all").strip()

    raw_rows = get_all_laporan_kunjungan(search=search_query)

    # Filter Waktu
    laporan_rows = []
    now = datetime.now()
    
    for row in raw_rows:
        row_date = row.get("created_at")
        # Filter Tanggal (Kalender)
        if date_filter and isinstance(row_date, datetime):
            if row_date.strftime("%Y-%m-%d") != date_filter:
                continue

        # Filter Waktu
        if row_date and isinstance(row_date, datetime):
            if time_filter == "mingguan" and (now - row_date) > timedelta(days=7):
                continue
            elif time_filter == "bulanan" and (now - row_date) > timedelta(days=30):
                continue
            elif time_filter == "tahunan" and (now - row_date) > timedelta(days=365):
                continue
        
        laporan_rows.append(row)

    for row in laporan_rows:
        if row.get("created_at") and isinstance(row["created_at"], datetime):
            row["created_at"] = row["created_at"].strftime("%d %b %Y, %H:%M")
        if row.get("visit_date") and isinstance(row["visit_date"], datetime):
            row["visit_date"] = row["visit_date"].strftime("%d %b %Y, %H:%M")

    stats = {
        "total": len(laporan_rows),
        "terjadwal": len([r for r in laporan_rows if r["status"] == "terjadwal"]),
        "selesai": len([r for r in laporan_rows if r["status"] == "selesai"]),
        "batal": len([r for r in laporan_rows if r["status"] == "batal"]),
    }

    # Mengarah ke folder owner
    return templates.TemplateResponse("owner/laporan.html", {
        "request": request, "user": user, "laporan_rows": laporan_rows,
        "stats": stats, "date_filter": date_filter, "time_filter": time_filter, 
        "search_query": search_query, "active_page": "laporan"
    })


@router.get("/laporan/{laporan_id}", response_class=HTMLResponse)
async def laporan_detail(request: Request, laporan_id: int):
    user = require_role(request, LAPORAN_ROLES)
    if not user:
        return RedirectResponse("/login", status_code=302)

    laporan = get_laporan_kunjungan_by_id(laporan_id)
    if not laporan:
        raise HTTPException(status_code=404, detail="Laporan kunjungan tidak ditemukan.")

    if laporan.get("created_at"):
        laporan["created_at"] = laporan["created_at"].strftime("%d %b %Y, %H:%M")
        
    if laporan.get("visit_date"):
        laporan["visit_date"] = laporan["visit_date"].strftime("%Y-%m-%dT%H:%M")

    return templates.TemplateResponse("owner/laporan_detail.html", {
        "request": request, "user": user, "laporan": laporan,
        "active_page": "laporan"
    })


@router.post("/laporan/{laporan_id}/status")
async def laporan_update_status(
    request: Request,
    laporan_id: int,
    status: str = Form(...),
    visit_date: str = Form(""),
):
    """
    Update status laporan kunjungan. HANYA OWNER yang boleh mengubah status kedatangan.
    """
    user = require_role(request, ["owner"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    if status not in ("terjadwal", "selesai", "batal"):
        raise HTTPException(status_code=400, detail="Status tidak valid.")

    parsed_date = None
    if visit_date.strip():
        try:
            parsed_date = datetime.strptime(visit_date.strip(), "%Y-%m-%dT%H:%M")
        except ValueError:
            parsed_date = None

    update_laporan_kunjungan_status(laporan_id, status, parsed_date)
    log_activity(user["id"], "update_laporan_status", f"Laporan #{laporan_id} → {status}")

    return RedirectResponse(f"/laporan/{laporan_id}", status_code=302)


@router.get("/laporan-rekomendasi", response_class=HTMLResponse)
async def laporan_rekomendasi_list(request: Request):
    user = require_role(request, LAPORAN_ROLES)
    if not user:
        return RedirectResponse("/login", status_code=302)

    # Ambil parameter dari URL
    time_filter = request.query_params.get("time", "all").strip()
    search_query = request.query_params.get("q", "").strip()
    date_filter = request.query_params.get("date", "").strip() # Ambil tanggal

    raw_recommendations = get_pending_recommendations(search=search_query)

    rekomendasi_rows = []
    now = datetime.now()

    for row in raw_recommendations:
        note_date = row.get("note_date")
        
        # Filter Tanggal (Kalender)
        if date_filter and isinstance(note_date, datetime):
            if note_date.strftime("%Y-%m-%d") != date_filter:
                continue
        
        # Filter Waktu (Dropdown)
        if note_date and isinstance(note_date, datetime):
            if time_filter == "mingguan" and (now - note_date) > timedelta(days=7):
                continue
            elif time_filter == "bulanan" and (now - note_date) > timedelta(days=30):
                continue
            elif time_filter == "tahunan" and (now - note_date) > timedelta(days=365):
                continue

        rekomendasi_rows.append(row)

    for row in rekomendasi_rows:
        if row.get("note_date") and isinstance(row["note_date"], datetime):
            row["note_date"] = row["note_date"].strftime("%d %b %Y, %H:%M")

    return templates.TemplateResponse("owner/laporan_rekomendasi.html", {
        "request": request, 
        "user": user, 
        "rekomendasi_rows": rekomendasi_rows,
        "time_filter": time_filter, 
        "date_filter": date_filter, # Kirim ke template
        "search_query": search_query,
        "active_page": "rekomendasi"
    })