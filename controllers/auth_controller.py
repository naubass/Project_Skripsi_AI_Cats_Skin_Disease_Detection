"""
controllers/auth_controller.py — Route otentikasi: login, register, logout.
"""

from datetime import datetime

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from database import get_db, log_activity
from auth import hash_password, verify_password
from core.state import templates
from core.dependencies import get_current_user

router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse("/", status_code=302)
    registered = request.query_params.get("registered")
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "registered": registered})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user or not verify_password(password, user["password_hash"]):
            return templates.TemplateResponse("login.html", {
                "request": request, "error": "Email atau password salah.", "registered": None
            })
        if not user.get("is_active", 1):
            return templates.TemplateResponse("login.html", {
                "request": request, "error": "Akun Anda telah dinonaktifkan. Hubungi admin.", "registered": None
            })
        cursor.execute("UPDATE users SET last_login = %s WHERE id = %s", (datetime.now(), user["id"]))
        db.commit()
        request.session["user"] = {
            "id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]
        }
        log_activity(user["id"], "login", f"Login sebagai {user['role']}")
        
        # 👇 PENGATURAN REDIRECT BERDASARKAN ROLE 👇
        if user["role"] == "admin":
            return RedirectResponse("/admin", status_code=302)
        elif user["role"] == "dokter":
            return RedirectResponse("/dokter", status_code=302)
        elif user["role"] == "owner":
            return RedirectResponse("/laporan", status_code=302)
        
        # Default untuk 'user' biasa
        return RedirectResponse("/", status_code=302)
    finally:
        cursor.close()
        db.close()


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if get_current_user(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    if password != password_confirm:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Password dan konfirmasi tidak cocok."})
    if len(password) < 6:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Password minimal 6 karakter."})
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return templates.TemplateResponse("register.html", {"request": request, "error": "Email sudah terdaftar. Silakan login."})
        hashed = hash_password(password)
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (%s, %s, %s, %s, %s)",
            (name, email, hashed, "user", datetime.now())
        )
        db.commit()
        return RedirectResponse("/login?registered=1", status_code=302)
    finally:
        cursor.close()
        db.close()


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)