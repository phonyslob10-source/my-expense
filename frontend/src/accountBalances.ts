import type { Transaction } from './types'

// Compute from the full ledger before display filtering or amount sorting.
export function balancesAfterTransactions(transactions: Transaction[]): Map<string, number> {
  const balances = new Map<string, number>()
  const byTransaction = new Map<string, number>()
  const chronological = transactions.filter(tx => !tx.is_deleted).sort((a, b) =>
    a.date.localeCompare(b.date) || a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id)
  )
  for (const tx of chronological) {
    const balance = (balances.get(tx.member) ?? 0) + (tx.type === 'income' ? tx.amount_cents : -tx.amount_cents)
    balances.set(tx.member, balance)
    byTransaction.set(tx.id, balance)
  }
  return byTransaction
}
