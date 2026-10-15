import { db } from './db'
import type { Category, Member, Transaction } from './types'

interface SyncResult {
  transactions: Transaction[]
  categories: Category[]
  members: Member[]
}

export async function saveTransactionLocally(tx: Transaction) {
  // Keep the visible change and its upload queue entry together, including offline.
  await db.transaction('rw', db.transactions, db.outbox, async () => {
    await db.transactions.put(tx)
    await db.outbox.add({ tx })
  })
}

export async function syncTransactionBatch(send: (changes: Transaction[]) => Promise<SyncResult>) {
  const batch = await db.outbox.toArray()
  const result = await send(batch.map(item => item.tx))
  await db.transaction('rw', db.transactions, db.categories, db.members, db.outbox, async () => {
    // A deletion can be queued while this request is in flight. Only acknowledge
    // this batch, then overlay changes that the server has not received yet.
    const ids = batch.map(item => item.id).filter((id): id is number => id !== undefined)
    await db.outbox.bulkDelete(ids)
    const pending = await db.outbox.toArray()
    await db.transactions.clear()
    await db.categories.clear()
    await db.members.clear()
    await db.transactions.bulkPut(result.transactions)
    await db.transactions.bulkPut(pending.map(item => item.tx))
    await db.categories.bulkPut(result.categories)
    await db.members.bulkPut(result.members)
  })
  return batch.length
}
