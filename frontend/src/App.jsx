import { useState, useEffect, useCallback } from 'react'
import AgentPanel from './components/AgentPanel'
import OrdersPanel, { KitchenPanel, CashierPanel } from './components/OrdersPanel'
import { useOrders } from './hooks/useApi'
import { KITCHEN_STATUSES, READY_STATUSES } from './lib/orderStatus'

const TABS = [
  { id: 'agente', label: 'Agente', icon: '🎙️', desc: 'Llamadas y pedidos' },
  { id: 'pedidos', label: 'Pedidos', icon: '📋', desc: 'Historial completo' },
  { id: 'cocina', label: 'Cocina', icon: '👨‍🍳', desc: 'Preparación' },
  { id: 'caja', label: 'Caja', icon: '💳', desc: 'Entrega y cobro' },
]

function tabCount(orders, tabId) {
  if (tabId === 'cocina') return orders.filter((o) => KITCHEN_STATUSES.includes(o.status)).length
  if (tabId === 'caja') return orders.filter((o) => READY_STATUSES.includes(o.status)).length
  return 0
}

export default function App() {
  const [tab, setTab] = useState('agente')
  const [health, setHealth] = useState(null)
  const { orders, connected, updateStatus, refresh } = useOrders()

  const onOrderFromAgent = useCallback(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: 'error' }))
  }, [])

  const activeTab = TABS.find((t) => t.id === tab)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">🍽️</div>
          <div>
            <strong>La Casa del Sabor</strong>
            <span>Call Center IA</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          {TABS.map((t) => {
            const count = tabCount(orders, t.id)
            return (
              <button
                key={t.id}
                type="button"
                className={`nav-item ${tab === t.id ? 'active' : ''}`}
                onClick={() => setTab(t.id)}
              >
                <span className="nav-icon">{t.icon}</span>
                <span className="nav-text">
                  <span className="nav-label">{t.label}</span>
                  <span className="nav-desc">{t.desc}</span>
                </span>
                {count > 0 && <span className="nav-badge">{count}</span>}
              </button>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          <div className={`status-chip ${connected ? 'online' : 'offline'}`}>
            <span className="status-dot" />
            {connected ? 'Tiempo real activo' : 'Sin conexión WS'}
          </div>
          {health && (
            <div className="sidebar-meta">
              <span className={health.openai_configured ? 'meta-ok' : 'meta-warn'}>
                OpenAI {health.openai_configured ? '✓' : '✗'}
              </span>
              <span>{orders.length} pedidos</span>
            </div>
          )}
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <p className="topbar-eyebrow">Panel operativo</p>
            <h1>{activeTab?.label}</h1>
            <p className="topbar-sub">{activeTab?.desc}</p>
          </div>
          <div className="topbar-chips">
            <div className="chip chip-accent">
              <span className="chip-label">STT · LLM · RAG</span>
            </div>
            {health?.twilio_call_available && (
              <div className="chip chip-teal">Twilio activo</div>
            )}
          </div>
        </header>

        <div className="content">
          {tab === 'agente' && <AgentPanel onOrderUpdate={onOrderFromAgent} />}
          {tab === 'pedidos' && <OrdersPanel orders={orders} updateStatus={updateStatus} />}
          {tab === 'cocina' && <KitchenPanel orders={orders} updateStatus={updateStatus} />}
          {tab === 'caja' && <CashierPanel orders={orders} updateStatus={updateStatus} />}
        </div>
      </main>
    </div>
  )
}
