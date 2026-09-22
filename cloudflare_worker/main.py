from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import mimetypes
import re
import time
import uuid
from datetime import date as Date, datetime, timedelta
from typing import Any, Optional
from urllib.parse import quote

from fastapi import Body, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from workers import asgi

APP_VERSION = "2.0.0-cloudflare"
TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60

app = FastAPI(title="我的记账", version=APP_VERSION)


class TransactionIn(BaseModel):
    id: Optional[str] = None
    project: str = Field(min_length=1, max_length=200)
    date: str
    member: str = Field(min_length=1, max_length=100)
    type: str = "expense"
    category1: Optional[str] = None
    category2: Optional[str] = None
    amount_cents: int = Field(ge=0)
    note: Optional[str] = Field(default=None, max_length=1000)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    device_id: Optional[str] = None
    is_deleted: bool = False


class CategoryIn(BaseModel):
    id: Optional[str] = None
    type: str
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0
    is_active: bool = True


class MemberIn(BaseModel):
    id: Optional[str] = None
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0
    is_active: bool = True


class SyncRequest(BaseModel):
    device_id: str
    changes: list[TransactionIn] = []


class AdminLogin(BaseModel):
    password: str


def env_of(request: Request) -> Any:
    return request.scope["env"]


def setting(request: Request, name: str, default: str = "") -> str:
    env = env_of(request)
    value = getattr(env, name, None)
    return str(value) if value is not None else default


def db_of(request: Request) -> Any:
    db = getattr(env_of(request), "DB", None)
    if db is None:
        raise HTTPException(500, "D1 数据库绑定未配置")
    return db


