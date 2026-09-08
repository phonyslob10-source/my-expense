from __future__ import annotations

import io
import json
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook

from .config import APP_NAME, HOST, PORT, DATA_DIR, DB_PATH
from .db import get_conn, init_db, utc_now
from .schemas import (
    AdminLogin, CategoryIn, CategoryOut, MemberIn, MemberOut,
    SyncRequest, TransactionIn, TransactionOut,
)
from .security import login, require_admin

init_db()
app = FastAPI(title=APP_NAME, version="1.0.0")

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


def row_tx(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "project": row["project"], "date": row["date"],
        "member": row["member"], "type": row["type"], "category1": row["category1"],
        "category2": row["category2"], "amount_cents": row["amount_cents"], "note": row["note"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "device_id": row["device_id"], "is_deleted": bool(row["is_deleted"]),
    }


def row_category(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "type": row["type"], "name": row["name"],
            "sort_order": row["sort_order"], "is_active": bool(row["is_active"]),
            "updated_at": row["updated_at"]}


def row_member(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "name": row["name"], "sort_order": row["sort_order"],
            "is_active": bool(row["is_active"]), "updated_at": row["updated_at"]}


def clean_iso(ts: Optional[str]) -> str:
    if not ts:
        return utc_now()
    return ts


def upsert_transaction(conn, payload: TransactionIn, fallback_device: str) -> dict:
    txid = payload.id or str(uuid.uuid4())
    now = utc_now()
    incoming_updated = clean_iso(payload.updated_at)
    existing = conn.execute("SELECT * FROM transactions WHERE id=?", (txid,)).fetchone()
    if existing and existing["updated_at"] > incoming_updated:
        return row_tx(existing)

    created_at = payload.created_at or (existing["created_at"] if existing else now)
    device_id = payload.device_id or fallback_device
    conn.execute(
        """INSERT INTO transactions
        (id,project,date,member,type,category1,category2,amount_cents,note,created_at,updated_at,device_id,is_deleted)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
        project=excluded.project,date=excluded.date,member=excluded.member,type=excluded.type,
        category1=excluded.category1,category2=excluded.category2,amount_cents=excluded.amount_cents,
        note=excluded.note,created_at=excluded.created_at,updated_at=excluded.updated_at,
        device_id=excluded.device_id,is_deleted=excluded.is_deleted""",
        (txid, payload.project, payload.date, payload.member, payload.type, payload.category1,
         payload.category2, payload.amount_cents, payload.note, created_at, incoming_updated,
         device_id, 1 if payload.is_deleted else 0),
    )
    row = conn.execute("SELECT * FROM transactions WHERE id=?", (txid,)).fetchone()
    return row_tx(row)


@app.get("/api/health")
def health():
    return {"ok": True, "app": APP_NAME, "time": utc_now()}


@app.post("/api/admin/login")
def admin_login(body: AdminLogin):
    return {"access_token": login(body.password)}


@app.get("/api/transactions", response_model=list[TransactionOut])
def get_transactions(
    start: Optional[str] = None,
    end: Optional[str] = None,
    type: Optional[str] = None,
    category: Optional[str] = None,
    member: Optional[str] = None,
    q: Optional[str] = None,
):
    clauses = ["is_deleted=0"]
    args: list = []
    if start:
        clauses.append("date>=?"); args.append(start)
    if end:
        clauses.append("date<=?"); args.append(end)
    if type:
        clauses.append("type=?"); args.append(type)
    if category:
        clauses.append("category1=?"); args.append(category)
    if member:
        clauses.append("member=?"); args.append(member)
    if q:
        clauses.append("(project LIKE ? OR note LIKE ?)"); args.extend([f"%{q}%", f"%{q}%"])
    sql = "SELECT * FROM transactions WHERE " + " AND ".join(clauses) + " ORDER BY date DESC, created_at DESC"
    with get_conn() as conn:
        return [row_tx(r) for r in conn.execute(sql, args).fetchall()]


@app.post("/api/transactions", response_model=TransactionOut)
def create_transaction(payload: TransactionIn, x_device_id: Optional[str] = Header(default=None)):
    with get_conn() as conn:
        if payload.id is None:
            payload.id = str(uuid.uuid4())
        if payload.device_id is None:
            payload.device_id = x_device_id or "unknown"
        return upsert_transaction(conn, payload, x_device_id or "unknown")


@app.put("/api/transactions/{tx_id}", response_model=TransactionOut)
def update_transaction(tx_id: str, payload: TransactionIn, x_device_id: Optional[str] = Header(default=None), authorization: Optional[str] = Header(default=None)):
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "记录不存在")
        is_admin = False
        if authorization:
            try:
                require_admin(authorization)
                is_admin = True
            except HTTPException:
                is_admin = False
        if not is_admin and existing["device_id"] != (x_device_id or ""):
            raise HTTPException(403, "只能修改自己设备创建的记录")
        payload.id = tx_id
        payload.device_id = existing["device_id"]
        return upsert_transaction(conn, payload, x_device_id or existing["device_id"])


