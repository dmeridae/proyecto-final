import { STATUS_FLOW, STATUS_LABELS, statusIndex } from '../lib/orderStatus'

export default function OrderFlowTracker({ status, compact = false }) {
  const current = statusIndex(status)

  return (
    <div className={`order-flow ${compact ? 'order-flow-compact' : ''}`}>
      {STATUS_FLOW.map((step, i) => {
        const done = i < current
        const active = i === current
        const pending = i > current
        return (
          <div
            key={step}
            className={`flow-step ${done ? 'done' : ''} ${active ? 'active' : ''} ${pending ? 'pending' : ''}`}
          >
            <div className="flow-dot">{done ? '✓' : i + 1}</div>
            {!compact && <span className="flow-label">{STATUS_LABELS[step]}</span>}
          </div>
        )
      })}
    </div>
  )
}

export function OrderStatusBadge({ status }) {
  return <span className={`badge ${status}`}>{STATUS_LABELS[status] || status}</span>
}
