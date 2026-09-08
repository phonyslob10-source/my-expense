import { useEffect, useMemo, useState } from 'react'
import { db } from './db'
import * as api from './api'
import type { Category, Member, Transaction, TxType } from './types'
import { nowIso, monthRange, today, uid, yuan } from './utils'
import { XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'

const defaultTx = (): Partial<Transaction> => ({
  id: uid(), project: '', date: today(), member: '', type: 'expense', category1: '', amount_cents: 0, note: '',
  created_at: nowIso(), updated_at: nowIso(), device_id: api.deviceId(), is_deleted: false,
})

const PIE_COLORS = ['#111827','#2563eb','#059669','#d97706','#dc2626','#7c3aed','#db2777','#0891b2','#65a30d','#9333ea']
const moneyLabel = (value: number) => `¥${Math.round(Number(value)).toLocaleString('zh-CN')}`

export default function App() {
  const [page, setPage] = useState<'home'|'add'|'list'|'stats'|'settings'>('home')
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [members, setMembers] = useState<Member[]>([])
  const [syncing, setSyncing] = useState(false)
  const [online, setOnline] = useState(navigator.onLine)
  const [editing, setEditing] = useState<Transaction | null>(null)
  const [toast, setToast] = useState('')
  const [adminMode, setAdminMode] = useState(Boolean(api.adminToken()))
  const [pendingCount, setPendingCount] = useState(0)

  const reloadLocal = async () => {
    const [tx, cats, mem] = await Promise.all([
      db.transactions.filter(t => !t.is_deleted).toArray(),
      db.categories.toArray(),
      db.members.toArray(),
    ])
    tx.sort((a,b) => b.date.localeCompare(a.date) || b.created_at.localeCompare(a.created_at))
    setTransactions(tx); setCategories(cats); setMembers(mem)
    setPendingCount(await db.outbox.count())
  }

  const sync = async () => {
    if (!navigator.onLine || syncing) return
    setSyncing(true)
    try {
      const outbox = await db.outbox.toArray()
      const result = await api.syncTransactions(outbox.map(x => x.tx))
      await db.transaction('rw', db.transactions, db.categories, db.members, db.outbox, async () => {
        await db.transactions.clear(); await db.categories.clear(); await db.members.clear()
        await db.transactions.bulkPut(result.transactions)
        await db.categories.bulkPut(result.categories)
        await db.members.bulkPut(result.members)
        await db.outbox.clear()
      })
      await reloadLocal()
      setToast(outbox.length ? `已同步 ${outbox.length} 笔` : '数据已同步')
    } catch (e) {
      setToast(e instanceof Error ? e.message : '同步失败')
    } finally { setSyncing(false) }
  }

  useEffect(() => {
    let active = true
    const boot = async () => {
      await reloadLocal()
      if (active && navigator.onLine) await sync()
    }
    boot()
    const onOnline = () => { setOnline(true); void sync() }
    const onOffline = () => setOnline(false)
    const onVisible = () => { if (document.visibilityState === 'visible' && navigator.onLine) void sync() }
    window.addEventListener('online', onOnline); window.addEventListener('offline', onOffline)
    window.addEventListener('focus', onVisible); document.addEventListener('visibilitychange', onVisible)
    return () => { active = false; window.removeEventListener('online', onOnline); window.removeEventListener('offline', onOffline); window.removeEventListener('focus', onVisible); document.removeEventListener('visibilitychange', onVisible) }
  }, [])

  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(''), 2200); return () => clearTimeout(t) } }, [toast])

  const saveLocalTransaction = async (tx: Transaction) => {
    await db.transactions.put(tx)
    await db.outbox.put({ tx })
    await reloadLocal()
    if (navigator.onLine) void sync()
  }

  const submitTx = async (draft: Partial<Transaction>, keepForm = false): Promise<Transaction | undefined> => {
    if (!draft.project?.trim() || !draft.member || !draft.amount_cents) {
      setToast('请填写项目、成员和金额')
      return undefined
    }
    const tx: Transaction = {
      id: draft.id || uid(), project: draft.project.trim(), date: draft.date || today(), member: draft.member,
      type: (draft.type || 'expense') as TxType, category1: draft.category1 || null, category2: null,
      amount_cents: Number(draft.amount_cents), note: draft.note || null, created_at: draft.created_at || nowIso(), updated_at: nowIso(),
      device_id: draft.device_id || api.deviceId(), is_deleted: false,
    }
    await saveLocalTransaction(tx)
    setToast('已保存')
    if (!keepForm) setPage('home')
    return tx
  }

  const doDelete = async (tx: Transaction) => {
    const deleted = { ...tx, is_deleted: true, updated_at: nowIso() }
    await db.transactions.put(deleted); await db.outbox.put({ tx: deleted }); await reloadLocal(); if (navigator.onLine) void sync();
    setToast('已删除')
  }

  const month = monthRange()
  const monthTx = useMemo(() => transactions.filter(t => t.date >= month.start && t.date <= month.end), [transactions])
  const monthExpense = monthTx.filter(t => t.type === 'expense').reduce((s,t)=>s+t.amount_cents,0)
  const monthIncome = monthTx.filter(t => t.type === 'income').reduce((s,t)=>s+t.amount_cents,0)
  const todayTx = transactions.filter(t => t.date === today())
  const todayExpense = todayTx.filter(t => t.type === 'expense').reduce((s,t)=>s+t.amount_cents,0)
  const todayIncome = todayTx.filter(t => t.type === 'income').reduce((s,t)=>s+t.amount_cents,0)

  const cat1 = categories.filter(c=>c.type==='expense_category1' && c.is_active)
  const incomeCats = categories.filter(c=>c.type==='income_category' && c.is_active)

  return <div className="app-shell">
    <header className="topbar">
      <div><strong>我的记账</strong><small>{online ? (syncing ? '同步中…' : '已连接') : '离线模式'}{pendingCount ? ` · 待同步 ${pendingCount}` : ''}</small></div>
      <button className="icon-btn" onClick={sync} disabled={!online || syncing}>↻</button>
    </header>

    <main className="content">
      {page==='home' && <HomePage monthExpense={monthExpense} monthIncome={monthIncome} todayExpense={todayExpense} transactions={transactions} members={members} onAdd={()=>{setEditing(null);setPage('add')}} onOpenTx={(t)=>{setEditing(t);setPage('add')}} />}
      {page==='add' && <AddPage editing={editing} members={members} cat1={cat1} incomeCats={incomeCats} onCancel={()=>setPage('home')} onSubmit={submitTx} />}
      {page==='list' && <ListPage transactions={transactions} categories={categories} members={members} onEdit={(t)=>{setEditing(t);setPage('add')}} onDelete={doDelete} />}
      {page==='stats' && <StatsPage transactions={transactions} categories={categories} members={members} />}
      {page==='settings' && <SettingsPage categories={categories} members={members} adminMode={adminMode} setAdminMode={setAdminMode} onReload={reloadLocal} onSync={sync} onToast={setToast} />}
    </main>

    <nav className="tabbar">
      <Tab active={page==='home'} label="首页" icon="⌂" onClick={()=>setPage('home')} />
      <Tab active={page==='list'} label="账单" icon="▤" onClick={()=>setPage('list')} />
      <button className="fab" onClick={()=>{setEditing(null);setPage('add')}}>＋<span>记一笔</span></button>
      <Tab active={page==='stats'} label="统计" icon="◒" onClick={()=>setPage('stats')} />
      <Tab active={page==='settings'} label="设置" icon="⚙" onClick={()=>setPage('settings')} />
    </nav>
    {toast && <div className="toast">{toast}</div>}
  </div>
}

