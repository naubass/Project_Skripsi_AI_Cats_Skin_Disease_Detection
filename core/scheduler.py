"""
core/scheduler.py — Background job untuk cek & kirim reminder booking 30 menit sebelum jadwal.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from database import (
    get_upcoming_telemed_reminders, get_upcoming_visit_reminders,
    mark_telemed_reminder_sent, mark_visit_reminder_sent
)
from core.email_service import send_email, build_telemed_reminder_html, build_visit_reminder_html

def check_and_send_reminders():
    """Dipanggil tiap 1 menit oleh scheduler. Cek jadwal 25-35 menit ke depan, kirim email, tandai terkirim."""

    try:
        telemed_list = get_upcoming_telemed_reminders()
        for t in telemed_list:
            room_url = f"http://127.0.0.1:8000/telemed/{t['room_id']}"  # ganti ke domain production nanti
            html = build_telemed_reminder_html(
                user_name=t["user_name"],
                doctor_name=t["doctor_name"] or "Dokter",
                prediction_label=t["prediction_label"],
                room_url=room_url,
            )
            success = send_email(
                to_email=t["user_email"],
                subject="⏰ Konsultasi Online Anda Dimulai 30 Menit Lagi — Sakti Pet Care",
                html_body=html,
            )
            if success:
                mark_telemed_reminder_sent(t["id"])
    except Exception as e:
        print(f"[SCHEDULER] Gagal kirim email: {e}")

    try:
        visit_list = get_upcoming_visit_reminders()
        for v in visit_list:
            visit_time_str = v["visit_date"].strftime("%d %b %Y, %H:%M WIB")
            html = build_visit_reminder_html(
                user_name=v["user_name"],
                doctor_name=v["doctor_name"] or "Dokter",
                prediction_label=v["prediction_label"],
                visit_time=visit_time_str,
            )
            success = send_email(
                to_email=v["user_email"],
                subject="⏰ Jadwal Kunjungan Klinik Anda 30 Menit Lagi — Sakti Pet Care",
                html_body=html,
            )
            if success:
                mark_visit_reminder_sent(v["id"])
    except Exception as e:
        print(f"[SCHEDULER] Gagal proses reminder kunjungan fisik: {e}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_send_reminders, "interval", minutes=1, id="reminder_job")
    scheduler.start()
    print("[SCHEDULER] Reminder scheduler jalan, cek tiap 1 menit.")
    return scheduler