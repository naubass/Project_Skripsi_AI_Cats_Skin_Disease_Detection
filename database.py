"""
database.py — Koneksi MySQL, inisialisasi tabel, migrasi otomatis,
dan fungsi helper data.
"""

import os
import mysql.connector
from mysql.connector import Error
from datetime import datetime

# ── Konfigurasi ────────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host"            : os.getenv("DB_HOST",     "localhost"),
    "port"            : int(os.getenv("DB_PORT", "3306")),
    "user"            : os.getenv("DB_USER",     "root"),
    "password"        : os.getenv("DB_PASSWORD", ""),
    "database"        : os.getenv("DB_NAME",     "catskindisease"),
    "connect_timeout" : 5,
}

# ── Koneksi dengan retry ─────────────────────────────────────────────────────────
def _connect_with_retry(config: dict, max_retries: int = 3, delay: int = 3):
    """Connect ke MySQL dengan mekanisme retry."""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[DB] Percobaan koneksi #{attempt}/{max_retries}...")
            conn = mysql.connector.connect(**config)
            print(f"[DB] Percobaan #{attempt} berhasil.")
            return conn
        except Error as e:
            last_error = e
            print(f"[DB] Percobaan #{attempt} gagal: {e}")
            if attempt < max_retries:
                import time
                time.sleep(delay)
    raise last_error


def get_db() -> mysql.connector.MySQLConnection:
    """Return satu koneksi MySQL baru (caller harus .close() sendiri)."""
    return _connect_with_retry(DB_CONFIG)


# ── Disease info default (seed pertama kali) ──────────────────────────────────
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


# ── Info klinik Sakti Pet Care (statis) ───────────────────────────────────────
CLINIC_INFO = {
    "name": "Sakti Pet Care",
    "phone": "0852-1132-2390",
    "phone_wa_link": "https://wa.me/6285211322390",
    "address": "Blok K2 No 11A, Jl. Binong Permai, Sukabakti, Kec. Curug, Kabupaten Tangerang, Banten 15810",
    "hours": [
        {"days": "Senin–Rabu, Sabtu–Minggu", "time": "09.00–21.00"},
        {"days": "Kamis", "time": "09.00–17.00"},
        {"days": "Jumat", "time": "09.00–11.00, 14.00–21.00 (istirahat siang)"},
    ],
}


def get_clinic_info() -> dict:
    """Return info kontak & jam operasional klinik."""
    return CLINIC_INFO


