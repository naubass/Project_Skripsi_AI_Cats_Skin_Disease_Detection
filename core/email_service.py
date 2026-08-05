"""
core/email_service.py — Kirim email notifikasi via Gmail SMTP.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Sakti Pet Care")

def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Kirim email HTML. Return True kalau berhasil, False kalau gagal (tidak melempar exception)."""
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[EMAIL] SMTP_USER atau SMTP_PASSWORD belum diset, email tidak dikirim.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["FROM"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())

        print(f"[EMAIL] Berhasil kirim ke {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"[EMAIL] Gagal kirim ke {to_email}: {e}")
        return False

def build_telemed_reminder_html(user_name: str, doctor_name: str, prediction_label: str, room_url: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px; background: #faf8f5;">
      <div style="background: linear-gradient(135deg, #2d1b69, #4c2fa0); padding: 24px; border-radius: 16px 16px 0 0;">
        <h2 style="color: #fff; margin: 0;">🐾 Sakti Pet Care</h2>
        <p style="color: #d4a843; margin: 4px 0 0; font-size: 12px; font-weight: bold; text-transform: uppercase;">Pengingat Konsultasi Online</p>
      </div>
      <div style="background: #fff; padding: 24px; border-radius: 0 0 16px 16px;">
        <p style="color: #1a1128;">Halo <strong>{user_name}</strong>,</p>
        <p style="color: #4a3f6b; line-height: 1.6;">
          Ruang konsultasi video Anda dengan <strong>dr. {doctor_name}</strong> mengenai hasil diagnosis
          <strong>{prediction_label}</strong> akan dibuka dalam <strong>30 menit</strong>. Siapkan kucing Anda! 🐱
        </p>
        <a href="{room_url}" style="display: inline-block; margin-top: 16px; background: #2563eb; color: #fff; padding: 12px 24px; border-radius: 10px; text-decoration: none; font-weight: bold;">
          📹 Masuk Ruang Video Call
        </a>
        <p style="color: #8b7fb8; font-size: 12px; margin-top: 24px;">
          Email ini dikirim otomatis oleh sistem Sakti Pet Care CatSkin AI.
        </p>
      </div>
    </div>
    """

def build_visit_reminder_html(user_name: str, doctor_name: str, prediction_label: str, visit_time: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px; background: #faf8f5;">
      <div style="background: linear-gradient(135deg, #2d1b69, #4c2fa0); padding: 24px; border-radius: 16px 16px 0 0;">
        <h2 style="color: #fff; margin: 0;">🐾 Sakti Pet Care</h2>
        <p style="color: #d4a843; margin: 4px 0 0; font-size: 12px; font-weight: bold; text-transform: uppercase;">Pengingat Kunjungan Klinik</p>
      </div>
      <div style="background: #fff; padding: 24px; border-radius: 0 0 16px 16px;">
        <p style="color: #1a1128;">Halo <strong>{user_name}</strong>,</p>
        <p style="color: #4a3f6b; line-height: 1.6;">
          Jadwal kunjungan Anda ke klinik untuk pemeriksaan <strong>{prediction_label}</strong>
          (dikonfirmasi oleh dr. {doctor_name}) akan dimulai pukul <strong>{visit_time}</strong>, sekitar 30 menit lagi.
        </p>
        <p style="color: #4a3f6b; line-height: 1.6;">
          📍 Sakti Pet Care, Blok K2 No 11A, Jl. Binong Permai, Sukabakti, Kec. Curug, Kabupaten Tangerang, Banten 15810
        </p>
        <p style="color: #8b7fb8; font-size: 12px; margin-top: 24px;">
          Email ini dikirim otomatis oleh sistem Sakti Pet Care CatSkin AI.
        </p>
      </div>
    </div>
    """
def build_telemed_approved_html(user_name: str, doctor_name: str, prediction_label: str, scheduled_at_str: str, room_url: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px; background: #faf8f5;">
      <div style="background: linear-gradient(135deg, #2d1b69, #4c2fa0); padding: 24px; border-radius: 16px 16px 0 0;">
        <h2 style="color: #fff; margin: 0;">🐾 Sakti Pet Care</h2>
        <p style="color: #d4a843; margin: 4px 0 0; font-size: 12px; font-weight: bold; text-transform: uppercase;">Konsultasi Disetujui</p>
      </div>
      <div style="background: #fff; padding: 24px; border-radius: 0 0 16px 16px;">
        <p style="color: #1a1128;">Halo <strong>{user_name}</strong>,</p>
        <p style="color: #4a3f6b; line-height: 1.6;">
          Pengajuan konsultasi online Anda mengenai <strong>{prediction_label}</strong> telah disetujui oleh
          <strong>dr. {doctor_name}</strong>, dijadwalkan pada <strong>{scheduled_at_str}</strong>.
        </p>
        <a href="{room_url}" style="display: inline-block; margin-top: 16px; background: #2563eb; color: #fff; padding: 12px 24px; border-radius: 10px; text-decoration: none; font-weight: bold;">
          📹 Lihat Detail
        </a>
        <p style="color: #8b7fb8; font-size: 12px; margin-top: 24px;">
          Anda juga akan menerima email pengingat 30 menit sebelum jadwal.
        </p>
      </div>
    </div>
    """

def build_visit_confirmed_html(user_name: str, doctor_name: str, prediction_label: str, visit_time: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px; background: #faf8f5;">
      <div style="background: linear-gradient(135deg, #2d1b69, #4c2fa0); padding: 24px; border-radius: 16px 16px 0 0;">
        <h2 style="color: #fff; margin: 0;">🐾 Sakti Pet Care</h2>
        <p style="color: #d4a843; margin: 4px 0 0; font-size: 12px; font-weight: bold; text-transform: uppercase;">Kunjungan Dikonfirmasi</p>
      </div>
      <div style="background: #fff; padding: 24px; border-radius: 0 0 16px 16px;">
        <p style="color: #1a1128;">Halo <strong>{user_name}</strong>,</p>
        <p style="color: #4a3f6b; line-height: 1.6;">
          Jadwal kunjungan Anda untuk pemeriksaan <strong>{prediction_label}</strong> telah dikonfirmasi oleh
          <strong>dr. {doctor_name}</strong>, pada <strong>{visit_time}</strong>.
        </p>
        <p style="color: #4a3f6b; line-height: 1.6;">
          📍 Sakti Pet Care, Blok K2 No 11A, Jl. Binong Permai, Sukabakti, Kec. Curug, Kabupaten Tangerang, Banten 15810
        </p>
        <p style="color: #8b7fb8; font-size: 12px; margin-top: 24px;">
          Anda akan menerima email pengingat lagi 30 menit sebelum jadwal.
        </p>
      </div>
    </div>
    """


def build_telemed_approved_html(user_name: str, doctor_name: str, prediction_label: str, scheduled_at_str: str, room_url: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px; background: #faf8f5;">
      <div style="background: linear-gradient(135deg, #2d1b69, #4c2fa0); padding: 24px; border-radius: 16px 16px 0 0;">
        <h2 style="color: #fff; margin: 0;">🐾 Sakti Pet Care</h2>
        <p style="color: #d4a843; margin: 4px 0 0; font-size: 12px; font-weight: bold; text-transform: uppercase;">Konsultasi Online Disetujui</p>
      </div>
      <div style="background: #fff; padding: 24px; border-radius: 0 0 16px 16px;">
        <p style="color: #1a1128;">Halo <strong>{user_name}</strong>,</p>
        <p style="color: #4a3f6b; line-height: 1.6;">
          Pengajuan konsultasi online Anda mengenai <strong>{prediction_label}</strong> telah disetujui oleh
          <strong>dr. {doctor_name}</strong>, dijadwalkan pada <strong>{scheduled_at_str}</strong>.
        </p>
        <a href="{room_url}" style="display: inline-block; margin-top: 16px; background: #2563eb; color: #fff; padding: 12px 24px; border-radius: 10px; text-decoration: none; font-weight: bold;">
          📹 Lihat Detail
        </a>
        <p style="color: #8b7fb8; font-size: 12px; margin-top: 24px;">
          Anda akan menerima email pengingat lagi 30 menit sebelum jadwal.
        </p>
      </div>
    </div>
    """