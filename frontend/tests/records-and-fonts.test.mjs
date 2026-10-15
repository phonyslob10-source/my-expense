import './setup.mjs'
import assert from 'node:assert/strict'
import { after, afterEach, beforeEach, test } from 'node:test'
import React from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from '../src/App.tsx'
import { db } from '../src/db.ts'
import { saveTransactionLocally, syncTransactionBatch } from '../src/transactionStore.ts'
import { FONT_SIZE_KEY, readFontSize } from '../src/fontPreferences.ts'

const originalTx = {
  id: 'test-expense', project: '测试午餐', date: '2026-10-15', member: '测试账户',
  type: 'expense', category1: null, category2: null, amount_cents: 2600, note: null,
  created_at: '2026-10-15T00:00:00.000Z', updated_at: '2026-10-15T00:00:00.000Z',
  device_id: 'test-device', is_deleted: false,
}
const otherTx = { ...originalTx, id: 'test-other', project: '另一笔测试记录', amount_cents: 1800 }
const deletedTx = { ...originalTx, is_deleted: true, updated_at: '2026-10-15T01:00:00.000Z' }
const server = transactions => ({ transactions, categories: [], members: [] })

beforeEach(async () => {
  assert.equal(db.backendDB()?.name === 'my-expense-db' || !db.isOpen(), true)
  await db.transaction('rw', db.transactions, db.outbox, db.members, db.categories, async () => {
    await db.transactions.clear(); await db.outbox.clear(); await db.members.clear(); await db.categories.clear()
    await db.transactions.bulkPut([originalTx, otherTx])
    await db.members.put({ id: 'test-member', name: '测试账户', sort_order: 1, is_active: true, updated_at: originalTx.updated_at })
  })
  localStorage.clear()
  document.documentElement.style.removeProperty('--font-scale')
  window.confirm = () => false
})
afterEach(() => cleanup())
after(async () => { db.close() })

test('editing allows cancelling or deleting exactly one record, with offline queueing', async () => {
  render(React.createElement(App))
  fireEvent.click(await screen.findByText('测试午餐'))
  const remove = screen.getByRole('button', { name: '删除这笔记录' })
  let message = ''
  window.confirm = text => { message = text; return false }
  fireEvent.click(remove)
  await waitFor(() => assert.equal(remove.disabled, false))
  assert.match(message, /测试午餐/); assert.match(message, /2026-10-15/); assert.match(message, /¥26\.00/)
  assert.equal((await db.transactions.get(originalTx.id)).is_deleted, false)
  assert.equal(await db.outbox.count(), 0)
  window.confirm = () => true
  fireEvent.click(remove)
  await screen.findByText('已在本机删除，联网后同步')
  assert.equal((await db.transactions.get(originalTx.id)).is_deleted, true)
  assert.deepEqual(await db.transactions.get(otherTx.id), otherTx)
  const queued = await db.outbox.toArray()
  assert.equal(queued.length, 1); assert.equal(queued[0].tx.id, originalTx.id); assert.equal(queued[0].tx.is_deleted, true)
  assert.equal(screen.queryByText('测试午餐'), null)
})

test('a queue write failure rolls back the deletion and keeps the editor open', async () => {
  const add = db.outbox.add
  db.outbox.add = async () => { throw new Error('测试存储失败') }
  try {
    window.confirm = () => true
    render(React.createElement(App))
    fireEvent.click(await screen.findByText('测试午餐'))
    fireEvent.click(screen.getByRole('button', { name: '删除这笔记录' }))
    await screen.findByText('删除失败：测试存储失败')
    assert.equal((await db.transactions.get(originalTx.id)).is_deleted, false)
    assert.equal(await db.outbox.count(), 0)
    assert.ok(screen.getByRole('heading', { name: '编辑记录' }))
  } finally { db.outbox.add = add }
})

test('the bill list deletes through the same confirmation and new records have no delete action', async () => {
  render(React.createElement(App))
  await screen.findByText('测试午餐')
  fireEvent.click(screen.getByRole('button', { name: /账单/ }))
  window.confirm = () => true
  fireEvent.click(screen.getByRole('button', { name: '删除记录：测试午餐' }))
  await waitFor(async () => assert.equal((await db.transactions.get(originalTx.id)).is_deleted, true))
  fireEvent.click(screen.getByRole('button', { name: /记一笔/ }))
  assert.equal(screen.queryByRole('button', { name: '删除这笔记录' }), null)
  assert.deepEqual(await db.transactions.get(otherTx.id), otherTx)
})

test('a deletion queued during an upload survives its stale server response and the next upload', async () => {
  let started, finish
  const sent = new Promise(resolve => { started = resolve })
  const response = new Promise(resolve => { finish = resolve })
  const syncing = syncTransactionBatch(async changes => { assert.equal(changes.length, 0); started(); return response })
  await sent
  await saveTransactionLocally(deletedTx)
  finish(server([originalTx, otherTx]))
  await syncing
  assert.equal((await db.transactions.get(originalTx.id)).is_deleted, true)
  assert.equal(await db.outbox.count(), 1)
  await syncTransactionBatch(async changes => { assert.deepEqual(changes, [deletedTx]); return server([deletedTx, otherTx]) })
  assert.equal(await db.outbox.count(), 0)
  assert.equal((await db.transactions.get(originalTx.id)).is_deleted, true)
  assert.deepEqual(await db.transactions.get(otherTx.id), otherTx)
})

test('upload failure preserves a queued deletion for a later retry', async () => {
  await saveTransactionLocally(deletedTx)
  await assert.rejects(syncTransactionBatch(async () => { throw new Error('offline') }), /offline/)
  assert.equal(await db.outbox.count(), 1)
  assert.equal((await db.transactions.get(originalTx.id)).is_deleted, true)
})

test('font settings offer smaller sizes, apply immediately and persist across remounts', async () => {
  const app = render(React.createElement(App))
  await screen.findByText('测试午餐')
  assert.equal(document.documentElement.style.getPropertyValue('--font-scale'), '0.875')
  fireEvent.click(screen.getByRole('button', { name: /设置/ }))
  assert.equal(screen.queryByRole('button', { name: '特大' }), null)
  fireEvent.click(screen.getByRole('button', { name: '小号' }))
  await waitFor(() => assert.equal(document.documentElement.style.getPropertyValue('--font-scale'), '0.8125'))
  assert.equal(localStorage.getItem(FONT_SIZE_KEY), 'small')
  assert.equal(screen.getByRole('button', { name: '小号' }).getAttribute('aria-pressed'), 'true')
  app.unmount()
  await act(async () => { render(React.createElement(App)) })
  assert.equal(document.documentElement.style.getPropertyValue('--font-scale'), '0.8125')
  assert.deepEqual(await db.transactions.toArray(), [originalTx, otherTx].sort((a,b) => a.id.localeCompare(b.id)))
})

test('unknown or unavailable font preferences fall back to the compact default', () => {
  localStorage.setItem(FONT_SIZE_KEY, 'invalid')
  assert.equal(readFontSize(), 'medium')
  const getItem = Object.getPrototypeOf(localStorage).getItem
  Object.getPrototypeOf(localStorage).getItem = () => { throw new Error('storage disabled') }
  try { assert.equal(readFontSize(), 'medium') }
  finally { Object.getPrototypeOf(localStorage).getItem = getItem }
})
