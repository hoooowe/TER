"""
教学情绪-行为双维自动编码流水线。

流程（需求文档 §6）：
视频导入 → 预处理 → 语音识别与时间对齐 → 多模态特征提取
→ 教学事件识别 → 教学行为分类 → 教学情绪识别
→ 行为—情绪时间同步 → 情绪变化检测 → 自动切分编码单元
→ 双维编码结果生成

原则：
- 事件抽样，不固定时间窗
- 行为按教学功能判断
- 情绪只识别可观察外显状态，X0 必须保留
- 一个时间片段 = 一个行为编码 + 一个情绪编码
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core import aliyun_config as acfg
from core.coding_framework import behavior_info, emotion_info, normalize_codes

logger = logging.getLogger(__name__)

ProgressCb = Optional[Callable[[float, str], None]]


@dataclass
class DraftUnit:
    """流水线中间态编码单元。"""
    index: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    text: str = ""
    behavior_code: str = "B1"
    behavior_name: str = ""
    behavior_dim: str = ""
    behavior_reason: str = ""
    emotion_code: str = "X0"
    emotion_name: str = ""
    emotion_dim: str = ""
    emotion_evidence: str = ""
    confidence: float = 0.0
    needs_review: bool = True
    source: str = "vl"  # vl | silence | merged
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "start_time": round(self.start_time, 2),
            "end_time": round(self.end_time, 2),
            "duration": round(self.end_time - self.start_time, 2),
            "text": self.text,
            "behavior_code": self.behavior_code,
            "behavior_name": self.behavior_name,
            "behavior_dim": self.behavior_dim,
            "behavior_reason": self.behavior_reason,
            "emotion_code": self.emotion_code,
            "emotion_name": self.emotion_name,
            "emotion_dim": self.emotion_dim,
            "emotion_evidence": self.emotion_evidence,
            "confidence": self.confidence,
            "needs_review": self.needs_review,
            "source": self.source,
        }


UnitCb = Optional[Callable[["DraftUnit"], None]]


def _report(cb: ProgressCb, progress: float, message: str) -> None:
    if cb:
        cb(max(0.0, min(1.0, progress)), message)


def group_utterances_into_events(
    sentences: List[dict],
    *,
    max_unit_sec: float = None,
    min_unit_sec: float = None,
    merge_gap_sec: float = None,
) -> List[dict]:
    """
    将 ASR 句子合并为候选教学事件（事件抽样）。

    规则：
    - 相邻句间隔小于 merge_gap 且合并后不超过 max_unit 时合并
    - 极短句并入邻居
    - 超过 max_unit*1.25 强制切开（情绪变化二次切分在编码阶段处理）
    返回 [{start, end, text, sent_indices}, ...]
    """
    max_unit_sec = max_unit_sec or acfg.DUAL_MAX_UNIT_SEC
    min_unit_sec = min_unit_sec or acfg.DUAL_MIN_UNIT_SEC
    merge_gap_sec = merge_gap_sec or acfg.DUAL_MERGE_GAP_SEC

    valid = []
    for i, s in enumerate(sentences or []):
        try:
            start = float(s["start"])
            end = float(s["end"])
        except (KeyError, TypeError, ValueError):
            continue
        text = (s.get("text") or "").strip()
        if not text:
            continue
        if end < start:
            end = start
        valid.append({"start": start, "end": end, "text": text, "si": i})

    if not valid:
        return []

    def blank_from(item: dict) -> dict:
        return {
            "start": item["start"],
            "end": item["end"],
            "texts": [item["text"]],
            "sent_indices": [item["si"]],
        }

    events: List[dict] = []
    cur = blank_from(valid[0])

    for item in valid[1:]:
        gap = item["start"] - cur["end"]
        merged_dur = max(cur["end"], item["end"]) - cur["start"]
        sent_dur = item["end"] - item["start"]
        can_merge = gap <= merge_gap_sec and (
            merged_dur <= max_unit_sec
            or (sent_dur < min_unit_sec and merged_dur <= max_unit_sec * 1.5)
        )
        if can_merge:
            cur["end"] = max(cur["end"], item["end"])
            cur["texts"].append(item["text"])
            cur["sent_indices"].append(item["si"])
        else:
            events.append(_finalize_event(cur))
            cur = blank_from(item)

        # 超长事件强制切分：当前事件落盘（已含 item），下一句另起，避免重复
        if cur["end"] - cur["start"] > max_unit_sec * 1.25 and cur["texts"]:
            events.append(_finalize_event(cur))
            cur = {
                "start": cur["end"],
                "end": cur["end"],
                "texts": [],
                "sent_indices": [],
            }

    if cur["texts"]:
        events.append(_finalize_event(cur))
    return events


def _finalize_event(cur: dict) -> dict:
    return {
        "start": cur["start"],
        "end": cur["end"],
        "text": "".join(cur["texts"]) if len(cur["texts"]) > 1 and all(
            t.endswith(("。", "！", "？", "，", "、")) for t in cur["texts"][:-1]
        ) else " ".join(t for t in cur["texts"] if t),
        "sent_indices": list(cur["sent_indices"]),
    }


def build_silence_units(
    events: List[dict],
    total_duration: float,
    *,
    silence_gap_sec: float = None,
) -> List[dict]:
    """在语音事件之间生成“无语音”间隙单元（便于人工复核板书/停顿）。"""
    silence_gap_sec = silence_gap_sec or acfg.DUAL_SILENCE_GAP_SEC
    gaps: List[dict] = []
    cursor = 0.0
    for ev in events:
        if ev["start"] - cursor >= silence_gap_sec:
            gaps.append({"start": cursor, "end": ev["start"], "text": "", "sent_indices": []})
        cursor = max(cursor, ev["end"])
    if total_duration and total_duration - cursor >= silence_gap_sec:
        gaps.append({"start": cursor, "end": total_duration, "text": "", "sent_indices": []})
    return gaps


def try_merge_into(prev: DraftUnit, nxt: DraftUnit, *, max_merge_sec: float = 25.0) -> bool:
    """若 nxt 与 prev 同（行为,情绪）且可衔接，则就地并入 prev，返回 True。"""
    same_codes = (
        prev.behavior_code == nxt.behavior_code
        and prev.emotion_code == nxt.emotion_code
    )
    gap = nxt.start_time - prev.end_time
    dur = nxt.end_time - prev.start_time
    if not (same_codes and gap <= 0.35 and dur <= max_merge_sec):
        return False
    prev.end_time = max(prev.end_time, nxt.end_time)
    if nxt.text:
        prev.text = f"{prev.text} {nxt.text}".strip() if prev.text else nxt.text
    if prev.confidence and nxt.confidence:
        prev.confidence = min(prev.confidence, nxt.confidence)
    else:
        prev.confidence = max(prev.confidence or 0.0, nxt.confidence or 0.0)
    prev.needs_review = bool(prev.needs_review or nxt.needs_review)
    prev.behavior_reason = prev.behavior_reason or nxt.behavior_reason
    prev.emotion_evidence = prev.emotion_evidence or nxt.emotion_evidence
    prev.source = "merged"
    return True


def merge_by_same_codes(units: List[DraftUnit], *, max_merge_sec: float = 25.0) -> List[DraftUnit]:
    """
    合并相邻且（行为码, 情绪码）相同的单元；
    同行为但情绪变化 → 保留切分（情绪变化节点二次切分）。
    """
    if not units:
        return []
    ordered = sorted(units, key=lambda u: (u.start_time, u.end_time))
    merged: List[DraftUnit] = []
    cur = ordered[0]

    for nxt in ordered[1:]:
        if try_merge_into(cur, nxt, max_merge_sec=max_merge_sec):
            continue
        merged.append(cur)
        cur = nxt
    merged.append(cur)

    for i, u in enumerate(merged):
        u.index = i
    return merged


def split_by_emotion_change(units: List[DraftUnit]) -> List[DraftUnit]:
    """
    同一行为持续过程中若情绪变化，已在编码阶段按事件边界天然切分。
    此处对超长单元做二次细分保护：当单元过长且置信度低时，保持原样但标记复核。
    """
    for u in units:
        dur = u.end_time - u.start_time
        if dur > acfg.DUAL_MAX_UNIT_SEC * 2 and u.confidence < acfg.DUAL_CONFIDENCE_THRESHOLD:
            u.needs_review = True
        # X0 必须保留，不允许强制归入其它情绪
        if u.emotion_code == "X0":
            u.needs_review = True
    return units


def run_dual_coding_pipeline(
    video_path: str,
    *,
    total_duration: Optional[float] = None,
    progress_cb: ProgressCb = None,
    unit_cb: UnitCb = None,
    sentences: Optional[List[dict]] = None,
) -> List[DraftUnit]:
    """
    完整双维自动编码流水线。

    unit_cb：每完成一个编码单元（或就地合并后更新）立刻回调，便于前端增量展示。
    返回最终 DraftUnit 列表。
    """
    from core.aliyun_asr import transcribe_video
    from core.aliyun_vl import code_segment

    def emit(unit: DraftUnit) -> None:
        if unit_cb:
            try:
                unit_cb(unit)
            except Exception:
                logger.exception("unit_cb failed")

    if total_duration is None:
        from core.ffmpeg_utils import get_video_duration
        total_duration = get_video_duration(video_path) or 0.0

    # 1) 语音识别与时间对齐
    if sentences is None:
        _report(progress_cb, 0.08, "语音识别（qwen3-asr）...")
        sentences = transcribe_video(video_path)
    else:
        _report(progress_cb, 0.08, "使用已提供转写时间轴...")
    _report(progress_cb, 0.18, f"ASR 完成，共 {len(sentences)} 句")

    # 2) 事件抽样（教学事件候选）
    events = group_utterances_into_events(sentences)
    gaps = build_silence_units(events, total_duration)
    work_items: List[dict] = [{"kind": "speech", **ev} for ev in events]
    work_items.extend({"kind": "silence", **g} for g in gaps)
    work_items.sort(key=lambda x: x["start"])

    total_n = max(1, len(work_items))
    _report(progress_cb, 0.22, f"事件抽样：{len(events)} 个语音事件 + {len(gaps)} 个间隙")

    # 3) 多模态编码：完成一段立刻合并/推送一段
    drafts: List[DraftUnit] = []
    for i, item in enumerate(work_items):
        start = float(item["start"])
        end = float(item["end"])
        text = item.get("text") or ""
        progress = 0.25 + 0.65 * ((i + 1) / total_n)
        _report(
            progress_cb,
            progress,
            f"双维编码 {i + 1}/{total_n}（{start:.1f}s–{end:.1f}s）· 已出 {len(drafts)} 段",
        )

        ctx_prev = work_items[i - 1].get("text") if i > 0 else ""
        ctx_next = work_items[i + 1].get("text") if i + 1 < total_n else ""

        if item["kind"] == "silence" and end - start >= 2.0:
            coded = code_segment(
                video_path, start, end, text="",
                context_prev=ctx_prev or "", context_next=ctx_next or "",
            )
            unit = DraftUnit(
                start_time=start, end_time=end, text="", source="silence",
                **_coded_to_fields(coded),
            )
        else:
            coded = code_segment(
                video_path, start, end, text,
                context_prev=ctx_prev or "", context_next=ctx_next or "",
            )
            unit = DraftUnit(
                start_time=start, end_time=end, text=text, source="vl",
                **_coded_to_fields(coded),
            )

        # 同码就地合并（不打乱已展示列表），否则新增一条
        if drafts and try_merge_into(drafts[-1], unit):
            emit(drafts[-1])
        else:
            unit.index = len(drafts)
            drafts.append(unit)
            emit(unit)

    # 4) 收尾：复核标记（X0 / 超长低置信）
    _report(progress_cb, 0.94, f"同步校验 {len(drafts)} 个编码单元...")
    final = split_by_emotion_change(drafts)
    for i, u in enumerate(final):
        u.index = i
        emit(u)

    _report(progress_cb, 0.98, f"双维编码完成，共 {len(final)} 个编码单元")
    return final


def _coded_to_fields(coded: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "behavior_code",
        "behavior_name",
        "behavior_dim",
        "behavior_reason",
        "emotion_code",
        "emotion_name",
        "emotion_dim",
        "emotion_evidence",
        "confidence",
        "needs_review",
    ]
    return {k: coded.get(k) for k in keys}


def fallback_code_from_text_only(text: str) -> Dict[str, Any]:
    """无 VL 时的极简启发式（仅内部兜底，不作为正式编码路径）。"""
    t = text or ""
    if any(k in t for k in ("？", "?", "吗", "什么呢", "请问")):
        return normalize_codes("B41", "U1", confidence=0.3, needs_review=True)
    return normalize_codes("B1", "U1", confidence=0.2, needs_review=True)
