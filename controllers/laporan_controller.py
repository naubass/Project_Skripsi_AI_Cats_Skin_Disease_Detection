"""
controllers/laporan_controller.py — Route halaman Laporan Kunjungan.

Laporan kunjungan dibuat otomatis ketika dokter menekan tombol "Konfirmasi
Kunjungan" di halaman detail pasien. Halaman ini dikelola penuh oleh 'owner'.
"""

from datetime import datetime

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

    status_filter = request.query_params.get("status", "").strip() or None
    laporan_rows = get_all_laporan_kunjungan(status_filter)

    for row in laporan_rows:
        if row.get("created_at"):
            row["created_at"] = row["created_at"].strftime("%d %b %Y, %H:%M")
        if row.get("visit_date"):
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
        "stats": stats, "status_filter": status_filter, "active_page": "laporan"
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
    """
    Halaman khusus untuk melihat pasien yang disarankan datang (need_visit = True)
    tetapi belum dikonfirmasi ke tabel laporan_kunjungan.
    """
    user = require_role(request, LAPORAN_ROLES)
    if not user:
        return RedirectResponse("/login", status_code=302)

    rekomendasi_rows = get_pending_recommendations()

    for row in rekomendasi_rows:
        if row.get("note_date"):
            row["note_date"] = row["note_date"].strftime("%d %b %Y, %H:%M")

    return templates.TemplateResponse("owner/laporan_rekomendasi.html", {
        "request": request, "user": user, "rekomendasi_rows": rekomendasi_rows,
        "active_page": "rekomendasi"
    })