"""
通义 qwen3-asr-flash 语音识别（DashScope MultiModalConversation）。

- 端点：https://maas.qianwenaiapi.com/api/v1（dashscope.base_http_api_url）
- 输出对齐 core.asr.transcribe：[{start, end, text}, ...]
- 时间戳：静音切分（ffmpeg silencedetect）+ 分段识别，保证事件抽样可用
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import wave
from typing import Any, Dict, List, Optional, Tuple

from core import aliyun_config as acfg

logger = logging.getLogger(__name__)


class AliyunASRError(RuntimeError):
    pass


def _require_key() -> str:
    if not acfg.has_api_key():
        raise AliyunASRError(
            "缺少 DASHSCOPE_API_KEY。请写入 backend/.env 或环境变量后重启服务。"
        )
    return acfg.DASHSCOPE_API_KEY


def _ensure_wav_16k_mono(audio_path: str) -> Tuple[str, bool]:
    """确保 16k mono wav；必要时 ffmpeg 转码。返回 (path, need_cleanup)。"""
    lower = audio_path.lower()
    if lower.endswith(".wav"):
        try:
            with wave.open(audio_path, "rb") as wf:
                if (
                    wf.getframerate() == 16000
                    and wf.getnchannels() == 1
                    and wf.getsampwidth() == 2
                ):
                    return audio_path, False
        except Exception:
            pass

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()
    cmd = [
        "ffmpeg", "-y", "-i", audio_path,
        "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le",
        tmp_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    if result.returncode != 0 or not os.path.isfile(tmp_path):
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise AliyunASRError(
            f"音频转码失败: {result.stderr.decode('utf-8', errors='ignore')[:200]}"
        )
    return tmp_path, True


def _wav_duration(path: str) -> float:
    try:
        with wave.open(path, "rb") as wf:
            return wf.getnframes() / float(wf.getframerate() or 1)
    except Exception:
        return 0.0


def detect_speech_segments(
    wav_path: str,
    *,
    silence_noise_db: float = -35.0,
    silence_min_sec: float = 0.45,
    min_speech_sec: float = 0.35,
    pad_sec: float = 0.12,
) -> List[Tuple[float, float]]:
    """
    用 ffmpeg silencedetect 得到语音区间 [(start, end), ...]（秒）。
    解析 stderr 中的 silence_start / silence_end，反推语音段。
    """
    total = _wav_duration(wav_path)
    if total <= 0:
        return []

    cmd = [
        "ffmpeg", "-i", wav_path,
        "-af", f"silencedetect=noise={silence_noise_db}dB:d={silence_min_sec}",
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        stderr = result.stderr.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.warning("silencedetect failed: %s", e)
        return [(0.0, total)]

    silences: List[Tuple[float, float]] = []
    cur_start: Optional[float] = None
    for line in stderr.splitlines():
        m1 = re.search(r"silence_start:\s*([0-9.]+)", line)
        if m1:
            cur_start = float(m1.group(1))
            continue
        m2 = re.search(r"silence_end:\s*([0-9.]+)", line)
        if m2 and cur_start is not None:
            end = float(m2.group(1))
            silences.append((cur_start, end))
            cur_start = None
    if cur_start is not None:
        silences.append((cur_start, total))

    # 语音 = 静音之间的空隙
    speech: List[Tuple[float, float]] = []
    cursor = 0.0
    for s0, s1 in silences:
        if s0 - cursor >= min_speech_sec:
            speech.append((cursor, s0))
        cursor = max(cursor, s1)
    if total - cursor >= min_speech_sec:
        speech.append((cursor, total))

    # 前后轻量 padding，并夹紧
    padded: List[Tuple[float, float]] = []
    for a, b in speech:
        a2 = max(0.0, a - pad_sec)
        b2 = min(total, b + pad_sec)
        if b2 - a2 >= 0.2:
            padded.append((round(a2, 3), round(b2, 3)))

    if not padded:
        return [(0.0, round(total, 3))]
    return padded


def _split_long_segments(
    segments: List[Tuple[float, float]],
    max_sec: float = 20.0,
) -> List[Tuple[float, float]]:
    out: List[Tuple[float, float]] = []
    for a, b in segments:
        dur = b - a
        if dur <= max_sec:
            out.append((a, b))
            continue
        n = int(dur // max_sec) + (1 if dur % max_sec > 1 else 0)
        n = max(1, n)
        step = dur / n
        for i in range(n):
            out.append((round(a + i * step, 3), round(a + (i + 1) * step, 3)))
    return out


def _cut_wav(src: str, start: float, end: float, out_path: str) -> bool:
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-t", f"{max(0.05, end - start):.3f}",
        "-i", src,
        "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le",
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
        return result.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 100
    except Exception:
        return False


def _is_http_url(value: str) -> bool:
    return bool(value) and value.lower().startswith(("http://", "https://"))


def _response_to_dict(response: Any) -> dict:
    if isinstance(response, dict):
        return response
    if hasattr(response, "to_dict") and callable(response.to_dict):
        try:
            d = response.to_dict()
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    if hasattr(response, "__dict__"):
        return dict(response.__dict__)
    return {}


def _parse_asr_text(response: Any) -> str:
    """从 MultiModalConversation 响应中抽出转写文本。"""
    if response is None:
        return ""
    data = _response_to_dict(response)
    if not data:
        return ""

    # 形态1：output.choices[0].message.content
    output = data.get("output") if isinstance(data.get("output"), dict) else data
    if isinstance(output, dict):
        choices = output.get("choices") or []
        if choices:
            msg = (choices[0] or {}).get("message") or {}
            content = msg.get("content") or output.get("text") or ""
            return _content_to_text(content)
        if output.get("text"):
            return str(output.get("text")).strip()
        if output.get("transcription"):
            return str(output.get("transcription")).strip()

    if data.get("text"):
        return str(data.get("text")).strip()
    return _content_to_text(data.get("content"))


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        return str(content.get("text") or "").strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or "").strip())
            else:
                parts.append(str(item).strip())
        return " ".join(p for p in parts if p).strip()
    return str(content).strip()


def _call_qwen3_asr_sdk(audio_ref: str) -> str:
    """
    dashscope MultiModalConversation 识别。
    本地文件必须走 SDK（SDK 会读文件）；http(s) URL 可由 SDK/HTTP 使用。
    注意：该接口不接受 data: URL，本地文件不能只用裸 HTTP 提交。
    """
    api_key = _require_key()
    try:
        import dashscope
        from dashscope import MultiModalConversation
    except ImportError as e:
        raise AliyunASRError(
            "未安装 dashscope SDK，无法识别本地音频。"
            "请在运行后端的环境执行: pip install 'dashscope>=1.20.0'"
        ) from e

    dashscope.api_key = api_key
    dashscope.base_http_api_url = acfg.ALIYUN_ASR_BASE_URL

    messages = [
        {"role": "system", "content": [{"text": ""}]},
        {"role": "user", "content": [{"audio": audio_ref}]},
    ]
    asr_options: Dict[str, Any] = {
        "enable_lid": True,
        "enable_itn": False,
    }
    if acfg.ALIYUN_ASR_LANGUAGE:
        asr_options["language"] = acfg.ALIYUN_ASR_LANGUAGE

    response = MultiModalConversation.call(
        api_key=api_key,
        model=acfg.ALIYUN_ASR_MODEL,
        messages=messages,
        result_format="message",
        asr_options=asr_options,
    )
    data = _response_to_dict(response)
    status = data.get("status_code", getattr(response, "status_code", None))
    if status is not None and int(status) >= 400:
        msg = data.get("message") or getattr(response, "message", "") or str(response)[:300]
        code = data.get("code") or ""
        raise AliyunASRError(f"qwen3-asr 调用失败 ({status} {code}): {msg}")

    text = _parse_asr_text(data or response)
    return text


def transcribe_chunk(audio_path: str) -> str:
    """
    识别单段本地音频文本。
    仅走 dashscope SDK（本地路径）；不再用 data: URL 兜底（服务端会报 url error）。
    """
    if not os.path.isfile(audio_path) or os.path.getsize(audio_path) < 200:
        return ""

    # 本地绝对路径，SDK 可直接读取
    audio_ref = os.path.abspath(audio_path)
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            return _call_qwen3_asr_sdk(audio_ref)
        except AliyunASRError as e:
            last_err = e
            msg = str(e)
            # 配置/缺包类错误直接抛，不重试
            if "未安装 dashscope" in msg or "缺少 DASHSCOPE" in msg:
                raise
            # 明确的远端参数错误也不做无意义重试
            if "InvalidParameter" in msg or "url error" in msg.lower():
                raise
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise
    raise AliyunASRError(f"qwen3-asr 重试后仍失败: {last_err}")


def transcribe(audio_path: str, language: str = "zh") -> List[Dict]:
    """
    转写音频并按静音切分输出句段时间轴。
    Returns: [{"start": float_sec, "end": float_sec, "text": str}, ...]
    """
    if not os.path.isfile(audio_path):
        raise AliyunASRError(f"音频文件不存在: {audio_path}")

    _require_key()
    wav_path, cleanup = _ensure_wav_16k_mono(audio_path)
    tmp_dir = tempfile.mkdtemp(prefix="asr_chunks_")
    try:
        segments = detect_speech_segments(wav_path)
        segments = _split_long_segments(segments, max_sec=acfg.ALIYUN_ASR_MAX_CHUNK_SEC)
        logger.info(
            "qwen3-asr: %s speech segments from %s",
            len(segments),
            audio_path,
        )

        sentences: List[Dict] = []
        for i, (start, end) in enumerate(segments):
            chunk_path = os.path.join(tmp_dir, f"chunk_{i:04d}.wav")
            if not _cut_wav(wav_path, start, end, chunk_path):
                continue
            try:
                text = transcribe_chunk(chunk_path)
            except AliyunASRError as e:
                logger.error("ASR chunk %s failed: %s", i, e)
                continue
            text = (text or "").strip()
            # 去掉可能的说话人/标签前缀
            text = re.sub(r"^(说话人\d+[:：]|SPEAKER_\d+[:：])\s*", "", text).strip()
            if not text:
                continue
            sentences.append({
                "start": round(float(start), 3),
                "end": round(float(end), 3),
                "text": text,
            })

        if not sentences:
            # 整段兜底
            try:
                text = transcribe_chunk(wav_path)
                if text.strip():
                    dur = _wav_duration(wav_path) or 0.0
                    sentences.append({"start": 0.0, "end": round(dur, 3), "text": text.strip()})
            except AliyunASRError as e:
                raise AliyunASRError(f"整段识别也失败: {e}") from e

        if not sentences:
            raise AliyunASRError("ASR 未识别到有效语音")

        logger.info("qwen3-asr produced %s sentences", len(sentences))
        return sentences
    finally:
        if cleanup and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


def transcribe_video(video_path: str) -> List[Dict]:
    """从视频抽取音频后转写。"""
    from core.ffmpeg_utils import extract_audio

    wav = extract_audio(video_path)
    if wav is None:
        raise AliyunASRError("从视频抽取音频失败")
    try:
        return transcribe(wav)
    finally:
        if os.path.exists(wav):
            try:
                os.remove(wav)
            except OSError:
                pass
