import os
import io
import numpy as np
from PIL import Image
import tensorflow as tf
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from tensorflow.keras.applications.resnet50 import preprocess_input
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime, timedelta
from database import get_db, init_db, get_disease_info_dict, log_activity
from auth import hash_password, verify_password
from rag import ask as rag_ask, build_index

app = FastAPI(title="Sakti Pet Care - CatSkin AI | Klasifikasi Penyakit Kulit Kucing")

# ── Session Middleware ─────────────────────────────────────────────────────────
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "sakti-petcare-secret-2026"))
templates = Jinja2Templates(directory="templates")

# Mount folder assets agar dibaca sebagai URL path '/assets'
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

MODEL_PATH  = "model_terbaik.keras"
IMG_SIZE    = (224, 224)
CLASS_NAMES = ["Flea_Allergy", "Health", "Ringworm", "Scabies"]

print("Loading model...")
model = tf.keras.models.load_model(MODEL_PATH)
print("Model loaded!")

@app.on_event("startup")
async def startup():
    init_db()
    from rag import load_index
    load_index()


def get_current_user(request: Request):
    return request.session.get("user")


def require_role(request: Request, allowed_roles: list):
    """
    Helper untuk proteksi route berdasarkan role.
    Return user dict jika lolos, atau None jika tidak (caller harus redirect/raise).
    """
    user = get_current_user(request)
    if not user:
        return None
    if user.get("role") not in allowed_roles:
        return None
    return user


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize(IMG_SIZE, Image.BILINEAR)
    img_array = np.array(img, dtype=np.float32)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = preprocess_input(img_array)
    return img_array


# ══ AUTH ROUTES ════════════════════════════════════════════════════════════════

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse("/", status_code=302)
    registered = request.query_params.get("registered")
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "registered": registered})


@app.post("/login", response_class=HTMLResponse)
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
        # Redirect sesuai role
        if user["role"] == "admin":
            return RedirectResponse("/admin", status_code=302)
        elif user["role"] == "dokter":
            return RedirectResponse("/dokter", status_code=302)
        return RedirectResponse("/", status_code=302)
    finally:
        cursor.close()
        db.close()


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if get_current_user(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@app.post("/register", response_class=HTMLResponse)
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
        # Registrasi publik selalu role 'user' — admin & dokter dibuat lewat panel admin
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (%s, %s, %s, %s, %s)",
            (name, email, hashed, "user", datetime.now())
        )
        db.commit()
        return RedirectResponse("/login?registered=1", status_code=302)
    finally:
        cursor.close()
        db.close()


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


# ══ MAIN ROUTES (role: user) ═══════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    # Admin & dokter punya panelnya sendiri, tapi tetap dibolehkan lihat halaman utama jika mau
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.post("/predict")
async def predict(request: Request, file: UploadFile = File(...)):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu.")
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File harus berupa gambar.")

    disease_info = get_disease_info_dict()

    image_bytes = await file.read()
    img_array   = preprocess_image(image_bytes)
    probs       = model.predict(img_array, verbose=0)[0]
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
            "INSERT INTO predictions (user_id, predicted_class, label, confidence, description, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (user["id"], predicted_key, info["label"], round(confidence, 2), info["description"], datetime.now())
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


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, predicted_class, label, confidence, description, created_at FROM predictions WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
            (user["id"],)
        )
        records = cursor.fetchall()
        disease_info = get_disease_info_dict()
        for r in records:
            info = disease_info.get(r["predicted_class"], {})
            r["emoji"] = info.get("emoji", "❓")
            r["color"] = info.get("color", "#888")
    finally:
        cursor.close()
        db.close()
    return templates.TemplateResponse("history.html", {"request": request, "user": user, "records": records})


# ══ CHATBOT ROUTES ═════════════════════════════════════════════════════════════

@app.get("/chatbot", response_class=HTMLResponse)
async def chatbot_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("chatbot.html", {"request": request, "user": user})