function Tab({active,label,icon,onClick}:{active:boolean,label:string,icon:string,onClick:()=>void}) {
  return <button className={`tab ${active?'active':''}`} onClick={onClick}><span>{icon}</span><small>{label}</small></button>
}

function HomePage({monthExpense,monthIncome,todayExpense,transactions,members,onAdd,onOpenTx}:{monthExpense:number,monthIncome:number,todayExpense:number,transactions:Transaction[],members:Member[],onAdd:()=>void,onOpenTx:(t:Transaction)=>void}) {
  const accountCards = members.filter(m => m.name === 'Jerry' || m.name === 'Flora')
  return <>
    <section className="hero-card">
      <div className="eyebrow">本月</div>
      <div className="hero-number">{yuan(monthExpense)}</div>
      <div className="hero-sub">收入 {yuan(monthIncome)} · 结余 {yuan(monthIncome-monthExpense)}</div>
    </section>
    <div className="two-cards">
      <div className="stat-card"><small>今日支出</small><strong>{yuan(todayExpense)}</strong></div>
      <div className="stat-card"><small>本月收入</small><strong>{yuan(monthIncome)}</strong></div>
    </div>
    <section className="account-grid">
      {accountCards.map(account => {
        const expense = transactions.filter(t => t.member === account.name && t.type === 'expense' && t.date >= monthRange().start && t.date <= monthRange().end).reduce((s,t)=>s+t.amount_cents,0)
        const income = transactions.filter(t => t.member === account.name && t.type === 'income' && t.date >= monthRange().start && t.date <= monthRange().end).reduce((s,t)=>s+t.amount_cents,0)
        const totalExpense = transactions.filter(t => t.member === account.name && t.type === 'expense').reduce((s,t)=>s+t.amount_cents,0)
        const totalIncome = transactions.filter(t => t.member === account.name && t.type === 'income').reduce((s,t)=>s+t.amount_cents,0)
        const balance = totalIncome - totalExpense
        return <div className="account-card" key={account.id}>
          <div className="account-name">{account.name}</div>
          <div><small>余额</small><strong className={balance >= 0 ? 'plus' : 'minus'}>{balance >= 0 ? '+' : '-'}{yuan(Math.abs(balance))}</strong></div>
          <div><small>本月支出</small><strong className="minus">-{yuan(expense)}</strong></div>
          <div><small>本月收入</small><strong className="plus">+{yuan(income)}</strong></div>
        </div>
      })}
    </section>
    <button className="primary wide" onClick={onAdd}>＋ 记一笔</button>
    <section className="panel"><div className="panel-title">最近 5 笔</div>
      {transactions.slice(0,5).map(t=><TxRow key={t.id} tx={t} onClick={()=>onOpenTx(t)} />)}
      {!transactions.length && <div className="empty">还没有记录，先记第一笔。</div>}
    </section>
  </>
}

