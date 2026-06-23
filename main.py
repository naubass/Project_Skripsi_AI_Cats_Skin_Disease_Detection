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
from datetime import datetime
from database import get_db, init_db
from auth import hash_password, verify_password
from rag import ask as rag_ask, build_index, load_index

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

DISEASE_INFO = {
    "Flea_Allergy": {
        "emoji": "🔴", "label": "Flea Allergy", "color": "#f59e0b",
        "description": "Alergi kutu pada kulit menyebabkan pengelupasan, kerontokan bulu, dan rasa gatal akibat pertumbuhan kutu berlebih.",
        "advice": [
            "Memandikan kucing dengan shampoo berbahan dasar soothing seperti oatmeal atau antiseptik ringan membantu menenangkan kulit yang meradang.",
            "Berikan obat kutu topikal berkualitas tinggi yang direkomendasikan dokter hewan (seperti Fluralaner, Selamectin, atau Imidacloprid). Obat ini harus diberikan secara konsisten setiap bulan, bukan hanya saat terlihat ada kutu, karena kucing FAD membutuhkan perlindungan konstan sepanjang tahun.",
            "Jika Anda memiliki hewan peliharaan lain (kucing atau anjing lain), mereka wajib diberikan obat kutu pada saat yang sama. Hewan lain bisa menjadi reservoir (pembawa) kutu yang akan terus mendatangkan kutu baru ke kucing yang sensitif.",
            "Cuci alas tidur, selimut, atau bantal kucing dengan air panas minimal seminggu sekali untuk mematikan sisa larva kutu.",
            "Pisahkan dari hewan peliharaan lain selama pengobatan agar menghindari penyebaran tungau/kutu.",
        ],
    },
    "Health": {
        "emoji": "✅", "label": "Sehat", "color": "#22c55e",
        "description": "Kulit kucing terlihat sehat dan tidak menunjukkan tanda-tanda penyakit.",
        "advice": [
            "Pertahankan rutinitas perawatan yang sudah baik ini!",
            "Mandikan kucing secara rutin (1–2 kali seminggu).",
            "Berikan makanan bergizi dan air bersih setiap hari.",
            "Lakukan pemeriksaan rutin ke dokter hewan setiap 6 bulan sekali.",
            "Pastikan vaksinasi dan pemberian antiparasit tetap terjadwal.",
        ],
    },
    "Ringworm": {
        "emoji": "🔵", "label": "Ringworm", "color": "#3b82f6",
        "description": "Ringworm (Dermatophytosis) adalah infeksi jamur menular yang menyebabkan bercak bulat bersisik dan kebotakan pada kulit.",
        "advice": [
            "Tempatkan kucing yang terinfeksi di ruangan khusus yang mudah dibersihkan (misalnya kamar mandi atau ruangan berlantai keramik tanpa karpet)",
            "Memandikan kucing menggunakan shampoo khusus anti-jamur (biasanya mengandung miconazole dan chlorhexidine) 2 kali seminggu. Biarkan shampoo meresap selama 10 menit sebelum dibilas.",
            "Untuk infeksi yang menyebar luas, konsultasi dengan dokter akan memberikan obat antijamur oral seperti Itraconazole atau Terbinafine. Obat ini wajib dihabiskan sesuai periode yang ditentukan (biasanya beberapa minggu) meskipun gejala klinis tampak sudah sembuh.",
            "Cuci semua permukaan, karpet, dan tempat tidur hewan dengan disinfektan.",
            "Jika bulu kucing sangat panjang atau gimbal, mencukur bulu di sekitar area lesi dapat membantu obat topikal meresap lebih baik dan mengurangi penyebaran.",
        ],
    },
    "Scabies": {
        "emoji": "🦠", "label": "Scabies", "color": "#a855f7",
        "description": "Scabies disebabkan oleh infeksi tungau parasit yang mengakibatkan kerak pada bulu dan iritasi kulit.",
        "advice": [
            "Pisahkan kucing di ruangan isolasi yang tidak memiliki akses ke hewan lain.",
            "Berikan obat tetes tengkuk yang mengandung bahan aktif seperti Selamectin atau Fluralaner. Obat ini diserap ke dalam darah dan sangat efektif membunuh tungau dalam beberapa hari.",
            "Untuk membantu merontokkan kerak tebal dan mengurangi gatal, kucing bisa dimandikan dengan shampoo yang mengandung belerang atau antiseptik. Mandi ini membantu membersihkan kulit mati tempat tungau bersarang.",
            "Jaga kebersihan tempat tidur dan peralatan kucing.",
            "Pasang Elizabethan collar pada leher kucing untuk mencegah mereka mencakar wajah dan telinga secara merusak selama masa pengobatan.",
        ],
    },
}
 
def get_current_user(request: Request):
    return request.session.get("user")

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
        cursor.execute("UPDATE users SET last_login = %s WHERE id = %s", (datetime.now(), user["id"]))
        db.commit()
        request.session["user"] = {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}
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

# ══ MAIN ROUTES ════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.post("/predict")
async def predict(request: Request, file: UploadFile = File(...)):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu.")
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File harus berupa gambar.")

    image_bytes = await file.read()
    img_array   = preprocess_image(image_bytes)
    probs       = model.predict(img_array, verbose=0)[0]
    idx         = int(np.argmax(probs))
    predicted_key = CLASS_NAMES[idx]
    confidence    = float(probs[idx]) * 100
    info          = DISEASE_INFO[predicted_key]

    all_probs = [
        {"class": CLASS_NAMES[i], "label": DISEASE_INFO[CLASS_NAMES[i]]["label"],
         "prob": round(float(probs[i]) * 100, 2), "color": DISEASE_INFO[CLASS_NAMES[i]]["color"]}
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
        for r in records:
            info = DISEASE_INFO.get(r["predicted_class"], {})
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
    
    # Panggil RAG
    result = rag_ask(query)
    return JSONResponse(result)


@app.post("/admin/upload-pdf")
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    """Endpoint khusus admin untuk upload PDF knowledge base."""
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Hanya admin yang bisa upload PDF.")
    
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File harus berformat PDF.")
    
    import os
    from pathlib import Path
    Path("rag_data/pdfs").mkdir(parents=True, exist_ok=True)
    
    save_path = f"rag_data/pdfs/{file.filename}"
    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)
    
    # Rebuild index setelah upload PDF baru
    build_index()
    
    return JSONResponse({"message": f"PDF '{file.filename}' berhasil diupload dan index diperbarui."})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
