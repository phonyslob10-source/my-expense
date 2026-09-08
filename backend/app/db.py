from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    date TEXT NOT NULL,
    member TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('expense','income')),
    category1 TEXT,
    category2 TEXT,
    amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    device_id TEXT NOT NULL,
    is_deleted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_tx_updated ON transactions(updated_at);
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cat_type ON categories(type, sort_order);
CREATE TABLE IF NOT EXISTS members (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);
"""

DEFAULT_CATEGORIES=[
    ("expense_category1","伙食支出",10),("expense_category1","生活支出",20),("expense_category1","水电气话费支出",30),("expense_category1","娱乐支出",40),("expense_category1","其他支出",50),("expense_category1","教育支出",60),("expense_category1","服装支出",70),
    ("income_category","工资",10),("income_category","奖金",20),("income_category","投资收益",30),("income_category","报销",40),("income_category","红包",50),("income_category","其他收入",60),
    ("expense_category2","FOR Jerry",10),("expense_category2","FOR Flora",20),
]
DEFAULT_MEMBERS=[("Jerry",10),("Flora",20)]

def init_db()->None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA); now=utc_now()
        for ctype,name,order_no in DEFAULT_CATEGORIES:
            exists=conn.execute("SELECT 1 FROM categories WHERE type=? AND name=? LIMIT 1",(ctype,name)).fetchone()
            if not exists:
                conn.execute("INSERT INTO categories(id,type,name,sort_order,is_active,updated_at) VALUES (lower(hex(randomblob(16))),?,?,?,?,?)",(ctype,name,order_no,1,now))
        if conn.execute("SELECT COUNT(*) FROM members WHERE is_active=1").fetchone()[0]==0:
            for name,order_no in DEFAULT_MEMBERS:
                if not conn.execute("SELECT 1 FROM members WHERE name=?",(name,)).fetchone():
                    conn.execute("INSERT INTO members(id,name,sort_order,is_active,updated_at) VALUES (lower(hex(randomblob(16))),?,?,?,?)",(name,order_no,1,now))
        conn.execute("UPDATE members SET is_active=0,updated_at=? WHERE name IN ('Flora & Jerry','Flora&Jerry') AND is_active=1",(now,))
        conn.execute("UPDATE categories SET is_active=0,updated_at=? WHERE type='beneficiary_category2' AND is_active=1",(now,))
        conn.execute("INSERT OR REPLACE INTO app_meta(key,value) VALUES('schema_version','3')",())
        conn.commit()

def utc_now()->str:
    from datetime import datetime,timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

@contextmanager
def get_conn():
    conn=sqlite3.connect(DB_PATH);conn.row_factory=sqlite3.Row
    try:
        yield conn;conn.commit()
    finally: conn.close()