async def raw_rows(db: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    stmt = db.prepare(sql)
    if params:
        stmt = stmt.bind(*params)
    raw = await stmt.raw(columnNames=True)
    rows = list(raw)
    if not rows:
        return []
    names = [str(v) for v in list(rows[0])]
    return [dict(zip(names, list(row))) for row in rows[1:]]


async def first_row(db: Any, sql: str, params: tuple[Any, ...] = ()) -> Optional[dict[str, Any]]:
    rows = await raw_rows(db, sql, params)
    return rows[0] if rows else None


async def run_sql(db: Any, sql: str, params: tuple[Any, ...] = ()) -> Any:
    stmt = db.prepare(sql)
    if params:
        stmt = stmt.bind(*params)
    return await stmt.run()


def row_tx(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project": row["project"],
        "date": row["date"],
        "member": row["member"],
        "type": row["type"],
        "category1": row.get("category1"),
        "category2": row.get("category2"),
        "amount_cents": int(row["amount_cents"]),
        "note": row.get("note"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "device_id": row["device_id"],
        "is_deleted": bool(row["is_deleted"]),
    }


def row_category(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "type": row["type"],
        "name": row["name"],
        "sort_order": int(row["sort_order"]),
        "is_active": bool(row["is_active"]),
        "updated_at": row["updated_at"],
    }


def row_member(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "sort_order": int(row["sort_order"]),
        "is_active": bool(row["is_active"]),
        "updated_at": row["updated_at"],
    }


def utc_now() -> str:
    return datetime.now().astimezone().astimezone().isoformat(timespec="milliseconds").replace("+00:00", "Z")


def token_signing_secret(request: Request) -> str:
    return setting(request, "ADMIN_TOKEN_SECRET", "CHANGE_ME_BEFORE_DEPLOYMENT")


def make_admin_token(request: Request) -> str:
    now = int(time.time())
    payload = str(now).encode()
    sig = hmac.new(token_signing_secret(request).encode(), payload, hashlib.sha256).digest()
    return f"{now}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"


def verify_admin(request: Request, authorization: Optional[str] = None) -> str:
    auth = authorization or request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(401, "需要管理员权限")
    token = auth.split(" ", 1)[1].strip()
    try:
        timestamp_text, signature = token.split(".", 1)
        timestamp = int(timestamp_text)
    except Exception:
        raise HTTPException(401, "管理员凭证无效")
    if timestamp < int(time.time()) - TOKEN_TTL_SECONDS or timestamp > int(time.time()) + 60:
        raise HTTPException(401, "管理员登录已过期，请重新进入管理员模式")
    expected = hmac.new(
        token_signing_secret(request).encode(),
        timestamp_text.encode(),
        hashlib.sha256,
    ).digest()
    actual = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
    if not hmac.compare_digest(actual, expected):
        raise HTTPException(401, "管理员凭证无效")
    return token


async def upsert_transaction(db: Any, payload: TransactionIn, fallback_device: str) -> dict[str, Any]:
    txid = payload.id or str(uuid.uuid4())
    incoming = payload.updated_at or utc_now()
    existing = await first_row(db, "SELECT * FROM transactions WHERE id = ? LIMIT 1", (txid,))
    if existing and str(existing["updated_at"]) > incoming:
        return row_tx(existing)

    created = payload.created_at or (existing["created_at"] if existing else utc_now())
    device = payload.device_id or fallback_device
    await run_sql(
        db,
        """
        INSERT INTO transactions(
            id, project, date, member, type, category1, category2,
            amount_cents, note, created_at, updated_at, device_id, is_deleted
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            project=excluded.project,
            date=excluded.date,
            member=excluded.member,
            type=excluded.type,
            category1=excluded.category1,
            category2=excluded.category2,
            amount_cents=excluded.amount_cents,
            note=excluded.note,
            created_at=excluded.created_at,
            updated_at=excluded.updated_at,
            device_id=excluded.device_id,
            is_deleted=excluded.is_deleted
        """,
        (
            txid, payload.project, payload.date, payload.member, payload.type,
            payload.category1, payload.category2, payload.amount_cents,
            payload.note, created, incoming, device, int(payload.is_deleted)
        ),
    )
    saved = await first_row(db, "SELECT * FROM transactions WHERE id = ? LIMIT 1", (txid,))
    if not saved:
        raise HTTPException(500, "保存记录失败")
    return row_tx(saved)


@app.get("/api/health")
async def health(request: Request):
    return {"ok": True, "app": setting(request, "APP_NAME", "我的记账"), "time": utc_now()}


@app.post("/api/admin/login")
async def admin_login(request: Request, body: AdminLogin):
    configured = setting(request, "ADMIN_PASSWORD")
    if not configured:
        raise HTTPException(503, "管理员密码尚未配置")
    if not hmac.compare_digest(body.password, configured):
        raise HTTPException(401, "管理员密码错误")
    return {"access_token": make_admin_token(request)}


@app.get("/api/transactions", response_model=list[dict])
async def get_transactions(
    request: Request,
    start: Optional[str] = None,
    end: Optional[str] = None,
    type: Optional[str] = None,
    category: Optional[str] = None,
    member: Optional[str] = None,
    q: Optional[str] = None,
):
    db = db_of(request)
    clauses = ["is_deleted = 0"]
    args: list[Any] = []
    if start:
        clauses.append("date >= ?")
        args.append(start)
    if end:
        clauses.append("date <= ?")
        args.append(end)
    if type:
        clauses.append("type = ?")
        args.append(type)
    if category:
        clauses.append("category1 = ?")
        args.append(category)
    if member:
        clauses.append("member = ?")
        args.append(member)
    if q:
        clauses.append("(project LIKE ? OR note LIKE ?)")
        args.extend([f"%{q}%", f"%{q}%"])
    rows = await raw_rows(
        db,
        "SELECT * FROM transactions WHERE " + " AND ".join(clauses) + " ORDER BY date DESC, created_at DESC",
        tuple(args),
    )
    return [row_tx(r) for r in rows]


@app.post("/api/transactions", response_model=dict)
async def create_transaction(
    request: Request,
    payload: TransactionIn,
    x_device_id: Optional[str] = Header(default=None),
):
    payload.device_id = payload.device_id or x_device_id or "unknown"
    return await upsert_transaction(db_of(request), payload, x_device_id or "unknown")


@app.put("/api/transactions/{tx_id}", response_model=dict)
async def update_transaction(
    request: Request,
    tx_id: str,
    payload: TransactionIn,
    x_device_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    db = db_of(request)
    existing = await first_row(db, "SELECT * FROM transactions WHERE id = ? LIMIT 1", (tx_id,))
    if not existing:
        raise HTTPException(404, "记录不存在")
    admin = False
    try:
        verify_admin(request, authorization)
        admin = True
    except HTTPException:
        pass
    if not admin and existing["device_id"] != (x_device_id or ""):
        raise HTTPException(403, "只能修改自己设备创建的记录")
    payload.id = tx_id
    payload.device_id = existing["device_id"]
    return await upsert_transaction(db, payload, x_device_id or existing["device_id"])


@app.delete("/api/transactions/{tx_id}", response_model=dict)
async def delete_transaction(
    request: Request,
    tx_id: str,
    x_device_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    db = db_of(request)
    existing = await first_row(db, "SELECT * FROM transactions WHERE id = ? LIMIT 1", (tx_id,))
    if not existing:
        raise HTTPException(404, "记录不存在")
    admin = False
    try:
        verify_admin(request, authorization)
        admin = True
    except HTTPException:
        pass
    if not admin and existing["device_id"] != (x_device_id or ""):
        raise HTTPException(403, "只能删除自己设备创建的记录")
    await run_sql(db, "UPDATE transactions SET is_deleted = 1, updated_at = ? WHERE id = ?", (utc_now(), tx_id))
    saved = await first_row(db, "SELECT * FROM transactions WHERE id = ? LIMIT 1", (tx_id,))
    return row_tx(saved or existing)


@app.get("/api/summary")
async def summary(
    request: Request,
    period: str = Query("month"),
    date_value: str = Query(..., alias="date"),
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    if period == "custom":
        if not start or not end:
            raise HTTPException(400, "自定义区间需要 start/end")
        s, e = start, end
    elif period == "day":
        s = e = date_value
    elif period == "week":
        d = datetime.strptime(date_value, "%Y-%m-%d").date()
        s = (d - timedelta(days=d.weekday())).isoformat()
        e = (d + timedelta(days=6 - d.weekday())).isoformat()
    elif period == "year":
        s, e = f"{date_value[:4]}-01-01", f"{date_value[:4]}-12-31"
    else:
        s = f"{date_value[:7]}-01"
        d = datetime.strptime(s, "%Y-%m-%d").date()
        n = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        e = (n - timedelta(days=1)).isoformat()

    rows = await raw_rows(
        db_of(request),
        "SELECT * FROM transactions WHERE is_deleted = 0 AND date BETWEEN ? AND ? ORDER BY date",
        (s, e),
    )
    totals = {"expense": 0, "income": 0}
    by_category1: dict[str, int] = {}
    by_category2: dict[str, int] = {}
    by_income_category: dict[str, int] = {}
    by_member: dict[str, dict[str, int]] = {}
    trend: dict[str, dict[str, int]] = {}

    for row in rows:
        typ = str(row["type"])
        amount = int(row["amount_cents"])
        totals[typ] += amount
        if typ == "expense":
            k = row["category1"] or "未分类"
            by_category1[k] = by_category1.get(k, 0) + amount
            k = row["category2"] or "未分类"
            by_category2[k] = by_category2.get(k, 0) + amount
        else:
            k = row["category1"] or "未分类"
            by_income_category[k] = by_income_category.get(k, 0) + amount
        member = row["member"]
        by_member.setdefault(member, {"expense": 0, "income": 0})[typ] += amount
        bucket = row["date"] if period in ("day", "custom", "week") else str(row["date"])[:7]
        trend.setdefault(bucket, {"expense": 0, "income": 0})[typ] += amount

    return {
        "range": {"start": s, "end": e},
        "totals": totals,
        "net": totals["income"] - totals["expense"],
        "by_category1": by_category1,
        "by_category2": by_category2,
        "by_income_category": by_income_category,
        "by_member": by_member,
        "trend": trend,
    }


@app.get("/api/categories", response_model=list[dict])
async def categories(request: Request):
    rows = await raw_rows(
        db_of(request),
        "SELECT * FROM categories WHERE is_active = 1 ORDER BY type, sort_order, name",
    )
    return [row_category(r) for r in rows]


@app.post("/api/categories", response_model=dict)
async def add_category(request: Request, body: CategoryIn, authorization: Optional[str] = Header(default=None)):
    verify_admin(request, authorization)
    cid = body.id or str(uuid.uuid4())
    await run_sql(
        db_of(request),
        "INSERT INTO categories(id,type,name,sort_order,is_active,updated_at) VALUES (?,?,?,?,?,?)",
        (cid, body.type, body.name, body.sort_order, int(body.is_active), utc_now()),
    )
    row = await first_row(db_of(request), "SELECT * FROM categories WHERE id = ?", (cid,))
    return row_category(row)


@app.put("/api/categories/{cid}", response_model=dict)
async def update_category(request: Request, cid: str, body: CategoryIn, authorization: Optional[str] = Header(default=None)):
    verify_admin(request, authorization)
    db = db_of(request)
    if not await first_row(db, "SELECT 1 AS ok FROM categories WHERE id = ?", (cid,)):
        raise HTTPException(404, "分类不存在")
    await run_sql(
        db,
        "UPDATE categories SET type=?,name=?,sort_order=?,is_active=?,updated_at=? WHERE id=?",
        (body.type, body.name, body.sort_order, int(body.is_active), utc_now(), cid),
    )
    return row_category(await first_row(db, "SELECT * FROM categories WHERE id = ?", (cid,)))


@app.delete("/api/categories/{cid}")
async def delete_category(request: Request, cid: str, authorization: Optional[str] = Header(default=None)):
    verify_admin(request, authorization)
    db = db_of(request)
    row = await first_row(db, "SELECT * FROM categories WHERE id = ?", (cid,))
    if not row:
        raise HTTPException(404, "分类不存在")
    usage = await first_row(
        db,
        "SELECT COUNT(*) AS count FROM transactions WHERE is_deleted=0 AND (category1=? OR category2=?)",
        (row["name"], row["name"]),
    )
    if int(usage["count"]) > 0:
        raise HTTPException(409, f"该分类已被 {usage['count']} 条记录使用，请先迁移后再删除")
    await run_sql(db, "UPDATE categories SET is_active=0,updated_at=? WHERE id=?", (utc_now(), cid))
    return {"ok": True}


@app.get("/api/members", response_model=list[dict])
async def members(request: Request):
    rows = await raw_rows(db_of(request), "SELECT * FROM members WHERE is_active=1 ORDER BY sort_order,name")
    return [row_member(r) for r in rows]


@app.post("/api/members", response_model=dict)
async def add_member(request: Request, body: MemberIn, authorization: Optional[str] = Header(default=None)):
    verify_admin(request, authorization)
    db = db_of(request)
    count_row = await first_row(db, "SELECT COUNT(*) AS count FROM members WHERE is_active=1")
    if int(count_row["count"]) >= 5:
        raise HTTPException(400, "最多 5 名成员")
    mid = body.id or str(uuid.uuid4())
    await run_sql(
        db,
        "INSERT INTO members(id,name,sort_order,is_active,updated_at) VALUES (?,?,?,?,?)",
        (mid, body.name, body.sort_order, 1, utc_now()),
    )
    return row_member(await first_row(db, "SELECT * FROM members WHERE id=?", (mid,)))


@app.put("/api/members/{mid}", response_model=dict)
async def update_member(request: Request, mid: str, body: MemberIn, authorization: Optional[str] = Header(default=None)):
    verify_admin(request, authorization)
    db = db_of(request)
    if not await first_row(db, "SELECT 1 AS ok FROM members WHERE id=?", (mid,)):
        raise HTTPException(404, "成员不存在")
    await run_sql(
        db,
        "UPDATE members SET name=?,sort_order=?,is_active=?,updated_at=? WHERE id=?",
        (body.name, body.sort_order, int(body.is_active), utc_now(), mid),
    )
    return row_member(await first_row(db, "SELECT * FROM members WHERE id=?", (mid,)))


@app.delete("/api/members/{mid}")
async def delete_member(request: Request, mid: str, authorization: Optional[str] = Header(default=None)):
    verify_admin(request, authorization)
    db = db_of(request)
    row = await first_row(db, "SELECT * FROM members WHERE id=?", (mid,))
    if not row:
        raise HTTPException(404, "成员不存在")
    usage = await first_row(db, "SELECT COUNT(*) AS count FROM transactions WHERE is_deleted=0 AND member=?", (row["name"],))
    if int(usage["count"]) > 0:
        raise HTTPException(409, f"该成员已被 {usage['count']} 条记录使用，不能直接删除")
    await run_sql(db, "UPDATE members SET is_active=0,updated_at=? WHERE id=?", (utc_now(), mid))
    return {"ok": True}


@app.post("/api/sync")
async def sync(request: Request, body: SyncRequest):
    db = db_of(request)
    for tx in body.changes:
        await upsert_transaction(db, tx, body.device_id)
    transactions = await raw_rows(db, "SELECT * FROM transactions ORDER BY date DESC, created_at DESC")
    cats = await raw_rows(db, "SELECT * FROM categories WHERE is_active=1 ORDER BY type,sort_order,name")
    mems = await raw_rows(db, "SELECT * FROM members WHERE is_active=1 ORDER BY sort_order,name")
    return {
        "server_time": utc_now(),
        "accepted": [row_tx(await first_row(db, "SELECT * FROM transactions WHERE id=?", (tx.id,))) for tx in body.changes if tx.id],
        "transactions": [row_tx(r) for r in transactions],
        "categories": [row_category(r) for r in cats],
        "members": [row_member(r) for r in mems],
    }


CN_HEADERS = ["项目", "分类", "分类2", "年份函数", "日期", "月份函数", "账户", "金额"]


def clean_import_value(value: str) -> str:
    return re.sub(r"\s*\(https?://[^)]*\)", "", (value or "").strip()).strip()


def parse_amount(value: str) -> int:
    cleaned = (value or "").strip().replace(",", "").replace("¥", "").replace("￥", "")
    return int(round(float(cleaned) * 100))


def parse_import_date(value: str) -> Optional[str]:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


async def infer_type(db: Any, category: str) -> str:
    row = await first_row(
        db,
        "SELECT type FROM categories WHERE is_active=1 AND name=? ORDER BY CASE type WHEN 'income_category' THEN 0 ELSE 1 END LIMIT 1",
        (category,),
    )
    return "income" if row and row["type"] == "income_category" else "expense"


async def import_rows(text: str, db: Any) -> tuple[int, list[str]]:
    reader = csv.DictReader(text.lstrip("\ufeff").splitlines())
    headers = {h.strip(): h for h in (reader.fieldnames or []) if h}
    is_cn = "项目" in headers and "日期" in headers and "账户" in headers
    required = ["项目", "日期", "账户", "金额"] if is_cn else ["project", "date", "member", "amount"]
    missing = [h for h in required if h not in headers]
    if missing:
        raise HTTPException(400, "缺少列：" + ", ".join(missing))

    count = 0
    errors: list[str] = []
    for line_no, row in enumerate(reader, 2):
        get = lambda key: row.get(headers.get(key, key), "") or ""
        project = clean_import_value(get("项目" if is_cn else "project"))
        member = clean_import_value(get("账户" if is_cn else "member"))
        cat1 = clean_import_value(get("分类" if is_cn else "category1"))
        cat2 = clean_import_value(get("分类2" if is_cn else "category2"))
        dt = parse_import_date(get("日期" if is_cn else "date"))
        if not project or not member or not dt:
            errors.append(f"第{line_no}行：项目、账户或日期无效")
            continue
        try:
            amount = parse_amount(get("金额" if is_cn else "amount"))
        except Exception:
            errors.append(f"第{line_no}行：金额无效")
            continue
        typ = get("type") if not is_cn else await infer_type(db, cat1)
        if typ not in ("expense", "income"):
            typ = await infer_type(db, cat1)
        txid = clean_import_value(get("id")) or str(uuid.uuid4())
        now = utc_now()
        created = clean_import_value(get("created_at")) or now
        await run_sql(
            db,
            """
            INSERT INTO transactions(
                id,project,date,member,type,category1,category2,amount_cents,note,
                created_at,updated_at,device_id,is_deleted
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)
            ON CONFLICT(id) DO UPDATE SET
                project=excluded.project,date=excluded.date,member=excluded.member,
                type=excluded.type,category1=excluded.category1,category2=excluded.category2,
                amount_cents=excluded.amount_cents,note=excluded.note,updated_at=excluded.updated_at
            """,
            (
                txid, project, dt, member, typ, cat1 or None, cat2 or None, amount,
                clean_import_value(get("note")), created, now, "import"
            ),
        )
        count += 1
    return count, errors


def export_rows(rows: list[dict[str, Any]]) -> list[list[Any]]:
    output = [CN_HEADERS]
    for row in rows:
        d = str(row["date"])
        output.append([
            row["project"],
            row.get("category1") or "",
            row.get("category2") or "",
            f"{d[:4]}年",
            d,
            d[:7],
            row["member"],
            f"¥{int(row['amount_cents']) / 100:.2f}",
        ])
    return output


@app.get("/api/export/csv")
async def export_csv(request: Request, start: Optional[str] = None, end: Optional[str] = None, authorization: Optional[str] = Header(default=None)):
    verify_admin(request, authorization)
    db = db_of(request)
    rows = await raw_rows(
        db,
        """
        SELECT * FROM transactions
        WHERE is_deleted=0
          AND (? IS NULL OR date>=?)
          AND (? IS NULL OR date<=?)
        ORDER BY date,created_at
        """,
        (start, start, end, end),
    )
    out = io.StringIO(newline="")
    csv.writer(out).writerows(export_rows(rows))
    return Response(
        content=out.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expense_export.csv"},
    )


@app.post("/api/import/csv")
async def import_csv(
    request: Request,
    body: str = Body(..., media_type="text/csv"),
    authorization: Optional[str] = Header(default=None),
):
    verify_admin(request, authorization)
    count, errors = await import_rows(body, db_of(request))
    return {"imported": count, "errors": errors}


@app.get("/api/backup")
async def backup(request: Request, authorization: Optional[str] = Header(default=None)):
    verify_admin(request, authorization)
    db = db_of(request)
    transactions = await raw_rows(db, "SELECT * FROM transactions ORDER BY date,created_at")
    categories = await raw_rows(db, "SELECT * FROM categories ORDER BY type,sort_order,name")
    members = await raw_rows(db, "SELECT * FROM members ORDER BY sort_order,name")
    payload = json.dumps(
        {"version": 1, "exported_at": utc_now(), "transactions": transactions, "categories": categories, "members": members},
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=expense_backup.json"},
    )


@app.get("/{path:path}")
async def frontend(path: str, request: Request):
    assets = getattr(env_of(request), "ASSETS", None)
    if assets is None:
        raise HTTPException(500, "静态资源绑定未配置")
    normalized = path or "index.html"
    url = "https://assets.local/" + quote(normalized, safe="/._-")
    asset_response = await assets.fetch(url)
    if asset_response.status == 404 and not normalized.startswith("api/"):
        asset_response = await assets.fetch("https://assets.local/index.html")
    body = await asset_response.bytes()
    content_type, _ = mimetypes.guess_type(normalized)
    if not content_type:
        content_type = asset_response.headers.get("content-type", "application/octet-stream")
    return Response(content=body, status_code=asset_response.status, media_type=content_type)


Default = asgi.entrypoint(app)
