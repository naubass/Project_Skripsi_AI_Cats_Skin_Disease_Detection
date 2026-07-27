import os

os.environ["TFLITE_DISABLE_XNNPACK"] = "1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import mysql.connector  # mysql.connector diimpor sebelum numpy/tensorflow

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from database import init_db
from core import state
from controllers import (
    auth_controller,
    home_controller,
    admin_controller,
    dokter_controller,
    chatbot_controller,
    laporan_controller,
    telemed_controller
)

app = FastAPI(title="Sakti Pet Care - CatSkin AI | Klasifikasi Penyakit Kulit Kucing")

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "sakti-petcare-secret-2026"))
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# ── Registrasi semua controller (router) ────────────────────────────────────
app.include_router(auth_controller.router)
app.include_router(home_controller.router)
app.include_router(admin_controller.router)
app.include_router(dokter_controller.router)
app.include_router(chatbot_controller.router)
app.include_router(laporan_controller.router)
app.include_router(telemed_controller.router)

@app.on_event("startup")
async def startup():
    """
    init_db() dipanggil langsung (bukan di background thread terpisah).
    Setelah root cause segfault (urutan import numpy/tensorflow sebelum
    mysql.connector) diperbaiki, dan koneksi DB sudah punya connect_timeout
    + retry yang wajar (lihat database.py), init_db() seharusnya selesai
    dalam hitungan detik, bukan menggantung. Menjalankannya langsung di sini
    (bukan background thread) juga menghindari risiko native-code conflict
    tambahan dari nested threading.
    """
    try:
        init_db()
        state.db_ready = True
        print("[STARTUP] init_db() selesai, db_ready = True")
    except Exception as e:
        state.db_init_error = str(e)
        print(f"[STARTUP] init_db() gagal: {e}")

@app.get("/health")
async def health_check():
    """Endpoint sederhana untuk cek status DB tanpa harus login dulu."""
    return JSONResponse({
        "db_ready": state.db_ready,
        "db_init_error": state.db_init_error,
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)