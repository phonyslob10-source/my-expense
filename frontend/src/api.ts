import type { Category, Member, Transaction } from './types'
import { uid } from './utils'

const API = '/api'
const DEVICE_KEY = 'expense-device-id'
const ADMIN_KEY = 'expense-admin-token'

export function deviceId() {
  let id = localStorage.getItem(DEVICE_KEY)
  if (!id) { id = uid(); localStorage.setItem(DEVICE_KEY, id) }
  return id
}
export function adminToken() { return localStorage.getItem(ADMIN_KEY) }
export function setAdminToken(token: string) { localStorage.setItem(ADMIN_KEY, token) }
export function clearAdminToken() { localStorage.removeItem(ADMIN_KEY) }

function adminExpiredMessage() {
  clearAdminToken()
  return '管理员登录已失效，请重新进入管理员模式'
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  headers.set('X-Device-ID', deviceId())
  const token = adminToken(); if (token) headers.set('Authorization', `Bearer ${token}`)
  const res = await fetch(`${API}${path}`, { ...init, headers })
  if (!res.ok) {
    let detail=`HTTP ${res.status}`
    try { detail=(await res.json()).detail ?? detail } catch {}
    if (res.status === 401 && token) detail = adminExpiredMessage()
    throw new Error(detail)
  }
  return res.json()
}

export async function getTransactions(params: URLSearchParams = new URLSearchParams()) { return request<Transaction[]>(`/transactions?${params.toString()}`) }
export async function createTransaction(tx: Partial<Transaction>) { return request<Transaction>('/transactions',{method:'POST',body:JSON.stringify(tx)}) }
export async function updateTransaction(id:string,tx:Partial<Transaction>) { return request<Transaction>(`/transactions/${id}`,{method:'PUT',body:JSON.stringify({...tx,id})}) }
export async function deleteTransaction(id:string) { return request<Transaction>(`/transactions/${id}`,{method:'DELETE'}) }
export async function getCategories() { return request<Category[]>('/categories') }
export async function getMembers() { return request<Member[]>('/members') }
export async function loginAdmin(password:string) { const result=await request<{access_token:string}>('/admin/login',{method:'POST',body:JSON.stringify({password})}); setAdminToken(result.access_token) }
export async function addCategory(body:Partial<Category>) { return request<Category>('/categories',{method:'POST',body:JSON.stringify(body)}) }
export async function updateCategory(id:string,body:Partial<Category>) { return request<Category>(`/categories/${id}`,{method:'PUT',body:JSON.stringify({...body,id})}) }
export async function deleteCategory(id:string) { return request<{ok:boolean}>(`/categories/${id}`,{method:'DELETE'}) }
export async function addMember(body:Partial<Member>) { return request<Member>('/members',{method:'POST',body:JSON.stringify(body)}) }
export async function updateMember(id:string,body:Partial<Member>) { return request<Member>(`/members/${id}`,{method:'PUT',body:JSON.stringify({...body,id})}) }
export async function deleteMember(id:string) { return request<{ok:boolean}>(`/members/${id}`,{method:'DELETE'}) }
export async function syncTransactions(changes:Transaction[]) { return request<{server_time:string,accepted:Transaction[],transactions:Transaction[],categories:Category[],members:Member[]}>('/sync',{method:'POST',body:JSON.stringify({device_id:deviceId(),changes})}) }

export async function exportCsv() {
  const token=adminToken()
  const headers=new Headers({'X-Device-ID':deviceId()}); if(token) headers.set('Authorization',`Bearer ${token}`)
  const res=await fetch(`${API}/export/csv`,{headers})
  if(!res.ok){
    if(res.status===401&&token) throw new Error(adminExpiredMessage())
    throw new Error(`导出失败 HTTP ${res.status}`)
  }
  return res.blob()
}

export async function importCsv(text:string) {
  const token=adminToken()
  const headers=new Headers({'Content-Type':'text/csv','X-Device-ID':deviceId()}); if(token) headers.set('Authorization',`Bearer ${token}`)
  const res=await fetch(`${API}/import/csv`,{method:'POST',headers,body:text})
  if(!res.ok){
    let detail=`HTTP ${res.status}`
    try{detail=(await res.json()).detail??detail}catch{}
    if(res.status===401&&token) detail=adminExpiredMessage()
    throw new Error(detail)
  }
  return res.json() as Promise<{imported:number,errors:string[]}>
}