@app.delete("/api/transactions/{tx_id}", response_model=TransactionOut)
def delete_transaction(tx_id: str, x_device_id: Optional[str] = Header(default=None), authorization: Optional[str] = Header(default=None)):
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "记录不存在")
        is_admin = False
        if authorization:
            try:
                require_admin(authorization)
                is_admin = True
            except HTTPException:
                is_admin = False
        if not is_admin and existing["device_id"] != (x_device_id or ""):
            raise HTTPException(403, "只能删除自己设备创建的记录")
        now = utc_now()
        conn.execute("UPDATE transactions SET is_deleted=1, updated_at=? WHERE id=?", (now, tx_id))
        return row_tx(conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone())


@app.get("/api/summary")
def summary(period: str = Query("month"), date_value: str = Query(..., alias="date"), start: Optional[str] = None, end: Optional[str] = None):
    if period == "custom":
        if not start or not end:
            raise HTTPException(400, "自定义区间需要 start/end")
        s, e = start, end
    elif period == "day":
        s = e = date_value
    elif period == "week":
        d = datetime.strptime(date_value, "%Y-%m-%d").date()
        s = (d - timedelta(days=d.weekday())).isoformat()
        e = (d + timedelta(days=6-d.weekday())).isoformat()
    elif period == "year":
        s, e = f"{date_value[:4]}-01-01", f"{date_value[:4]}-12-31"
    else:
        s, e = f"{date_value[:7]}-01", None
        d = datetime.strptime(s, "%Y-%m-%d").date()
        next_month = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        e = (next_month - timedelta(days=1)).isoformat()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM transactions WHERE is_deleted=0 AND date BETWEEN ? AND ? ORDER BY date", (s, e)).fetchall()
    totals = {"expense": 0, "income": 0}
    by_category1: dict[str, int] = {}
    by_category2: dict[str, int] = {}
    by_income_category: dict[str, int] = {}
    by_member: dict[str, dict[str, int]] = {}
    trend: dict[str, dict[str, int]] = {}
    for r in rows:
        typ = r["type"]
        amt = r["amount_cents"]
        totals[typ] += amt
        if typ == "expense":
            by_category1[r["category1"] or "未分类"] = by_category1.get(r["category1"] or "未分类", 0) + amt
            by_category2[r["category2"] or "未分类"] = by_category2.get(r["category2"] or "未分类", 0) + amt
        else:
            by_income_category[r["category1"] or "未分类"] = by_income_category.get(r["category1"] or "未分类", 0) + amt
        m = r["member"]
        by_member.setdefault(m, {"expense": 0, "income": 0})[typ] += amt
        bucket = r["date"] if period in ("day", "custom") else (r["date"][:7] if period in ("month", "year") else r["date"])
        trend.setdefault(bucket, {"expense": 0, "income": 0})[typ] += amt
    return {
        "range": {"start": s, "end": e}, "totals": totals,
        "net": totals["income"] - totals["expense"], "by_category1": by_category1,
        "by_category2": by_category2, "by_income_category": by_income_category,
        "by_member": by_member, "trend": trend,
    }


@app.get("/api/categories", response_model=list[CategoryOut])
def categories():
    with get_conn() as conn:
        return [row_category(r) for r in conn.execute("SELECT * FROM categories WHERE is_active=1 ORDER BY type, sort_order, name").fetchall()]


@app.post("/api/categories", response_model=CategoryOut)
def add_category(body: CategoryIn, _=Depends(require_admin)):
    cid = body.id or str(uuid.uuid4()); now = utc_now()
    with get_conn() as conn:
        conn.execute("INSERT INTO categories(id,type,name,sort_order,is_active,updated_at) VALUES (?,?,?,?,?,?)", (cid, body.type, body.name, body.sort_order, int(body.is_active), now))
        return row_category(conn.execute("SELECT * FROM categories WHERE id=?", (cid,)).fetchone())


@app.put("/api/categories/{cid}", response_model=CategoryOut)
def update_category(cid: str, body: CategoryIn, _=Depends(require_admin)):
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM categories WHERE id=?", (cid,)).fetchone(): raise HTTPException(404, "分类不存在")
        now = utc_now(); conn.execute("UPDATE categories SET type=?,name=?,sort_order=?,is_active=?,updated_at=? WHERE id=?", (body.type, body.name, body.sort_order, int(body.is_active), now, cid))
        return row_category(conn.execute("SELECT * FROM categories WHERE id=?", (cid,)).fetchone())


@app.delete("/api/categories/{cid}")
def delete_category(cid: str, _=Depends(require_admin)):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM categories WHERE id=?", (cid,)).fetchone()
        if not row: raise HTTPException(404, "分类不存在")
        usage = conn.execute("SELECT COUNT(*) FROM transactions WHERE is_deleted=0 AND (category1=? OR category2=?)", (row["name"], row["name"])).fetchone()[0]
        if usage:
            raise HTTPException(409, f"该分类已被 {usage} 条记录使用，请先迁移后再删除")
        conn.execute("UPDATE categories SET is_active=0, updated_at=? WHERE id=?", (utc_now(), cid))
        return {"ok": True}


