export const STATUS_LABELS = {
  recibido: 'Recibido',
  confirmando: 'Confirmando',
  confirmado: 'Confirmado',
  en_cocina: 'En cocina',
  listo: 'Listo',
  entregado: 'Entregado',
  cancelado: 'Cancelado',
}

export const STATUS_FLOW = ['recibido', 'confirmando', 'confirmado', 'en_cocina', 'listo', 'entregado']

export const NEXT_STATUS = {
  recibido: 'confirmando',
  confirmando: 'confirmado',
  confirmado: 'en_cocina',
  en_cocina: 'listo',
  listo: 'entregado',
}

export const KITCHEN_STATUSES = ['confirmado', 'en_cocina', 'listo']
export const ACTIVE_STATUSES = ['recibido', 'confirmando', 'confirmado', 'en_cocina']
export const READY_STATUSES = ['listo']

export function statusIndex(status) {
  const idx = STATUS_FLOW.indexOf(status)
  return idx >= 0 ? idx : 0
}

export function isConfirmedOrLater(status) {
  return statusIndex(status) >= statusIndex('confirmado')
}
