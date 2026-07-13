"""
core/state.py — Objek & state global yang dipakai lintas controller.

Sengaja dipisah dari main.py supaya semua controller bisa mengimpor
`templates` yang SAMA (satu instance Jinja2Templates), dan supaya
main.py bisa mengisi status db_ready/db_init_error dari startup event
tanpa controller lain perlu tahu detail proses startup itu sendiri.
"""

from typing import Optional
from fastapi.templating import Jinja2Templates

# Satu instance Jinja2Templates dipakai bersama oleh semua controller.
templates = Jinja2Templates(directory="templates")

# Status DB, diisi oleh startup event di main.py.
# Endpoint /health membaca ini supaya bisa dicek tanpa harus login dulu.
db_ready: bool = False
db_init_error: Optional[str] = None