import { useEffect, useRef, useState, useCallback } from 'react'

// Usa el proxy de Vite (5173 → 8000) para evitar problemas de conexión directa
const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/orders`

export function useWebSocket(onMessage) {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        setTimeout(connect, 3000)
      }
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          onMessageRef.current?.(msg)
        } catch {}
      }
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  return { connected }
}

export async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    const msg = Array.isArray(detail)
      ? detail.map((d) => d.msg).join(', ')
      : (typeof detail === 'string' ? detail : res.statusText)
    if (res.status === 500) {
      throw new Error(`${msg}. Reinicia el backend: Ctrl+C y vuelve a ejecutar uvicorn.`)
    }
    throw new Error(msg || 'Error en la API')
  }
  return res.json()
}

export function useOrders() {
  const [orders, setOrders] = useState([])

  const refresh = useCallback(async () => {
    const data = await api('/orders')
    setOrders(data)
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const handleWs = useCallback((msg) => {
    if (msg.type === 'order_updated') {
      setOrders(prev => {
        const idx = prev.findIndex(o => o.id === msg.data.id)
        if (idx >= 0) {
          const next = [...prev]
          next[idx] = msg.data
          return next
        }
        return [msg.data, ...prev]
      })
    }
    if (msg.type === 'call_updated' && msg.data?.session?.order) {
      const order = msg.data.session.order
      setOrders(prev => {
        const idx = prev.findIndex(o => o.id === order.id)
        if (idx >= 0) {
          const next = [...prev]
          next[idx] = order
          return next
        }
        return [order, ...prev]
      })
    }
  }, [])

  const { connected } = useWebSocket(handleWs)

  const updateStatus = async (orderId, status) => {
    await api(`/orders/${orderId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
    await refresh()
  }

  return { orders, connected, refresh, updateStatus }
}

export function useAudioRecorder() {
  const [recording, setRecording] = useState(false)
  const mediaRef = useRef(null)
  const chunksRef = useRef([])

  const start = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mimeTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg']
    const mimeType = mimeTypes.find((t) => MediaRecorder.isTypeSupported(t)) || ''
    const recorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream)
    chunksRef.current = []
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data)
    }
    mediaRef.current = recorder
    recorder.start(250)
    setRecording(true)
  }

  const stop = () => new Promise((resolve) => {
    const recorder = mediaRef.current
    if (!recorder) return resolve(null)
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
      recorder.stream.getTracks().forEach(t => t.stop())
      setRecording(false)
      resolve(blob)
    }
    recorder.stop()
  })

  return { recording, start, stop }
}

export async function playTts(text) {
  const res = await fetch(`/api/tts?text=${encodeURIComponent(text)}`, { method: 'POST' })
  if (!res.ok) return
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  await audio.play()
  audio.onended = () => URL.revokeObjectURL(url)
}

export async function sendAudioTurn(sessionId, blob) {
  const form = new FormData()
  const ext = blob.type.includes('mp4') ? 'recording.mp4' : 'recording.webm'
  form.append('audio', blob, ext)
  const res = await fetch(`/api/calls/audio?session_id=${encodeURIComponent(sessionId)}`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    throw new Error(typeof detail === 'string' ? detail : 'Error procesando audio')
  }
  return res.json()
}
