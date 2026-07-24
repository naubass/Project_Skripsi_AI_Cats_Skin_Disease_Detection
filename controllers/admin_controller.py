"""
controllers/admin_controller.py — Route panel admin: dashboard, kelola
user, log aktivitas, dan upload PDF knowledge base chatbot.
"""

import math
from pathlib import Path

from fastapi import APIRouter, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from datetime import datetime

from database import get_db
from auth import hash_password
from rag import build_index
from core.state import templates
from core.dependencies import require_role

router = APIRouter(tags=["admin"])


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    user = require_role(request, ["admin"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'user'")
        total_users = cursor.fetchone()["c"]
        cursor.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'dokter'")
        total_dokter = cursor.fetchone()["c"]
        cursor.execute("SELECT COUNT(*) AS c FROM predictions")
        total_predictions = cursor.fetchone()["c"]
        cursor.execute("SELECT COUNT(*) AS c FROM activity_logs WHERE DATE(created_at) = CURDATE()")
        today_logs = cursor.fetchone()["c"]

        cursor.execute("""
            SELECT al.action, al.detail, al.created_at, u.name
            FROM activity_logs al
            LEFT JOIN users u ON al.user_id = u.id
            ORDER BY al.created_at DESC
            LIMIT 10
        """)
        recent_logs = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    stats = {
        "total_users": total_users,
        "total_dokter": total_dokter,
        "total_predictions": total_predictions,
        "today_logs": today_logs,
    }

    return templates.TemplateResponse("admin/index.html", {
        "request": request, "user": user, "stats": stats,
        "recent_logs": recent_logs, "active_page": "dashboard"
    })


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request, page: int = 1, per_page: int = 10, q: str = ""):
    user = require_role(request, ["admin"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    query = q.strip()
    if page < 1:
        page = 1

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        # Hitung Total Data untuk Pagination
        if query:
            cursor.execute(
                "SELECT COUNT(id) AS total FROM users WHERE name LIKE %s OR email LIKE %s",
                (f"%{query}%", f"%{query}%")
            )
        else:
            cursor.execute("SELECT COUNT(id) AS total FROM users")
            
        total_data = cursor.fetchone()["total"]
        total_pages = math.ceil(total_data / per_page) if total_data > 0 else 1
        
        offset = (page - 1) * per_page

        # Ambil Data Sesuai Halaman (LIMIT & OFFSET)
        if query:
            cursor.execute(
                """
                SELECT id, name, email, role, is_active, created_at 
                FROM users 
                WHERE name LIKE %s OR email LIKE %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (f"%{query}%", f"%{query}%", per_page, offset)
            )
        else:
            cursor.execute(
                "SELECT id, name, email, role, is_active, created_at FROM users ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (per_page, offset)
            )
        users = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    for u in users:
        if u.get("created_at"):
            u["created_at"] = u["created_at"].strftime("%d %b %Y")
        if u.get("last_login"):
            u["last_login"] = u["last_login"].strftime("%d %b %Y %H:%M")

    msg = request.query_params.get("msg")
    error = request.query_params.get("error")
    return templates.TemplateResponse("admin/users.html", {
        "request": request, "user": user, "users": users,
        "active_page": "users", "msg": msg, "error": error,
        "query": query, "page": page, "total_pages": total_pages, "total_data": total_data
    })


@router.post("/admin/users/create")
async def admin_create_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
    is_active: str = Form(None),
):
    admin_user = require_role(request, ["admin"])
    if not admin_user:
        return RedirectResponse("/login", status_code=302)

    # 👇 SUDAH DIPERBAIKI: Menambahkan "owner" ke daftar role yang diizinkan 👇
    if role not in ("user", "admin", "dokter", "owner"):
        role = "user"
    active_flag = 1 if is_active else 0

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return RedirectResponse("/admin/users?error=Email sudah terdaftar", status_code=302)
        if len(password) < 6:
            return RedirectResponse("/admin/users?error=Password minimal 6 karakter", status_code=302)

        hashed = hash_password(password)
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role, is_active, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (name, email, hashed, role, active_flag, datetime.now())
        )
        db.commit()
    finally:
        cursor.close()
        db.close()

    return RedirectResponse(f"/admin/users?msg=User '{name}' berhasil ditambahkan ({role})", status_code=302)


@router.post("/admin/users/{user_id}/edit")
async def admin_edit_user(
    request: Request,
    user_id: int,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(""),
    role: str = Form("user"),
    is_active: str = Form(None),
):
    admin_user = require_role(request, ["admin"])
    if not admin_user:
        return RedirectResponse("/login", status_code=302)

    # 👇 SUDAH DIPERBAIKI: Menambahkan "owner" ke daftar role yang diizinkan 👇
    if role not in ("user", "admin", "dokter", "owner"):
        role = "user"
    active_flag = 1 if is_active else 0

    db = get_db()
    cursor = db.cursor()
    try:
        if password.strip():
            if len(password) < 6:
                return RedirectResponse("/admin/users?error=Password minimal 6 karakter", status_code=302)
            hashed = hash_password(password)
            cursor.execute(
                "UPDATE users SET name=%s, email=%s, password_hash=%s, role=%s, is_active=%s WHERE id=%s",
                (name, email, hashed, role, active_flag, user_id)
            )
        else:
            cursor.execute(
                "UPDATE users SET name=%s, email=%s, role=%s, is_active=%s WHERE id=%s",
                (name, email, role, active_flag, user_id)
            )
        db.commit()
    finally:
        cursor.close()
        db.close()

    return RedirectResponse(f"/admin/users?msg=User '{name}' berhasil diperbarui", status_code=302)


@router.post("/admin/users/{user_id}/delete")
async def admin_delete_user(request: Request, user_id: int):
    admin_user = require_role(request, ["admin"])
    if not admin_user:
        return RedirectResponse("/login", status_code=302)

    if admin_user["id"] == user_id:
        return RedirectResponse("/admin/users?error=Tidak bisa menghapus akun sendiri", status_code=302)

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        db.commit()
    finally:
        cursor.close()
        db.close()

    return RedirectResponse("/admin/users?msg=User berhasil dihapus", status_code=302)


@router.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs_page(
    request: Request,
    page: int = 1,
    per_page: int = 20,
    action: str = "",
    time: str = "all",
    date: str = ""
):
    user = require_role(request, ["admin"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        # Base query untuk menghitung total dan mengambil data
        count_query = "SELECT COUNT(al.id) AS total FROM activity_logs al LEFT JOIN users u ON al.user_id = u.id WHERE 1=1"
        data_query = "SELECT al.action, al.detail, al.created_at, u.name FROM activity_logs al LEFT JOIN users u ON al.user_id = u.id WHERE 1=1"
        
        params = []
        
        # 1. Filter Action
        if action:
            count_query += " AND al.action = %s"
            data_query += " AND al.action = %s"
            params.append(action)
            
        # 2. Filter Date (Kalender)
        if date:
            count_query += " AND DATE(al.created_at) = %s"
            data_query += " AND DATE(al.created_at) = %s"
            params.append(date)
            
        # 3. Filter Time (Dropdown Rentang Waktu)
        if time == "mingguan":
            count_query += " AND al.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
            data_query += " AND al.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        elif time == "bulanan":
            count_query += " AND al.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
            data_query += " AND al.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        elif time == "tahunan":
            count_query += " AND al.created_at >= DATE_SUB(NOW(), INTERVAL 365 DAY)"
            data_query += " AND al.created_at >= DATE_SUB(NOW(), INTERVAL 365 DAY)"

        # Hitung Total Data (setelah difilter)
        cursor.execute(count_query, tuple(params))
        total_data = cursor.fetchone()["total"]
        
        # Hitung Pagination
        if page < 1: page = 1
        total_pages = math.ceil(total_data / per_page) if total_data > 0 else 1
        offset = (page - 1) * per_page
        
        # Ambil Data (setelah difilter + dilimit)
        data_query += " ORDER BY al.created_at DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        
        cursor.execute(data_query, tuple(params))
        logs = cursor.fetchall()
        
    finally:
        cursor.close()
        db.close()

    return templates.TemplateResponse("admin/logs.html", {
        "request": request, "user": user, "logs": logs,
        "active_page": "logs",
        "filter_action": action, "time_filter": time, "date_filter": date,
        "page": page, "total_pages": total_pages, "total_data": total_data
    })


@router.post("/admin/upload-pdf")
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    """Endpoint khusus admin untuk upload PDF knowledge base."""
    user = require_role(request, ["admin"])
    if not user:
        raise HTTPException(status_code=403, detail="Hanya admin yang bisa upload PDF.")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File harus berformat PDF.")

    Path("rag_data/pdfs").mkdir(parents=True, exist_ok=True)

    save_path = f"rag_data/pdfs/{file.filename}"
    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    build_index()

    return JSONResponse({"message": f"PDF '{file.filename}' berhasil diupload dan index diperbarui."})