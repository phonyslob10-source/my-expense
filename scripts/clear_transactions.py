#!/usr/bin/env python3
"""清空记账交易记录，但保留分类、成员和其他应用配置。"""

from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "expense.db"


def main() -> int:
    if not DB_PATH.exists():
        print(f"错误：找不到数据库：{DB_PATH}")
        return 1

    print(f"数据库：{DB_PATH}")
    answer = input("确认删除 transactions 表中的全部记录？输入 YES 继续：").strip()
    if answer != "YES":
        print("已取消，没有修改数据库。")
        return 0

    backup_path = DB_PATH.with_name("expense.db.before-clear.bak")
    backup_path.write_bytes(DB_PATH.read_bytes())
    print(f"已创建备份：{backup_path}")

    conn = sqlite3.connect(DB_PATH)
    try:
        before = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        conn.execute("DELETE FROM transactions")
        conn.commit()
        conn.execute("VACUUM")
        after = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        categories = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        members = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
        print(f"交易记录：{before} -> {after}")
        print(f"分类记录：{categories}（保留）")
        print(f"成员记录：{members}（保留）")
        if after != 0:
            print("错误：transactions 未清空。")
            return 2
        print("完成。")
        return 0
    except Exception as exc:
        conn.rollback()
        print(f"错误：{exc}")
        print(f"原始备份仍保留在：{backup_path}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
