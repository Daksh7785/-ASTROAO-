from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Dict, List
import json

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)
    
    def disconnect(self, session_id: str, websocket: WebSocket):
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
    
    async def broadcast_frame(self, session_id: str, frame_data: dict):
        message = json.dumps(frame_data)
        if session_id in self.active_connections:
            for ws in self.active_connections[session_id][:]:
                try:
                    await ws.send_text(message)
                except Exception:
                    self.disconnect(session_id, ws)

manager = ConnectionManager()

@router.websocket("/ws/stream/{session_id}")
async def websocket_frame_stream(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
