"""双维编码任务管理：进度 SSE、partial 落盘、结果读写。"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from pathlib import Path
from queue import Queue
from typing import Optional

from api.schemas import DualCodingResult, DualCodingUnit, DualJobStatus
from core import history as history_store

logger = logging.getLogger(__name__)


class DualJobManager:
    def __init__(self, jobs_dir: Path):
        self.jobs_dir = jobs_dir
        self._jobs: dict[str, DualJobStatus] = {}
        self._results: dict[str, DualCodingResult] = {}
        self._live: dict[str, DualCodingResult] = {}
        self._video_paths: dict[str, str] = {}
        self._owners: dict[str, str] = {}
        self._video_names: dict[str, str] = {}
        self._totals: dict[str, float] = {}
        self._units_total: dict[str, int] = {}
        self._queues: dict[str, list[Queue]] = {}
        self._lock = threading.Lock()

    def create_job(self, video_path: str, video_name: str, user_id: str = "") -> str:
        job_id = uuid.uuid4().hex[:12]
        job_dir = self.jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        with self._lock:
            self._jobs[job_id] = DualJobStatus(
                job_id=job_id, status="pending", progress=0.0, message="Queued"
            )
            self._video_paths[job_id] = video_path
            self._video_names[job_id] = video_name
            self._owners[job_id] = user_id
            self._queues[job_id] = []
            self._live[job_id] = DualCodingResult(
                job_id=job_id,
                video_name=video_name,
                total_duration=0.0,
                units=[],
                complete=False,
            )

        history_store.write_job_meta(
            self.jobs_dir,
            job_id,
            user_id=user_id,
            video_name=video_name,
            video_path=video_path,
            status="pending",
            message="Queued",
            extra={"job_type": "dual"},
        )
        return job_id

    def get_status(self, job_id: str) -> Optional[DualJobStatus]:
        with self._lock:
            return self._jobs.get(job_id)

    def get_result(self, job_id: str) -> Optional[DualCodingResult]:
        with self._lock:
            cached = self._results.get(job_id)
            if cached is not None:
                return cached
            live = self._live.get(job_id)
            if live is not None and live.units:
                return live.model_copy(deep=True)

        result = history_store.read_dual_job_result(self.jobs_dir, job_id)
        if result is not None:
            with self._lock:
                self._results[job_id] = result
            meta = history_store.read_job_meta(self.jobs_dir, job_id)
            if meta:
                with self._lock:
                    if meta.get("video_path"):
                        self._video_paths[job_id] = meta["video_path"]
                    if meta.get("user_id"):
                        self._owners[job_id] = meta["user_id"]
                    if job_id not in self._jobs:
                        self._jobs[job_id] = DualJobStatus(
                            job_id=job_id,
                            status="done",
                            progress=1.0,
                            message=meta.get("message", "Done"),
                            complete=True,
                            event="done",
                        )
        return result

    def get_video_path(self, job_id: str) -> Optional[str]:
        with self._lock:
            path = self._video_paths.get(job_id)
        if path:
            return path
        meta = history_store.read_job_meta(self.jobs_dir, job_id)
        return meta.get("video_path") if meta else None

    def get_owner(self, job_id: str) -> Optional[str]:
        with self._lock:
            owner = self._owners.get(job_id)
        if owner:
            return owner
        meta = history_store.read_job_meta(self.jobs_dir, job_id)
        return meta.get("user_id") if meta else None

    def assert_owner(self, job_id: str, user_id: str) -> None:
        owner = self.get_owner(job_id)
        if owner is None:
            status = self.get_status(job_id)
            result = self.get_result(job_id)
            if status is None and result is None:
                raise KeyError(job_id)
            return
        if owner != user_id:
            raise PermissionError(job_id)

    def set_job_context(self, job_id: str, *, total_duration: float = 0.0, units_total: int = 0):
        with self._lock:
            if total_duration:
                self._totals[job_id] = float(total_duration)
                if job_id in self._live:
                    self._live[job_id].total_duration = float(total_duration)
            if units_total >= 0:
                self._units_total[job_id] = int(units_total)

    def append_unit(
        self,
        job_id: str,
        unit: DualCodingUnit,
        *,
        progress: float,
        message: str,
        video_name: str = "",
        total_duration: float = 0.0,
    ) -> None:
        with self._lock:
            live = self._live.get(job_id)
            if live is None:
                live = DualCodingResult(
                    job_id=job_id,
                    video_name=video_name or self._video_names.get(job_id, ""),
                    total_duration=total_duration,
                    units=[],
                    complete=False,
                )
                self._live[job_id] = live
            if video_name:
                live.video_name = video_name
                self._video_names[job_id] = video_name
            if total_duration:
                live.total_duration = total_duration
                self._totals[job_id] = float(total_duration)

            existing = {u.index: i for i, u in enumerate(live.units)}
            if unit.index in existing:
                live.units[existing[unit.index]] = unit
            else:
                live.units.append(unit)
                live.units.sort(key=lambda u: u.index)
            partial = live.model_copy(deep=True)

            total = self._units_total.get(job_id, len(live.units))
            done = len(live.units)
            if job_id in self._jobs:
                self._jobs[job_id].progress = progress
                self._jobs[job_id].message = message
                self._jobs[job_id].status = "processing"
                self._jobs[job_id].event = "unit"
                self._jobs[job_id].units_done = done
                self._jobs[job_id].units_total = total
                self._jobs[job_id].unit = unit
                self._jobs[job_id].units = None
                self._jobs[job_id].video_name = partial.video_name
                self._jobs[job_id].total_duration = partial.total_duration
                self._jobs[job_id].complete = False
                payload = self._jobs[job_id].model_dump()
            else:
                payload = DualJobStatus(
                    job_id=job_id,
                    status="processing",
                    progress=progress,
                    message=message,
                    event="unit",
                    units_done=done,
                    units_total=total,
                    unit=unit,
                    video_name=partial.video_name,
                    total_duration=partial.total_duration,
                    complete=False,
                ).model_dump()

        try:
            (self.jobs_dir / job_id).mkdir(parents=True, exist_ok=True)
            (self.jobs_dir / job_id / "dual_result.json").write_text(
                partial.model_dump_json(indent=2), encoding="utf-8"
            )
        except OSError as e:
            logger.warning("persist dual partial failed: %s", e)

        history_store.update_job_meta_status(
            self.jobs_dir,
            job_id,
            status="processing",
            message=message,
            total_duration=partial.total_duration,
            segment_count=len(partial.units),
        )
        self._broadcast(job_id, payload)

    def update_progress(self, job_id: str, progress: float, message: str, event: str = "progress"):
        with self._lock:
            status = None
            if job_id in self._jobs:
                self._jobs[job_id].progress = progress
                self._jobs[job_id].message = message
                if self._jobs[job_id].status not in ("done", "failed"):
                    self._jobs[job_id].status = "processing"
                self._jobs[job_id].event = event
                self._jobs[job_id].unit = None
                live = self._live.get(job_id)
                if live is not None:
                    self._jobs[job_id].units_done = len(live.units)
                    self._jobs[job_id].video_name = live.video_name
                    self._jobs[job_id].total_duration = live.total_duration
                self._jobs[job_id].units_total = self._units_total.get(job_id, 0)
                status = self._jobs[job_id].model_dump()
        history_store.update_job_meta_status(
            self.jobs_dir, job_id, status="processing", message=message
        )
        if status:
            self._broadcast(job_id, status)

    def set_done(self, job_id: str, result: DualCodingResult):
        result = result.model_copy(deep=True)
        result.complete = True
        with self._lock:
            self._results[job_id] = result
            self._live[job_id] = result
            payload = None
            if job_id in self._jobs:
                self._jobs[job_id].status = "done"
                self._jobs[job_id].progress = 1.0
                self._jobs[job_id].message = "Done"
                self._jobs[job_id].event = "done"
                self._jobs[job_id].unit = None
                self._jobs[job_id].units = result.units
                self._jobs[job_id].units_done = len(result.units)
                self._jobs[job_id].units_total = len(result.units)
                self._jobs[job_id].video_name = result.video_name
                self._jobs[job_id].total_duration = result.total_duration
                self._jobs[job_id].complete = True
                payload = self._jobs[job_id].model_dump()
        history_store.update_job_meta_status(
            self.jobs_dir,
            job_id,
            status="done",
            message="Done",
            total_duration=result.total_duration,
            segment_count=len(result.units),
        )
        if payload is None:
            payload = DualJobStatus(
                job_id=job_id,
                status="done",
                progress=1.0,
                message="Done",
                event="done",
                units=result.units,
                units_done=len(result.units),
                units_total=len(result.units),
                video_name=result.video_name,
                total_duration=result.total_duration,
                complete=True,
            ).model_dump()
        self._broadcast(job_id, payload)

    def set_failed(self, job_id: str, error: str):
        with self._lock:
            payload = None
            if job_id in self._jobs:
                self._jobs[job_id].status = "failed"
                self._jobs[job_id].message = error
                self._jobs[job_id].event = "failed"
                payload = self._jobs[job_id].model_dump()
        history_store.update_job_meta_status(
            self.jobs_dir, job_id, status="failed", message=error
        )
        if payload is None:
            payload = DualJobStatus(
                job_id=job_id,
                status="failed",
                progress=0.0,
                message=error,
                event="failed",
            ).model_dump()
        self._broadcast(job_id, payload)

    def get_sse_snapshot(self, job_id: str) -> Optional[dict]:
        with self._lock:
            status = self._jobs.get(job_id)
            live = self._live.get(job_id)
            done = self._results.get(job_id)
            if status is None and live is None and done is None:
                return None
            if done is not None:
                units = done.units
                event = "done"
                status_name = "done"
                progress = 1.0
                message = "Done"
                complete = True
                video_name = done.video_name
                total_duration = done.total_duration
            elif live is not None:
                units = live.units
                event = "snapshot"
                status_name = status.status if status else "processing"
                progress = status.progress if status else 0.0
                message = status.message if status else ""
                complete = False
                video_name = live.video_name
                total_duration = live.total_duration
            else:
                units = []
                event = "snapshot"
                status_name = status.status
                progress = status.progress
                message = status.message
                complete = status.complete
                video_name = status.video_name
                total_duration = status.total_duration
            total = self._units_total.get(job_id, len(units))
            return DualJobStatus(
                job_id=job_id,
                status=status_name,
                progress=progress,
                message=message,
                event=event,
                units=units,
                units_done=len(units),
                units_total=total,
                video_name=video_name,
                total_duration=total_duration,
                complete=complete,
            ).model_dump()

    def subscribe_sse(self, job_id: str) -> Queue:
        q = Queue()
        with self._lock:
            if job_id not in self._queues:
                self._queues[job_id] = []
            self._queues[job_id].append(q)
        return q

    def _broadcast(self, job_id: str, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            queues = list(self._queues.get(job_id, []))
        dead = []
        for q in queues:
            try:
                q.put_nowait(data)
            except Exception:
                dead.append(q)
        if dead:
            with self._lock:
                current = self._queues.get(job_id, [])
                self._queues[job_id] = [q for q in current if q not in dead]

    def cleanup_sse(self, job_id: str, q: Queue):
        with self._lock:
            if job_id in self._queues and q in self._queues[job_id]:
                self._queues[job_id].remove(q)


def run_dual_processing_job(
    job_manager: DualJobManager,
    job_id: str,
    video_path: str,
    video_name: str,
    jobs_dir: Path,
):
    """后台：ASR → 逐段 Qwen-VL 双维编码 → 完成一段立刻推送前端。"""
    from core.coding_framework import compute_process_metrics, build_transition_matrices
    from core.dual_coder import DraftUnit, run_dual_coding_pipeline
    from core.ffmpeg_utils import get_video_duration

    job_dir = jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    prog = {"p": 0.25, "planned": 1}

    def on_progress(p: float, msg: str):
        prog["p"] = p
        job_manager.update_progress(job_id, p, msg)

    live_units: dict[int, DualCodingUnit] = {}

    def _to_schema(d: DraftUnit) -> DualCodingUnit:
        return DualCodingUnit(
            index=d.index,
            start_time=d.start_time,
            end_time=d.end_time,
            duration=round(d.end_time - d.start_time, 2),
            text=d.text,
            behavior_code=d.behavior_code,
            behavior_name=d.behavior_name,
            behavior_dim=d.behavior_dim,
            behavior_reason=d.behavior_reason,
            emotion_code=d.emotion_code,
            emotion_name=d.emotion_name,
            emotion_dim=d.emotion_dim,
            emotion_evidence=d.emotion_evidence,
            confidence=d.confidence,
            needs_review=d.needs_review,
            status="ok",
            source=d.source,
            original_behavior_code=d.behavior_code,
            original_emotion_code=d.emotion_code,
            original_behavior_name=d.behavior_name,
            original_emotion_name=d.emotion_name,
            original_text=d.text,
        )

    def on_unit(d: DraftUnit) -> None:
        """完成一段（或就地合并更新）立刻 SSE + 落盘 partial。"""
        u = _to_schema(d)
        # 若前端已有人工改过，保留编辑（按 index）
        prev = live_units.get(u.index)
        if prev is not None:
            if prev.behavior_code != prev.original_behavior_code:
                u.behavior_code = prev.behavior_code
                u.behavior_name = prev.behavior_name
                u.behavior_dim = prev.behavior_dim
            if prev.emotion_code != prev.original_emotion_code:
                u.emotion_code = prev.emotion_code
                u.emotion_name = prev.emotion_name
                u.emotion_dim = prev.emotion_dim
            if (prev.text or "") != (prev.original_text or ""):
                u.text = prev.text
            if prev.review_marked:
                u.review_marked = True
        live_units[u.index] = u
        n = len(live_units)
        job_manager.append_unit(
            job_id,
            u,
            progress=min(0.95, max(prog["p"], 0.2 + 0.7 * n / max(prog["planned"], 1))),
            message=f"已展示 {n} 个编码单元",
            video_name=video_name,
            total_duration=total_duration,
        )

    try:
        total_duration = get_video_duration(video_path) or 0.0
        job_manager.set_job_context(job_id, total_duration=total_duration)
        job_manager.update_progress(job_id, 0.03, "准备双维自动编码...")

        drafts = run_dual_coding_pipeline(
            video_path,
            total_duration=total_duration,
            progress_cb=lambda p, m: on_progress(p, m),
            unit_cb=on_unit,
        )
        # 流水线在事件抽样后会通过 progress_cb 上报；这里用最终结果回填 planned
        if drafts:
            prog["planned"] = max(len(drafts), 1)

        if not drafts:
            job_manager.set_failed(job_id, "未生成任何编码单元")
            return

        units: list[DualCodingUnit] = [live_units[d.index] for d in drafts if d.index in live_units]
        if not units:
            units = [_to_schema(d) for d in drafts]
        job_manager.set_job_context(
            job_id, total_duration=total_duration, units_total=len(units)
        )

        metrics = compute_process_metrics(units)
        matrices = build_transition_matrices(units)
        summary = {
            **metrics,
            "needs_review_count": sum(1 for u in units if u.needs_review),
            "unit_count": len(units),
        }

        result = DualCodingResult(
            job_id=job_id,
            video_name=video_name,
            total_duration=total_duration,
            units=units,
            complete=True,
            summary=summary,
            sequences={
                "behavior_sequence": matrices.get("behavior_sequence", []),
                "emotion_sequence": matrices.get("emotion_sequence", []),
            },
        )
        (job_dir / "dual_result.json").write_text(
            result.model_dump_json(indent=2), encoding="utf-8"
        )
        # 矩阵单独落盘，便于研究分析
        (job_dir / "dual_matrices.json").write_text(
            json.dumps(
                {
                    "behavior_transition": matrices["behavior_transition"],
                    "emotion_transition": matrices["emotion_transition"],
                    "emotion_behavior_cooccurrence": matrices["emotion_behavior_cooccurrence"],
                    "summary": summary,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        job_manager.set_done(job_id, result)

    except Exception as e:
        logger.error("Dual job %s failed: %s", job_id, e, exc_info=True)
        job_manager.set_failed(job_id, str(e))
