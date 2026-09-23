"""识别历史：基于 storage/jobs/<id>/{meta.json,result.json} 的轻量持久化。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from api.schemas import HistoryItem, JobResult


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def write_job_meta(
    jobs_dir: Path,
    job_id: str,
    *,
    user_id: str,
    video_name: str,
    video_path: str,
    status: str = "pending",
    message: str = "",
    total_duration: float = 0.0,
    segment_count: int = 0,
    extra: Optional[dict] = None,
) -> dict:
    job_dir = jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    meta_path = job_dir / "meta.json"
    meta: dict[str, Any] = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            meta = {}

    meta.update(
        {
            "job_id": job_id,
            "user_id": user_id,
            "video_name": video_name,
            "video_path": video_path,
            "status": status,
            "message": message,
            "total_duration": total_duration,
            "segment_count": segment_count,
        }
    )
    if extra and "job_type" in extra:
        meta["job_type"] = extra["job_type"]
    if "created_at" not in meta:
        meta["created_at"] = _now_iso()
    meta["updated_at"] = _now_iso()
    if extra:
        meta.update(extra)

    tmp = meta_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(meta_path)
    return meta


def read_job_meta(jobs_dir: Path, job_id: str) -> Optional[dict]:
    meta_path = jobs_dir / job_id / "meta.json"
    if not meta_path.is_file():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def read_job_result(jobs_dir: Path, job_id: str) -> Optional[JobResult]:
    result_path = jobs_dir / job_id / "result.json"
    if not result_path.is_file():
        return None
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        return JobResult.model_validate(data)
    except Exception:
        return None


def read_dual_job_result(jobs_dir: Path, job_id: str):
    result_path = jobs_dir / job_id / "dual_result.json"
    if not result_path.is_file():
        return None
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        from api.schemas import DualCodingResult
        return DualCodingResult.model_validate(data)
    except Exception:
        return None


def update_job_meta_status(
    jobs_dir: Path,
    job_id: str,
    *,
    status: str,
    message: str = "",
    total_duration: Optional[float] = None,
    segment_count: Optional[int] = None,
) -> Optional[dict]:
    meta = read_job_meta(jobs_dir, job_id)
    if meta is None:
        return None
    meta["status"] = status
    meta["message"] = message
    if total_duration is not None:
        meta["total_duration"] = total_duration
    if segment_count is not None:
        meta["segment_count"] = segment_count
    meta["updated_at"] = _now_iso()
    meta_path = jobs_dir / job_id / "meta.json"
    tmp = meta_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(meta_path)
    return meta


def list_history(jobs_dir: Path, user_id: str) -> list[HistoryItem]:
    items: list[HistoryItem] = []
    if not jobs_dir.is_dir():
        return items

    for job_dir in jobs_dir.iterdir():
        if not job_dir.is_dir() or job_dir.name.startswith("_"):
            continue
        meta = read_job_meta(jobs_dir, job_dir.name)
        if not meta:
            continue
        # 按用户隔离：仅返回本人任务
        if meta.get("user_id") != user_id:
            continue
        items.append(
            HistoryItem(
                job_id=meta.get("job_id", job_dir.name),
                video_name=meta.get("video_name", ""),
                status=meta.get("status", "unknown"),
                message=meta.get("message", ""),
                created_at=meta.get("updated_at") or meta.get("created_at") or "",
                total_duration=float(meta.get("total_duration") or 0.0),
                segment_count=int(meta.get("segment_count") or 0),
                job_type=meta.get("job_type") or "emotion",
            )
        )

    items.sort(key=lambda x: x.created_at, reverse=True)
    return items


def ensure_owner(jobs_dir: Path, job_id: str, user_id: str) -> dict:
    meta = read_job_meta(jobs_dir, job_id)
    if meta is None:
        raise KeyError(job_id)
    if meta.get("user_id") != user_id:
        raise PermissionError(job_id)
    return meta


def delete_job(jobs_dir: Path, job_id: str, user_id: str) -> dict:
    """
    删除识别历史：校验归属后删除 jobs/<id>/ 整目录，
    并尝试删除该任务独占的上传视频。
    """
    import shutil

    meta = ensure_owner(jobs_dir, job_id, user_id)
    job_dir = jobs_dir / job_id
    if job_dir.is_dir():
        shutil.rmtree(job_dir, ignore_errors=True)

    # 上传视频：若无其它任务引用同一路径则一并删除
    video_path = meta.get("video_path") or ""
    upload_removed = False
    if video_path:
        vp = Path(video_path)
        still_used = False
        if jobs_dir.is_dir():
            for other in jobs_dir.iterdir():
                if not other.is_dir() or other.name == job_id:
                    continue
                other_meta = read_job_meta(jobs_dir, other.name)
                if other_meta and other_meta.get("video_path") == video_path:
                    still_used = True
                    break
        if not still_used and vp.is_file():
            try:
                vp.unlink()
                upload_removed = True
            except OSError:
                pass

    return {
        "ok": True,
        "job_id": job_id,
        "upload_removed": upload_removed,
    }