function AddPage({editing,members,cat1,incomeCats,onCancel,onSubmit}:{editing:Transaction|null,members:Member[],cat1:Category[],incomeCats:Category[],onCancel:()=>void,onSubmit:(draft:Partial<Transaction>, keepForm?:boolean)=>Promise<Transaction|undefined>}) {
  const [form,setForm] = useState<Partial<Transaction>>(editing ? {...editing} : defaultTx())
  useEffect(()=>{ if(!form.member && members[0]) setForm(f=>({...f,member:members[0].name})) },[members,form.member])
  const set = (k:keyof Transaction, v:unknown)=>setForm(f=>({...f,[k]:v}))
  const submit = async (keep=false) => {
    await onSubmit(form,keep)
    if (keep) setForm(f=>({ ...defaultTx(), member:f.member, date:f.date, category1:f.category1 }))
  }
  const isIncome=form.type==='income'
  return <>
    <div className="page-head"><button className="back" onClick={onCancel}>‹</button><h2>{editing?'编辑记录':'记一笔'}</h2></div>
    <div className="form panel">
      <label>项目 / 用途<input autoFocus value={form.project||''} onChange={e=>set('project',e.target.value)} placeholder="例如：买菜、工资" /></label>
      <div className="segmented"><button className={isIncome?'':'selected'} onClick={()=>set('type','expense')}>支出</button><button className={isIncome?'selected':''} onClick={()=>set('type','income')}>收入</button></div>
      <label>日期<input type="date" value={form.date||today()} onChange={e=>set('date',e.target.value)} /></label>
      <label>账户<select value={form.member||''} onChange={e=>set('member',e.target.value)}>{members.filter(m=>m.is_active).map(m=><option key={m.id}>{m.name}</option>)}</select></label>
      <label>金额<input inputMode="decimal" type="number" step="0.01" min="0" value={form.amount_cents ? (form.amount_cents/100).toString() : ''} onChange={e=>set('amount_cents',Math.round(Number(e.target.value||0)*100))} placeholder="0.00" /></label>
      <label>{isIncome?'收入分类':'分类1'}<select value={form.category1||''} onChange={e=>set('category1',e.target.value)}><option value="">请选择</option>{(isIncome?incomeCats:cat1).map(c=><option key={c.id}>{c.name}</option>)}</select></label>
      <label>备注<textarea value={form.note||''} onChange={e=>set('note',e.target.value)} placeholder="可选" rows={3}/></label>
      <button className="primary wide" onClick={()=>submit(false)}>保存</button>
      {!editing && <button className="secondary wide" onClick={()=>submit(true)}>保存并继续</button>}
      {editing && <button className="secondary wide" onClick={onCancel}>取消</button>}
    </div>
  </>
}