# ── Init Tabel & Migrasi Otimatis ─────────────────────────────────────────────
def init_db():
    """Buat database & tabel bila belum ada + jalankan migrasi kolom otomatis."""
    print("[DB] Memulai init_db()...")
    print(f"[DB] Target koneksi: host={DB_CONFIG['host']} port={DB_CONFIG['port']} db={DB_CONFIG['database']}")

    cfg_no_db = {k: v for k, v in DB_CONFIG.items() if k != "database"}
    try:
        print("[DB] Menghubungkan ke server MySQL untuk CREATE DATABASE...")
        conn = _connect_with_retry(cfg_no_db)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        cursor.close()
        conn.close()
        print("[DB] Database OK.")
    except Error as e:
        print(f"[DB] Gagal membuat database: {e}")
        return

    try:
        print("[DB] Menghubungkan ke database aplikasi...")
        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute("SET SESSION lock_wait_timeout = 10")
        except Error as e:
            print(f"[DB] Tidak bisa set lock_wait_timeout: {e}")

        # ── 1. Tabel users ──
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INT AUTO_INCREMENT PRIMARY KEY,
                name          VARCHAR(100)        NOT NULL,
                email         VARCHAR(150) UNIQUE  NOT NULL,
                password_hash VARCHAR(255)         NOT NULL,
                role          ENUM('user','admin','dokter','owner') NOT NULL DEFAULT 'user',
                is_active     TINYINT(1)           NOT NULL DEFAULT 1,
                last_login    DATETIME             NULL,
                created_at    DATETIME             NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()

        # Migrasi Users
        try:
            cursor.execute("ALTER TABLE users MODIFY COLUMN role ENUM('user','admin','dokter','owner') NOT NULL DEFAULT 'user'")
            conn.commit()
        except Error: pass

        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1")
            conn.commit()
        except Error: pass

        # ── 2. Tabel disease_info ──
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
        conn.commit()

        # ── 3. Tabel predictions ──
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                user_id         INT          NOT NULL,
                predicted_class VARCHAR(50) NOT NULL,
                label           VARCHAR(100) NOT NULL,
                confidence      FLOAT        NOT NULL,
                description     TEXT         NULL,
                image_data      LONGBLOB     NULL,
                visit_confirmed TINYINT(1)   NOT NULL DEFAULT 0,
                visit_confirmed_at DATETIME  NULL,
                created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()

        # Migrasi Predictions
        try:
            cursor.execute("ALTER TABLE predictions ADD COLUMN image_data LONGBLOB NULL")
            conn.commit()
        except Error: pass

        try:
            cursor.execute("ALTER TABLE predictions ADD COLUMN visit_confirmed TINYINT(1) NOT NULL DEFAULT 0")
            conn.commit()
        except Error: pass

        try:
            cursor.execute("ALTER TABLE predictions ADD COLUMN visit_confirmed_at DATETIME NULL")
            conn.commit()
        except Error: pass

        # ── 4. Tabel activity_logs ──
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

        # ── 5. Tabel doctor_notes ──
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctor_notes (
                id             INT AUTO_INCREMENT PRIMARY KEY,
                prediction_id  INT          NOT NULL,
                doctor_id      INT          NOT NULL,
                note           TEXT         NOT NULL,
                need_visit     TINYINT(1)   NOT NULL DEFAULT 0,
                created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE CASCADE,
                FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()

        try:
            cursor.execute("ALTER TABLE doctor_notes ADD COLUMN need_visit TINYINT(1) NOT NULL DEFAULT 0")
            conn.commit()
        except Error: pass

        # ── 6. Tabel laporan_kunjungan (Otomatis dibuat dengan user_id & confirmed_by NULLABLE) ──
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS laporan_kunjungan (
                id                 INT AUTO_INCREMENT PRIMARY KEY,
                prediction_id      INT          NOT NULL,
                user_id            INT          NULL,
                patient_id         INT          NULL,
                confirmed_by       INT          NULL,
                catatan_kunjungan  TEXT         NULL,
                status             ENUM('terjadwal','selesai','batal') NOT NULL DEFAULT 'terjadwal',
                visit_date         DATETIME     NULL,
                created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (confirmed_by) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()

        # Migrasi Laporan Kunjungan (Menambahkan kolom user_id jika belum ada)
        try:
            cursor.execute("ALTER TABLE laporan_kunjungan ADD COLUMN user_id INT NULL AFTER prediction_id")
            conn.commit()
            print("[DB] Migrasi kolom user_id pada laporan_kunjungan selesai.")
        except Error as e:
            print(f"[DB] Migrasi user_id dilewati/sudah ada ({e}).")

        try:
            cursor.execute("ALTER TABLE laporan_kunjungan MODIFY COLUMN patient_id INT NULL")
            cursor.execute("ALTER TABLE laporan_kunjungan MODIFY COLUMN confirmed_by INT NULL")
            conn.commit()
        except Error: pass

        # ── Seed data default ──
        cursor.execute("SELECT COUNT(*) FROM disease_info")
        if cursor.fetchone()[0] == 0:
            for d in DEFAULT_DISEASE_INFO:
                cursor.execute(
                    """INSERT INTO disease_info (predicted_class, label, emoji, color, description, advice)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (d["predicted_class"], d["label"], d["emoji"], d["color"], d["description"], d["advice"])
                )
            conn.commit()

        cursor.close()
        conn.close()
        print("[DB] Tabel & migrasi berhasil diinisialisasi.")
    except Error as e:
        print(f"[DB] Gagal membuat tabel: {e}")


# ── Helper: Ambil disease_info sebagai dict ──────────────────────────────────
def get_disease_info_dict() -> dict:
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


# ── Helper: Catat Log Aktivitas ───────────────────────────────────────────────
def log_activity(user_id, action: str, detail: str = None):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO activity_logs (user_id, action, detail, created_at) VALUES (%s, %s, %s, %s)",
            (user_id, action, detail, datetime.now())
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        print(f"[DB] Gagal mencatat log aktivitas: {e}")


# ── Helper: Catatan Dokter ───────────────────────────────────────────────────
def add_doctor_note(prediction_id: int, doctor_id: int, note: str, need_visit: bool = False) -> int:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO doctor_notes (prediction_id, doctor_id, note, need_visit, created_at) VALUES (%s, %s, %s, %s, %s)",
            (prediction_id, doctor_id, note, 1 if need_visit else 0, datetime.now())
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        conn.close()


def delete_doctor_note(note_id: int, doctor_id: int) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM doctor_notes WHERE id = %s AND doctor_id = %s",
            (note_id, doctor_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


def get_doctor_notes_for_predictions(prediction_ids: list) -> dict:
    result = {}
    if not prediction_ids:
        return result
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        placeholders = ", ".join(["%s"] * len(prediction_ids))
        cursor.execute(
            f"""SELECT dn.id, dn.prediction_id, dn.note, dn.need_visit, dn.created_at, u.name AS doctor_name
                FROM doctor_notes dn
                JOIN users u ON dn.doctor_id = u.id
                WHERE dn.prediction_id IN ({placeholders})
                ORDER BY dn.created_at DESC""",
            tuple(prediction_ids)
        )
        for row in cursor.fetchall():
            row["need_visit"] = bool(row["need_visit"])
            result.setdefault(row["prediction_id"], []).append(row)
        return result
    finally:
        cursor.close()
        conn.close()


# ── Helper: Booking & Laporan Kunjungan ────────────────────────────────────────

def get_booked_slots(date_str: str):
    """Mengambil daftar jam (format HH:MM) yang sedang di-booking pasien lain (status 'terjadwal' atau 'selesai')."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        date_clean = date_str.strip()
        cursor.execute(
            """SELECT DATE_FORMAT(visit_date, '%H:%i') AS booked_time 
               FROM laporan_kunjungan 
               WHERE DATE(visit_date) = %s 
                 AND status IN ('terjadwal', 'selesai') 
                 AND visit_date IS NOT NULL""",
            (date_clean,)
        )
        rows = cursor.fetchall()
        # Mengembalikan list jam bersih tanpa detik, contoh: ['10:00', '20:00']
        return [r["booked_time"].strip() for r in rows if r.get("booked_time")]
    finally:
        cursor.close()
        db.close()


def save_user_booking(prediction_id: int, user_id: int, visit_datetime: datetime):
    """Menyimpan atau memperbarui booking kunjungan dari sisi user. 
    Jika sebelumnya dibatalkan, booking baru akan mereset status konfirmasi dokter (kembali ke null/perlu persetujuan)."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        # Cek apakah sudah ada laporan kunjungan untuk prediksi ini
        cursor.execute("SELECT id, status FROM laporan_kunjungan WHERE prediction_id = %s", (prediction_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Jika sebelumnya dibatalkan atau terjadwal, saat user booking ulang, 
            # kita set ulang confirmed_by = NULL agar butuh persetujuan dokter kembali dari awal!
            cursor.execute(
                """UPDATE laporan_kunjungan 
                   SET visit_date = %s, status = 'terjadwal', confirmed_by = NULL, user_id = %s, patient_id = %s, catatan_kunjungan = NULL
                   WHERE prediction_id = %s""",
                (visit_datetime, user_id, user_id, prediction_id)
            )
        else:
            cursor.execute(
                """INSERT INTO laporan_kunjungan (prediction_id, user_id, patient_id, confirmed_by, status, visit_date, created_at)
                   VALUES (%s, %s, %s, NULL, 'terjadwal', %s, NOW())""",
                (prediction_id, user_id, user_id, visit_datetime)
            )
        db.commit()
    finally:
        cursor.close()
        db.close()


def cancel_user_booking(prediction_id: int, user_id: int):
    """Membatalkan booking kunjungan milik user dan mereset status konfirmasi di prediksi."""
    db = get_db()
    cursor = db.cursor()
    try:
        # Ubah status laporan menjadi 'batal' tanpa menghapus confirmed_by jika dokter pernah mengonfirmasi
        cursor.execute(
            """UPDATE laporan_kunjungan 
               SET status = 'batal', catatan_kunjungan = 'Dibatalkan oleh Pasien' 
               WHERE prediction_id = %s AND (user_id = %s OR patient_id = %s)""",
            (prediction_id, user_id, user_id)
        )
        
        # Reset tanda visit_confirmed pada tabel predictions ke 0
        cursor.execute(
            """UPDATE predictions 
               SET visit_confirmed = 0, visit_confirmed_at = NULL 
               WHERE id = %s AND user_id = %s""",
            (prediction_id, user_id)
        )
        db.commit()
    finally:
        cursor.close()
        db.close()


def auto_update_expired_visits():
    """Mengubah status 'terjadwal' menjadi 'selesai' secara otomatis jika waktu booking sudah lewat."""
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """UPDATE laporan_kunjungan 
               SET status = 'selesai' 
               WHERE status = 'terjadwal' AND visit_date IS NOT NULL AND visit_date <= NOW()"""
        )
        db.commit()
    finally:
        cursor.close()
        db.close()


def confirm_visit(prediction_id: int, patient_id: int, doctor_id: int, catatan: str = None) -> int:
    """Konfirmasi kunjungan oleh dokter."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        now = datetime.now()
        cursor.execute(
            "UPDATE predictions SET visit_confirmed = 1, visit_confirmed_at = %s WHERE id = %s",
            (now, prediction_id)
        )
        
        cursor.execute("SELECT id, visit_date FROM laporan_kunjungan WHERE prediction_id = %s", (prediction_id,))
        existing = cursor.fetchone()
        
        if existing:
            v_date = existing["visit_date"] or now
            cursor.execute(
                """UPDATE laporan_kunjungan 
                   SET confirmed_by = %s, catatan_kunjungan = %s, status = 'terjadwal', visit_date = %s
                   WHERE id = %s""",
                (doctor_id, catatan, v_date, existing["id"])
            )
            conn.commit()
            return existing["id"]
        else:
            cursor.execute(
                """INSERT INTO laporan_kunjungan
                   (prediction_id, user_id, patient_id, confirmed_by, catatan_kunjungan, status, visit_date, created_at)
                   VALUES (%s, %s, %s, %s, %s, 'terjadwal', %s, %s)""",
                (prediction_id, patient_id, patient_id, doctor_id, catatan, now, now)
            )
            conn.commit()
            return cursor.lastrowid
    finally:
        cursor.close()
        conn.close()


def get_all_laporan_kunjungan(status: str = None, search: str = None) -> list:
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        base = """
            SELECT lk.*, 
                   COALESCE(u.name, 'Pasien') AS patient_name, 
                   COALESCE(u.email, '-') AS patient_email,
                   COALESCE(d.name, 'Dokter') AS confirmed_by_name,
                   p.predicted_class, p.label, p.confidence
            FROM laporan_kunjungan lk
            LEFT JOIN users u ON (lk.patient_id = u.id OR lk.user_id = u.id)
            JOIN users d ON lk.confirmed_by = d.id
            JOIN predictions p ON lk.prediction_id = p.id
            WHERE lk.confirmed_by IS NOT NULL
        """
        conditions = []
        params = []
        
        if status:
            conditions.append("lk.status = %s")
            params.append(status)
        if search:
            conditions.append("u.name LIKE %s")
            params.append(f"%{search}%")
            
        if conditions:
            base += " AND " + " AND ".join(conditions)
        base += " ORDER BY lk.created_at DESC"
        
        cursor.execute(base, tuple(params))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def get_laporan_kunjungan_by_id(laporan_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT lk.*, 
                   COALESCE(u.name, 'Pasien') AS patient_name, 
                   COALESCE(u.email, '-') AS patient_email,
                   COALESCE(d.name, 'Sistem') AS confirmed_by_name,
                   p.predicted_class, p.label, p.confidence, p.description AS prediction_description
            FROM laporan_kunjungan lk
            LEFT JOIN users u ON (lk.patient_id = u.id OR lk.user_id = u.id)
            LEFT JOIN users d ON lk.confirmed_by = d.id
            JOIN predictions p ON lk.prediction_id = p.id
            WHERE lk.id = %s
        """, (laporan_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def update_laporan_kunjungan_status(laporan_id: int, status: str, visit_date=None) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE laporan_kunjungan SET status = %s, visit_date = %s WHERE id = %s",
            (status, visit_date, laporan_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


def get_pending_recommendations(search: str = None) -> list:
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        sql = """
            SELECT dn.id AS note_id, dn.note, dn.created_at AS note_date,
                   p.id AS prediction_id, p.label, p.confidence,
                   u.id AS patient_id, u.name AS patient_name, u.email AS patient_email,
                   d.name AS doctor_name
            FROM doctor_notes dn
            JOIN predictions p ON dn.prediction_id = p.id
            JOIN users u ON p.user_id = u.id
            JOIN users d ON dn.doctor_id = d.id
            WHERE dn.need_visit = 1 AND p.visit_confirmed = 0
        """
        params = []
        if search:
            sql += " AND u.name LIKE %s"
            params.append(f"%{search}%")
        sql += " ORDER BY dn.created_at DESC"
        
        cursor.execute(sql, tuple(params))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()