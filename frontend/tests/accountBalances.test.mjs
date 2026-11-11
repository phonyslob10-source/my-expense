import assert from 'node:assert/strict'
import { test } from 'node:test'
import { balancesAfterTransactions } from '../src/accountBalances.ts'
import { filterBills } from '../src/billFilters.ts'
const tx=(id,amount_cents,changes={})=>({id,project:id,date:'2026-11-01',created_at:`2026-11-01T0${id}:00:00Z`,updated_at:'2026-11-01T12:00:00Z',member:'A',type:'expense',category1:'生活',category2:null,note:null,device_id:'test',is_deleted:false,amount_cents,...changes})
const rows=[tx('3',20000),tx('1',100000,{type:'income'}),tx('2',10000),tx('4',5000,{member:'B'}),tx('5',99999,{is_deleted:true})]
test('running balances follow date and creation order per account, in cents, without mutating inputs',()=>{
 const result=balancesAfterTransactions(rows)
 assert.deepEqual([...result],[['1',100000],['2',90000],['3',70000],['4',-5000]])
 assert.equal(rows[0].id,'3')
})
test('filtering and amount sorting do not recalculate the historical balances',()=>{
 const balances=balancesAfterTransactions(rows)
 const displayed=filterBills(rows,{q:'',type:'expense',member:'A',category1:'生活',category2:'',sort:'expense-desc'})
 assert.deepEqual(displayed.map(t=>[t.id,balances.get(t.id)]),[['3',70000],['2',90000]])
})
test('backdated entries, edits and deletions recalculate subsequent balances',()=>{
 const backdated=tx('6',123,{date:'2026-10-31',type:'income'})
 assert.equal(balancesAfterTransactions([...rows,backdated]).get('3'),70123)
 assert.equal(balancesAfterTransactions(rows.map(t=>t.id==='2'?{...t,amount_cents:5000}:t)).get('3'),75000)
 assert.equal(balancesAfterTransactions(rows.map(t=>t.id==='2'?{...t,is_deleted:true}:t)).get('3'),80000)
 assert.equal(balancesAfterTransactions(rows.map(t=>t.id==='2'?{...t,member:'B'}:t)).get('3'),80000)
})
