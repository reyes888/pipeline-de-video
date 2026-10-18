from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.ws.manager import manager

router = APIRouter()


@router.websocket("/ws/{project_id}")
async def project_ws(websocket: WebSocket, project_id: str) -> None:
    await manager.connect(project_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(project_id, websocket)
