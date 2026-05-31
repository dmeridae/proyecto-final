import { useEffect, useState } from 'react'
import { api } from '../hooks/useApi'

export default function CallOptionsBar() {
  const [status, setStatus] = useState(null)

  useEffect(() => {
    api('/twilio/status')
      .then(setStatus)
      .catch(() => setStatus(null))
  }, [])

  const phone = status?.phone_number
  const phoneWorks = status?.call_available

  return (
    <div className="call-options-bar">
      <div className="call-option call-option-web">
        <div className="call-option-icon-wrap web">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
            <rect x="3" y="4" width="18" height="13" rx="2" stroke="currentColor" strokeWidth="1.8" />
            <path d="M8 20h8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </div>
        <div className="call-option-body">
          <h3>Desde el navegador</h3>
          <p>Chat con texto o micrófono usando OpenAI STT y TTS.</p>
          <span className="call-option-status ok">Siempre disponible</span>
        </div>
      </div>

      <div className="call-option call-option-phone">
        <div className="call-option-icon-wrap phone">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path
              d="M6.5 4h3l1.5 5-2 1.2a11 11 0 005.3 5.3L15.5 14l5 1.5v3A2 2 0 0118.7 21 16 16 0 013 6.3 2 2 0 016.5 4z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <div className="call-option-body">
          <h3>Desde tu teléfono</h3>
          {phone ? (
            <>
              <p>Marca para hablar con el agente de voz:</p>
              <a href={`tel:${phone}`} className="call-phone-number">
                {phone}
              </a>
              <span className={`call-option-status ${phoneWorks ? 'ok' : 'warn'}`}>
                {phoneWorks
                  ? 'Listo para recibir llamadas'
                  : 'Falta webhook público — ver detalles abajo'}
              </span>
            </>
          ) : (
            <>
              <p>Agrega tu número Twilio en <code>backend/.env</code>.</p>
              <span className="call-option-status warn">Configuración pendiente</span>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
