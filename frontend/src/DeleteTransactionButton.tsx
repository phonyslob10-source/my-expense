import { useRef, useState } from 'react'
import type { Transaction } from './types'

export function DeleteTransactionButton({ tx, onDelete }: {
  tx: Transaction
  onDelete: (tx: Transaction) => Promise<boolean>
}) {
  const [pending, setPending] = useState(false)
  const inFlight = useRef(false)
  const remove = async () => {
    if (inFlight.current) return
    inFlight.current = true
    setPending(true)
    try {
      await onDelete(tx)
    } finally {
      inFlight.current = false
      setPending(false)
    }
  }
  return <button type="button" className="delete-link" disabled={pending}
    aria-label={`删除记录：${tx.project}`} onClick={() => void remove()}>
    {pending ? '删除中…' : '删除'}
  </button>
}
