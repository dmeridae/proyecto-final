import json
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

from app.config import settings

MENU_PATH = Path(__file__).resolve().parents[3] / "data" / "menu.json"
COLLECTION_NAME = "restaurant_menu"

_vectorstore: Chroma | None = None


def _load_menu_documents() -> list[dict]:
    with open(MENU_PATH, encoding="utf-8") as f:
        return [json.load(f)]


def _menu_to_text_chunks(menu: dict) -> list[str]:
    chunks: list[str] = []
    restaurant = menu.get("restaurant", "Restaurante")
    chunks.append(f"Restaurante: {restaurant}")

    policies = menu.get("policies", {})
    if policies:
        chunks.append(
            "Políticas del restaurante: "
            + json.dumps(policies, ensure_ascii=False)
        )

    for category in menu.get("categories", []):
        cat_name = category.get("name", "")
        for item in category.get("items", []):
            allergens = ", ".join(item.get("allergens", [])) or "ninguno"
            chunks.append(
                f"Categoría: {cat_name}. "
                f"ID: {item['id']}. "
                f"Platillo: {item['name']}. "
                f"Precio: ${item['price']:.2f}. "
                f"Descripción: {item['description']}. "
                f"Alérgenos: {allergens}."
            )
    return chunks


def get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    embeddings = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        openai_api_key=settings.openai_api_key,
    )

    persist_dir = Path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)

    if any(persist_dir.iterdir()):
        _vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=str(persist_dir),
        )
        return _vectorstore

    menu = _load_menu_documents()[0]
    raw_chunks = _menu_to_text_chunks(menu)
    splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)
    docs = splitter.create_documents(raw_chunks)

    _vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(persist_dir),
    )
    return _vectorstore


def search_menu(query: str, k: int = 4) -> str:
    """Tool RAG: búsqueda semántica sobre el menú."""
    store = get_vectorstore()
    results = store.similarity_search(query, k=k)
    if not results:
        return "No se encontraron platillos relacionados con la consulta."
    return "\n".join(doc.page_content for doc in results)


def ingest_menu() -> dict:
    """Re-ingesta el menú en ChromaDB (útil si se actualiza menu.json)."""
    global _vectorstore
    _vectorstore = None
    persist_dir = Path(settings.chroma_persist_dir)
    if persist_dir.exists():
        import shutil
        shutil.rmtree(persist_dir)
    store = get_vectorstore()
    return {"status": "ok", "documents": store._collection.count()}
