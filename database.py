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
    # PENTING: tanpa connect_timeout, mysql.connector bisa hang TANPA BATAS
    # WAKTU dan TANPA ERROR kalau host tidak merespon (umum terjadi dengan
    # proxy publik seperti Railway TCP proxy yang sesekali lambat/hang dari
    # luar jaringannya). Timeout pendek di sini dikombinasikan dengan retry
    # di _connect_with_retry() supaya total waktu tunggu tetap terbatas,
    # dan kalau gagal kamu dapat error jelas, bukan startup yang diam.
    "connect_timeout": 5,
}

# ── Koneksi dengan retry ─────────────────────────────────────────────────────────
def _connect_with_retry(config: dict, max_retries: int = 3, delay: int = 3):
    """
    Connect ke MySQL dengan retry. Railway (dan proxy publik sejenis) kadang
    mengalami koneksi pertama yang hang/lambat dari luar jaringannya sendiri.
    Daripada bergantung pada satu kali percobaan, kita coba beberapa kali
    dengan connect_timeout pendek per percobaan (lihat DB_CONFIG) — supaya
    prosesnya lebih cepat ketahuan gagal/berhasil, bukan diam lama.

    CATATAN: sengaja TIDAK menambahkan ThreadPoolExecutor/nested-thread di
    sini untuk membatasi waktu connect secara manual. mysql.connector punya
    native C extension, dan menjalankannya di dalam thread bersarang
    (apalagi saat dipanggil dari background thread lain seperti init_db())
    berisiko memicu segfault akibat konflik native code — ini yang terjadi
    sebelumnya. connect_timeout di level driver sudah cukup selama urutan
    import di app.py benar (mysql.connector diimpor sebelum numpy/tensorflow).
    """
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


# ── Info klinik Sakti Pet Care (statis, dipakai di halaman riwayat) ───────────
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
    """Return info kontak & jam operasional klinik (statis)."""
    return CLINIC_INFO