function TxRow({tx,onClick}:{tx:Transaction,onClick?:()=>void}) {
  return <button className="tx-row" onClick={onClick}>
    <div><strong>{tx.project}</strong><small>{tx.date} · {tx.member}{tx.category1?` · ${tx.category1}`:''}</small></div>
    <strong className={tx.type==='expense'?'minus':'plus'}>{tx.type==='expense'?'-':'+'}{yuan(tx.amount_cents)}</strong>
  </button>
}

function ListPage({transactions,onEdit,onDelete,categories,members}:{transactions:Transaction[],onEdit:(t:Transaction)=>void,onDelete:(t:Transaction)=>void,categories:Category[],members:Member[]}) {
  const [q,setQ]=useState(''); const [type,setType]=useState(''); const [member,setMember]=useState('')
  const filtered=transactions.filter(t=>(!q||`${t.project} ${t.note||''}`.includes(q))&&(!type||t.type===type)&&(!member||t.member===member))
  return <>
    <div className="page-head"><h2>账单</h2></div>
    <div className="filters"><input value={q} onChange={e=>setQ(e.target.value)} placeholder="搜索项目、备注"/><select value={type} onChange={e=>setType(e.target.value)}><option value="">全部类型</option><option value="expense">支出</option><option value="income">收入</option></select><select value={member} onChange={e=>setMember(e.target.value)}><option value="">全部账户</option>{members.filter(m=>m.is_active).map(m=><option key={m.id}>{m.name}</option>)}</select></div>
    <section className="panel">{filtered.map(t=><div key={t.id} className="tx-wrap"><TxRow tx={t} onClick={()=>onEdit(t)}/><button className="delete-link" onClick={(e)=>{e.stopPropagation(); if(confirm('删除这笔记录？')) onDelete(t)}}>删除</button></div>)}{!filtered.length&&<div className="empty">没有匹配记录。</div>}</section>
  </>
}

