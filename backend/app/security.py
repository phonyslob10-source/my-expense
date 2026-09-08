from __future__ import annotations

import secrets
from fastapi import Header, HTTPException
from .config import ADMIN_PASSWORD

_ACTIVE_TOKENS: set[str] = set()


def login(password: str) -> str:
    if not secrets.compare_digest(password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="管理员密码错误")
    token = secrets.token_urlsafe(32)
    _ACTIVE_TOKENS.add(token)
    return token


def require_admin(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="需要管理员权限")
    token = authorization.split(" ", 1)[1]
    if token not in _ACTIVE_TOKENS:
        raise HTTPException(status_code=401, detail="管理员凭证无效或已过期")
    return token
