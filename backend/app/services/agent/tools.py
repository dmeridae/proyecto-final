import json
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from app.services.rag.menu_rag import search_menu

MENU_PATH = Path(__file__).resolve().parents[3] / "data" / "menu.json"


@tool
def buscar_en_menu(consulta: Annotated[str, "Consulta del cliente sobre platillos, precios, alérgenos o categorías"]) -> str:
    """Busca platillos y precios en el menú del restaurante usando búsqueda semántica (RAG)."""
    return search_menu(consulta, k=5)


@tool
def calcular_total_pedido(items_json: Annotated[str, "JSON con lista de items: [{name, quantity, unit_price}]"]) -> str:
    """Calcula subtotal y total estimado del pedido incluyendo costo de domicilio si aplica."""
    try:
        items = json.loads(items_json)
    except json.JSONDecodeError:
        return "Error: JSON de items inválido."

    with open(MENU_PATH, encoding="utf-8") as f:
        menu = json.load(f)

    delivery_fee = float(menu.get("policies", {}).get("delivery_fee", 0))
    subtotal = sum(float(i.get("unit_price", 0)) * int(i.get("quantity", 1)) for i in items)
    return json.dumps({
        "subtotal": round(subtotal, 2),
        "delivery_fee": delivery_fee,
        "total": round(subtotal + delivery_fee, 2),
        "item_count": sum(int(i.get("quantity", 1)) for i in items),
    }, ensure_ascii=False)


@tool
def validar_disponibilidad(nombre_platillo: Annotated[str, "Nombre del platillo a validar"]) -> str:
    """Verifica si un platillo existe en el menú y devuelve su ID y precio."""
    with open(MENU_PATH, encoding="utf-8") as f:
        menu = json.load(f)

    nombre_lower = nombre_platillo.lower()
    for category in menu.get("categories", []):
        for item in category.get("items", []):
            if nombre_lower in item["name"].lower() or item["name"].lower() in nombre_lower:
                return json.dumps({
                    "found": True,
                    "id": item["id"],
                    "name": item["name"],
                    "price": item["price"],
                    "category": category["name"],
                }, ensure_ascii=False)

    results = search_menu(nombre_platillo, k=2)
    return json.dumps({"found": False, "suggestions": results}, ensure_ascii=False)


AGENT_TOOLS = [buscar_en_menu, calcular_total_pedido, validar_disponibilidad]
