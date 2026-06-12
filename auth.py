"""
auth.py — Helper untuk hash & verifikasi password menggunakan bcrypt.
"""
import bcrypt

def hash_password(plain: str) -> str:
    """Hash password polos menjadi bcrypt hash (string)."""
    hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verifikasi password polos terhadap hash yang tersimpan."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
