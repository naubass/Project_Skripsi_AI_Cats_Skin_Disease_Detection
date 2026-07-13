"""
controllers/chatbot_controller.py — Route halaman & endpoint chatbot (RAG).
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from database import log_activity
from core.state import templates
from core.dependencies import get_current_user

router = APIRouter(tags=["chatbot"])


def _rag_ask(query: str):
    # Import di dalam fungsi (lazy) supaya modul rag (yang bisa memuat
    # model embedding / index berat) tidak wajib ter-load di awal startup
    # aplikasi, cukup saat endpoint ini benar-benar dipanggil.
    from rag import ask
    return ask(query)


@router.get("/chatbot", response_class=HTMLResponse)
async def chatbot_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("chatbot.html", {"request": request, "user": user})


@router.post("/chatbot/ask")
async def chatbot_ask(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login diperlukan.")

    body = await request.json()
    query = body.get("query", "").strip()

    if not query:
        raise HTTPException(status_code=400, detail="Pertanyaan tidak boleh kosong.")
    if len(query) > 500:
        raise HTTPException(status_code=400, detail="Pertanyaan terlalu panjang.")

    result = _rag_ask(query)
    log_activity(user["id"], "chatbot", query[:100])
    return JSONResponse(result)