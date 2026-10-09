import assert from 'node:assert/strict'
import { filterBills } from '../src/billFilters.ts'
const base={project:'买菜',note:'市场',date:'2026-10-01',created_at:'2026-10-01T00:00:00Z',member:'A',type:'expense',category1:'生活',category2:'食品',is_deleted:false}
const rows=[{...base,id:'small',amount_cents:1234},{...base,id:'large',amount_cents:9000,date:'2026-09-01'},{...base,id:'income',type:'income',amount_cents:99999},{...base,id:'other-category',category2:'交通',amount_cents:7000},{...base,id:'other-member',member:'B',amount_cents:8000},{...base,id:'deleted',is_deleted:true,amount_cents:100000}]
const all={q:'',type:'',member:'',category1:'',category2:'',sort:'date'}
assert.deepEqual(filterBills(rows,{...all,q:'市场',member:'A',category1:'生活',category2:'食品',sort:'expense-desc'}).map(t=>t.id),['large','small'])
assert.deepEqual(filterBills(rows,{...all,type:'income'}).map(t=>t.id),['income'])
assert.equal(filterBills(rows,{...all,category1:'不存在'}).length,0)
assert.equal(filterBills(rows,all).at(-1).id,'large')
assert.equal(rows[0].id,'small')
assert.deepEqual(filterBills(rows,{...all,sort:'expense-desc'}).map(t=>t.id),['large','other-member','other-category','small'])
console.log('PASS: combined filters, amount order, income exclusion, deleted records, default dates, source array preserved')
