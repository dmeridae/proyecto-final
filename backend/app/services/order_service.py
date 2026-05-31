import json
import re
import uuid
from datetime import datetime

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import CallSession, CallStatus, Order, OrderItem, OrderStatus
from app.schemas.order import StructuredOrder

CONFIRMATION_PHRASES = (
    "confirmo", "confirmado", "correcto", "está bien", "esta bien", "sí", "si ",
    "yes", "ok", "perfecto", "de acuerdo", "así es", "asi es", "listo", "proceda",
)


def user_confirmed(text: str) -> bool:
    lower = text.lower().strip()
    return any(p in lower for p in CONFIRMATION_PHRASES)


def _resolve_status(structured: StructuredOrder, current: OrderStatus | None) -> OrderStatus:
    if not structured.items:
        return current or OrderStatus.RECIBIDO

    if structured.is_complete:
        # Pedido confirmado → entra directo a cola de cocina (flujo real KDS)
        return OrderStatus.EN_COCINA

    if current in (OrderStatus.ENTREGADO, OrderStatus.CANCELADO, OrderStatus.LISTO):
        return current

    if current in (OrderStatus.EN_COCINA, OrderStatus.CONFIRMADO):
        return current

    return OrderStatus.CONFIRMANDO if current else OrderStatus.RECIBIDO


async def create_call_session(
    db: AsyncSession,
    mode: str = "simulation",
    customer_name: str | None = None,
    customer_phone: str | None = None,
) -> CallSession:
    session = CallSession(
        session_id=str(uuid.uuid4()),
        mode=mode,
        status=CallStatus.ACTIVA,
        customer_name=customer_name,
        customer_phone=customer_phone,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_call_session(db: AsyncSession, session_id: str) -> CallSession | None:
    result = await db.execute(
        select(CallSession)
        .options(selectinload(CallSession.order).selectinload(Order.items))
        .where(CallSession.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def get_order_for_session(db: AsyncSession, session_id: int) -> Order | None:
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.call_session_id == session_id)
    )
    return result.scalar_one_or_none()


_TRANSCRIPT_LINE = re.compile(r"^\[[^\]]+\]\s*(Cliente|Agente):\s*(.*)$", re.MULTILINE)


def transcript_to_messages(transcript: str | None) -> list[BaseMessage]:
    """Convierte el transcript persistido en mensajes para el agente LangGraph."""
    if not transcript or not transcript.strip():
        return []

    messages: list[BaseMessage] = []
    for line in transcript.strip().splitlines():
        match = _TRANSCRIPT_LINE.match(line.strip())
        if not match:
            continue
        role, text = match.group(1), match.group(2).strip()
        if not text:
            continue
        if role == "Cliente":
            messages.append(HumanMessage(content=text))
        else:
            messages.append(AIMessage(content=text))
    return messages


async def append_transcript(db: AsyncSession, session: CallSession, role: str, text: str) -> None:
    line = f"[{datetime.utcnow().isoformat()}] {role}: {text}\n"
    session.transcript = (session.transcript or "") + line
    session.updated_at = datetime.utcnow()
    await db.commit()


async def upsert_order_from_structured(
    db: AsyncSession,
    session: CallSession,
    structured: StructuredOrder,
) -> Order | None:
    if not structured.items:
        result = await db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.call_session_id == session.id)
        )
        existing = result.scalar_one_or_none()
        if not existing:
            return None
        existing.customer_name = structured.customer_name or existing.customer_name
        existing.customer_phone = structured.customer_phone or existing.customer_phone
        existing.order_type = structured.order_type
        existing.delivery_address = structured.delivery_address
        existing.payment_method = structured.payment_method
        existing.notes = structured.notes
        existing.structured_json = json.dumps(structured.model_dump(), ensure_ascii=False)
        existing.updated_at = datetime.utcnow()
        await db.commit()
        result = await db.execute(
            select(Order).options(selectinload(Order.items)).where(Order.id == existing.id)
        )
        return result.scalar_one()

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.call_session_id == session.id)
    )
    order = result.scalar_one_or_none()
    previous_status = order.status if order else None

    if not order:
        order = Order(
            call_session_id=session.id,
            status=OrderStatus.RECIBIDO,
            customer_name=structured.customer_name or session.customer_name,
            customer_phone=structured.customer_phone or session.customer_phone,
        )
        db.add(order)
        await db.flush()

    order.status = _resolve_status(structured, order.status)

    order.delivery_address = structured.delivery_address
    order.order_type = structured.order_type
    order.payment_method = structured.payment_method
    order.notes = structured.notes
    order.customer_name = structured.customer_name or order.customer_name
    order.customer_phone = structured.customer_phone or order.customer_phone
    order.structured_json = json.dumps(structured.model_dump(), ensure_ascii=False)

    await db.execute(delete(OrderItem).where(OrderItem.order_id == order.id))

    subtotal = 0.0
    for item in structured.items:
        line_total = item.unit_price * item.quantity
        subtotal += line_total
        db.add(OrderItem(
            order_id=order.id,
            menu_item_id=item.menu_item_id,
            name=item.name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            notes=item.notes,
        ))

    delivery_fee = 3.0 if structured.order_type == "domicilio" else 0.0
    order.subtotal = round(subtotal, 2)
    order.delivery_fee = delivery_fee
    order.total = round(subtotal + delivery_fee, 2)
    order.updated_at = datetime.utcnow()

    if structured.is_complete:
        session.status = CallStatus.FINALIZADA
    elif order.status == OrderStatus.EN_COCINA and previous_status != OrderStatus.EN_COCINA:
        session.status = CallStatus.FINALIZADA

    await db.commit()

    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order.id)
    )
    return result.scalar_one()


async def list_orders(db: AsyncSession, status: str | None = None) -> list[Order]:
    query = select(Order).options(selectinload(Order.items)).order_by(Order.created_at.desc())
    if status:
        query = query.where(Order.status == OrderStatus(status))
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_order_status(db: AsyncSession, order_id: int, status: str) -> Order | None:
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        return None
    order.status = OrderStatus(status)
    order.updated_at = datetime.utcnow()
    await db.commit()
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    return result.scalar_one_or_none()


async def confirm_order_for_session(db: AsyncSession, session_id: str) -> Order | None:
    """Confirma el pedido de una llamada y lo envía a cocina."""
    session = await get_call_session(db, session_id)
    if not session:
        return None
    order = await get_order_for_session(db, session.id)
    if not order or not order.items:
        return None

    order.status = OrderStatus.EN_COCINA
    order.updated_at = datetime.utcnow()
    session.status = CallStatus.FINALIZADA
    await db.commit()

    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order.id)
    )
    return result.scalar_one_or_none()


async def list_active_calls(db: AsyncSession, mode: str | None = None) -> list[CallSession]:
    query = (
        select(CallSession)
        .options(selectinload(CallSession.order).selectinload(Order.items))
        .where(CallSession.status == CallStatus.ACTIVA)
        .order_by(CallSession.created_at.desc())
    )
    if mode:
        query = query.where(CallSession.mode == mode)
    result = await db.execute(query)
    return list(result.scalars().all())
