"""认证与双维识别历史 API（本分支仅教室情感双维编码）。"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.schemas import AuthUserOut, HistoryItem, LoginRequest
from core.auth import AuthUser, get_auth_store, require_user
from core import history as history_store

logger = logging.getLogger(__name__)

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent
JOBS_DIR = BASE_DIR / "storage" / "jobs"
STORAGE_DIR = BASE_DIR / "storage"

auth_store = get_auth_store(STORAGE_DIR)


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@router.post("/auth/login", response_model=AuthUserOut)
async def auth_login(payload: LoginRequest, request: Request, response: Response):
    user = auth_store.login(payload.username, payload.password, client_ip=_client_ip(request))
    token = auth_store.create_token(user)
    auth_store.set_auth_cookie(response, token)
    return AuthUserOut(user_id=user.user_id, username=user.username)


@router.post("/auth/logout")
async def auth_logout(response: Response):
    auth_store.clear_auth_cookie(response)
    return {"ok": True}


@router.get("/auth/me", response_model=AuthUserOut)
async def auth_me(user: AuthUser = Depends(require_user)):
    return AuthUserOut(user_id=user.user_id, username=user.username)


@router.get("/history", response_model=list[HistoryItem])
async def get_history(user: AuthUser = Depends(require_user)):
    items = history_store.list_history(JOBS_DIR, user.user_id)
    return [i for i in items if i.job_type == "dual"]


@router.delete("/history/{job_id}")
async def history_delete(job_id: str, user: AuthUser = Depends(require_user)):
    try:
        info = history_store.delete_job(JOBS_DIR, job_id, user.user_id)
    except KeyError:
        raise HTTPException(404, "Job not found")
    except PermissionError:
        raise HTTPException(403, "无权删除该识别记录")
    return info
