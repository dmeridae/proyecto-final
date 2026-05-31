import json
import logging
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.serializers import order_to_out, session_to_out
from app.config import settings
from app.database import get_db
from app.schemas.order import StructuredOrder
from app.services.agent.workflow import process_turn
from app.services.order_service import (
    append_transcript,
    create_call_session,
    get_call_session,
    get_order_for_session,
    upsert_order_from_structured,
    user_confirmed,
)
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/twilio")

TWILIO_GREETING = (
    "Bienvenido a La Casa del Sabor. ¿En qué puedo ayudarle con su pedido?"
)

TWILIO_UNAVAILABLE_MSG = (
    "Lo sentimos, el servicio telefónico no está disponible en este momento. "
    "Por favor intente más tarde o realice su pedido por nuestro canal web."
)


def twiml(content: str) -> Response:
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?><Response>{content}</Response>',
        media_type="application/xml",
    )


def _gather_url(session_id: str) -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/twilio/voice/gather?session_id={session_id}"


def _twilio_unavailable_response() -> Response:
    return twiml(
        f'<Say language="es-MX">{escape(TWILIO_UNAVAILABLE_MSG)}</Say><Hangup/>'
    )


async def _prior_order(db: AsyncSession, session) -> dict | None:
    order = await get_order_for_session(db, session.id)
    if order and order.structured_json:
        return json.loads(order.structured_json)
    return None


@router.api_route("/voice/incoming", methods=["GET", "POST"])
async def incoming_call(request: Request, db: AsyncSession = Depends(get_db)):
    if request.method == "POST":
        form = await request.form()
        call_sid = str(form.get("CallSid", ""))
        caller = str(form.get("From", ""))
        called = str(form.get("To", ""))
    else:
        call_sid = request.query_params.get("CallSid", "")
        caller = request.query_params.get("From", "")
        called = request.query_params.get("To", "")

    logger.info("Twilio incoming CallSid=%s From=%s To=%s", call_sid, caller, called)
    if not settings.twilio_call_available:
        logger.warning("Llamada Twilio rechazada: webhook no disponible (revisa PUBLIC_BASE_URL)")
        return _twilio_unavailable_response()

    session = await create_call_session(db, mode="twilio")
    if caller:
        session.customer_phone = caller.replace(" ", "")
        await db.commit()
    await append_transcript(db, session, "Agente", TWILIO_GREETING)
    gather_url = _gather_url(session.session_id)
    twiml_body = (
        f'<Say language="es-MX" voice="Polly.Mia">{escape(TWILIO_GREETING)}</Say>'
        f'<Gather input="speech" language="es-MX" action="{gather_url}" method="POST" speechTimeout="auto"/>'
    )
    await manager.broadcast("call_started", session_to_out(session).model_dump(mode="json"))
    return twiml(twiml_body)


@router.post("/voice/gather")
async def gather_speech(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    SpeechResult: str = Form(default=""),
):
    if not settings.twilio_call_available:
        return _twilio_unavailable_response()

    session = await get_call_session(db, session_id)
    if not session:
        return twiml('<Say language="es-MX">Lo sentimos, hubo un error. Adiós.</Say><Hangup/>')

    user_text = SpeechResult.strip()
    if not user_text:
        gather_url = _gather_url(session_id)
        return twiml(
            '<Say language="es-MX">No le escuché. ¿Puede repetir?</Say>'
            f'<Gather input="speech" language="es-MX" action="{gather_url}" method="POST" speechTimeout="auto"/>'
        )

    await append_transcript(db, session, "Cliente", user_text)
    await db.refresh(session)

    try:
        prior = await _prior_order(db, session)
        result = await process_turn(session_id, session.transcript, prior)
        structured = StructuredOrder(**result["structured_order"])
        if user_confirmed(user_text) and structured.items:
            structured.is_complete = True
            structured.needs_confirmation = False
        order = await upsert_order_from_structured(db, session, structured)
        spoken = escape(result["spoken_response"])
        await append_transcript(db, session, "Agente", result["spoken_response"])
    except Exception:
        logger.exception("Error procesando turno Twilio session=%s", session_id)
        gather_url = _gather_url(session_id)
        return twiml(
            '<Say language="es-MX">Disculpe, tuvimos un problema técnico. ¿Puede repetir su pedido?</Say>'
            f'<Gather input="speech" language="es-MX" action="{gather_url}" method="POST" speechTimeout="auto"/>'
        )

    session = await get_call_session(db, session_id)
    payload = {
        "session": session_to_out(session).model_dump(mode="json"),
        "spoken_response": result["spoken_response"],
        "structured_order": result["structured_order"],
    }
    await manager.broadcast("call_updated", payload)
    if order:
        await manager.broadcast("order_updated", order_to_out(order).model_dump(mode="json"))

    if structured.is_complete:
        return twiml(
            f'<Say language="es-MX">{spoken}</Say>'
            '<Say language="es-MX">Gracias por su pedido. ¡Hasta pronto!</Say><Hangup/>'
        )

    gather_url = _gather_url(session_id)
    return twiml(
        f'<Say language="es-MX">{spoken}</Say>'
        f'<Gather input="speech" language="es-MX" action="{gather_url}" method="POST" speechTimeout="auto"/>'
    )
