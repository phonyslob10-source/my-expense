import Dexie, { type EntityTable } from 'dexie'
import type { Category, Member, Transaction } from './types'

export interface OutboxItem {
  id?: number
  tx: Transaction
}

class ExpenseDB extends Dexie {
  transactions!: EntityTable<Transaction, 'id'>
  categories!: EntityTable<Category, 'id'>
  members!: EntityTable<Member, 'id'>
  outbox!: EntityTable<OutboxItem, 'id'>

  constructor() {
    super('my-expense-db')
    this.version(1).stores({
      transactions: 'id,date,updated_at,device_id',
      categories: 'id,type,sort_order,updated_at',
      members: 'id,name,sort_order,updated_at',
      outbox: '++id,tx.id,tx.updated_at',
    })
  }
}

export const db = new ExpenseDB()
