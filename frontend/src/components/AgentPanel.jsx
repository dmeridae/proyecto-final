import { useState } from 'react'
import CallOptionsBar from './CallOptionsBar'
import SimulationCall from './SimulationCall'
import TwilioMonitor from './TwilioMonitor'
import OrderFlowTracker, { OrderStatusBadge } from './OrderFlowTracker'
import { STATUS_LABELS } from '../lib/orderStatus'

export default function AgentPanel({ onOrderUpdate }) {
  const [structured, setStructured] = useState(null)
  const [liveOrder, setLiveOrder] = useState(null)

  const handleOrder = (order) => {
    if (order) setLiveOrder(order)
    onOrderUpdate?.(order)
  }

  return (
    <div className="agent-panel">
      <CallOptionsBar />

      <div className="grid-2 agent-grid">
        <div className="agent-left">
          <SimulationCall setStructured={setStructured} onOrderUpdate={handleOrder} />
          <TwilioMonitor setStructured={setStructured} onOrderUpdate={handleOrder} />
        </div>

        <div className="card">
          <h2>Estado del pedido</h2>
          {liveOrder ? (
            <>
              <div className="live-order-header" style={{ marginBottom: '1rem' }}>
                <strong>#{liveOrder.id}</strong>
                <OrderStatusBadge status={liveOrder.status} />
              </div>
              <OrderFlowTracker status={liveOrder.status} />
              <p className="section-desc" style={{ marginTop: '1rem' }}>
                Siguiente paso:{' '}
                <strong style={{ color: 'var(--text)' }}>{STATUS_LABELS[liveOrder.status]}</strong>
                {liveOrder.status === 'en_cocina' && ' → revisa pestaña Cocina'}
                {liveOrder.status === 'listo' && ' → revisa pestaña Caja'}
              </p>
              <details style={{ marginTop: '1rem' }}>
                <summary>Ver JSON del LLM</summary>
                <div className="structured-preview" style={{ marginTop: '0.5rem' }}>
                  {JSON.stringify(structured || liveOrder, null, 2)}
                </div>
              </details>
            </>
          ) : (
            <p className="empty">
              El pedido y su estado aparecerán aquí cuando el cliente pida platillos.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
