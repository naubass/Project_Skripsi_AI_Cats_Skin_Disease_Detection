import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.state import templates
from core.dependencies import get_current_user
from database import get_db
from datetime import datetime
import json

router = APIRouter(tags=["telemed"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, client_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = {}
        self.active_connections[room_id][client_id] = websocket

    def disconnect(self, room_id: str, client_id: str):
        if room_id in self.active_connections:
            if client_id in self.active_connections[room_id]:
                del self.active_connections[room_id][client_id]
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast(self, message: str, room_id: str, sender_id: str):
        if room_id in self.active_connections:
            for cid, ws in self.active_connections[room_id].items():
                if cid != sender_id:
                    await ws.send_text(message)

manager = ConnectionManager()

@router.get("/telemed/{room_id}", response_class=HTMLResponse)
async def view_telemed_room(room_id: str, request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM konsultasi_online WHERE room_id = %s", (room_id,))
        record = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
    
    if not record or record.get("status") in ["selesai", "batal"]:
        return HTMLResponse("<h3>❌ Sesi konsultasi ini telah berakhir atau dibatalkan.</h3>", status_code=403)
        
    scheduled_at = record.get("scheduled_at")
    if scheduled_at and datetime.now() < scheduled_at:
        return HTMLResponse(f"<h3>⏳ Belum waktunya. Ruang konsultasi baru dapat diakses pada: {scheduled_at}</h3>", status_code=403)

    return templates.TemplateResponse("telemed_room.html", {
        "request": request, 
        "user": user, 
        "room_id": room_id,
        "turn_host": os.getenv("TURN_HOST"),
        "turn_port": os.getenv("TURN_PORT", "3478"),
        "turn_username": os.getenv("TURN_USERNAME"),
        "turn_credential": os.getenv("TURN_CREDENTIAL"),
    })

@router.websocket("/ws/telemed/{room_id}/{client_id}")
async def telemed_signaling(websocket: WebSocket, room_id: str, client_id: str):
    await manager.connect(websocket, room_id, client_id)
    try:
        await manager.broadcast(json.dumps({"type": "peer_joined", "client_id": client_id}), room_id, client_id)
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data, room_id, client_id)
    except WebSocketDisconnect:
        manager.disconnect(room_id, client_id)
        await manager.broadcast(json.dumps({"type": "peer_left", "client_id": client_id}), room_id, client_id)

@router.post("/api/telemed/{room_id}/end")
async def end_telemed_room(room_id: str, request: Request):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM konsultasi_online WHERE room_id = %s", (room_id,))
        record = cursor.fetchone()
        
        if record:
            # 1. Tutup status konsultasi online (mengunci room agar tidak bisa dibuka lagi)
            cursor.execute(
                "UPDATE konsultasi_online SET status = 'selesai' WHERE room_id = %s",
                (room_id,)
            )
            # 2. Reset visit_confirmed pada prediksi agar user bisa melakukan booking ulang jika perlu
            cursor.execute(
                "UPDATE predictions SET visit_confirmed = 0 WHERE id = %s",
                (record["prediction_id"],)
            )
            conn.commit()
    finally:
        cursor.close()
        conn.close()
        
    return {"status": "success", "message": "Room ended successfully"}