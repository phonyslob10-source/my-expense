import type { Transaction } from './types'

interface BillFilters {
  q: string
  type: string
  member: string
  category1: string
  category2: string
  sort: string
}

export function filterBills(transactions: Transaction[], filters: BillFilters): Transaction[] {
  const { q, type, member, category1, category2, sort } = filters
  return transactions.filter(t =>
    !t.is_deleted &&
    (!q || `${t.project} ${t.note || ''}`.includes(q)) &&
    (!type || t.type === type) &&
    (!member || t.member === member) &&
    (!category1 || t.category1 === category1) &&
    (!category2 || t.category2 === category2) &&
    (sort !== 'expense-desc' || t.type === 'expense')
  ).sort((a, b) =>
    (sort === 'expense-desc' ? b.amount_cents - a.amount_cents : 0) ||
    b.date.localeCompare(a.date) || b.created_at.localeCompare(a.created_at)
  )
}
