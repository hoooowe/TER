import os
import re
import logging
from typing import List, Dict, Optional

from core import memory_config as memcfg

logger = logging.getLogger(__name__)

_asr_model = None
_asr_loaded_key = None

PUNCTUATION = set('。！？，、；：,.!?;:')


def _build_asr_key(backend: str, *model_ids: Optional[str]) -> tuple:
    return (backend, tuple(x or "" for x in model_ids))


def _load_paraformer():
    from funasr import AutoModel

    candidates = []
    if memcfg.PUNC_MODEL_ID:
        for pid in getattr(memcfg, "PUNC_FALLBACK_IDS", [memcfg.PUNC_MODEL_ID]):
            if pid and pid not in candidates:
                candidates.append(pid)
    candidates.append("")  # 最后不加载标点

    last_err = None
    for punc_id in candidates:
        kwargs = dict(
            model=memcfg.PARAFORMER_MODEL_ID,
            vad_model=memcfg.VAD_MODEL_ID,
            hub="ms",
            disable_update=True,
        )
        if punc_id:
            kwargs["punc_model"] = punc_id
            logger.info("Loading ASR: Paraformer-large + VAD + punc(%s)", punc_id)
        else:
            logger.info("Loading ASR: Paraformer-large + VAD (no punctuation model)")
        try:
            model = AutoModel(**kwargs)
            # 若指定了标点但内部未真正挂载，避免后续 generate 失败
            memcfg.PUNC_MODEL_ID = punc_id
            return model
        except Exception as e:
            last_err = e
            logger.warning("ASR punc=%s load failed: %s", punc_id or "none", e)
            continue
    raise RuntimeError(f"Failed to load Paraformer ASR: {last_err}")


def _load_sensevoice():
    from funasr import AutoModel

    logger.info("Loading ASR: SenseVoiceSmall + VAD")
    kwargs = dict(
        model=memcfg.SENSEVOICE_MODEL_ID,
        vad_model=memcfg.VAD_MODEL_ID,
        hub="ms",
        disable_update=True,
    )
    if memcfg.PUNC_MODEL_ID:
        kwargs["punc_model"] = memcfg.PUNC_MODEL_ID
    return AutoModel(**kwargs)


def get_asr_model():
    global _asr_model, _asr_loaded_key

    backend = memcfg.ASR_BACKEND
    if backend in {"sensevoice", "sv", "sense"}:
        key = _build_asr_key("sensevoice", memcfg.SENSEVOICE_MODEL_ID, memcfg.VAD_MODEL_ID, memcfg.PUNC_MODEL_ID)
    else:
        backend = "paraformer"
        key = _build_asr_key("paraformer", memcfg.PARAFORMER_MODEL_ID, memcfg.VAD_MODEL_ID, memcfg.PUNC_MODEL_ID)

    if _asr_model is not None and _asr_loaded_key == key:
        return _asr_model

    # 配置变更时先丢掉旧模型
    if _asr_model is not None:
        release_asr()

    if backend == "sensevoice":
        _asr_model = _load_sensevoice()
    else:
        _asr_model = _load_paraformer()

    _asr_loaded_key = key
    logger.info("ASR model loaded (backend=%s)", backend)
    return _asr_model


def release_asr() -> None:
    """释放 ASR 占用的内存（任务结束后可选调用）。"""
    global _asr_model, _asr_loaded_key
    if _asr_model is None:
        return
    try:
        del _asr_model
    except Exception:
        pass
    _asr_model = None
    _asr_loaded_key = None
    try:
        import gc
        gc.collect()
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    logger.info("ASR model released")


def _strip_sensevoice_tags(text: str) -> str:
    """去掉 SenseVoice 输出里的 <|zh|> <|HAPPY|> <|woitn|> 等标记。"""
    return re.sub(r"<\|[^|]+\|>", "", text or "")


def _timestamps_from_result(r: dict) -> list:
    ts = r.get("timestamp") or r.get("timestamps") or []
    return ts if isinstance(ts, list) else []


