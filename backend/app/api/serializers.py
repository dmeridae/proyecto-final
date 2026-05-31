from sqlalchemy import inspect as sa_inspect

from app.schemas.order import CallSessionOut, OrderItemOut, OrderOut


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def order_to_out(order) -> OrderOut:
    insp = sa_inspect(order)
    items: list[OrderItemOut] = []
    if "items" not in insp.unloaded:
        items = [OrderItemOut.model_validate(i) for i in order.items]

    return OrderOut(
        id=order.id,
        status=_enum_value(order.status),
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        delivery_address=order.delivery_address,
        order_type=order.order_type,
        payment_method=order.payment_method,
        notes=order.notes,
        subtotal=order.subtotal,
        delivery_fee=order.delivery_fee,
        total=order.total,
        items=items,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def session_to_out(session) -> CallSessionOut:
    insp = sa_inspect(session)
    order_out = None
    if "order" not in insp.unloaded and session.order is not None:
        order_out = order_to_out(session.order)

    return CallSessionOut(
        id=session.id,
        session_id=session.session_id,
        mode=session.mode,
        status=_enum_value(session.status),
        customer_name=session.customer_name,
        customer_phone=session.customer_phone,
        transcript=session.transcript,
        created_at=session.created_at,
        order=order_out,
    )