function StatsPage({transactions,categories,members}:{transactions:Transaction[],categories:Category[],members:Member[]}) {
  const [start,setStart]=useState(monthRange().start)
  const [end,setEnd]=useState(monthRange().end)
  const tx=transactions.filter(t=>t.date>=start&&t.date<=end)
  const expense=tx.filter(t=>t.type==='expense').reduce((s,t)=>s+t.amount_cents,0)
  const income=tx.filter(t=>t.type==='income').reduce((s,t)=>s+t.amount_cents,0)
  const byCat=Object.entries(tx.filter(t=>t.type==='expense').reduce<Record<string,number>>((a,t)=>{
    const key=t.category1||'未分类'
    a[key]=(a[key]||0)+t.amount_cents
    return a
  },{})).map(([name,value])=>({name,value:value/100}))
  const byMember=members.filter(m=>m.is_active).map(m=>({
    name:m.name,
    支出:Math.round(tx.filter(t=>t.member===m.name&&t.type==='expense').reduce((s,t)=>s+t.amount_cents,0)/100),
    收入:Math.round(tx.filter(t=>t.member===m.name&&t.type==='income').reduce((s,t)=>s+t.amount_cents,0)/100)
  }))
  const pieTotal=byCat.reduce((s,d)=>s+d.value,0)
  return <>
    <div className="page-head"><h2>统计</h2></div>
    <div className="date-range">
      <input aria-label="开始日期" type="date" value={start} onChange={e=>setStart(e.target.value)}/>
      <span className="date-sep">至</span>
      <input aria-label="结束日期" type="date" value={end} onChange={e=>setEnd(e.target.value)}/>
    </div>
    <div className="two-cards">
      <div className="stat-card"><small>总支出</small><strong>{yuan(expense)}</strong></div>
      <div className="stat-card"><small>总收入</small><strong className="plus">{yuan(income)}</strong></div>
    </div>
    <div className="two-cards">
      <div className="stat-card"><small>净结余</small><strong>{yuan(income-expense)}</strong></div>
      <div className="stat-card"><small>记录数</small><strong>{tx.length}</strong></div>
    </div>
    <section className="panel chart"><div className="panel-title">支出分类</div>
      {byCat.length ? <>
        <div className="pie-wrap">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={byCat} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={76} innerRadius={34} paddingAngle={2} label={false} labelLine={false}>
                {byCat.map((_,i)=><Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]}/>)}
              </Pie>
              <Tooltip formatter={(v)=>moneyLabel(Number(v))}/>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="pie-legend">
          {byCat.map((item,i)=> <div className="pie-legend-row" key={item.name}>
            <span className="legend-dot" style={{background:PIE_COLORS[i % PIE_COLORS.length]}} />
            <span className="legend-name">{item.name}</span>
            <span className="legend-value">{moneyLabel(item.value)} · {pieTotal ? Math.round(item.value / pieTotal * 100) : 0}%</span>
          </div>)}
        </div>
      </> : <div className="empty">当前区间没有支出。</div>}
    </section>
    <section className="panel chart"><div className="panel-title">按账户</div>
      {byMember.length ? <AccountBarChart data={byMember} /> : <div className="empty">暂无账户。</div>}
    </section>
  </>
}

function AccountBarChart({data}:{data:{name:string,支出:number,收入:number}[]}) {
  const maxValue = Math.max(1, ...data.flatMap(d => [d.支出, d.收入]))
  const niceMax = Math.ceil(maxValue / 500) * 500 || 500
  const ticks = [1, 0.75, 0.5, 0.25, 0]
  return <div className="account-bar-chart">
    <div className="chart-plot">
      <div className="chart-y-labels">
        {ticks.map((ratio, i) => <span key={i}>{moneyLabel(niceMax * ratio)}</span>)}
      </div>
      <div className="chart-grid-area">
        <div className="chart-grid-lines">{ticks.map((_,i)=><span key={i}/>)}</div>
        <div className="chart-groups">
          {data.map((d) => <div className="chart-group" key={d.name}>
            <div className="chart-bars">
              <div className="chart-bar-col">
                <div className="chart-value">{moneyLabel(d.支出)}</div>
                <div className="chart-bar expense-bar" style={{height:`${Math.max(d.支出 ? 4 : 0, d.支出 / niceMax * 100)}%`}}/>
              </div>
              <div className="chart-bar-col">
                <div className="chart-value">{moneyLabel(d.收入)}</div>
                <div className="chart-bar income-bar" style={{height:`${Math.max(d.收入 ? 4 : 0, d.收入 / niceMax * 100)}%`}}/>
              </div>
            </div>
            <div className="chart-x-label">{d.name}</div>
          </div>)}
        </div>
      </div>
    </div>
    <div className="chart-legend">
      <span><i className="legend-square expense-square"/>支出</span>
      <span><i className="legend-square income-square"/>收入</span>
    </div>
  </div>
}

