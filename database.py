"""
database.py — Koneksi MySQL dan inisialisasi tabel

Konfigurasi via environment variable atau langsung di DB_CONFIG di bawah.
Sesuaikan DB_CONFIG dengan setting MySQL kamu.
"""

import os
import mysql.connector
from mysql.connector import Error

# ── Konfigurasi ────────────────────────────────────────────────────────────────
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


# ── Disease info default (dipakai untuk seed pertama kali saja) ───────────────
DEFAULT_DISEASE_INFO = [
    {
        "predicted_class": "Flea_Allergy",
        "label": "Flea Allergy",
        "emoji": "🔴",
        "color": "#f59e0b",
        "description": "Alergi kutu pada kulit menyebabkan pengelupasan, kerontokan bulu, dan rasa gatal akibat pertumbuhan kutu berlebih.",
        "advice": (
            "Memandikan kucing dengan shampoo berbahan dasar soothing seperti oatmeal atau antiseptik ringan membantu menenangkan kulit yang meradang.\n"
            "Berikan obat kutu topikal berkualitas tinggi yang direkomendasikan dokter hewan (seperti Fluralaner, Selamectin, atau Imidacloprid). Obat ini harus diberikan secara konsisten setiap bulan, bukan hanya saat terlihat ada kutu, karena kucing FAD membutuhkan perlindungan konstan sepanjang tahun.\n"
            "Jika Anda memiliki hewan peliharaan lain (kucing atau anjing lain), mereka wajib diberikan obat kutu pada saat yang sama. Hewan lain bisa menjadi reservoir (pembawa) kutu yang akan terus mendatangkan kutu baru ke kucing yang sensitif.\n"
            "Cuci alas tidur, selimut, atau bantal kucing dengan air panas minimal seminggu sekali untuk mematikan sisa larva kutu.\n"
            "Pisahkan dari hewan peliharaan lain selama pengobatan agar menghindari penyebaran tungau/kutu."
        ),
    },
    {
        "predicted_class": "Health",
        "label": "Sehat",
        "emoji": "✅",
        "color": "#22c55e",
        "description": "Kulit kucing terlihat sehat dan tidak menunjukkan tanda-tanda penyakit.",
        "advice": (
            "Pertahankan rutinitas perawatan yang sudah baik ini!\n"
            "Mandikan kucing secara rutin (1–2 kali seminggu).\n"
            "Berikan makanan bergizi dan air bersih setiap hari.\n"
            "Lakukan pemeriksaan rutin ke dokter hewan setiap 6 bulan sekali.\n"
            "Pastikan vaksinasi dan pemberian antiparasit tetap terjadwal."
        ),
    },
    {
        "predicted_class": "Ringworm",
        "label": "Ringworm",
        "emoji": "🔵",
        "color": "#3b82f6",
        "description": "Ringworm (Dermatophytosis) adalah infeksi jamur menular yang menyebabkan bercak bulat bersisik dan kebotakan pada kulit.",
        "advice": (
            "Tempatkan kucing yang terinfeksi di ruangan khusus yang mudah dibersihkan (misalnya kamar mandi atau ruangan berlantai keramik tanpa karpet).\n"
            "Memandikan kucing menggunakan shampoo khusus anti-jamur (biasanya mengandung miconazole dan chlorhexidine) 2 kali seminggu. Biarkan shampoo meresap selama 10 menit sebelum dibilas.\n"
            "Untuk infeksi yang menyebar luas, konsultasi dengan dokter akan memberikan obat antijamur oral seperti Itraconazole atau Terbinafine. Obat ini wajib dihabiskan sesuai periode yang ditentukan (biasanya beberapa minggu) meskipun gejala klinis tampak sudah sembuh.\n"
            "Cuci semua permukaan, karpet, dan tempat tidur hewan dengan disinfektan.\n"
            "Jika bulu kucing sangat panjang atau gimbal, mencukur bulu di sekitar area lesi dapat membantu obat topikal meresap lebih baik dan mengurangi penyebaran."
        ),
    },
    {
        "predicted_class": "Scabies",
        "label": "Scabies",
        "emoji": "🦠",
        "color": "#a855f7",
        "description": "Scabies disebabkan oleh infeksi tungau parasit yang mengakibatkan kerak pada bulu dan iritasi kulit.",
        "advice": (
            "Pisahkan kucing di ruangan isolasi yang tidak memiliki akses ke hewan lain.\n"
            "Berikan obat tetes tengkuk yang mengandung bahan aktif seperti Selamectin atau Fluralaner. Obat ini diserap ke dalam darah dan sangat efektif membunuh tungau dalam beberapa hari.\n"
            "Untuk membantu merontokkan kerak tebal dan mengurangi gatal, kucing bisa dimandikan dengan shampoo yang mengandung belerang atau antiseptik. Mandi ini membantu membersihkan kulit mati tempat tungau bersarang.\n"
            "Jaga kebersihan tempat tidur dan peralatan kucing.\n"
            "Pasang Elizabethan collar pada leher kucing untuk mencegah mereka mencakar wajah dan telinga secara merusak selama masa pengobatan."
        ),
    },
]


