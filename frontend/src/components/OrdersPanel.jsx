import { STATUS_LABELS, NEXT_STATUS, KITCHEN_STATUSES, ACTIVE_STATUSES, READY_STATUSES } from '../lib/orderStatus'
import OrderFlowTracker, { OrderStatusBadge } from './OrderFlowTracker'

function OrderCard({ order, onStatusChange, showActions = true }) {
  const next = NEXT_STATUS[order.status]

  return (
    <div className="order-card">
      <header>
        <strong>Pedido #{order.id}</strong>
        <OrderStatusBadge status={order.status} />
      </header>
      <OrderFlowTracker status={order.status} compact />
      <div className="order-meta">
        {order.customer_name && <div>Cliente: {order.customer_name}</div>}
        {order.customer_phone && <div>Tel: {order.customer_phone}</div>}
        {order.order_type && <div>Tipo: {order.order_type}</div>}
        {order.delivery_address && <div>Dirección: {order.delivery_address}</div>}
        {order.payment_method && <div>Pago: {order.payment_method}</div>}
      </div>
      <ul className="order-items">
        {order.items?.map((item) => (
          <li key={item.id}>
            {item.quantity}x {item.name} — ${item.unit_price.toFixed(2)}
            {item.notes && ` (${item.notes})`}
          </li>
        ))}
      </ul>
      <div className="total-row">
        <span>Total</span>
        <span>${order.total.toFixed(2)}</span>
      </div>
      {showActions && next && (
        <div className="order-actions">
          <button className="btn btn-primary" onClick={() => onStatusChange(order.id, next)}>
            → {STATUS_LABELS[next]}
          </button>
        </div>
      )}
    </div>
  )
}

export default function OrdersPanel({ orders, updateStatus, filter }) {
  const filtered = filter ? orders.filter((o) => filter.includes(o.status)) : orders

  return (
    <div>
      {filtered.length === 0 ? (
        <p className="empty">No hay pedidos en esta vista.</p>
      ) : (
        filtered.map((order) => (
          <OrderCard key={order.id} order={order} onStatusChange={updateStatus} />
        ))
      )}
    </div>
  )
}

export function KitchenPanel({ orders, updateStatus }) {
  const kitchenOrders = orders.filter((o) => KITCHEN_STATUSES.includes(o.status))

  return (
    <div>
      <p className="kitchen-intro">
        Pedidos confirmados y en preparación. Avanza el estado cuando corresponda.
      </p>
      <div className="kitchen-grid">
        {kitchenOrders.length === 0 ? (
          <p className="empty">Cocina sin pedidos. Confirma un pedido en Agente primero.</p>
        ) : (
          kitchenOrders.map((order) => (
            <div
              key={order.id}
              className={`kitchen-card ${order.status === 'listo' ? 'listo' : ''} ${order.status === 'en_cocina' ? 'preparing' : ''}`}
            >
              <header>
                <strong>#{order.id}</strong>
                <OrderStatusBadge status={order.status} />
              </header>
              <ul className="order-items">
                {order.items?.map((item) => (
                  <li key={item.id}>
                    {item.quantity}x {item.name}
                  </li>
                ))}
              </ul>
              {order.notes && (
                <p className="section-desc" style={{ marginTop: '0.5rem', marginBottom: 0 }}>
                  Notas: {order.notes}
                </p>
              )}
              {order.status === 'confirmado' && (
                <button
                  type="button"
                  className="btn btn-primary btn-full"
                  onClick={() => updateStatus(order.id, 'en_cocina')}
                >
                  Iniciar preparación
                </button>
              )}
              {order.status === 'en_cocina' && (
                <button
                  type="button"
                  className="btn btn-primary btn-full"
                  onClick={() => updateStatus(order.id, 'listo')}
                >
                  Marcar listo
                </button>
              )}
              {order.status === 'listo' && (
                <p className="kitchen-hint">Listo — pasa a Caja para entregar.</p>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export function CashierPanel({ orders, updateStatus }) {
  const ready = orders.filter((o) => READY_STATUSES.includes(o.status))
  const active = orders.filter((o) => ACTIVE_STATUSES.includes(o.status))

  return (
    <div className="grid-2">
      <div className="card">
        <h2>Por cobrar / entregar</h2>
        {ready.length === 0 ? (
          <p className="empty">Sin pedidos listos. Cocina debe marcar &quot;Listo&quot; primero.</p>
        ) : (
          ready.map((order) => (
            <OrderCard key={order.id} order={order} onStatusChange={updateStatus} />
          ))
        )}
      </div>
      <div className="card">
        <h2>En proceso</h2>
        {active.length === 0 ? (
          <p className="empty">Sin pedidos en proceso.</p>
        ) : (
          active.map((order) => (
            <OrderCard key={order.id} order={order} onStatusChange={updateStatus} showActions={false} />
          ))
        )}
      </div>
    </div>
  )
}