@app.get("/api/members", response_model=list[MemberOut])
def members():
    with get_conn() as conn:
        return [row_member(r) for r in conn.execute("SELECT * FROM members WHERE is_active=1 ORDER BY sort_order, name").fetchall()]


@app.post("/api/members", response_model=MemberOut)
def add_member(body: MemberIn, _=Depends(require_admin)):
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM members WHERE is_active=1").fetchone()[0]
        if count >= 5: raise HTTPException(400, "最多 5 名成员")
        mid = body.id or str(uuid.uuid4()); now = utc_now()
        conn.execute("INSERT INTO members(id,name,sort_order,is_active,updated_at) VALUES (?,?,?,?,?)", (mid, body.name, body.sort_order, 1, now))
        return row_member(conn.execute("SELECT * FROM members WHERE id=?", (mid,)).fetchone())


@app.put("/api/members/{mid}", response_model=MemberOut)
def update_member(mid: str, body: MemberIn, _=Depends(require_admin)):
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM members WHERE id=?", (mid,)).fetchone(): raise HTTPException(404, "成员不存在")
        now = utc_now(); conn.execute("UPDATE members SET name=?,sort_order=?,is_active=?,updated_at=? WHERE id=?", (body.name, body.sort_order, int(body.is_active), now, mid))
        return row_member(conn.execute("SELECT * FROM members WHERE id=?", (mid,)).fetchone())


@app.delete("/api/members/{mid}")
def delete_member(mid: str, _=Depends(require_admin)):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM members WHERE id=?", (mid,)).fetchone()
        if not row: raise HTTPException(404, "成员不存在")
        usage = conn.execute("SELECT COUNT(*) FROM transactions WHERE is_deleted=0 AND member=?", (row["name"],)).fetchone()[0]
        if usage:
            raise HTTPException(409, f"该成员已被 {usage} 条记录使用，不能直接删除")
        conn.execute("UPDATE members SET is_active=0, updated_at=? WHERE id=?", (utc_now(), mid))
        return {"ok": True}


@app.post("/api/sync")
def sync(body: SyncRequest):
    with get_conn() as conn:
        accepted = []
        for tx in body.changes:
            accepted.append(upsert_transaction(conn, tx, body.device_id))
        transactions = [row_tx(r) for r in conn.execute("SELECT * FROM transactions ORDER BY date DESC, created_at DESC").fetchall()]
        cats = [row_category(r) for r in conn.execute("SELECT * FROM categories WHERE is_active=1 ORDER BY type,sort_order,name").fetchall()]
        mems = [row_member(r) for r in conn.execute("SELECT * FROM members WHERE is_active=1 ORDER BY sort_order,name").fetchall()]
        return {"server_time": utc_now(), "accepted": accepted, "transactions": transactions, "categories": cats, "members": mems}


def iter_export_rows(rows):
    yield ["id","project","date","member","type","category1","category2","amount","note","created_at","updated_at","device_id"]
    for r in rows:
        yield [r["id"], r["project"], r["date"], r["member"], r["type"], r["category1"] or "", r["category2"] or "", f'{r["amount_cents"]/100:.2f}', r["note"] or "", r["created_at"], r["updated_at"], r["device_id"]]


@app.get("/api/export/csv")
def export_csv(start: Optional[str] = None, end: Optional[str] = None, _=Depends(require_admin)):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM transactions WHERE is_deleted=0 AND (? IS NULL OR date>=?) AND (? IS NULL OR date<=?) ORDER BY date", (start, start, end, end)).fetchall()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerows(iter_export_rows(rows))
    return StreamingResponse(iter([output.getvalue().encode("utf-8-sig")]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=expense_export.csv"})


@app.get("/api/export/xlsx")
def export_xlsx(start: Optional[str] = None, end: Optional[str] = None, _=Depends(require_admin)):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM transactions WHERE is_deleted=0 AND (? IS NULL OR date>=?) AND (? IS NULL OR date<=?) ORDER BY date", (start, start, end, end)).fetchall()
    wb = Workbook(); ws = wb.active; ws.title = "账单"
    headers = ["id","project","date","member","type","category1","category2","amount","note","created_at","updated_at","device_id"]
    ws.append(headers)
    for row in iter_export_rows(rows): ws.append(row)
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=expense_export.xlsx"})


# Notion import is intentionally disabled in this personal build.


@app.get("/api/backup")
def backup(_=Depends(require_admin)):
    return FileResponse(DB_PATH, media_type="application/octet-stream", filename="expense_backup.db")


@app.get("/{path:path}")
def spa(path: str):
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "前端尚未构建，请先运行 npm run build"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