# ── Init Tabel ────────────────────────────────────────────────────────────────
def init_db():
    """Buat database & tabel bila belum ada."""
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

    try:
        conn = get_db()
        cursor = conn.cursor()

        # ── Tabel users (role ditambah 'dokter') ──────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INT AUTO_INCREMENT PRIMARY KEY,
                name          VARCHAR(100)        NOT NULL,
                email         VARCHAR(150) UNIQUE  NOT NULL,
                password_hash VARCHAR(255)         NOT NULL,
                role          ENUM('user','admin','dokter') NOT NULL DEFAULT 'user',
                is_active     TINYINT(1)           NOT NULL DEFAULT 1,
                last_login    DATETIME             NULL,
                created_at    DATETIME             NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # Migrasi: kalau tabel users sudah ada dari versi lama (role tanpa 'dokter'
        # atau tanpa kolom is_active), tambahkan secara aman.
        try:
            cursor.execute("ALTER TABLE users MODIFY COLUMN role ENUM('user','admin','dokter') NOT NULL DEFAULT 'user'")
        except Error:
            pass
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1")
        except Error:
            pass

        # ── Tabel disease_info (pengganti hardcode DISEASE_INFO) ──────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS disease_info (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                predicted_class VARCHAR(50) UNIQUE NOT NULL,
                label           VARCHAR(100)        NOT NULL,
                emoji           VARCHAR(10)          NOT NULL DEFAULT '🐱',
                color           VARCHAR(20)          NOT NULL DEFAULT '#888888',
                description     TEXT                 NULL,
                advice          TEXT                 NULL,
                updated_by      INT                  NULL,
                updated_at      DATETIME             NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # ── Tabel predictions ──────────────────────────────────────────────
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

        # ── Tabel activity_logs (log aktivitas dasar untuk admin) ─────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                user_id     INT          NULL,
                action      VARCHAR(50)  NOT NULL,
                detail      VARCHAR(255) NULL,
                created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        conn.commit()

        # ── Seed disease_info kalau masih kosong ──────────────────────────
        cursor.execute("SELECT COUNT(*) FROM disease_info")
        count = cursor.fetchone()[0]
        if count == 0:
            for d in DEFAULT_DISEASE_INFO:
                cursor.execute(
                    """INSERT INTO disease_info
                       (predicted_class, label, emoji, color, description, advice)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (d["predicted_class"], d["label"], d["emoji"], d["color"], d["description"], d["advice"])
                )
            conn.commit()
            print("[DB] disease_info di-seed dengan data default.")

        cursor.close()
        conn.close()
        print("[DB] Tabel berhasil diinisialisasi.")
    except Error as e:
        print(f"[DB] Gagal membuat tabel: {e}")


# ── Helper: ambil semua disease_info sebagai dict (key=predicted_class) ──────
def get_disease_info_dict() -> dict:
    """
    Ambil seluruh disease_info dari database dan kembalikan sebagai dict
    dengan key predicted_class, supaya kompatibel dengan struktur DISEASE_INFO lama.
    advice disimpan sebagai TEXT multi-baris, di-split jadi list di sini.
    """
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM disease_info")
        rows = cursor.fetchall()
        result = {}
        for r in rows:
            advice_list = [line.strip() for line in (r["advice"] or "").split("\n") if line.strip()]
            result[r["predicted_class"]] = {
                "emoji": r["emoji"],
                "label": r["label"],
                "color": r["color"],
                "description": r["description"],
                "advice": advice_list,
            }
        return result
    finally:
        cursor.close()
        conn.close()


# ── Helper: catat log aktivitas ──────────────────────────────────────────────
def log_activity(user_id, action: str, detail: str = None):
    """
    Catat aktivitas dasar user ke tabel activity_logs.
    action contoh: 'login', 'predict', 'chatbot'
    Dipanggil secara best-effort — kalau gagal, tidak boleh mengganggu request utama.
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO activity_logs (user_id, action, detail, created_at) VALUES (%s, %s, %s, %s)",
            (user_id, action, detail, __import__("datetime").datetime.now())
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        print(f"[DB] Gagal mencatat log aktivitas: {e}")