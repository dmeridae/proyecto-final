import { useState } from 'react'
import { api, playTts, sendAudioTurn, useAudioRecorder } from '../hooks/useApi'
import OrderFlowTracker, { OrderStatusBadge } from './OrderFlowTracker'

const GREETING =
  '¡Bienvenido a La Casa del Sabor! Soy su agente virtual. ¿En qué puedo ayudarle con su pedido hoy?'

export default function SimulationCall({ setStructured, onOrderUpdate }) {
  const [session, setSession] = useState(null)
  const [liveOrder, setLiveOrder] = useState(null)
  const [statusMessage, setStatusMessage] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const { recording, start, stop } = useAudioRecorder()

  const applyTurnResult = (result) => {
    setMessages((prev) => [...prev, { role: 'agente', text: result.spoken_response }])
    setStructured(result.structured_order)
    setSession(result.session)
    const order = result.order || result.session?.order
    if (order) {
      setLiveOrder(order)
      onOrderUpdate?.(order)
    }
    if (result.status_message) setStatusMessage(result.status_message)
  }

  const startCall = async () => {
    setLoading(true)
    setError(null)
    setLiveOrder(null)
    setStatusMessage(null)
    try {
      const data = await api('/calls/simulation/start', {
        method: 'POST',
        body: JSON.stringify({ customer_name: 'Cliente Demo' }),
      })
      setSession(data)
      setMessages([{ role: 'agente', text: GREETING }])
      setStructured(null)
      playTts(GREETING).catch(() => {})
    } catch (e) {
      setError(e.message || 'No se pudo iniciar la llamada. ¿Está el backend en el puerto 8000?')
    } finally {
      setLoading(false)
    }
  }

  const sendText = async (text) => {
    if (!session || !text.trim()) return
    setLoading(true)
    setMessages((prev) => [...prev, { role: 'cliente', text }])
    setInput('')
    try {
      const result = await api('/calls/turn', {
        method: 'POST',
        body: JSON.stringify({ session_id: session.session_id, text }),
      })
      applyTurnResult(result)
      await playTts(result.spoken_response)
    } catch (e) {
      setMessages((prev) => [...prev, { role: 'agente', text: `Error: ${e.message}` }])
    } finally {
      setLoading(false)
    }
  }

  const confirmAndSendKitchen = async () => {
    if (!session?.session_id) return
    setLoading(true)
    try {
      const result = await api(`/calls/${session.session_id}/confirm`, { method: 'POST' })
      if (result.order) {
        setLiveOrder(result.order)
        onOrderUpdate?.(result.order)
      }
      setStatusMessage(result.status_message)
      setMessages((prev) => [
        ...prev,
        { role: 'agente', text: `✓ ${result.status_message} Revise la pestaña Cocina.` },
      ])
    } catch (e) {
      setMessages((prev) => [...prev, { role: 'agente', text: `Error: ${e.message}` }])
    } finally {
      setLoading(false)
    }
  }

  const toggleRecord = async () => {
    if (recording) {
      const blob = await stop()
      if (!blob || blob.size < 1000) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'agente',
            text: 'No se captó audio. Habla más cerca del micrófono e intenta de nuevo.',
          },
        ])
        return
      }
      if (!session) return
      setLoading(true)
      setMessages((prev) => [...prev, { role: 'cliente', text: '🎤 Transcribiendo...' }])
      try {
        const result = await sendAudioTurn(session.session_id, blob)
        setMessages((prev) => {
          const withoutPending = prev.filter((m) => m.text !== '🎤 Transcribiendo...')
          return [
            ...withoutPending,
            { role: 'cliente', text: result.transcription || '(sin texto detectado)' },
            { role: 'agente', text: result.spoken_response },
          ]
        })
        applyTurnResult(result)
        playTts(result.spoken_response).catch(() => {})
      } catch (e) {
        setMessages((prev) => {
          const withoutPending = prev.filter((m) => m.text !== '🎤 Transcribiendo...')
          return [...withoutPending, { role: 'agente', text: `Error de voz: ${e.message}` }]
        })
      } finally {
        setLoading(false)
      }
    } else {
      try {
        await start()
        setMessages((prev) => [
          ...prev,
          { role: 'agente', text: '🎤 Grabando... habla ahora y pulsa "Detener grabación".' },
        ])
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            role: 'agente',
            text: 'No se pudo acceder al micrófono. Permite el micrófono en el navegador o usa texto.',
          },
        ])
      }
    }
  }

  const canConfirm =
    liveOrder &&
    liveOrder.items?.length > 0 &&
    !['en_cocina', 'listo', 'entregado', 'cancelado'].includes(liveOrder.status)

  return (
    <div className="card">
      <h2>Atención en el navegador</h2>
      {!session ? (
        <div>
          <p className="section-desc">
            Simula una llamada al restaurante. Al confirmar el pedido, aparecerá en Cocina y Caja.
          </p>
          <button className="btn btn-primary" onClick={startCall} disabled={loading}>
            {loading ? 'Conectando...' : 'Iniciar llamada en el navegador'}
          </button>
          {error && <p className="text-error">{error}</p>}
        </div>
      ) : (
        <>
          {liveOrder && (
            <div className="live-order-panel">
              <div className="live-order-header">
                <strong>Pedido #{liveOrder.id}</strong>
                <OrderStatusBadge status={liveOrder.status} />
              </div>
              <OrderFlowTracker status={liveOrder.status} />
              {statusMessage && <p className="status-message">{statusMessage}</p>}
              {liveOrder.items?.length > 0 && (
                <ul className="order-items compact">
                  {liveOrder.items.map((item) => (
                    <li key={item.id}>
                      {item.quantity}x {item.name} — ${item.unit_price.toFixed(2)}
                    </li>
                  ))}
                </ul>
              )}
              <p className="live-order-total">Total: ${liveOrder.total?.toFixed(2) ?? '0.00'}</p>
              {canConfirm && (
                <button
                  type="button"
                  className="btn btn-primary btn-full"
                  onClick={confirmAndSendKitchen}
                  disabled={loading}
                >
                  Confirmar y enviar a cocina
                </button>
              )}
              {liveOrder.status === 'en_cocina' && (
                <p className="kitchen-hint">✓ En cocina — ve a la pestaña Cocina para avanzar estados.</p>
              )}
            </div>
          )}

          <div className="chat">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                <div className="role">{m.role}</div>
                {m.text}
              </div>
            ))}
          </div>
          <input
            placeholder="Ej: Quiero 2 hamburguesas y un refresco... luego: sí, confirmo"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !loading && sendText(input)}
            disabled={loading}
          />
          <div className="controls">
            <button
              className="btn btn-primary"
              onClick={() => sendText(input)}
              disabled={loading || !input.trim()}
            >
              Enviar texto
            </button>
            <button
              className={`btn btn-record ${recording ? 'recording' : ''}`}
              onClick={toggleRecord}
              disabled={loading}
            >
              {recording ? 'Detener grabación' : 'Grabar voz (STT)'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
