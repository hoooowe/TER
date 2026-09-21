import uuid
import logging
import threading
import json
from pathlib import Path
from typing import Optional
from queue import Queue

from api.schemas import JobStatus, JobResult, SegmentResult
from core import history as history_store

logger = logging.getLogger(__name__)


class JobManager:
    def __init__(self, jobs_dir: Path):
        self.jobs_dir = jobs_dir
        self._jobs: dict[str, JobStatus] = {}
        self._results: dict[str, JobResult] = {}
        self._live: dict[str, JobResult] = {}  # 处理中的部分结果
        self._video_paths: dict[str, str] = {}
        self._owners: dict[str, str] = {}
        self._video_names: dict[str, str] = {}
        self._totals: dict[str, float] = {}
        self._segments_total: dict[str, int] = {}
        self._queues: dict[str, list[Queue]] = {}
        self._lock = threading.Lock()

    def create_job(self, video_path: str, video_name: str, user_id: str = "") -> str:
        job_id = uuid.uuid4().hex[:12]
        job_dir = self.jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        with self._lock:
            self._jobs[job_id] = JobStatus(job_id=job_id, status="pending", progress=0.0, message="Queued")
            self._video_paths[job_id] = video_path
            self._video_names[job_id] = video_name
            self._owners[job_id] = user_id
            self._queues[job_id] = []
            self._live[job_id] = JobResult(
                job_id=job_id,
                video_name=video_name,
                total_duration=0.0,
                segments=[],
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
        )
        return job_id

    def get_status(self, job_id: str) -> Optional[JobStatus]:
        with self._lock:
            return self._jobs.get(job_id)

    def get_result(self, job_id: str) -> Optional[JobResult]:
        """完整结果优先；处理中可返回 partial（complete=False）。"""
        with self._lock:
            cached = self._results.get(job_id)
            if cached is not None:
                return cached
            live = self._live.get(job_id)
            if live is not None and live.segments:
                return live.model_copy(deep=True)

        result = history_store.read_job_result(self.jobs_dir, job_id)
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
                        self._jobs[job_id] = JobStatus(
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

    def set_job_context(self, job_id: str, *, total_duration: float = 0.0, segments_total: int = 0):
        with self._lock:
            if total_duration:
                self._totals[job_id] = float(total_duration)
                if job_id in self._live:
                    self._live[job_id].total_duration = float(total_duration)
            if segments_total >= 0:
                self._segments_total[job_id] = int(segments_total)

    def append_segment(
        self,
        job_id: str,
        segment: SegmentResult,
        *,
        progress: float,
        message: str,
        video_name: str = "",
        total_duration: float = 0.0,
    ) -> None:
        """识别完一段后立刻入内存并通过 SSE 推送，同时落盘 partial 结果。"""
        with self._lock:
            live = self._live.get(job_id)
            if live is None:
                live = JobResult(
                    job_id=job_id,
                    video_name=video_name or self._video_names.get(job_id, ""),
                    total_duration=total_duration,
                    segments=[],
                    complete=False,
                )
                self._live[job_id] = live
            if video_name:
                live.video_name = video_name
                self._video_names[job_id] = video_name
            if total_duration:
                live.total_duration = total_duration
                self._totals[job_id] = float(total_duration)
            # 按 index upsert，避免重复
            existing = {s.index: i for i, s in enumerate(live.segments)}
            if segment.index in existing:
                live.segments[existing[segment.index]] = segment
            else:
                live.segments.append(segment)
                live.segments.sort(key=lambda s: s.index)
            partial = live.model_copy(deep=True)

            total = self._segments_total.get(job_id, len(live.segments))
            done = len(live.segments)
            if job_id in self._jobs:
                self._jobs[job_id].progress = progress
                self._jobs[job_id].message = message
                self._jobs[job_id].status = "processing"
                self._jobs[job_id].event = "segment"
                self._jobs[job_id].segments_done = done
                self._jobs[job_id].segments_total = total
                self._jobs[job_id].segment = segment
                self._jobs[job_id].segments = None
                self._jobs[job_id].video_name = partial.video_name
                self._jobs[job_id].total_duration = partial.total_duration
                self._jobs[job_id].complete = False
                payload = self._jobs[job_id].model_dump()
            else:
                payload = JobStatus(
                    job_id=job_id,
                    status="processing",
                    progress=progress,
                    message=message,
                    event="segment",
                    segments_done=done,
                    segments_total=total,
                    segment=segment,
                    video_name=partial.video_name,
                    total_duration=partial.total_duration,
                    complete=False,
                ).model_dump()

        # 磁盘 partial，刷新页面/历史也能看到已出片段
        try:
            (self.jobs_dir / job_id).mkdir(parents=True, exist_ok=True)
            (self.jobs_dir / job_id / "result.json").write_text(
                partial.model_dump_json(indent=2), encoding="utf-8"
            )
        except OSError as e:
            logger.warning("persist partial result failed: %s", e)

        history_store.update_job_meta_status(
            self.jobs_dir,
            job_id,
            status="processing",
            message=message,
            total_duration=partial.total_duration,
            segment_count=len(partial.segments),
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
                self._jobs[job_id].segment = None
                live = self._live.get(job_id)
                if live is not None:
                    self._jobs[job_id].segments_done = len(live.segments)
                    self._jobs[job_id].video_name = live.video_name
                    self._jobs[job_id].total_duration = live.total_duration
                self._jobs[job_id].segments_total = self._segments_total.get(job_id, 0)
                status = self._jobs[job_id].model_dump()
        history_store.update_job_meta_status(
            self.jobs_dir, job_id, status="processing", message=message
        )
        if status:
            self._broadcast(job_id, status)

    def set_done(self, job_id: str, result: JobResult):
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
                self._jobs[job_id].segment = None
                self._jobs[job_id].segments = result.segments
                self._jobs[job_id].segments_done = len(result.segments)
                self._jobs[job_id].segments_total = len(result.segments)
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
            segment_count=len(result.segments),
        )
        if payload is None:
            payload = JobStatus(
                job_id=job_id,
                status="done",
                progress=1.0,
                message="Done",
                event="done",
                segments=result.segments,
                segments_done=len(result.segments),
                segments_total=len(result.segments),
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
            payload = JobStatus(
                job_id=job_id,
                status="failed",
                progress=0.0,
                message=error,
                event="failed",
            ).model_dump()
        self._broadcast(job_id, payload)

    def get_sse_snapshot(self, job_id: str) -> Optional[dict]:
        """订阅时立即下发的当前状态（含已识别片段），避免刷新丢进度。"""
        with self._lock:
            status = self._jobs.get(job_id)
            live = self._live.get(job_id)
            done = self._results.get(job_id)
            if status is None and live is None and done is None:
                return None
            if done is not None:
                segments = done.segments
                event = "done"
                status_name = "done"
                progress = 1.0
                message = "Done"
                complete = True
                video_name = done.video_name
                total_duration = done.total_duration
            elif live is not None:
                segments = live.segments
                event = "snapshot"
                status_name = status.status if status else "processing"
                progress = status.progress if status else 0.0
                message = status.message if status else ""
                complete = False
                video_name = live.video_name
                total_duration = live.total_duration
            else:
                segments = []
                event = "snapshot"
                status_name = status.status
                progress = status.progress
                message = status.message
                complete = status.complete
                video_name = status.video_name
                total_duration = status.total_duration
            total = self._segments_total.get(job_id, len(segments))
            return JobStatus(
                job_id=job_id,
                status=status_name,
                progress=progress,
                message=message,
                event=event,
                segments=segments,
                segments_done=len(segments),
                segments_total=total,
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


def _maybe_release_models():
    """任务结束后按配置释放大模型，降低空闲内存。"""
    import gc

    from core import memory_config as memcfg
    if not memcfg.RELEASE_MODELS_AFTER_JOB:
        return
    try:
        from core.asr import release_asr
        release_asr()
    except Exception as e:
        logger.warning(f"release ASR failed: {e}")
    try:
        from core.recognizer import release_emotion_model
        release_emotion_model()
    except Exception as e:
        logger.warning(f"release emotion model failed: {e}")
    try:
        gc.collect()
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def run_processing_job(job_manager: JobManager, job_id: str, video_path: str, video_name: str, jobs_dir: Path):
    """Background: ASR → 逐句切分/识别 → 每段结果立刻推送前端。"""
    from core.segmentation import run_asr_timeline, iter_utterance_segments
    from core.ffmpeg_utils import get_video_duration
    from core import memory_config as memcfg

    use_custom = memcfg.EMOTION_MODEL == "custom"
    if use_custom:
        try:
            from core.custom_predictor import recognize_segment_custom
            recognize_fn = recognize_segment_custom
            logger.info("Job %s using custom multimodal model", job_id)
        except Exception as e:
            logger.warning(f"自训练模型不可用，回退到 emotion2vec: {e}")
            from core.recognizer import recognize_segment
            recognize_fn = recognize_segment
            use_custom = False
    else:
        from core.recognizer import recognize_segment
        recognize_fn = recognize_segment
        logger.info("Job %s using emotion2vec (%s)", job_id, memcfg.EMOTION2VEC_MODEL_ID)

    job_dir = jobs_dir / job_id
    segments_dir = job_dir / "segments"
    segments_dir.mkdir(exist_ok=True)

    try:
        total_duration = get_video_duration(video_path) or 0.0
        job_manager.set_job_context(job_id, total_duration=total_duration)
        job_manager.update_progress(job_id, 0.05, "Extracting audio...")

        def asr_progress(msg):
            job_manager.update_progress(job_id, 0.15, msg)

        sentences = run_asr_timeline(video_path, progress_callback=asr_progress)
        # 预估有效段数，便于进度展示
        min_seg = 2.0
        planned = [
            s for s in sentences
            if s.get("text") and (float(s["end"]) - float(s["start"])) >= min_seg
        ]
        total_planned = len(planned) or 1
        job_manager.set_job_context(job_id, total_duration=total_duration, segments_total=total_planned)

        results: list[SegmentResult] = []
        cut_iter = iter_utterance_segments(
            video_path,
            str(segments_dir),
            sentences,
            min_segment_duration=min_seg,
            progress_callback=lambda msg: job_manager.update_progress(job_id, 0.28, msg),
        )

        for cut_idx, seg in enumerate(cut_iter):
            done = len(results) + 1
            progress = 0.30 + 0.65 * (done / total_planned)
            job_manager.update_progress(
                job_id,
                progress,
                f"Recognizing segment {done}/{total_planned}...",
            )

            try:
                if use_custom:
                    pred = recognize_fn(seg.output_path, text=seg.text)
                else:
                    pred = recognize_fn(seg.output_path)
            except Exception as e:
                logger.error("segment %s recognize failed: %s", seg.index, e)
                pred = {"error": str(e)}

            seg_result = SegmentResult(
                index=seg.index,
                start_time=round(seg.start_time, 2),
                end_time=round(seg.end_time, 2),
                duration=round(seg.end_time - seg.start_time, 2),
                text=seg.text,
                label=pred.get("label_4", 1),
                label_name=pred.get("label_name_4", "calm"),
                label_name_cn=pred.get("label_name_4_cn", "平稳中性"),
                confidence=pred.get("confidence", 0.0),
                emotion2vec_label=pred.get("label_9", 8),
                emotion2vec_label_name=pred.get("label_name_9", "unknown"),
                status="error" if "error" in pred else "ok",
            )
            results.append(seg_result)

            # 逐段推送到前端
            job_manager.append_segment(
                job_id,
                seg_result,
                progress=min(0.98, progress),
                message=f"已识别 {len(results)}/{total_planned} 段",
                video_name=video_name,
                total_duration=total_duration,
            )

        if not results:
            job_manager.set_failed(job_id, "No segments produced from video")
            return

        job_result = JobResult(
            job_id=job_id,
            video_name=video_name,
            total_duration=total_duration,
            segments=results,
            complete=True,
        )
        result_path = job_dir / "result.json"
        result_path.write_text(job_result.model_dump_json(indent=2), encoding="utf-8")
        job_manager.set_done(job_id, job_result)

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        job_manager.set_failed(job_id, str(e))
    finally:
        _maybe_release_models()
