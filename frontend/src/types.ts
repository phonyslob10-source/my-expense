export type TxType = 'expense' | 'income'
export type CategoryType = 'expense_category1' | 'income_category'

export interface Transaction {
  id: string
  project: string
  date: string
  member: string
  type: TxType
  category1: string | null
  category2: string | null
  amount_cents: number
  note: string | null
  created_at: string
  updated_at: string
  device_id: string
  is_deleted: boolean
}

export interface Category {
  id: string
  type: CategoryType
  name: string
  sort_order: number
  is_active: boolean
  updated_at: string
}

export interface Member {
  id: string
  name: string
  sort_order: number
  is_active: boolean
  updated_at: string
}
