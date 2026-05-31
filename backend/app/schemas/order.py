from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OrderItemSchema(BaseModel):
    menu_item_id: str | None = None
    name: str
    quantity: int = Field(ge=1, default=1)
    unit_price: float = Field(ge=0, default=0.0)
    notes: str | None = None


class StructuredOrder(BaseModel):
    """Salida estructurada del agente para convertir la conversación en orden."""
    customer_name: str | None = None
    customer_phone: str | None = None
    order_type: Literal["local", "domicilio", "para_llevar"] = "local"
    delivery_address: str | None = None
    payment_method: Literal["efectivo", "tarjeta", "transferencia"] | None = None
    items: list[OrderItemSchema] = Field(default_factory=list)
    notes: str | None = None
    needs_confirmation: bool = True
    confirmation_message: str = ""
    missing_info: list[str] = Field(default_factory=list)
    is_complete: bool = False


class AgentResponse(BaseModel):
    """Respuesta del agente en cada turno de la conversación."""
    spoken_response: str
    order: StructuredOrder
    intent: Literal["saludo", "consulta_menu", "agregar_item", "confirmar", "modificar", "cancelar", "despedida", "error"] = "consulta_menu"
    confidence: float = Field(ge=0, le=1, default=0.8)


class OrderItemOut(BaseModel):
    id: int
    menu_item_id: str | None
    name: str
    quantity: int
    unit_price: float
    notes: str | None

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    status: str
    customer_name: str | None
    customer_phone: str | None
    delivery_address: str | None
    order_type: str
    payment_method: str | None
    notes: str | None
    subtotal: float
    delivery_fee: float
    total: float
    items: list[OrderItemOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CallSessionOut(BaseModel):
    id: int
    session_id: str
    mode: str
    status: str
    customer_name: str | None
    customer_phone: str | None
    transcript: str | None
    created_at: datetime
    order: OrderOut | None = None

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: Literal["recibido", "confirmando", "confirmado", "en_cocina", "listo", "entregado", "cancelado"]


class CallTurnRequest(BaseModel):
    session_id: str
    text: str | None = None


class SimulationStartRequest(BaseModel):
    customer_name: str | None = None
    customer_phone: str | None = None