function SettingsPage({categories,members,adminMode,setAdminMode,onReload,onSync,onToast}:{categories:Category[],members:Member[],adminMode:boolean,setAdminMode:(v:boolean)=>void,onReload:()=>void,onSync:()=>Promise<void>,onToast:(s:string)=>void}) {
  const [password,setPassword]=useState('')
  const doLogin=async()=>{try{await api.loginAdmin(password);setAdminMode(true);onToast('管理员模式已开启')}catch(e){onToast(e instanceof Error?e.message:'登录失败')}}
  return <>
    <div className="page-head"><h2>设置</h2></div>
    {!adminMode && <section className="panel"><div className="panel-title">管理员</div><div className="hint">普通用户可以记账和查看，分类/成员管理需要管理员密码。</div><input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="管理员密码"/><button className="primary wide" onClick={doLogin}>进入管理员模式</button></section>}
    {adminMode && <AdminPanel categories={categories} members={members} onReload={onReload} onSync={onSync} onToast={onToast}/>} 
    <section className="panel"><div className="panel-title">设备</div><div className="hint">设备 ID：{api.deviceId()}</div><button className="secondary wide" onClick={()=>{localStorage.removeItem('expense-admin-token');setAdminMode(false);onToast('已退出管理员模式')}}>退出管理员模式</button></section>
  </>
}

function AdminPanel({categories,members,onReload,onSync,onToast}:{categories:Category[],members:Member[],onReload:()=>void,onSync:()=>Promise<void>,onToast:(s:string)=>void}) {
  const [newCat,setNewCat]=useState(''); const [catType,setCatType]=useState<'expense_category1'|'income_category'>('expense_category1'); const [newMember,setNewMember]=useState('')
  const addCat=async()=>{try{await api.addCategory({name:newCat,type:catType,sort_order:100});setNewCat('');await onSync();onToast('分类已添加')}catch(e){onToast(e instanceof Error?e.message:'添加失败')}}
  const addMem=async()=>{try{await api.addMember({name:newMember,sort_order:100});setNewMember('');await onSync();onToast('成员已添加')}catch(e){onToast(e instanceof Error?e.message:'添加失败')}}
  return <section className="panel admin"><div className="panel-title">分类与成员</div>
    <div className="admin-block"><strong>新增分类</strong><div className="inline"><select value={catType} onChange={e=>setCatType(e.target.value as typeof catType)}><option value="expense_category1">支出分类1</option><option value="income_category">收入分类</option></select><input value={newCat} onChange={e=>setNewCat(e.target.value)} placeholder="分类名称"/><button className="secondary" onClick={addCat}>添加</button></div></div>
    <div className="admin-block"><strong>新增成员</strong><div className="inline"><input value={newMember} onChange={e=>setNewMember(e.target.value)} placeholder="姓名（最多 5 人）"/><button className="secondary" onClick={addMem}>添加</button></div></div>
    <div className="admin-block"><strong>现有分类</strong>{categories.map(c=><div className="manage-row" key={c.id}><span>{c.name}<small>{c.type==='expense_category1'?'支出分类':c.type==='income_category'?'收入分类':'旧数据'}</small></span><button className="delete-link" onClick={async()=>{try{await api.deleteCategory(c.id);await onSync();onToast('已删除')}catch(e){onToast(e instanceof Error?e.message:'删除失败')}}}>删除</button></div>)}</div>
    <div className="admin-block"><strong>成员</strong>{members.map(m=><div className="manage-row" key={m.id}><span>{m.name}</span><button className="delete-link" onClick={async()=>{try{await api.deleteMember(m.id);await onSync();onToast('已删除')}catch(e){onToast(e instanceof Error?e.message:'删除失败')}}}>删除</button></div>)}</div>
    <div className="admin-block"><strong>备份</strong><a className="secondary link-btn" href="/api/backup">下载 SQLite 备份</a></div>
  </section>
}
