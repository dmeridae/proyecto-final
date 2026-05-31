import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.api.twilio_routes import router as twilio_router
from app.config import settings
from app.database import init_db
from app.services.rag.menu_rag import get_vectorstore
from app.websocket.manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        get_vectorstore()
    except Exception as e:
        print(f"[WARN] RAG no inicializado (¿falta OPENAI_API_KEY?): {e}")
    yield


app = FastAPI(
    title="Call Center Inteligente - La Casa del Sabor",
    description="Sistema de pedidos por llamada con STT, LLM, RAG y tiempo real",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(twilio_router)


@app.websocket("/ws/orders")
async def websocket_orders(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
