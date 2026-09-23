"""阿里云 / 通义 MaaS 配置（ASR + 多模态大模型）。"""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    """从 backend/.env 与仓库根目录 .env 加载键值（不覆盖已有环境变量）。"""
    candidates = [
        Path(__file__).resolve().parent.parent / ".env",  # backend/.env
        Path(__file__).resolve().parent.parent.parent / ".env",  # repo/.env
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
        except OSError:
            continue


_load_dotenv()


def _str(name: str, default: str = "") -> str:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip()


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# API Key：DASHSCOPE_API_KEY / ALIYUN_DASHSCOPE_API_KEY / QIANWEN_API_KEY
DASHSCOPE_API_KEY = (
    _str("DASHSCOPE_API_KEY")
    or _str("ALIYUN_DASHSCOPE_API_KEY")
    or _str("QIANWEN_API_KEY")
)

# ASR：qwen3-asr-flash（MultiModalConversation）
ALIYUN_ASR_MODEL = _str("ALIYUN_ASR_MODEL", "qwen3-asr-flash")
ALIYUN_ASR_BASE_URL = _str(
    "ALIYUN_ASR_BASE_URL",
    "https://maas.qianwenaiapi.com/api/v1",
)
# 已知语种可填 zh / en，提升准确率；默认交给 enable_lid
ALIYUN_ASR_LANGUAGE = _str("ALIYUN_ASR_LANGUAGE", "")
ALIYUN_ASR_MAX_CHUNK_SEC = _float("ALIYUN_ASR_MAX_CHUNK_SEC", 20.0)

# 多模态大模型（通义千问 Omni / VL）
# 默认：qwen3.8-omni-flash @ maas.qianwenaiapi.com（OpenAI 兼容）
ALIYUN_VL_MODEL = _str("ALIYUN_VL_MODEL", "qwen3.8-omni-flash")
ALIYUN_VL_BASE_URL = _str(
    "ALIYUN_VL_BASE_URL",
    "https://maas.qianwenaiapi.com/compatible-mode/v1",
)


def vl_chat_completions_url() -> str:
    """归一化为 chat/completions 完整 URL。"""
    base = ALIYUN_VL_BASE_URL.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


# 双维编码抽帧：adaptive（默认，4/8/12 按时长）| fixed（固定 DUAL_FRAMES_PER_UNIT）
# 高精度 8 帧方案：3～8s 默认 8 帧，≤3s 用 4，>8s 用 12
DUAL_FRAMES_MODE = _str("DUAL_FRAMES_MODE", "adaptive").lower()
DUAL_FRAMES_PER_UNIT = _int("DUAL_FRAMES_PER_UNIT", 8)
DUAL_MAX_UNIT_SEC = _float("DUAL_MAX_UNIT_SEC", 12.0)
DUAL_MIN_UNIT_SEC = _float("DUAL_MIN_UNIT_SEC", 0.8)
DUAL_MERGE_GAP_SEC = _float("DUAL_MERGE_GAP_SEC", 0.45)
DUAL_CONFIDENCE_THRESHOLD = _float("DUAL_CONFIDENCE_THRESHOLD", 0.70)
DUAL_SILENCE_GAP_SEC = _float("DUAL_SILENCE_GAP_SEC", 3.0)

ALIYUN_TIMEOUT_SEC = _int("ALIYUN_TIMEOUT_SEC", 120)


def has_api_key() -> bool:
    return bool(DASHSCOPE_API_KEY)


def describe() -> str:
    key_hint = "set" if DASHSCOPE_API_KEY else "MISSING"
    if DASHSCOPE_API_KEY:
        key_hint = f"set({DASHSCOPE_API_KEY[:8]}...)"
    return (
        f"ASR={ALIYUN_ASR_MODEL}@{ALIYUN_ASR_BASE_URL}, "
        f"VL={ALIYUN_VL_MODEL}, "
        f"base={ALIYUN_VL_BASE_URL}, "
        f"api_key={key_hint}, "
        f"frames={DUAL_FRAMES_MODE}/{DUAL_FRAMES_PER_UNIT}, "
        f"conf_th={DUAL_CONFIDENCE_THRESHOLD}"
    )