@app.post("/chatbot/ask")
async def chatbot_ask(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login diperlukan.")

    body = await request.json()
    query = body.get("query", "").strip()

    if not query:
        raise HTTPException(status_code=400, detail="Pertanyaan tidak boleh kosong.")
    if len(query) > 500:
        raise HTTPException(status_code=400, detail="Pertanyaan terlalu panjang.")

    result = rag_ask(query)
    log_activity(user["id"], "chatbot", query[:100])
    return JSONResponse(result)


@app.post("/admin/upload-pdf")
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    """Endpoint khusus admin untuk upload PDF knowledge base."""
    user = require_role(request, ["admin"])
    if not user:
        raise HTTPException(status_code=403, detail="Hanya admin yang bisa upload PDF.")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File harus berformat PDF.")

    from pathlib import Path
    Path("rag_data/pdfs").mkdir(parents=True, exist_ok=True)

    save_path = f"rag_data/pdfs/{file.filename}"
    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    build_index()

    return JSONResponse({"message": f"PDF '{file.filename}' berhasil diupload dan index diperbarui."})


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES (role: admin)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/admin", response_class=HTMLResponse)
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


@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    user = require_role(request, ["admin"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, name, email, role, is_active, created_at FROM users ORDER BY created_at DESC")
        users = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    # ── Fix: konversi datetime ke string agar tojson tidak error ──
    for u in users:
        if u.get("created_at"):
            u["created_at"] = u["created_at"].strftime("%d %b %Y")
        if u.get("last_login"):
            u["last_login"] = u["last_login"].strftime("%d %b %Y %H:%M")

    msg = request.query_params.get("msg")
    error = request.query_params.get("error")
    return templates.TemplateResponse("admin/users.html", {
        "request": request, "user": user, "users": users,
        "active_page": "users", "msg": msg, "error": error
    })


@app.post("/admin/users/create")
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

    if role not in ("user", "admin", "dokter"):
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


@app.post("/admin/users/{user_id}/edit")
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

    if role not in ("user", "admin", "dokter"):
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


@app.post("/admin/users/{user_id}/delete")
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


@app.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs_page(request: Request):
    user = require_role(request, ["admin"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    filter_action = request.query_params.get("action", "")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        if filter_action:
            cursor.execute("""
                SELECT al.action, al.detail, al.created_at, u.name
                FROM activity_logs al
                LEFT JOIN users u ON al.user_id = u.id
                WHERE al.action = %s
                ORDER BY al.created_at DESC
                LIMIT 200
            """, (filter_action,))
        else:
            cursor.execute("""
                SELECT al.action, al.detail, al.created_at, u.name
                FROM activity_logs al
                LEFT JOIN users u ON al.user_id = u.id
                ORDER BY al.created_at DESC
                LIMIT 200
            """)
        logs = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    return templates.TemplateResponse("admin/logs.html", {
        "request": request, "user": user, "logs": logs,
        "active_page": "logs", "filter_action": filter_action
    })


# ══════════════════════════════════════════════════════════════════════════════
# DOKTER ROUTES (role: dokter)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/dokter", response_class=HTMLResponse)
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


@app.get("/dokter/patients", response_class=HTMLResponse)
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


@app.get("/dokter/patients/{patient_id}", response_class=HTMLResponse)
async def dokter_patient_detail(request: Request, patient_id: int):
    user = require_role(request, ["dokter"])
    if not user:
        return RedirectResponse("/login", status_code=302)

    disease_info = get_disease_info_dict()

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        # SESUDAH — tambahkan konversi datetime sebelum ke template
        cursor.execute("SELECT id, name, email, created_at FROM users WHERE id = %s AND role = 'user'", (patient_id,))
        patient = cursor.fetchone()
        if not patient:
            cursor.close()
            db.close()
            raise HTTPException(status_code=404, detail="Pasien tidak ditemukan.")

        # ── Fix patient datetime ──
        if patient.get("created_at"):
            patient["created_at"] = patient["created_at"].strftime("%d %b %Y")

        cursor.execute(
            "SELECT id, predicted_class, label, confidence, description, created_at FROM predictions WHERE user_id = %s ORDER BY created_at DESC",
            (patient_id,)
        )
        records = cursor.fetchall()
        for r in records:
            info = disease_info.get(r["predicted_class"], {})
            r["emoji"] = info.get("emoji", "❓")
            r["color"] = info.get("color", "#888")
            # ── Fix records datetime ──
            if r.get("created_at"):
                r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M")
    finally:
        cursor.close()
        db.close()

    return templates.TemplateResponse("dokter/patient_detail.html", {
        "request": request, "user": user, "patient": patient,
        "records": records, "active_page": "patients"
    })


@app.get("/dokter/disease-info", response_class=HTMLResponse)
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


@app.post("/dokter/disease-info/{disease_id}/update")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)