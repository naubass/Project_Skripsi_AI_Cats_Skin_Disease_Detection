"""
database.py — Koneksi MySQL dan inisialisasi tabel

Konfigurasi via environment variable atau langsung di DB_CONFIG di bawah.
Sesuaikan DB_CONFIG dengan setting MySQL kamu.
"""

import os
import mysql.connector
from mysql.connector import Error

# ── Konfigurasi ────────────────────────────────────────────────────────────────
# Bisa juga pakai os.getenv() dari file .env
DB_CONFIG = {
    "host"    : os.getenv("DB_HOST",     "localhost"),
    "port"    : int(os.getenv("DB_PORT", "3306")),
    "user"    : os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "catskindisease"),
}

# ── Koneksi ───────────────────────────────────────────────────────────────────
def get_db() -> mysql.connector.MySQLConnection:
    """Return satu koneksi MySQL baru (caller harus .close() sendiri)."""
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn


# ── Init Tabel ────────────────────────────────────────────────────────────────
def init_db():
    """Buat database & tabel bila belum ada."""
    # Koneksi tanpa nama database dulu untuk buat DB-nya
    cfg_no_db = {k: v for k, v in DB_CONFIG.items() if k != "database"}
    try:
        conn = mysql.connector.connect(**cfg_no_db)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        print(f"[DB] Gagal membuat database: {e}")
        return

    # Buat tabel
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INT AUTO_INCREMENT PRIMARY KEY,
                name          VARCHAR(100)        NOT NULL,
                email         VARCHAR(150) UNIQUE  NOT NULL,
                password_hash VARCHAR(255)         NOT NULL,
                role          ENUM('user','admin') NOT NULL DEFAULT 'user',
                last_login    DATETIME             NULL,
                created_at    DATETIME             NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id             INT AUTO_INCREMENT PRIMARY KEY,
                user_id        INT          NOT NULL,
                predicted_class VARCHAR(50) NOT NULL,
                label          VARCHAR(100) NOT NULL,
                confidence     FLOAT        NOT NULL,
                description    TEXT         NULL,
                created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        conn.commit()
        cursor.close()
        conn.close()
        print("[DB] Tabel berhasil diinisialisasi.")
    except Error as e:
        print(f"[DB] Gagal membuat tabel: {e}")
