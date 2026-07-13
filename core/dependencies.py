"""
core/dependencies.py — Helper otorisasi/sesi yang dipakai hampir semua controller.
"""

from fastapi import Request


def get_current_user(request: Request):
    """Ambil data user dari session (None kalau belum login)."""
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