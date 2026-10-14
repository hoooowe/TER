"""通义 ASR 与 OpenAI 兼容多模态模型配置，从 .env / 环境变量读取。"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Iterable


def _load_dotenv(paths: Iterable[Path] | None = None) -> None:
    """从 backend/.env 与仓库根目录 .env 加载键值（不覆盖已有环境变量）。"""
    candidates = paths if paths is not None else [
        Path(__file__).resolve().parent.parent / ".env",  # backend/.env
        Path(__file__).resolve().parent.parent.parent / ".env",  # repo/.env
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:].strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                raw_val = val
                val = val.strip()
                if val.startswith(('"', "'")):
                    quote = val[0]
                    closing = val.find(quote, 1)
                    if closing < 0:
                        raise ValueError(f"{path.name}: {key} 的引号未闭合")
                    val = val[1:closing]
                else:
                    # .env 中仅空白后的 # 是注释，密钥内的 # 保持原样。
                    val = re.split(r"\s+#", raw_val, maxsplit=1)[0].strip()
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


def _optional_float(name: str, default: float | None = None) -> float | None:
    raw = os.environ.get(name)
    if raw is None:
        return default
    if not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须为数字或留空") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} 必须为有限数字")
    return value


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

# 保留旧变量作为兼容兜底；新配置统一使用 VL_*。
ALIYUN_VL_MODEL = _str("ALIYUN_VL_MODEL", "qwen3.8-omni-flash")
ALIYUN_VL_BASE_URL = _str(
    "ALIYUN_VL_BASE_URL",
    "https://maas.qianwenaiapi.com/compatible-mode/v1",
)

VL_PROVIDER = _str("VL_PROVIDER", "aliyun").lower()
VL_MODEL = _str("VL_MODEL") or ALIYUN_VL_MODEL
VL_BASE_URL = _str("VL_BASE_URL") or ALIYUN_VL_BASE_URL
# 只有阿里云模式可复用旧密钥，避免将 ASR 密钥发送给其它服务商。
VL_API_KEY = _str("VL_API_KEY") or (
    DASHSCOPE_API_KEY if VL_PROVIDER == "aliyun" else ""
)
VL_TEMPERATURE = _optional_float(
    "VL_TEMPERATURE", 0.2 if VL_PROVIDER == "aliyun" else None
)
VL_MAX_TOKENS = _int("VL_MAX_TOKENS", 800 if VL_PROVIDER == "aliyun" else 4096)
VL_TIMEOUT_SEC = _int("VL_TIMEOUT_SEC", _int("ALIYUN_TIMEOUT_SEC", 120))
if VL_MAX_TOKENS <= 0 or VL_TIMEOUT_SEC <= 0:
    raise ValueError("VL_MAX_TOKENS 和 VL_TIMEOUT_SEC 必须大于 0")
# 留空时不发送；非阿里云服务默认不携带 modalities 扩展字段。
VL_MODALITIES = [
    part.strip()
    for part in _str("VL_MODALITIES", "text" if VL_PROVIDER == "aliyun" else "").split(",")
    if part.strip()
]
VL_THINKING = _str("VL_THINKING").lower()
if VL_THINKING not in {"", "enabled", "disabled"}:
    raise ValueError("VL_THINKING 只能是 enabled、disabled 或留空")


def vl_chat_completions_url() -> str:
    """归一化为 chat/completions 完整 URL。"""
    base = VL_BASE_URL.rstrip("/")
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
    """通义 ASR 是否配置密钥（与多模态模型独立）。"""
    return bool(DASHSCOPE_API_KEY)


def has_vl_api_key() -> bool:
    return bool(VL_API_KEY)


def describe() -> str:
    return (
        f"ASR={ALIYUN_ASR_MODEL}@{ALIYUN_ASR_BASE_URL}, "
        f"asr_key={'set' if has_api_key() else 'MISSING'}, "
        f"VL={VL_PROVIDER}/{VL_MODEL}@{VL_BASE_URL}, "
        f"vl_key={'set' if has_vl_api_key() else 'MISSING'}, "
        f"thinking={VL_THINKING or 'default'}, "
        f"max_tokens={VL_MAX_TOKENS}, "
        f"frames={DUAL_FRAMES_MODE}/{DUAL_FRAMES_PER_UNIT}, "
        f"conf_th={DUAL_CONFIDENCE_THRESHOLD}"
    )