def _fallback_split_by_silence(timestamps: list, text: str, gap_sec: float = 0.6) -> List[Dict]:
    """无标点时：按时间戳空隙分句。"""
    if not timestamps or not text:
        return []

    # 时间戳数量与非标点字符对齐逻辑见 _map_chars_to_timestamps
    chars = [c for c in text if c not in PUNCTUATION]
    if not timestamps:
        return []

    n = min(len(chars), len(timestamps))
    if n <= 0:
        return []

    sentences: List[Dict] = []
    buf_chars: List[str] = []
    buf_start: Optional[float] = None
    buf_end: float = 0.0

    for i in range(n):
        try:
            start_ms = float(timestamps[i][0])
            end_ms = float(timestamps[i][1])
        except Exception:
            continue
        ch = chars[i]

        if buf_start is None:
            buf_start = start_ms
        elif (start_ms - buf_end) / 1000.0 >= gap_sec and buf_chars:
            clean = "".join(buf_chars).strip()
            if clean:
                sentences.append({
                    "start": buf_start / 1000.0,
                    "end": buf_end / 1000.0,
                    "text": clean,
                })
            buf_chars = []
            buf_start = start_ms

        buf_chars.append(ch)
        buf_end = max(buf_end, end_ms)

    if buf_chars and buf_start is not None:
        clean = "".join(buf_chars).strip()
        if clean:
            sentences.append({
                "start": buf_start / 1000.0,
                "end": buf_end / 1000.0,
                "text": clean,
            })
    return sentences


def transcribe(audio_path: str, language: str = "zh") -> List[Dict]:
    """
    转写音频并按句切分。
    Returns: [{"start": float, "end": float, "text": str}, ...]
    """
    model = get_asr_model()

    gen_kwargs = {"input": audio_path, "batch_size_s": 300}
    if memcfg.ASR_BACKEND in {"sensevoice", "sv", "sense"}:
        # SenseVoice：语言与标点/ITN 开关
        gen_kwargs.update({
            "language": "auto",
            "use_itn": True,
            "use_vad": True,
        })
        if memcfg.PUNC_MODEL_ID:
            # 自带情感事件；标点模型可选用
            pass

    result = model.generate(**gen_kwargs)
    if not result:
        return []

    r = result[0] if isinstance(result, list) else result
    if not isinstance(r, dict):
        return []

    text_punct = r.get("text", "") or ""
    if memcfg.ASR_BACKEND in {"sensevoice", "sv", "sense"}:
        text_punct = _strip_sensevoice_tags(text_punct)

    timestamps = _timestamps_from_result(r)

    if not text_punct.strip():
        return []
    if not timestamps:
        return []

    char_timestamps = _map_chars_to_timestamps(text_punct, timestamps)

    has_sentence_punct = bool(re.search(r"[。！？]", text_punct))
    if has_sentence_punct:
        sentences = _split_sentences(text_punct, char_timestamps)
    else:
        sentences = _fallback_split_by_silence(timestamps, text_punct)

    logger.info("ASR produced %s sentences from %s", len(sentences), audio_path)
    return sentences


def _map_chars_to_timestamps(text: str, timestamps: list) -> list:
    """Map each character in punctuated text to its [start_ms, end_ms]."""
    ts_idx = 0
    char_ts = []

    for ch in text:
        if ch in PUNCTUATION:
            if ts_idx > 0:
                char_ts.append(timestamps[ts_idx - 1])
            else:
                char_ts.append([0, 0])
        else:
            if ts_idx < len(timestamps):
                char_ts.append(timestamps[ts_idx])
                ts_idx += 1
            else:
                char_ts.append([0, 0])

    return char_ts


def _split_sentences(text: str, char_timestamps: list) -> list:
    """Split punctuated text by sentence-ending marks and map to timestamps."""
    parts = re.split(r'([。！？])', text)

    combined = []
    for i in range(0, len(parts) - 1, 2):
        s = parts[i]
        if i + 1 < len(parts):
            s += parts[i + 1]
        if s.strip():
            combined.append(s)
    if len(parts) % 2 == 1 and parts[-1].strip():
        combined.append(parts[-1])

    sentences = []
    pos = 0
    for sent in combined:
        start_pos = pos
        end_pos = pos + len(sent)

        if start_pos >= len(char_timestamps) or end_pos - 1 >= len(char_timestamps):
            break

        start_ms = char_timestamps[start_pos][0]
        end_ms = char_timestamps[end_pos - 1][1]

        clean_text = re.sub(r'[。！？，、；：]', '', sent).strip()

        if clean_text:
            sentences.append({
                "start": start_ms / 1000.0,
                "end": end_ms / 1000.0,
                "text": clean_text,
            })

        pos = end_pos

    return sentences