# ── Init Tabel ──────────────────────────────────────────────────────────────────
def init_db():
    """Buat database & tabel bila belum ada."""
    print("[DB] Memulai init_db()...")
    print(f"[DB] Target koneksi: host={DB_CONFIG['host']} port={DB_CONFIG['port']} db={DB_CONFIG['database']}")

    cfg_no_db = {k: v for k, v in DB_CONFIG.items() if k != "database"}
    try:
        print("[DB] Menghubungkan ke server MySQL (tanpa database) untuk CREATE DATABASE...")
        conn = _connect_with_retry(cfg_no_db)
        print("[DB] Koneksi server berhasil. Membuat database jika belum ada...")
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
        print("[DB] Koneksi database aplikasi berhasil.")

        # Batasi waktu tunggu metadata lock — supaya kalau ada koneksi lama
        # yang masih memegang lock di tabel (misal dari proses sebelumnya
        # yang tidak tertutup rapi saat container restart/redeploy),
        # ALTER TABLE tidak hang selamanya tanpa pesan error sama sekali.
        # Default MySQL bisa menunggu lock dalam waktu yang sangat lama.
        try:
            cursor.execute("SET SESSION lock_wait_timeout = 10")
        except Error as e:
            print(f"[DB] Tidak bisa set lock_wait_timeout: {e}")

        print("[DB] Membuat/memeriksa tabel users...")
        # ── Tabel users (role ditambah 'dokter') ──────────────────────────
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
        print("[DB] Tabel users OK. Menjalankan migrasi kolom (jika perlu)...")

        # Migrasi: kalau tabel users sudah ada dari versi lama (role tanpa
        # 'dokter' atau tanpa kolom is_active), tambahkan secara aman.
        # Setiap ALTER di-commit sendiri & errornya dicetak (bukan di-pass
        # diam-diam) supaya kalau memang gagal/timeout, kelihatan di log
        # alih-alih bikin proses terlihat "stuck tanpa error".
        try:
            cursor.execute("ALTER TABLE users MODIFY COLUMN role ENUM('user','admin','dokter','owner') NOT NULL DEFAULT 'user'")
            conn.commit()
            print("[DB] Migrasi kolom role (+owner) selesai.")
        except Error as e:
            print(f"[DB] Migrasi kolom role dilewati ({e}).")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1")
            conn.commit()
            print("[DB] Migrasi kolom is_active selesai.")
        except Error as e:
            print(f"[DB] Migrasi kolom is_active dilewati ({e}).")

        print("[DB] Membuat/memeriksa tabel disease_info...")
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
        conn.commit()
        print("[DB] Tabel disease_info OK.")

        print("[DB] Membuat/memeriksa tabel predictions...")
        # ── Tabel predictions ──────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id             INT AUTO_INCREMENT PRIMARY KEY,
                user_id        INT          NOT NULL,
                predicted_class VARCHAR(50) NOT NULL,
                label          VARCHAR(100) NOT NULL,
                confidence     FLOAT        NOT NULL,
                description    TEXT         NULL,
                image_data     LONGBLOB     NULL,
                created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()
        print("[DB] Tabel predictions OK.")

        # Migrasi: kalau tabel predictions sudah ada dari versi sebelum
        # kolom image_data ditambahkan (foto hasil deteksi disimpan
        # langsung di DB sebagai BLOB, dipakai oleh endpoint
        # /predictions/{id}/image), tambahkan secara aman.
        try:
            cursor.execute("ALTER TABLE predictions ADD COLUMN image_data LONGBLOB NULL")
            conn.commit()
            print("[DB] Migrasi kolom image_data selesai.")
        except Error as e:
            print(f"[DB] Migrasi kolom image_data dilewati ({e}).")

        # Migrasi: tandai apakah saran kunjungan klinik pada satu prediksi
        # sudah dikonfirmasi oleh dokter (lalu otomatis dicatat di
        # laporan_kunjungan). Dipakai untuk mengubah badge "Perlu kunjungan"
        # menjadi "Sudah kunjungan" di halaman riwayat pasien (history.html).
        try:
            cursor.execute("ALTER TABLE predictions ADD COLUMN visit_confirmed TINYINT(1) NOT NULL DEFAULT 0")
            conn.commit()
            print("[DB] Migrasi kolom visit_confirmed selesai.")
        except Error as e:
            print(f"[DB] Migrasi kolom visit_confirmed dilewati ({e}).")

        try:
            cursor.execute("ALTER TABLE predictions ADD COLUMN visit_confirmed_at DATETIME NULL")
            conn.commit()
            print("[DB] Migrasi kolom visit_confirmed_at selesai.")
        except Error as e:
            print(f"[DB] Migrasi kolom visit_confirmed_at dilewati ({e}).")

        print("[DB] Membuat/memeriksa tabel activity_logs...")
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
        print("[DB] Tabel activity_logs OK.")

        print("[DB] Membuat/memeriksa tabel doctor_notes...")
        # ── Tabel doctor_notes (catatan dokter ke riwayat prediksi user) ──
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
        print("[DB] Tabel doctor_notes OK.")

        # Migrasi: kalau tabel doctor_notes sudah ada dari versi sebelum
        # kolom need_visit ditambahkan, tambahkan secara aman (sama seperti
        # pola migrasi kolom is_active di atas).
        try:
            cursor.execute("ALTER TABLE doctor_notes ADD COLUMN need_visit TINYINT(1) NOT NULL DEFAULT 0")
            conn.commit()
            print("[DB] Migrasi kolom need_visit selesai.")
        except Error as e:
            print(f"[DB] Migrasi kolom need_visit dilewati ({e}).")

        print("[DB] Membuat/memeriksa tabel laporan_kunjungan...")
        # ── Tabel laporan_kunjungan ─────────────────────────────────────────
        # Dibuat otomatis ketika dokter menekan tombol "Konfirmasi Kunjungan"
        # pada halaman detail pasien (patient_detail.html), untuk prediksi
        # yang sebelumnya ditandai need_visit oleh catatan dokter.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS laporan_kunjungan (
                id                 INT AUTO_INCREMENT PRIMARY KEY,
                prediction_id      INT          NOT NULL,
                patient_id         INT          NOT NULL,
                confirmed_by       INT          NOT NULL,
                catatan_kunjungan  TEXT         NULL,
                status             ENUM('terjadwal','selesai','batal') NOT NULL DEFAULT 'terjadwal',
                visit_date         DATETIME     NULL,
                created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE CASCADE,
                FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (confirmed_by) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()
        print("[DB] Tabel laporan_kunjungan OK.")

        # ── Seed disease_info kalau masih kosong ──────────────────────────
        cursor.execute("SELECT COUNT(*) FROM disease_info")
        count = cursor.fetchone()[0]
        if count == 0:
            print("[DB] disease_info kosong, melakukan seed data default...")
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


