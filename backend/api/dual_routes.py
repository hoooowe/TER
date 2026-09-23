"""教学情绪-行为双维自动编码 API。"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from api.schemas import (
    AuthUserOut,
    DualCodingResult,
    DualCodingUnit,
    DualExportRequest,
    DualJobStatus,
    HistoryItem,
    LoginRequest,
)
from core.auth import AuthUser, require_user
from core.coding_framework import codebook
from core.dual_export import build_dual_excel_bytes
from core import history as history_store
from tasks.dual_manager import DualJobManager, run_dual_processing_job

logger = logging.getLogger(__name__)

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent
UPLOADS_DIR = BASE_DIR / "storage" / "uploads"
JOBS_DIR = BASE_DIR / "storage" / "jobs"

dual_job_manager = DualJobManager(JOBS_DIR)

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"}


def _check_job_access(job_id: str, user: AuthUser) -> None:
    try:
        dual_job_manager.assert_owner(job_id, user.user_id)
    except KeyError:
        raise HTTPException(404, "Job not found")
    except PermissionError:
        raise HTTPException(403, "无权访问该识别记录")


@router.get("/dual/codebook")
async def get_codebook(user: AuthUser = Depends(require_user)):
    return codebook()


@router.get("/dual/history", response_model=list[HistoryItem])
async def dual_history(user: AuthUser = Depends(require_user)):
    items = history_store.list_history(JOBS_DIR, user.user_id)
    return [i for i in items if i.job_type == "dual"]


@router.post("/dual/upload", response_model=DualJobStatus)
async def dual_upload(file: UploadFile = File(...), user: AuthUser = Depends(require_user)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file format: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    save_path = UPLOADS_DIR / f"dual_{user.user_id}_{file.filename}"
    content = await file.read()
    save_path.write_bytes(content)

    job_id = dual_job_manager.create_job(str(save_path), file.filename, user_id=user.user_id)

    thread = threading.Thread(
        target=run_dual_processing_job,
        args=(dual_job_manager, job_id, str(save_path), file.filename, JOBS_DIR),
        daemon=True,
    )
    thread.start()

    return dual_job_manager.get_status(job_id)


@router.get("/dual/jobs/{job_id}/progress")
async def dual_progress(job_id: str, request: Request, user: AuthUser = Depends(require_user)):
    _check_job_access(job_id, user)
    status = dual_job_manager.get_status(job_id)
    snapshot = dual_job_manager.get_sse_snapshot(job_id)
    if status is None and snapshot is None:
        raise HTTPException(404, "Job not found")

    if status is not None and status.status in ("done", "failed"):
        payload = snapshot or status.model_dump()

        async def single_event():
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        return StreamingResponse(single_event(), media_type="text/event-stream")

    q = dual_job_manager.subscribe_sse(job_id)

    async def event_generator():
        try:
            if snapshot is not None:
                yield f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
                if snapshot.get("status") in ("done", "failed"):
                    return
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.to_thread(q.get, timeout=30)
                    yield f"data: {data}\n\n"
                    parsed = json.loads(data)
                    if parsed.get("status") in ("done", "failed") or parsed.get("event") in ("done", "failed"):
                        break
                except Exception:
                    yield ": keepalive\n\n"
        finally:
            dual_job_manager.cleanup_sse(job_id, q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.delete("/dual/jobs/{job_id}")
async def dual_delete(job_id: str, user: AuthUser = Depends(require_user)):
    """删除双维识别历史（与 /history/{id} 共用存储）。"""
    try:
        info = history_store.delete_job(JOBS_DIR, job_id, user.user_id)
    except KeyError:
        raise HTTPException(404, "Job not found")
    except PermissionError:
        raise HTTPException(403, "无权删除该识别记录")
    return info


@router.get("/dual/jobs/{job_id}/result", response_model=DualCodingResult)
async def dual_result(job_id: str, user: AuthUser = Depends(require_user)):
    _check_job_access(job_id, user)
    result = dual_job_manager.get_result(job_id)
    if result is None:
        status = dual_job_manager.get_status(job_id)
        if status is None:
            raise HTTPException(404, "Job not found")
        if status.status == "failed":
            raise HTTPException(500, f"Job failed: {status.message}")
        raise HTTPException(202, "Job still processing")
    return result


@router.get("/dual/jobs/{job_id}/original-video")
async def dual_original_video(job_id: str, user: AuthUser = Depends(require_user)):
    from fastapi.responses import FileResponse

    _check_job_access(job_id, user)
    video_path = dual_job_manager.get_video_path(job_id)
    if video_path is None or not Path(video_path).is_file():
        raise HTTPException(404, "Original video not found")
    return FileResponse(video_path, media_type="video/mp4")


def _xlsx_response(data: bytes, display_name: str) -> StreamingResponse:
    """
    返回 Excel。HTTP 头只能 latin-1，中文文件名必须走 RFC 5987 filename*。
    """
    from urllib.parse import quote

    # ASCII 回退名，避免 Content-Disposition 编码炸掉（500）
    ascii_name = "dual_coding.xlsx"
    # 展示名（可含中文）
    utf8_name = quote(display_name or ascii_name)
    cd = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{utf8_name}"
    )
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": cd},
    )


@router.post("/dual/jobs/{job_id}/export")
async def dual_export(job_id: str, payload: DualExportRequest, user: AuthUser = Depends(require_user)):
    _check_job_access(job_id, user)
    video_name = payload.video_name or job_id
    try:
        data = build_dual_excel_bytes(
            payload.units,
            video_name=video_name,
            include_matrices=payload.include_matrices,
        )
    except Exception as e:
        logger.exception("dual export failed")
        raise HTTPException(500, f"导出失败: {e}")
    safe_name = (video_name or "dual_coding").rsplit(".", 1)[0]
    return _xlsx_response(data, f"{safe_name}_双维编码表.xlsx")


@router.get("/dual/jobs/{job_id}/export")
async def dual_export_server(job_id: str, user: AuthUser = Depends(require_user)):
    """未编辑时直接导出服务端识别结果。"""
    _check_job_access(job_id, user)
    result = dual_job_manager.get_result(job_id)
    if result is None:
        status = dual_job_manager.get_status(job_id)
        if status is None:
            raise HTTPException(404, "Job not found")
        if status.status == "failed":
            raise HTTPException(500, f"Job failed: {status.message}")
        raise HTTPException(202, "Job still processing")

    try:
        data = build_dual_excel_bytes(result.units, video_name=result.video_name, include_matrices=True)
    except Exception as e:
        logger.exception("dual export (server) failed")
        raise HTTPException(500, f"导出失败: {e}")
    safe_name = (result.video_name or job_id).rsplit(".", 1)[0]
    return _xlsx_response(data, f"{safe_name}_双维编码表.xlsx")
