-- 我的记账 Cloudflare D1 schema
-- No historical data is migrated.

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
    type TEXT NOT NULL CHECK(type IN ('expense_category1','income_category','expense_category2')),
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

CREATE INDEX IF NOT EXISTS idx_member_sort ON members(sort_order, name);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO categories(id,type,name,sort_order,is_active,updated_at)
VALUES
('cf-exp-001','expense_category1','伙食支出',10,1,'2026-09-22T00:00:00.000Z'),
('cf-exp-002','expense_category1','生活支出',20,1,'2026-09-22T00:00:00.000Z'),
('cf-exp-003','expense_category1','水电气话费支出',30,1,'2026-09-22T00:00:00.000Z'),
('cf-exp-004','expense_category1','娱乐支出',40,1,'2026-09-22T00:00:00.000Z'),
('cf-exp-005','expense_category1','其他支出',50,1,'2026-09-22T00:00:00.000Z'),
('cf-exp-006','expense_category1','教育支出',60,1,'2026-09-22T00:00:00.000Z'),
('cf-exp-007','expense_category1','服装支出',70,1,'2026-09-22T00:00:00.000Z'),
('cf-inc-001','income_category','工资',10,1,'2026-09-22T00:00:00.000Z'),
('cf-inc-002','income_category','奖金',20,1,'2026-09-22T00:00:00.000Z'),
('cf-inc-003','income_category','投资收益',30,1,'2026-09-22T00:00:00.000Z'),
('cf-inc-004','income_category','报销',40,1,'2026-09-22T00:00:00.000Z'),
('cf-inc-005','income_category','红包',50,1,'2026-09-22T00:00:00.000Z'),
('cf-inc-006','income_category','其他收入',60,1,'2026-09-22T00:00:00.000Z'),
('cf-exp2-001','expense_category2','FOR Jerry',10,1,'2026-09-22T00:00:00.000Z'),
('cf-exp2-002','expense_category2','FOR Flora',20,1,'2026-09-22T00:00:00.000Z');

INSERT OR IGNORE INTO members(id,name,sort_order,is_active,updated_at)
VALUES
('cf-member-jerry','Jerry',10,1,'2026-09-22T00:00:00.000Z'),
('cf-member-flora','Flora',20,1,'2026-09-22T00:00:00.000Z');

INSERT OR REPLACE INTO app_meta(key,value)
VALUES('schema_version','1'),('created_for','cloudflare-d1');
