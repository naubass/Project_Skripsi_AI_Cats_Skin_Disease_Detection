from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.state import templates
from core.dependencies import get_current_user
import json

router = APIRouter(tags=["telemed"])

class ConnectionManager:
    def __init__(self):
        # Menyimpan websocket aktif berdasarkan room_id
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
        """Kirim pesan ke partisipan lain di room yang sama."""
        if room_id in self.active_connections:
            for cid, ws in self.active_connections[room_id].items():
                if cid != sender_id:
                    await ws.send_text(message)

manager = ConnectionManager()

@router.get("/telemed/{room_id}", response_class=HTMLResponse)
async def telemed_room_page(request: Request, room_id: str):
    """Merender halaman UI Video Call."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse("telemed_room.html", {
        "request": request, 
        "user": user, 
        "room_id": room_id
    })

@router.websocket("/ws/telemed/{room_id}/{client_id}")
async def telemed_signaling(websocket: WebSocket, room_id: str, client_id: str):
    """Endpoint WebSocket untuk pertukaran sinyal WebRTC (SDP & ICE)."""
    await manager.connect(websocket, room_id, client_id)
    try:
        await manager.broadcast(json.dumps({"type": "peer_joined", "client_id": client_id}), room_id, client_id)
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data, room_id, client_id)
    except WebSocketDisconnect:
        manager.disconnect(room_id, client_id)
        await manager.broadcast(json.dumps({"type": "peer_left", "client_id": client_id}), room_id, client_id)