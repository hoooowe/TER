"""
通义千问多模态教学双维编码客户端（OpenAI 兼容）。

默认模型：qwen3.8-omni-flash @ maas.qianwenaiapi.com
输入：视频抽帧（base64 image_url）+ 转写文本 + 编码手册提示词
输出：行为编码 + 可观察情绪编码 + 依据 + 置信度（JSON）
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from core import aliyun_config as acfg
from core.coding_framework import build_coding_prompt, normalize_codes, parse_vl_json

logger = logging.getLogger(__name__)


class AliyunVLError(RuntimeError):
    pass


def _require_key() -> str:
    if not acfg.has_api_key():
        raise AliyunVLError(
            "缺少 DASHSCOPE_API_KEY（阿里云百炼 API Key）。"
            "请在 backend 环境变量中设置后重启服务。"
        )
    return acfg.DASHSCOPE_API_KEY


def plan_frame_count(duration: float) -> int:
    """
    高精度 8 帧方案（按时长自适应）：
    ≤3s → 4 帧；3～8s → 8 帧；>8s → 12 帧。
    可用 n_frames 显式覆盖。
    """
    d = float(duration or 0)
    if d <= 3.0:
        return 4
    if d <= 8.0:
        return 8
    return 12


def _grab_frame(video_path: str, t: float, out_path: str) -> bool:
    import subprocess

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{t:.3f}",
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "3",
        "-vf", "scale='min(720,iw)':-2",
        out_path,
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return (
            result.returncode == 0
            and os.path.isfile(out_path)
            and os.path.getsize(out_path) > 500
        )
    except Exception as e:
        logger.warning("frame extract failed at t=%.2f: %s", t, e)
        return False


def _frame_diff_score(path_a: str, path_b: str) -> float:
    """两帧差异分（越大表示动作/表情变化越大）。失败返回 0。"""
    try:
        from PIL import Image, ImageChops, ImageStat

        a = Image.open(path_a).convert("L").resize((64, 36))
        b = Image.open(path_b).convert("L").resize((64, 36))
        diff = ImageChops.difference(a, b)
        return float(ImageStat.Stat(diff).mean[0])
    except Exception:
        return 0.0


def extract_keyframes(
    video_path: str,
    start: float,
    end: float,
    n_frames: Optional[int] = None,
    out_dir: Optional[str] = None,
) -> List[str]:
    """
    高精度抽帧：先密采候选，再按「首/尾 + 动作峰值 + 均匀补齐」选出 n 帧。

    - n_frames 未指定时按 plan_frame_count(时长) 自适应（默认 8 帧档）
    - 返回按时间排序的 JPEG 路径
    """
    duration = max(0.0, end - start)
    if duration <= 0:
        return []

    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="dual_frames_")
    os.makedirs(out_dir, exist_ok=True)

    n = int(n_frames) if n_frames else plan_frame_count(duration)
    n = max(2, min(16, n))

    # 候选帧：约 2 倍目标密度，覆盖动作峰值
    cand_n = max(n * 2, n + 4)
    cand_n = min(cand_n, 24)
    candidates: List[tuple] = []  # (t, path)

    for i in range(cand_n):
        # 避开贴边界：在小区间内均匀取
        t = start + duration * (i + 0.5) / cand_n
        out_path = os.path.join(out_dir, f"c{i:02d}_{int(t * 1000)}.jpg")
        if _grab_frame(video_path, t, out_path):
            candidates.append((t, out_path))

    if not candidates:
        return []
    if len(candidates) <= n:
        return [p for _, p in sorted(candidates, key=lambda x: x[0])]

    # 与前一候选帧的差异 → 动作/表情变化峰值
    diffs = [0.0]
    for i in range(1, len(candidates)):
        diffs.append(_frame_diff_score(candidates[i - 1][1], candidates[i][1]))

    picked_idx = {0, len(candidates) - 1}  # 必含首、尾

    # 峰值（按 diff 从大到小，且与已选保持最小间隔）
    ranked = sorted(range(1, len(candidates) - 1), key=lambda i: diffs[i], reverse=True)
    min_gap = max(1, len(candidates) // (n * 2))
    for i in ranked:
        if len(picked_idx) >= n:
            break
        if any(abs(i - j) < min_gap for j in picked_idx):
            continue
        picked_idx.add(i)

    # 均匀补齐到 n
    if len(picked_idx) < n:
        step = (len(candidates) - 1) / max(1, n - 1)
        for k in range(n):
            idx = int(round(k * step))
            idx = max(0, min(len(candidates) - 1, idx))
            if len(picked_idx) >= n:
                break
            picked_idx.add(idx)

    selected = sorted(picked_idx, key=lambda i: candidates[i][0])[:n]
    paths = [candidates[i][1] for i in selected]

    # 清理未选中的候选文件，减小临时目录
    keep = set(paths)
    for _, p in candidates:
        if p not in keep:
            try:
                os.remove(p)
            except OSError:
                pass

    logger.debug(
        "keyframes %s [%.2f-%.2f]: n=%s from %s candidates",
        video_path, start, end, len(paths), len(candidates),
    )
    return paths


def image_to_base64_url(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def call_qwen_vl(
    prompt: str,
    image_paths: Optional[List[str]] = None,
    temperature: float = 0.2,
    max_tokens: int = 800,
) -> str:
    api_key = _require_key()
    content: List[Dict[str, Any]] = []
    for p in image_paths or []:
        if os.path.isfile(p):
            content.append({"type": "image_url", "image_url": {"url": image_to_base64_url(p)}})
    content.append({"type": "text", "text": prompt})

    # qwen3.8-omni-flash：仅支持文本输出；模态在消息 content 中传入
    payload = {
        "model": acfg.ALIYUN_VL_MODEL,
        "messages": [{"role": "user", "content": content}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "modalities": ["text"],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = acfg.vl_chat_completions_url()
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                data=body,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=acfg.ALIYUN_TIMEOUT_SEC) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices") or []
            if not choices:
                raise AliyunVLError(f"模型返回为空: {str(data)[:300]}")
            message = choices[0].get("message") or {}
            text = message.get("content") or ""
            if isinstance(text, list):
                text = "".join(
                    (part.get("text") or "") if isinstance(part, dict) else str(part)
                    for part in text
                )
            return text
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="ignore")[:400]
            except Exception:
                pass
            if e.code == 429 or e.code >= 500:
                last_err = AliyunVLError(f"HTTP {e.code}: {err_body}")
                time.sleep(1.5 * (attempt + 1))
                continue
            raise AliyunVLError(f"多模态模型调用失败 HTTP {e.code}: {err_body}") from e
        except urllib.error.URLError as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
        except AliyunVLError:
            raise
        except Exception as e:
            raise AliyunVLError(f"多模态模型调用异常: {e}") from e
    raise AliyunVLError(f"多模态模型重试后仍失败: {last_err}")


def code_segment(
    video_path: str,
    start: float,
    end: float,
    text: str,
    *,
    context_prev: str = "",
    context_next: str = "",
    n_frames: Optional[int] = None,
) -> Dict[str, Any]:
    """对单个编码单元调用 Qwen-VL，返回规范化双维编码。"""
    # 高精度：默认按时长自适应 4/8/12 帧；n_frames 可强制覆盖
    if n_frames is None:
        if acfg.DUAL_FRAMES_MODE == "fixed" and acfg.DUAL_FRAMES_PER_UNIT:
            n_frames = acfg.DUAL_FRAMES_PER_UNIT
        else:
            n_frames = plan_frame_count(end - start)
    frame_paths = extract_keyframes(video_path, start, end, n_frames=n_frames)
    has_visual = bool(frame_paths)
    prompt = build_coding_prompt(
        text=text,
        context_prev=context_prev,
        context_next=context_next,
        has_visual=has_visual,
    )

    try:
        raw = call_qwen_vl(prompt, image_paths=frame_paths)
    except AliyunVLError as e:
        logger.error("VL coding failed: %s", e)
        return normalize_codes(
            "B1",
            "X0",
            behavior_reason="多模态调用失败，默认不可观测",
            emotion_evidence=str(e),
            confidence=0.0,
            needs_review=True,
        )

    parsed = parse_vl_json(raw)
    if not parsed:
        logger.warning("VL JSON parse failed, raw=%.200s", raw)
        return normalize_codes(
            "B1",
            "X0",
            behavior_reason="模型输出无法解析",
            emotion_evidence=(raw or "")[:200],
            confidence=0.0,
            needs_review=True,
        )

    return normalize_codes(
        behavior_code=str(parsed.get("behavior_code") or ""),
        emotion_code=str(parsed.get("emotion_code") or ""),
        behavior_reason=str(parsed.get("behavior_reason") or ""),
        emotion_evidence=str(parsed.get("emotion_evidence") or ""),
        confidence=float(parsed.get("confidence") or 0.0),
        needs_review=parsed.get("needs_review"),
        confidence_threshold=acfg.DUAL_CONFIDENCE_THRESHOLD,
    )
