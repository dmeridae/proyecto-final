from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.config import settings
from app.schemas.order import AgentResponse, StructuredOrder
from app.services.agent.tools import AGENT_TOOLS
from app.services.order_service import transcript_to_messages

SYSTEM_PROMPT = """Eres un agente de voz amable de un call center de restaurante llamado "La Casa del Sabor".
Tu trabajo es tomar pedidos por teléfono: entender qué quiere el cliente, consultar el menú con tus herramientas,
confirmar datos (nombre, tipo de pedido, dirección si es domicilio, forma de pago) y estructurar el pedido.

Reglas:
- Usa la herramienta buscar_en_menu cuando el cliente pregunte por platillos, precios o alérgenos.
- Usa validar_disponibilidad antes de agregar un platillo al pedido.
- Usa calcular_total_pedido cuando tengas items para dar el total.
- Habla en español, de forma natural y breve (como en una llamada telefónica).
- Si falta información importante, pídela amablemente.
- Cuando el cliente confirme el pedido (dice sí, confirmo, correcto, etc.), marca is_complete=true y needs_confirmation=false.
- Cuando is_complete=true, el pedido pasa a cocina automáticamente.
- Si el cliente solo saluda, responde cordialmente y ofrece ayuda con el menú.
"""


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    structured_order: dict
    agent_response: dict
    turn_count: int


def _get_llm():
    return ChatOpenAI(
        model=settings.openai_model,
        openai_api_key=settings.openai_api_key,
        temperature=0.3,
    ).bind_tools(AGENT_TOOLS)


def agent_node(state: AgentState) -> dict:
    llm = _get_llm()
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response], "turn_count": state.get("turn_count", 0) + 1}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "structure"


tool_node = ToolNode(AGENT_TOOLS)


def structure_output_node(state: AgentState) -> dict:
    llm = ChatOpenAI(
        model=settings.openai_model,
        openai_api_key=settings.openai_api_key,
        temperature=0,
    ).with_structured_output(AgentResponse)

    conversation = "\n".join(
        f"{'Cliente' if isinstance(m, HumanMessage) else 'Agente'}: {m.content}"
        for m in state["messages"]
        if isinstance(m, (HumanMessage, AIMessage)) and m.content
    )

    prompt = f"""Basándote en esta conversación de call center, genera la respuesta hablada del agente
y la orden estructurada actualizada.

Conversación:
{conversation}

Estado previo del pedido (si existe):
{state.get('structured_order', {})}
"""
    result: AgentResponse = llm.invoke(prompt)
    spoken = result.spoken_response

    if not spoken and state["messages"]:
        last_ai = next((m for m in reversed(state["messages"]) if isinstance(m, AIMessage) and m.content), None)
        if last_ai:
            spoken = str(last_ai.content)

    result.spoken_response = spoken or "¿En qué puedo ayudarle con su pedido?"
    return {
        "structured_order": result.order.model_dump(),
        "agent_response": result.model_dump(),
        "messages": [AIMessage(content=result.spoken_response)],
    }


def build_order_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("structure", structure_output_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "structure": "structure"})
    graph.add_edge("tools", "agent")
    graph.add_edge("structure", END)

    return graph.compile()


order_agent = build_order_agent_graph()


async def process_turn(
    session_id: str,
    transcript: str | None = None,
    prior_order: dict | None = None,
) -> dict:
    history = transcript_to_messages(transcript)
    if not history or not isinstance(history[-1], HumanMessage):
        raise ValueError("El transcript debe incluir al menos un mensaje del cliente al final del turno.")

    initial_state: AgentState = {
        "messages": history,
        "session_id": session_id,
        "structured_order": prior_order or StructuredOrder().model_dump(),
        "agent_response": {},
        "turn_count": 0,
    }
    result = await order_agent.ainvoke(initial_state)
    return {
        "spoken_response": result["agent_response"].get("spoken_response", ""),
        "structured_order": result["structured_order"],
        "agent_response": result["agent_response"],
    }