# ── Helper: catat log aktivitas ───────────────────────────────────────────────
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


# ── Helper: catatan dokter pada riwayat prediksi ──────────────────────────────
def add_doctor_note(prediction_id: int, doctor_id: int, note: str, need_visit: bool = False) -> int:
    """Simpan catatan dokter untuk satu record prediksi. Return id catatan baru."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO doctor_notes (prediction_id, doctor_id, note, need_visit, created_at) VALUES (%s, %s, %s, %s, %s)",
            (prediction_id, doctor_id, note, 1 if need_visit else 0, __import__("datetime").datetime.now())
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        conn.close()


def delete_doctor_note(note_id: int, doctor_id: int) -> bool:
    """Hapus catatan dokter. Hanya dokter pemilik catatan yang boleh menghapus."""
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


# ── Helper: laporan kunjungan (konfirmasi kunjungan klinik) ──────────────────
def confirm_visit(prediction_id: int, patient_id: int, doctor_id: int, catatan: str = None) -> int:
    """
    Menandai kunjungan sebagai 'selesai' secara otomatis saat dikonfirmasi dokter.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        now = __import__("datetime").datetime.now()
        
        # 1. Update status prediksi sebagai sudah kunjungan
        cursor.execute(
            "UPDATE predictions SET visit_confirmed = 1, visit_confirmed_at = %s WHERE id = %s",
            (now, prediction_id)
        )
        
        # 2. Masukkan ke laporan_kunjungan dengan status 'selesai' dan visit_date = now
        cursor.execute(
            """INSERT INTO laporan_kunjungan
               (prediction_id, patient_id, confirmed_by, catatan_kunjungan, status, visit_date, created_at)
               VALUES (%s, %s, %s, %s, 'selesai', %s, %s)""",
            (prediction_id, patient_id, doctor_id, catatan, now, now)
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
            SELECT lk.*, u.name AS patient_name, u.email AS patient_email,
                   d.name AS confirmed_by_name,
                   p.predicted_class, p.label, p.confidence
            FROM laporan_kunjungan lk
            JOIN users u ON lk.patient_id = u.id
            JOIN users d ON lk.confirmed_by = d.id
            JOIN predictions p ON lk.prediction_id = p.id
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
            base += " WHERE " + " AND ".join(conditions)
        base += " ORDER BY lk.created_at DESC"
        
        cursor.execute(base, tuple(params))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def get_laporan_kunjungan_by_id(laporan_id: int) -> dict:
    """Ambil satu laporan kunjungan beserta detail pasien, dokter, dan prediksi terkait."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT lk.*, u.name AS patient_name, u.email AS patient_email,
                   d.name AS confirmed_by_name,
                   p.predicted_class, p.label, p.confidence, p.description AS prediction_description
            FROM laporan_kunjungan lk
            JOIN users u ON lk.patient_id = u.id
            JOIN users d ON lk.confirmed_by = d.id
            JOIN predictions p ON lk.prediction_id = p.id
            WHERE lk.id = %s
        """, (laporan_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def update_laporan_kunjungan_status(laporan_id: int, status: str, visit_date=None) -> bool:
    """Ubah status laporan kunjungan ('terjadwal' / 'selesai' / 'batal') dan tanggal kunjungan opsional."""
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


def get_doctor_notes_for_predictions(prediction_ids: list) -> dict:
    """
    Ambil semua catatan dokter untuk sekumpulan prediction_id sekaligus,
    dikelompokkan per prediction_id (list terurut dari yang terbaru).
    Return: { prediction_id: [ {id, note, doctor_name, created_at}, ... ] }
    """
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