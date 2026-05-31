import { useEffect, useState, useCallback } from 'react'
import { api, useWebSocket } from '../hooks/useApi'

function parseTranscript(transcript) {
  if (!transcript) return []
  return transcript
    .trim()
    .split('\n')
    .map((line) => {
      const m = line.match(/^\[[^\]]+\]\s*(Cliente|Agente):\s*(.*)$/)
      if (!m) return null
      return { role: m[1] === 'Cliente' ? 'cliente' : 'agente', text: m[2] }
    })
    .filter(Boolean)
}

export default function TwilioMonitor({ setStructured, onOrderUpdate }) {
  const [status, setStatus] = useState(null)
  const [activeCall, setActiveCall] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [st, calls] = await Promise.all([
        api('/twilio/status'),
        api('/calls/active?mode=twilio'),
      ])
      setStatus(st)
      setActiveCall(calls[0] || null)
    } catch {
      setStatus(null)
      setActiveCall(null)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 8000)
    return () => clearInterval(id)
  }, [refresh])

  const handleWs = useCallback(
    (msg) => {
      const session = msg.data?.session
      if (!session || session.mode !== 'twilio') return
      if (msg.type === 'call_started' || msg.type === 'call_updated') {
        setActiveCall(session)
        if (msg.data?.structured_order) setStructured(msg.data.structured_order)
        if (msg.data?.order) onOrderUpdate?.(msg.data.order)
        else if (msg.data?.session?.order) onOrderUpdate?.(msg.data.session.order)
      }
    },
    [setStructured, onOrderUpdate]
  )

  useWebSocket(handleWs)

  const messages = activeCall ? parseTranscript(activeCall.transcript) : []

  return (
    <div className="card twilio-monitor">
      <h2>Llamada telefónica en vivo</h2>
      <p className="section-desc">
        Al marcar el número de arriba, la conversación aparece aquí. El pedido se refleja en Cocina y
        Caja.
      </p>

      {status && !status.call_available && status.issues?.length > 0 && (
        <details className="twilio-issues-details">
          <summary>Para que funcionen las llamadas entrantes</summary>
          <ul className="setup-issues">
            {status.issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
          {status.voice_webhook_url && (
            <p className="webhook-hint" style={{ marginTop: '0.5rem' }}>
              Webhook en Twilio: <code>{status.voice_webhook_url}</code>
            </p>
          )}
        </details>
      )}

      {!activeCall ? (
        <p className="empty">
          {status?.phone_number
            ? 'Esperando llamada al número configurado...'
            : 'Configura Twilio para habilitar llamadas telefónicas.'}
        </p>
      ) : (
        <>
          <p className="session-label">
            Sesión activa · {activeCall.status}
          </p>
          <div className="chat chat-compact">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                <div className="role">{m.role}</div>
                {m.text}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
