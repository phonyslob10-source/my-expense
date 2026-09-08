from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("EXPENSE_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "expense.db"
PORT = int(os.getenv("EXPENSE_PORT", "3000"))
HOST = os.getenv("EXPENSE_HOST", "0.0.0.0")
APP_NAME = os.getenv("EXPENSE_APP_NAME", "我的记账")
ADMIN_PASSWORD = os.getenv("EXPENSE_ADMIN_PASSWORD", "change-me")
