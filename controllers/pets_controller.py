"""
controllers/pets_controller.py — CRUD profil kucing (pets) milik user.
"""

from fastapi import APIRouter, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from core.state import templates
from core.dependencies import get_current_user
from database import (
    create_pet, get_pets_by_user, get_pet_by_id,
    update_pet, delete_pet, get_db
)

router = APIRouter(tags=["pets"])
MAX_PETS_PER_USER = 10

@router.get("/pets", response_class=HTMLResponse)
async def pets_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    pets = get_pets_by_user(user["id"])
    return templates.TemplateResponse("pets.html", {
        "request": request, "user": user, "pets": pets,
        "max_pets": MAX_PETS_PER_USER
    })


@router.post("/pets/create")
async def pets_create(
    request: Request,
    name: str = Form(...),
    breed: str = Form(""),
    gender: str = Form(""),
    age_years: str = Form(""),
    age_months: str = Form(""),
    notes: str = Form(""),
    photo: UploadFile = File(None),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    # Cek batas maksimal profil kucing
    existing_pets = get_pets_by_user(user["id"])
    if len(existing_pets) >= MAX_PETS_PER_USER:
        return RedirectResponse(
            f"/pets?error=Maksimal {MAX_PETS_PER_USER} profil kucing per akun. Hapus salah satu profil dulu untuk menambah yang baru.",
            status_code=302
        )

    photo_bytes = await photo.read() if photo and photo.filename else None

    create_pet(
        user_id=user["id"],
        name=name,
        breed=breed.strip() or None,
        gender=gender.strip() or None,
        age_years=int(age_years) if age_years.strip().isdigit() else None,
        age_months=int(age_months) if age_months.strip().isdigit() else None,
        photo_bytes=photo_bytes,
        notes=notes.strip() or None,
    )

    return RedirectResponse("/pets?msg=Profil kucing berhasil ditambahkan!", status_code=302)


@router.post("/pets/{pet_id}/update")
async def pets_update(
    request: Request,
    pet_id: int,
    name: str = Form(...),
    breed: str = Form(""),
    gender: str = Form(""),
    age_years: str = Form(""),
    age_months: str = Form(""),
    notes: str = Form(""),
    photo: UploadFile = File(None),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    photo_bytes = await photo.read() if photo and photo.filename else None

    update_pet(
        pet_id=pet_id,
        user_id=user["id"],
        name=name,
        breed=breed.strip() or None,
        gender=gender.strip() or None,
        age_years=int(age_years) if age_years.strip().isdigit() else None,
        age_months=int(age_months) if age_months.strip().isdigit() else None,
        photo_bytes=photo_bytes,
        notes=notes.strip() or None,
    )

    return RedirectResponse("/pets?msg=Profil kucing berhasil diperbarui!", status_code=302)


@router.post("/pets/{pet_id}/delete")
async def pets_delete(request: Request, pet_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    delete_pet(pet_id, user["id"])
    return RedirectResponse("/pets?msg=Profil kucing berhasil dihapus. Riwayat prediksi tetap tersimpan.", status_code=302)


@router.get("/pets/{pet_id}/photo")
async def pets_photo(request: Request, pet_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT photo_data FROM pets WHERE id = %s AND user_id = %s",
            (pet_id, user["id"])
        )
        row = cursor.fetchone()
    finally:
        cursor.close()
        db.close()

    if not row or not row["photo_data"]:
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan.")

    return Response(content=row["photo_data"], media_type="image/jpeg")