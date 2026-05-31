import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.serializers import order_to_out, session_to_out
from app.database import get_db
from app.models.order import Order
from app.schemas.order import (
    CallSessionOut,
    CallTurnRequest,
    OrderOut,
    OrderStatusUpdate,
    SimulationStartRequest,
    StructuredOrder,
)
from app.services.agent.workflow import process_turn
from app.services.order_service import (
    append_transcript,
    confirm_order_for_session,
    create_call_session,
    get_call_session,
    get_order_for_session,
    list_active_calls,
    list_orders,
    update_order_status,
    upsert_order_from_structured,
    user_confirmed,
)
from app.services.rag.menu_rag import ingest_menu
from app.services.voice.stt_tts import synthesize_speech, transcribe_audio
from app.websocket.manager import manager

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    from app.config import settings
    return {
        "status": "ok",
        "openai_configured": bool(settings.openai_api_key),
        "simulation_available": True,
        "twilio_configured": settings.twilio_configured,
        "twilio_call_available": settings.twilio_call_available,
        "twilio_phone_number": settings.twilio_phone_number if settings.twilio_configured else None,
    }


@router.get("/twilio/status")
async def twilio_status():
    """Estado de la opción telefónica. La simulación web siempre está disponible."""
    from app.config import settings

    issues: list[str] = []
    if not settings.twilio_configured:
        issues.append("Faltan TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN o TWILIO_PHONE_NUMBER en backend/.env")
    if settings.twilio_configured and settings.public_base_url_is_local:
        issues.append(
            "PUBLIC_BASE_URL apunta a localhost. Usa ngrok y pon la URL https en .env para recibir llamadas."
        )

    return {
        "simulation_available": True,
        "configured": settings.twilio_configured,
        "call_available": settings.twilio_call_available,
        "phone_number": settings.twilio_phone_number if settings.twilio_configured else None,
        "voice_webhook_url": settings.twilio_voice_webhook_url,
        "public_base_url": settings.public_base_url,
        "issues": issues,
        "setup_steps": [
            "Cuenta en https://www.twilio.com — consola → Account Info (SID y Auth Token).",
            "Phone Numbers → Buy a number → capacidad Voice.",
            "Pegar en backend/.env: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER.",
            "Terminal: ngrok http 8000 → copiar URL https a PUBLIC_BASE_URL en .env.",
            "Twilio → Phone Numbers → tu número → Voice Configuration:",
            f"  A call comes in: Webhook POST → {settings.twilio_voice_webhook_url}",
            "Reiniciar backend (uvicorn). Marcar el número; ver conversación en esta página.",
        ],
    }


@router.post("/rag/ingest")
async def rag_ingest():
    return ingest_menu()


@router.post("/calls/simulation/start", response_model=CallSessionOut)
async def start_simulation(
    body: SimulationStartRequest,
    db: AsyncSession = Depends(get_db),
):
    session = await create_call_session(
        db,
        mode="simulation",
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
    )
    greeting = (
        "¡Bienvenido a La Casa del Sabor! Soy su agente virtual. "
        "¿En qué puedo ayudarle con su pedido hoy?"
    )
    await append_transcript(db, session, "Agente", greeting)
    await db.refresh(session)
    out = session_to_out(session)
    await manager.broadcast("call_started", out.model_dump(mode="json"))
    return out


@router.post("/calls/turn")
async def call_turn(body: CallTurnRequest, db: AsyncSession = Depends(get_db)):
    session = await get_call_session(db, body.session_id)
    if not session:
        raise HTTPException(404, "Sesión no encontrada")
    if not body.text:
        raise HTTPException(400, "Se requiere texto del cliente")

    await append_transcript(db, session, "Cliente", body.text)
    await db.refresh(session)

    prior = None
    existing_order = await get_order_for_session(db, session.id)
    if existing_order and existing_order.structured_json:
        prior = json.loads(existing_order.structured_json)

    result = await process_turn(body.session_id, session.transcript, prior)
    structured = StructuredOrder(**result["structured_order"])

    if user_confirmed(body.text) and structured.items:
        structured.is_complete = True
        structured.needs_confirmation = False

    order = await upsert_order_from_structured(db, session, structured)
    await append_transcript(db, session, "Agente", result["spoken_response"])

    session = await get_call_session(db, body.session_id)
    out = order_to_out(order) if order else None
    payload = {
        "session": session_to_out(session).model_dump(mode="json"),
        "spoken_response": result["spoken_response"],
        "structured_order": result["structured_order"],
        "agent_response": result["agent_response"],
        "order": out.model_dump(mode="json") if out else None,
        "status_message": _status_message(order),
    }
    await manager.broadcast("call_updated", payload)
    if out:
        await manager.broadcast("order_updated", out.model_dump(mode="json"))
    return payload


def _status_message(order: Order | None) -> str | None:
    if not order:
        return None
    status = order.status.value if hasattr(order.status, "value") else str(order.status)
    messages = {
        "recibido": "Pedido registrado.",
        "confirmando": "Pedido en preparación — confirma con el cliente.",
        "confirmado": "Pedido confirmado.",
        "en_cocina": f"Pedido #{order.id} enviado a cocina.",
        "listo": f"Pedido #{order.id} listo para entrega.",
        "entregado": f"Pedido #{order.id} entregado.",
    }
    return messages.get(status)


@router.post("/calls/{session_id}/confirm")
async def confirm_call_order(session_id: str, db: AsyncSession = Depends(get_db)):
    order = await confirm_order_for_session(db, session_id)
    if not order:
        raise HTTPException(400, "No hay pedido con ítems para confirmar")
    out = order_to_out(order)
    await manager.broadcast("order_updated", out.model_dump(mode="json"))
    session = await get_call_session(db, session_id)
    return {
        "order": out.model_dump(mode="json"),
        "status_message": f"Pedido #{order.id} confirmado y enviado a cocina.",
        "session": session_to_out(session).model_dump(mode="json") if session else None,
    }


@router.post("/calls/audio")
async def call_audio_turn(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    audio: UploadFile = File(...),
):
    session = await get_call_session(db, session_id)
    if not session:
        raise HTTPException(404, "Sesión no encontrada")

    audio_bytes = await audio.read()
    text = await transcribe_audio(audio_bytes, audio.filename or "audio.webm")
    if not text:
        raise HTTPException(400, "No se pudo transcribir el audio")

    turn_result = await call_turn(CallTurnRequest(session_id=session_id, text=text), db)
    turn_result["transcription"] = text
    turn_result["tts_available"] = True
    return turn_result


@router.get("/calls/active", response_model=list[CallSessionOut])
async def active_calls(mode: str | None = None, db: AsyncSession = Depends(get_db)):
    sessions = await list_active_calls(db, mode=mode)
    return [session_to_out(s) for s in sessions]


@router.get("/orders", response_model=list[OrderOut])
async def get_orders(status: str | None = None, db: AsyncSession = Depends(get_db)):
    orders = await list_orders(db, status)
    return [order_to_out(o) for o in orders]


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
async def patch_order_status(
    order_id: int,
    body: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    order = await update_order_status(db, order_id, body.status)
    if not order:
        raise HTTPException(404, "Pedido no encontrado")
    out = order_to_out(order)
    await manager.broadcast("order_updated", out.model_dump())
    return out


@router.post("/tts")
async def text_to_speech(text: str):
    if not text.strip():
        raise HTTPException(400, "Texto vacío")
    audio = await synthesize_speech(text)
    return Response(content=audio, media_type="audio/mpeg")
