# Call Center Inteligente — La Casa del Sabor

Sistema web de pedidos por llamada con agente de voz IA, RAG sobre menú, LangGraph, STT/TTS y actualizaciones en tiempo real.

## Arquitectura

```
Cliente (voz/texto) → STT (Whisper) → LangGraph Agent → Tools (RAG menú)
                                    ↓
                          Structured Output (orden)
                                    ↓
                    SQLite + WebSocket → Paneles (Cocina, Caja, Pedidos)
```

### Requisitos del curso cubiertos

| Requisito | Implementación |
|-----------|----------------|
| Frontend web | React + Vite |
| Backend | FastAPI + WebSockets |
| LLM | OpenAI GPT-4o-mini |
| Structured output | `StructuredOrder` + `AgentResponse` (Pydantic) |
| Tool | `buscar_en_menu`, `calcular_total_pedido`, `validar_disponibilidad` |
| RAG + embeddings | LangChain + OpenAI embeddings + ChromaDB |
| Vector store | ChromaDB persistente |
| Workflow agentic | LangGraph (agent → tools → structure) |
| Persistencia | SQLite (SQLAlchemy async) |
| STT / TTS | OpenAI Whisper + OpenAI TTS |
| Llamadas | Simulación web + teléfono Twilio (ambas en pestaña Agente) |
| Tiempo real | WebSocket `/ws/orders` |

## Inicio rápido

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env       # Luego edita .env con tu OPENAI_API_KEY
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Abre http://localhost:5173

## Qué debes configurar tú

### Obligatorio

1. **OPENAI_API_KEY** en `backend/.env`
   - Crea una clave en https://platform.openai.com/api-keys
   - Sin esto no funcionan: LLM, embeddings, RAG, STT ni TTS

### Twilio (opción 2 — llamada telefónica)

En la pestaña **Agente** siempre verás las dos opciones: navegador y número telefónico.

1. Credenciales en `backend/.env`: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
2. `ngrok http 8000` → URL https en `PUBLIC_BASE_URL`
3. Twilio Console → tu número → Voice webhook POST → `{PUBLIC_BASE_URL}/twilio/voice/incoming`

Sin créditos Twilio la llamada fallará; la opción web sigue funcionando.

Consulta estado: `GET /api/twilio/status`

3. **Menú del restaurante**
   - Edita `backend/data/menu.json` y ejecuta `POST /api/rag/ingest` para re-indexar

4. **Base de datos**
   - SQLite se crea sola en `backend/callcenter.db`
   - Para PostgreSQL cambia `DATABASE_URL` en `.env`

## Demo sugerida para presentación

1. Pestaña **Agente** → "Iniciar llamada"
2. Escribe o graba: *"Quiero una hamburguesa clásica con refresco y nachos"*
3. El agente consulta el menú (RAG), valida platillos y muestra la orden estructurada
4. Confirma nombre, tipo de pedido y pago
5. Cambia a **Cocina** y avanza estados en tiempo real
6. **Caja** muestra pedidos listos para entregar

## Endpoints principales

- `GET /api/health` — estado del sistema
- `POST /api/calls/simulation/start` — iniciar llamada simulada
- `POST /api/calls/turn` — turno de conversación (texto)
- `POST /api/calls/audio` — turno con audio (STT)
- `GET /api/orders` — listar pedidos
- `PATCH /api/orders/{id}/status` — actualizar estado
- `WS /ws/orders` — eventos en tiempo real

## Estructura del proyecto

```
backend/
  app/
    api/           # Rutas REST y Twilio
    models/        # SQLAlchemy (CallSession, Order, OrderItem)
    schemas/       # Pydantic (StructuredOrder, AgentResponse)
    services/
      agent/       # LangGraph workflow + tools
      rag/         # ChromaDB + embeddings del menú
      voice/       # STT/TTS
    websocket/     # Broadcast tiempo real
  data/menu.json   # Menú del restaurante
frontend/
  src/
    components/    # Agente, Cocina, Caja, Pedidos
    hooks/         # WebSocket, API, grabación de audio
```
